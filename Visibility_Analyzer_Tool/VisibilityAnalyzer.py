import os
import numpy as np
import tensorflow as tf
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # Suppress TensorFlow warnings
tf.get_logger().setLevel('ERROR')  # Only show errors

# Your existing imports
from tensorflow.keras.preprocessing.image import load_img, img_to_array
from tensorflow.keras.applications import VGG16
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Flatten, Dropout
from tensorflow.keras.applications.vgg16 import preprocess_input
from sklearn.model_selection import train_test_split
import tkinter as tk
from tkinter import filedialog, messagebox
import json
import csv

# Add imports for plotting
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

class VisibilityChecker:
    def __init__(self, model_path=None):
        self.categories = ['zero_visibility', 'low_visibility', 'good_visibility', 'great_visibility']
        self.model = self._build_model() if model_path is None else self.load_model(model_path)
        
    def _build_model(self):
        # Use VGG16 as base model with pre-trained weights
        base_model = VGG16(weights='imagenet', include_top=False, input_shape=(224, 224, 3))
        
        # Freeze base model layers
        for layer in base_model.layers:
            layer.trainable = False
            
        model = Sequential([
            base_model,
            Flatten(),
            Dense(256, activation='relu'),
            Dropout(0.5),
            Dense(len(self.categories), activation='softmax')
        ])
        
        model.compile(optimizer='adam',
                     loss='categorical_crossentropy',
                     metrics=['accuracy'])
        return model
    
    def load_model(self, model_path):
        from tensorflow.keras.models import load_model
        return load_model(model_path)
    
    def save_model(self, model_path):
        """Save the model to the specified path."""
        self.model.save(model_path)
        return model_path
    
    def train(self, training_data_path):
        images = []
        labels = []
        
        # Load and preprocess training data
        for category_idx, category in enumerate(self.categories):
            category_path = os.path.join(training_data_path, category)
            for img_name in os.listdir(category_path):
                # Skip non-image files (including CSVs)
                if not img_name.lower().endswith(('.png', '.jpg', '.jpeg')):
                    continue
                    
                img_path = os.path.join(category_path, img_name)
                img = load_img(img_path, target_size=(224, 224))
                img_array = img_to_array(img)
                img_array = preprocess_input(img_array)
                images.append(img_array)
                labels.append(category_idx)
        
        X = np.array(images)
        y = np.eye(len(self.categories))[labels]  # One-hot encode labels
        
        # Split data into training and validation sets
        X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # Train the model
        self.model.fit(X_train, y_train,
                      validation_data=(X_val, y_val),
                      epochs=10,
                      batch_size=32)
    
    def predict(self, image_path):
        img = load_img(image_path, target_size=(224, 224))
        img_array = img_to_array(img)
        img_array = preprocess_input(img_array)
        img_array = np.expand_dims(img_array, axis=0)
        
        predictions = self.model.predict(img_array)
        category_idx = np.argmax(predictions[0])
        confidence = predictions[0][category_idx]
        
        return {
            'visibility': self.categories[category_idx],
            'confidence': float(confidence)
        }
    
    def analyze_folder(self, folder_path):
        results = []
        for img_name in os.listdir(folder_path):
            if img_name.lower().endswith(('.png', '.jpg', '.jpeg')):
                img_path = os.path.join(folder_path, img_name)
                result = self.predict(img_path)
                results.append({
                    'image': img_name,
                    'visibility': result['visibility'],
                    'confidence': result['confidence']
                })
        return results

def plot_visibility_results(csv_path, output_folder=None):
    # Read the CSV file
    df = pd.read_csv(csv_path)
    
    # Count occurrences of each visibility category
    visibility_counts = df['visibility'].value_counts().sort_index()
    
    # Set up the plot style
    plt.figure(figsize=(10, 6))
    sns.set_style("whitegrid")
    
    # Color mapping for different visibility categories
    colors = {
        'zero_visibility': 'red',
        'low_visibility': 'orange',
        'good_visibility': 'green',
        'great_visibility': 'blue'
    }
    
    # Create the bar chart
    ax = sns.barplot(x=visibility_counts.index, y=visibility_counts.values, 
                     palette=[colors.get(cat, 'gray') for cat in visibility_counts.index])
    
    # Add count labels on top of each bar
    for i, count in enumerate(visibility_counts.values):
        ax.text(i, count + 5, str(count), ha='center', fontweight='bold')
    
    # Add labels and title
    plt.title('Visibility Analysis Results', fontsize=16)
    plt.xlabel('Visibility Category', fontsize=14)
    plt.ylabel('Number of Images', fontsize=14)
    plt.xticks(rotation=15)
    
    # Calculate percentages for each category
    total = visibility_counts.sum()
    percentages = [(count/total)*100 for count in visibility_counts.values]
    
    # Add percentage annotations
    for i, percentage in enumerate(percentages):
        ax.text(i, visibility_counts.values[i]/2, f'{percentage:.1f}%', 
                ha='center', color='white', fontweight='bold')
    
    plt.tight_layout()
    
    # Save the chart if output_folder is provided
    if output_folder:
        os.makedirs(output_folder, exist_ok=True)
        output_path = os.path.join(output_folder, 'visibility_analysis.png')
        plt.savefig(output_path, dpi=300)
        print(f"Chart saved to {output_path}")
    
    plt.show()

if __name__ == "__main__":
    # Example usage
    checker = VisibilityChecker()
    
    # Train the model
    # checker.train("path/to/training/data")
    
    # Analyze a folder of images
    # results = checker.analyze_folder("path/to/test/images")
    # for result in results:
    #     print(f"Image: {result['image']}")
    #     print(f"Visibility: {result['visibility']}")
    #     print(f"Confidence: {result['confidence']:.2f}")

def create_gui():
    
    window = tk.Tk()
    window.title("Visibility Checker")
    window.geometry("600x400")
    
    def browse_training():
        folder = filedialog.askdirectory()
        training_path.set(folder)
    
    def browse_model():
        file = filedialog.askopenfilename(filetypes=[("Model files", "*.h5")])
        model_path.set(file)
    
    def browse_input():
        folder = filedialog.askdirectory()
        input_path.set(folder)
    
    def browse_output():
        folder = filedialog.askdirectory()
        output_path.set(folder)
    
    def process_images():
        try:
            checker = VisibilityChecker(model_path.get() if model_path.get() else None)
            
            # Train if path provided
            if training_path.get():
                checker.train(training_path.get())
                
                # Save the newly trained model
                model_save_path = os.path.join(output_path.get(), 'visibility_model.h5')
                checker.save_model(model_save_path)
                print(f"Training complete! Model saved to: {model_save_path}")
            
            # Process images
            results = checker.analyze_folder(input_path.get())
            
            # Save results to output file
            with open(os.path.join(output_path.get(), 'results.json'), 'w') as f:
                json.dump(results, f, indent=4)
            
            # Also save as CSV for easier viewing
            csv_path = os.path.join(output_path.get(), 'results.csv')
            with open(csv_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['image', 'visibility', 'confidence'])
                writer.writeheader()
                writer.writerows(results)
            
            # Generate and save the results plot
            plot_visibility_results(csv_path, output_path.get())
            
            messagebox.showinfo("Success", "Processing complete! Analysis plot has been saved.")
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    training_path = tk.StringVar()
    model_path = tk.StringVar()
    input_path = tk.StringVar()
    output_path = tk.StringVar()
    
    tk.Label(window, text="Training Data Path:").pack(pady=5)
    tk.Entry(window, textvariable=training_path, width=50).pack()
    tk.Button(window, text="Browse", command=browse_training).pack()
    
    tk.Label(window, text="Model Path (optional):").pack(pady=5)
    tk.Entry(window, textvariable=model_path, width=50).pack()
    tk.Button(window, text="Browse", command=browse_model).pack()
    
    tk.Label(window, text="Input Folder:").pack(pady=5)
    tk.Entry(window, textvariable=input_path, width=50).pack()
    tk.Button(window, text="Browse", command=browse_input).pack()
    
    tk.Label(window, text="Output Folder:").pack(pady=5)
    tk.Entry(window, textvariable=output_path, width=50).pack()
    tk.Button(window, text="Browse", command=browse_output).pack()
    
    tk.Button(window, text="Process Images", command=process_images).pack(pady=20)
    
    window.mainloop()

if __name__ == "__main__":
    # Just launch the GUI directly
    create_gui()