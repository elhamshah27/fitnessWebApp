"""
Vercel serverless function wrapper for Flask app
"""
import sys
import os

# Add parent directory to path so we can import main
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

# Import the Flask app
from main import app

# Vercel automatically converts Flask WSGI apps
# Just export the app directly

