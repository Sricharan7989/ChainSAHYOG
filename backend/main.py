"""
Entry point for the VASP Attribution Engine backend.

Run with:  uvicorn main:app --reload --port 8000   (from backend/)

CORS is only set up for localhost:5173 as of now inside app/__init__.py
"""

from app import create_app

app = create_app()
