import threading
import time

import cv2
from pyzbar.pyzbar import decode

from backend.cart import add_to_cart_logic
from backend.database import SessionLocal
from backend.models import Product

# Global vars for scanning logic
LAST_SCAN = None
LAST_TIME = 0.0
LAST_PRODUCT = None
SCAN_DELAY = 1.2  # Minimum time between scanning the same item twice
FRAME_SKIP = 2  # Decode every Nth frame to keep the stream fluent
DOWNSCALE_FACTOR = 0.75

_scan_lock = threading.Lock()
_product_cache = {}


def pop_last_product():
    global LAST_PRODUCT
    with _scan_lock:
        if not LAST_PRODUCT:
            return None
        product = LAST_PRODUCT
        LAST_PRODUCT = None
        return product


def _lookup_product(db, barcode_data):
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


def generate_frames():
    global LAST_SCAN, LAST_TIME, LAST_PRODUCT

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 960)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 540)

    db = SessionLocal()
    frame_index = 0

    try:
        while True:
            success, frame = cap.read()
            if not success:
                break

            frame_index += 1
            barcodes = []

            if frame_index % FRAME_SKIP == 0:
                work_frame = frame
                if DOWNSCALE_FACTOR < 1:
                    work_frame = cv2.resize(
                        frame,
                        None,
                        fx=DOWNSCALE_FACTOR,
                        fy=DOWNSCALE_FACTOR,
                        interpolation=cv2.INTER_LINEAR,
                    )
                gray = cv2.cvtColor(work_frame, cv2.COLOR_BGR2GRAY)
                barcodes = decode(gray)

            now = time.time()
            for obj in barcodes:
                barcode_data = obj.data.decode("utf-8")

                with _scan_lock:
                    recently_scanned = (
                        barcode_data == LAST_SCAN and (now - LAST_TIME) <= SCAN_DELAY
                    )

                if recently_scanned:
                    continue

                product_data = _lookup_product(db, barcode_data)
                if not product_data:
                    continue

                product = db.get(Product, product_data["id"])
                if not product or product.stock <= 0:
                    continue

                add_to_cart_logic(product)
                product.stock -= 1
                db.commit()

                with _scan_lock:
                    LAST_SCAN = barcode_data
                    LAST_TIME = now
                    LAST_PRODUCT = {
                        "id": product.id,
                        "name": product.name,
                        "price": product.price,
                        "category": product.category,
                    }

                print(f"Detected and Added: {product.name}")

                scale = 1 / DOWNSCALE_FACTOR if DOWNSCALE_FACTOR < 1 else 1
                x, y, w, h = obj.rect
                x = int(x * scale)
                y = int(y * scale)
                w = int(w * scale)
                h = int(h * scale)
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                cv2.putText(
                    frame,
                    "SCANNED",
                    (x, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    2,
                )

            ret, buffer = cv2.imencode(".jpg", frame)
            if not ret:
                continue

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"
            )
    finally:
        db.close()
        cap.release()
