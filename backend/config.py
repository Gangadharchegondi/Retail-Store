"""
Centralized configuration for SmartRetail application
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env", override=True)

# ========================
# DATABASE CONFIGURATION
# ========================
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./smart_store.db")

# ========================
# STORE PROFILE
# ========================
STORE_NAME = os.getenv("STORE_NAME", "SmartRetail")
STORE_EMAIL = os.getenv("STORE_EMAIL", "support@smartretail.local")
STORE_PHONE = os.getenv("STORE_PHONE", "9999999999")

# ========================
# CAMERA & SCANNING CONFIGURATION
# ========================
SCAN_DELAY = 1.2  # Minimum time between scanning same item
FRAME_SKIP = 1    # Decode every Nth frame (1 = every frame, 2 = every 2nd, etc)
DOWNSCALE_FACTOR = 0.65  # Lower = faster but less accurate (0.65 is optimal for speed)

# Camera performance optimization
ENABLE_MOTION_DETECTION = True  # Skip frames with no movement
ENABLE_THREADED_DECODE = False  # Use background thread for barcode decoding (disabled - causes stability issues)
MOTION_THRESHOLD = 800  # Pixel difference threshold for motion detection
CAMERA_BUFFER_SIZE = 1  # Minimize buffer for lower latency
JPEG_QUALITY = 75  # JPEG encoding quality (lower = faster but less quality)

# ========================
# WEIGHT SENSOR CONFIGURATION
# ========================
WEIGHT_DEVIATION_THRESHOLD = 35  # grams - threshold for theft detection
WEIGHT_NOISE_RANGE = 5  # grams - simulated sensor noise

# ========================
# API CONFIGURATION
# ========================
API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("API_PORT", "8000"))
DEBUG = os.getenv("DEBUG", "True").lower() == "true"

# ========================
# SESSION CONFIGURATION
# ========================
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "smartretail-dev-secret-change-me")
SESSION_MAX_AGE_SECONDS = int(os.getenv("SESSION_MAX_AGE_SECONDS", "86400"))

# ========================
# CORS CONFIGURATION
# ========================
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

# ========================
# PATHS CONFIGURATION
# ========================
STATIC_DIR = "static"
TEMPLATES_DIR = "frontend/templates"

