# FILE: /USBL_Nav_Smoother/USBL_Nav_Smoother/src/gui/widgets.py

from tkinter import Checkbutton, IntVar, Frame, Label, Button, messagebox
from tkinter import ttk

def create_model_selection_frame(parent, window_var, kalman_var, oer_var, compare_mode_var):
    model_frame = ttk.LabelFrame(parent, text="Smoothing Model Selection")
    model_frame.pack(fill="x", padx=10, pady=10)

    # Add checkboxes for model selection
    window_checkbox = Checkbutton(model_frame, text="Window Smoothing", variable=window_var)
    window_checkbox.grid(row=0, column=0, sticky="w", padx=20, pady=5)

    kalman_checkbox = Checkbutton(model_frame, text="Kalman Filter", variable=kalman_var)
    kalman_checkbox.grid(row=0, column=1, sticky="w", padx=20, pady=5)

    oer_checkbox = Checkbutton(model_frame, text="OER Moving Average", variable=oer_var)
    oer_checkbox.grid(row=0, column=2, sticky="w", padx=20, pady=5)

    compare_checkbox = Checkbutton(model_frame, text="Compare All Models (No Shapefiles)", 
                                   variable=compare_mode_var, command=lambda: update_model_selection(window_checkbox, kalman_checkbox, oer_checkbox, compare_mode_var))
    compare_checkbox.grid(row=1, column=0, columnspan=3, sticky="w", padx=20, pady=5)

    # Add a note about compare mode
    ttk.Label(model_frame, text="Note: Compare mode shows all models but doesn't generate shapefiles", 
              font=("Arial", 8, "italic")).grid(row=2, column=0, columnspan=3, sticky="w", padx=20, pady=(0, 5))

def update_model_selection(window_checkbox, kalman_checkbox, oer_checkbox, compare_mode_var):
    """Enable/disable appropriate checkboxes based on compare mode selection"""
    if compare_mode_var.get() == 1:
        # If compare mode is selected, enable all models and select them
        window_checkbox.select()
        kalman_checkbox.select()
        oer_checkbox.select()
        window_checkbox.config(state="disabled")
        kalman_checkbox.config(state="disabled")
        oer_checkbox.config(state="disabled")
    else:
        # If compare mode is not selected, enable individual selection
        window_checkbox.config(state="normal")
        kalman_checkbox.config(state="normal")
        oer_checkbox.config(state="normal")