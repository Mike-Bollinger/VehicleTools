# FILE: /USBL_Nav_Smoother/src/main.py

import sys
import os

# Add the parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Now import the app module
from src.gui.app import run_app

if __name__ == "__main__":
    print("Starting USBL Navigation Smoothing Tool...")
    run_app()