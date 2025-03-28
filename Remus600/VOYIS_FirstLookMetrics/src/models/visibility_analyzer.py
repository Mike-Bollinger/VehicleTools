import os
from typing import Dict, List, Optional, Callable, Tuple
import time
import traceback

# Flag to track if TensorFlow has been imported
TF_IMPORTED = False
TF_AVAILABLE = None

class VisibilityAnalyzer:
    """
    Class to analyze image visibility in underwater imagery.
    Uses a pre-trained deep learning model or can train a new one.
    """
    
    def __init__(self, altitude_threshold=9.0):
        """
        Initialize the visibility analyzer
        
        Args:
            altitude_threshold: Altitude threshold for filtering images (same as used in metrics)
        """
        self.altitude_threshold = altitude_threshold
        
        # Default image categories for visibility
        self.categories = ['zero_visibility', 'low_visibility', 'good_visibility', 'great_visibility']
        self.model = None
        
        # Statistics from analysis
        self.visibility_stats = {
            'total_images': 0,
            'by_category': {},
            'percentages': {},
            'analyzed_images': []
        }
        
        # Don't check for TensorFlow until we need it
        self.tf_available = None
    
    def _import_tensorflow(self):
        """Lazy import TensorFlow when needed"""
        global TF_IMPORTED, TF_AVAILABLE
        
        # Only import if we haven't tried already
        if TF_IMPORTED:
            self.tf_available = TF_AVAILABLE
            return TF_AVAILABLE
        
        try:
            # Configure TensorFlow to suppress warnings before importing
            os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # Suppress TensorFlow warnings
            
            # Now import TensorFlow and related libraries
            import tensorflow as tf
            tf.get_logger().setLevel('ERROR')  # Only show errors
            import numpy as np
            import matplotlib.pyplot as plt
            import seaborn as sns
            import pandas as pd
            
            from tensorflow.keras.utils import load_img, img_to_array # type: ignore
            from tensorflow.keras.applications import VGG16 # type: ignore
            from tensorflow.keras.models import Sequential, load_model # type: ignore
            from tensorflow.keras.layers import Dense, Flatten, Dropout # type: ignore
            from tensorflow.keras.applications.vgg16 import preprocess_input # type: ignore
            from sklearn.model_selection import train_test_split
            
            # Store references to the modules in the class for later use
            self._tf = tf
            self._np = np
            self._plt = plt
            self._sns = sns
            self._pd = pd
            self._load_img = load_img
            self._img_to_array = img_to_array
            self._VGG16 = VGG16
            self._Sequential = Sequential
            self._load_model = load_model
            self._Dense = Dense
            self._Flatten = Flatten
            self._Dropout = Dropout
            self._preprocess_input = preprocess_input
            self._train_test_split = train_test_split
            
            TF_AVAILABLE = True
            
        except ImportError as e:
            print(f"TensorFlow not available. Visibility analysis will be disabled: {e}")
            TF_AVAILABLE = False
        
        # Mark as imported regardless of success
        TF_IMPORTED = True
        self.tf_available = TF_AVAILABLE
        return TF_AVAILABLE
    
    def load_or_train_model(self, path: str, progress_callback: Optional[Callable] = None) -> bool:
        """
        Load an existing model or train a new one if the path is a directory
        
        Args:
            path: Path to the model file (.h5) or training data directory
            progress_callback: Optional callback function for progress updates
            
        Returns:
            Boolean indicating success
        """
        # Only import TensorFlow when we actually need it
        if not self._import_tensorflow():
            if progress_callback:
                progress_callback(0, "TensorFlow not available. Cannot load or train model.")
            return False
            
        try:
            # If path is a file, try to load it as a model
            if os.path.isfile(path) and path.lower().endswith('.h5'):
                if progress_callback:
                    progress_callback(10, f"Loading model from {path}...")
                self.model = self._load_model(path)
                if progress_callback:
                    progress_callback(100, "Model loaded successfully.")
                return True
                
            # If path is a directory, assume it's training data
            elif os.path.isdir(path):
                if progress_callback:
                    progress_callback(10, "Preparing to train model...")
                    
                return self._train_model(path, progress_callback)
                
            else:
                if progress_callback:
                    progress_callback(0, "Invalid path. Must be a .h5 model file or a training data directory.")
                return False
                
        except Exception as e:
            if progress_callback:
                progress_callback(0, f"Error loading/training model: {str(e)}")
            print(f"Error loading/training model: {e}")
            print(traceback.format_exc())
            return False
    
    def _build_model(self) -> 'Sequential':  # type: ignore
        """
        Build the CNN model for visibility classification
        
        Returns:
            Compiled Keras Sequential model
        """
        # Use VGG16 as base model with pre-trained weights
        base_model = self._VGG16(weights='imagenet', include_top=False, input_shape=(224, 224, 3))
        
        # Freeze base model layers
        for layer in base_model.layers:
            layer.trainable = False
            
        model = self._Sequential([
            base_model,
            self._Flatten(),
            self._Dense(256, activation='relu'),
            self._Dropout(0.5),
            self._Dense(len(self.categories), activation='softmax')
        ])
        
        model.compile(optimizer='adam',
                     loss='categorical_crossentropy',
                     metrics=['accuracy'])
        return model
    
    def _train_model(self, training_data_path: str, progress_callback: Optional[Callable] = None) -> bool:
        """
        Train the model on the provided dataset
        
        Args:
            training_data_path: Path to training data directory (with subdirectories for each category)
            progress_callback: Optional callback function for progress updates
            
        Returns:
            Boolean indicating success
        """
        try:
            # Check if the training data directory contains category subdirectories
            category_paths = [os.path.join(training_data_path, cat) for cat in self.categories]
            for cat_path in category_paths:
                if not os.path.isdir(cat_path):
                    if progress_callback:
                        progress_callback(0, f"Training data directory must contain subdirectories for each category: {', '.join(self.categories)}")
                    return False
            
            if progress_callback:
                progress_callback(20, "Loading and preprocessing images...")
            
            # Import required modules
            np = self._np
            
            # Initialize data lists
            images = []
            labels = []
            
            total_files = 0
            # Count total files for progress tracking
            for category_idx, category in enumerate(self.categories):
                category_path = os.path.join(training_data_path, category)
                for img_name in os.listdir(category_path):
                    if img_name.lower().endswith(('.png', '.jpg', '.jpeg', '.tif', '.tiff')):
                        total_files += 1
            
            # Load and preprocess training data
            loaded_files = 0
            for category_idx, category in enumerate(self.categories):
                category_path = os.path.join(training_data_path, category)
                
                for img_name in os.listdir(category_path):
                    # Skip non-image files
                    if not img_name.lower().endswith(('.png', '.jpg', '.jpeg', '.tif', '.tiff')):
                        continue
                        
                    # Progress updates every 20 files
                    loaded_files += 1
                    if progress_callback and loaded_files % 20 == 0:
                        progress_percent = 20 + int((loaded_files / total_files) * 30)  # 20-50% range
                        progress_callback(progress_percent, f"Preprocessing images: {loaded_files}/{total_files}")
                    
                    try:
                        img_path = os.path.join(category_path, img_name)
                        img = self._load_img(img_path, target_size=(224, 224))
                        img_array = self._img_to_array(img)
                        img_array = self._preprocess_input(img_array)
                        images.append(img_array)
                        labels.append(category_idx)
                    except Exception as img_error:
                        print(f"Error processing image {img_name}: {img_error}")
                        continue
            
            if not images:
                if progress_callback:
                    progress_callback(0, "No valid images found for training.")
                return False
                
            if progress_callback:
                progress_callback(50, "Preprocessing complete. Preparing to train...")
            
            # Convert to arrays
            X = np.array(images)
            y = np.eye(len(self.categories))[labels]  # One-hot encode labels
            
            # Split data into training and validation sets
            X_train, X_val, y_train, y_val = self._train_test_split(X, y, test_size=0.2, random_state=42)
            
            if progress_callback:
                progress_callback(60, "Training model...")
            
            # Build the model
            self.model = self._build_model()
            
            # Setup training callbacks
            class ProgressCallback(self._tf.keras.callbacks.Callback):
                def __init__(self, callback_fn, total_epochs):
                    self.callback_fn = callback_fn
                    self.total_epochs = total_epochs
                    
                def on_epoch_end(self, epoch, logs=None):
                    epoch_progress = (epoch + 1) / self.total_epochs
                    progress_percent = 60 + int(epoch_progress * 35)  # 60-95% range
                    accuracy = logs.get('val_accuracy', 0.0) * 100
                    self.callback_fn(progress_percent, f"Training epoch {epoch+1}/{self.total_epochs}, accuracy: {accuracy:.1f}%")
            
            # Setup training callbacks
            callbacks = []
            if progress_callback:
                epochs = 10  # Number of epochs to train for
                callbacks.append(ProgressCallback(progress_callback, epochs))
            
            # Train the model
            self.model.fit(
                X_train, y_train,
                validation_data=(X_val, y_val),
                epochs=epochs,
                batch_size=32,
                callbacks=callbacks,
                verbose=0  # Don't print to console
            )
            
            # Evaluate model
            loss, accuracy = self.model.evaluate(X_val, y_val, verbose=0)
            
            if progress_callback:
                progress_callback(95, f"Training complete. Validation accuracy: {accuracy*100:.1f}%")
            
            return True
            
        except Exception as e:
            if progress_callback:
                progress_callback(0, f"Error training model: {str(e)}")
            print(f"Error training model: {e}")
            print(traceback.format_exc())
            return False