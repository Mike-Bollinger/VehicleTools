"""
Dive Report Generator - Main Entry Point

Enhanced version with:
- Preview pane for QAQC
- Flexible multi-source data management
- Smart dive number matching
- Checkbox selection interface

Author: Mike Bollinger, Enhanced by GitHub Copilot
Updated Date: January 2026
"""

import sys
import tkinter as tk
from tkinter import messagebox

try:
    from main_gui import MainGUI
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Make sure all required modules are in the same directory:")
    print("  - dive_finder.py")
    print("  - report_generator.py")
    print("  - preview_widget.py")
    print("  - main_gui.py")
    sys.exit(1)


def check_dependencies():
    """Check if all required packages are available"""
    missing = []
    
    try:
        import pandas
    except ImportError:
        missing.append("pandas")
    
    try:
        import docx
    except ImportError:
        missing.append("python-docx")
        
    try:
        from PIL import Image
    except ImportError:
        missing.append("Pillow")
    
    if missing:
        error_msg = "Missing required packages:\n\n"
        error_msg += "\n".join(f"  - {pkg}" for pkg in missing)
        error_msg += "\n\nInstall them with:\n"
        error_msg += f"  pip install {' '.join(missing)}"
        
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Missing Dependencies", error_msg)
        root.destroy()
        return False
    
    return True


def main():
    """Main entry point"""
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Create and run GUI
    root = tk.Tk()
    
    try:
        app = MainGUI(root)
        root.mainloop()
    except Exception as e:
        messagebox.showerror("Error", f"Application error:\n{e}")
        raise


if __name__ == "__main__":
    main()
