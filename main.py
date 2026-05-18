"""
SmartRetail - Main Application Entry Point
Run with: python main.py
"""
import uvicorn
from backend.config import API_HOST, API_PORT, DEBUG

if __name__ == "__main__":
    uvicorn.run(
        "backend.app:app",
        host=API_HOST,
        port=API_PORT,
        reload=DEBUG
    )