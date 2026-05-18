"""
Shared templates configuration for all routes
"""
from fastapi.templating import Jinja2Templates
from backend.config import TEMPLATES_DIR

# Initialize templates globally for all routes to use
templates = Jinja2Templates(directory=TEMPLATES_DIR)
