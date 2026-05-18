"""
Camera and barcode scanning service module - OPTIMIZED FOR SPEED
"""
import os
import threading
import time
import cv2
import numpy as np
from fastapi import Request
from pyzbar.pyzbar import decode, ZBarSymbol
from backend.services.cart import add_to_cart
from backend.database import SessionLocal
from backend.models import Product
from backend.config import (
    SCAN_DELAY, 
    FRAME_SKIP, 
    DOWNSCALE_FACTOR,
    ENABLE_MOTION_DETECTION,
    MOTION_THRESHOLD,
    CAMERA_BUFFER_SIZE,
    JPEG_QUALITY
)

# Global vars for scanning logic
LAST_SCAN = None
LAST_TIME = 0.0
LAST_PRODUCT = None
_scan_lock = threading.Lock()
_product_cache = {}
_barcode_last_seen = {}

# Keep memory bounded if many unknown/temporary barcodes appear.
MAX_TRACKED_BARCODES = 256

# Limit symbols to common retail barcodes/QR to avoid unstable decoders (e.g. PDF417 asserts).
SUPPORTED_SYMBOLS = [
    ZBarSymbol.EAN13,
    ZBarSymbol.EAN8,
    ZBarSymbol.UPCA,
    ZBarSymbol.UPCE,
    ZBarSymbol.CODE128,
    ZBarSymbol.CODE39,
    ZBarSymbol.QRCODE,
]

JPEG_ENCODE_PARAMS = [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]


def _build_camera_candidates():
    """Build camera index/backend candidates with Windows-friendly fallbacks."""
    raw_indexes = os.getenv("CAMERA_INDEXES", "0,1")
    indexes = []
    for token in raw_indexes.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            indexes.append(int(token))
        except ValueError:
            continue

    if not indexes:
        indexes = [0]

    backends = [cv2.CAP_ANY]
    if os.name == "nt":
        # CAP_DSHOW works well for many USB webcams; CAP_MSMF is a common fallback.
        backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]

    candidates = []
    for idx in indexes:
        for backend in backends:
            candidates.append((idx, backend))
    return candidates


def _try_open_camera(index, backend):
    """Attempt to open a camera and validate we can read at least one frame."""
    try:
        cap = cv2.VideoCapture(index, backend)
    except cv2.error:
        return None

    if not cap.isOpened():
        cap.release()
        return None

    # Some camera drivers throw native OpenCV errors when setting properties.
    # Treat those as non-fatal and continue with driver defaults.
    for prop, value in (
        (cv2.CAP_PROP_BUFFERSIZE, 1),
        (cv2.CAP_PROP_FRAME_WIDTH, 960),
        (cv2.CAP_PROP_FRAME_HEIGHT, 540),
    ):
        try:
            cap.set(prop, value)
        except cv2.error:
            pass

    # Warm-up reads: some drivers need a short delay before first valid frame.
    for _ in range(8):
        try:
            ok, _frame = cap.read()
        except cv2.error:
            ok = False
        if ok:
            return cap
        time.sleep(0.05)

    cap.release()
    return None


def _open_camera_with_fallbacks():
    """Try multiple camera candidates and return an opened capture object."""
    for index, backend in _build_camera_candidates():
        cap = _try_open_camera(index, backend)
        if cap is not None:
            return cap
    return None


def _error_frame(message):
    """Generate a readable fallback frame so UI shows actionable camera errors."""
    frame = np.zeros((540, 960, 3), dtype=np.uint8)
    frame[:] = (18, 24, 38)
    cv2.putText(frame, "Camera unavailable", (220, 220), cv2.FONT_HERSHEY_SIMPLEX, 1.3, (64, 196, 255), 3)
    cv2.putText(frame, message[:68], (90, 280), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (220, 230, 245), 2)
    cv2.putText(frame, "Check webcam permissions, close other camera apps, then refresh.", (58, 330), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (180, 190, 210), 1)

    ok, buffer = cv2.imencode(".jpg", frame, JPEG_ENCODE_PARAMS)
    if not ok:
        return None
    return (
        b"--frame\r\n"
        b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"
    )


def pop_last_product():
    """Pop and return the last scanned product."""
    global LAST_PRODUCT
    with _scan_lock:
        if not LAST_PRODUCT:
            return None
        product = LAST_PRODUCT
        LAST_PRODUCT = None
        return product


def _lookup_product(db, barcode_data):
    """Look up product in database with caching."""
    cached = _product_cache.get(barcode_data)
    if cached:
        return cached

    product = db.query(Product).filter(Product.barcode == barcode_data).first()
    if not product:
        return None

    cached = {
        "id": product.id,
        "name": product.name,
        "price": product.price,
        "category": product.category,
        "weight": product.weight,
    }
    _product_cache[barcode_data] = cached
    return cached


def _dedupe_and_decode(work_frame):
    """Decode barcodes from multiple preprocessed variants for better robustness."""
    def _safe_decode(image):
        try:
            return decode(image, symbols=SUPPORTED_SYMBOLS)
        except Exception:
            return []

    gray = cv2.cvtColor(work_frame, cv2.COLOR_BGR2GRAY)
    
    # Fast decode attempt
    decoded = _safe_decode(gray)

    # Fallback improves difficult reads (glare/low-contrast labels).
    if not decoded:
        # Use bilateral filter to reduce noise while preserving edges (faster than histogram equalization)
        enhanced = cv2.bilateralFilter(gray, 5, 50, 50)
        decoded = _safe_decode(enhanced)

    unique = {}
    for item in decoded:
        code = item.data.decode("utf-8").strip()
        if not code or code in unique:
            continue
        unique[code] = item
    return unique


def _detect_motion(prev_gray, curr_gray):
    """Fast motion detection using frame difference."""
    if prev_gray is None:
        return True
    
    diff = cv2.absdiff(prev_gray, curr_gray)
    motion_pixels = np.count_nonzero(diff > 25)
    return motion_pixels > MOTION_THRESHOLD


def generate_frames(request: Request | None = None):
    """
    Generate video frames with barcode detection for streaming - OPTIMIZED.
    
    Yields:
        Encoded JPEG frames with barcodes detected
    """
    global LAST_SCAN, LAST_TIME, LAST_PRODUCT
    
    cap = _open_camera_with_fallbacks()
    if cap is not None:
        # Set camera buffer size to minimize latency
        cap.set(cv2.CAP_PROP_BUFFERSIZE, CAMERA_BUFFER_SIZE)
    
    frame_count = 0
    db = SessionLocal()
    consecutive_read_failures = 0
    prev_gray = None
    user_id = None

    if request is not None:
        try:
            user_id = int(request.session.get("user_id"))
        except (TypeError, ValueError):
            user_id = None

    try:
        if cap is None:
            fallback = _error_frame("No camera device could be opened.")
            while True:
                if fallback is not None:
                    yield fallback
                time.sleep(0.35)

        while True:
            try:
                ret, frame = cap.read()
            except cv2.error:
                ret, frame = False, None

            if not ret:
                consecutive_read_failures += 1
                if consecutive_read_failures >= 10:
                    # Try to recover by reopening the camera.
                    try:
                        cap.release()
                    except cv2.error:
                        pass
                    cap = _open_camera_with_fallbacks()
                    if cap is not None:
                        cap.set(cv2.CAP_PROP_BUFFERSIZE, CAMERA_BUFFER_SIZE)
                    consecutive_read_failures = 0

                    if cap is None:
                        fallback = _error_frame("Camera disconnected or busy.")
                        if fallback is not None:
                            yield fallback
                        time.sleep(0.25)
                continue

            consecutive_read_failures = 0
            frame_count += 1
            
            should_decode = frame_count % FRAME_SKIP == 0

            # Motion detection to skip processing static frames
            if should_decode and ENABLE_MOTION_DETECTION:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                if not _detect_motion(prev_gray, gray):
                    should_decode = False
                prev_gray = gray

            if should_decode:
                # Downscale for faster processing
                height, width = frame.shape[:2]
                small_frame = cv2.resize(
                    frame,
                    (int(width * DOWNSCALE_FACTOR), int(height * DOWNSCALE_FACTOR)),
                    interpolation=cv2.INTER_LINEAR,
                )

                # Decode barcodes (fast single-threaded approach)
                decoded_map = _dedupe_and_decode(small_frame)
                current_time = time.time()

                # Clean stale entries to avoid unbounded growth
                if len(_barcode_last_seen) > MAX_TRACKED_BARCODES:
                    cutoff = current_time - (SCAN_DELAY * 3)
                    stale = [k for k, ts in _barcode_last_seen.items() if ts < cutoff]
                    for key in stale:
                        _barcode_last_seen.pop(key, None)

                for barcode_data, barcode in decoded_map.items():
                    x, y, w, h = barcode.rect
                    scale = (1 / DOWNSCALE_FACTOR) if DOWNSCALE_FACTOR else 1
                    x = int(x * scale)
                    y = int(y * scale)
                    w = int(w * scale)
                    h = int(h * scale)

                    # Pulse effect for scanned barcodes
                    pulse_thickness = 3 if int(current_time * 6) % 2 == 0 else 4
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), pulse_thickness)

                    last_seen = _barcode_last_seen.get(barcode_data, 0.0)
                    if (current_time - last_seen) < SCAN_DELAY:
                        continue

                    product_data = _lookup_product(db, barcode_data)
                    if not product_data:
                        continue

                    product_obj = db.get(Product, product_data["id"])
                    if not product_obj or product_obj.stock <= 0:
                        continue

                    if user_id is None:
                        continue

                    add_to_cart(product_obj, user_id=user_id)
                    product_obj.stock -= 1
                    db.commit()

                    with _scan_lock:
                        LAST_SCAN = barcode_data
                        LAST_TIME = current_time
                        LAST_PRODUCT = {
                            "id": product_obj.id,
                            "name": product_obj.name,
                            "price": product_obj.price,
                            "category": product_obj.category,
                            "weight": product_obj.weight,
                        }

                    _barcode_last_seen[barcode_data] = current_time
                    print(f"✓ Fast Detected: {product_obj.name}")

            # Encode frame to JPEG with optimized quality
            ret, buffer = cv2.imencode(".jpg", frame, JPEG_ENCODE_PARAMS)
            if not ret:
                continue

            frame_bytes = buffer.tobytes()
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
            )
    finally:
        db.close()
        if cap is not None:
            try:
                cap.release()
            except cv2.error:
                pass
