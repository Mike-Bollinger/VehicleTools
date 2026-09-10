"""
Title: Rock vs. Sand Image Classifier
Author: Mike Bollinger with help from ChatGPT v4.0
Description:
    This script classifies images of rocks and sand using a machine learning model
    (Random Forest). It extracts features from images, trains the model, and sorts
    unseen images into appropriate folders (rock only). Skips previously classified images.
    Additionally, it generates a CSV report of classifications.

USAGE:
    Edit the folder paths in the `if __name__ == "__main__":` block (rock_folder,
    sand_folder training examples; input_folder to classify; output_rock_folder;
    csv_output_path), then run:
        python HBdetector_NemoSens.py

INPUTS:
    - rock_folder / sand_folder: labeled example images used to train the
      Random Forest classifier.
    - input_folder: unclassified images to sort.
    - model_save_path: path to save/load the trained model (.pkl).

OUTPUTS:
    - Images classified as "rock" copied into output_rock_folder.
    - A CSV report of image classifications at csv_output_path.
    - A saved/reused trained model file (model_save_path).

Version: 1.1.0
Last Updated: 2025-01-09
"""

import os
import cv2
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
import joblib
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor
import shutil

# Feature Extraction Functions
def calculate_contrast(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return gray.std()

def calculate_blob_density(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    detector = cv2.SimpleBlobDetector_create()
    keypoints = detector.detect(gray)
    return len(keypoints)

def calculate_color_variance(image):
    variance = np.var(image, axis=(0, 1))
    return np.mean(variance)

def extract_features_from_path(image_path):
    try:
        image = cv2.imread(image_path)
        contrast = calculate_contrast(image)
        blob_density = calculate_blob_density(image)
        color_variance = calculate_color_variance(image)
        return [contrast, blob_density, color_variance]
    except Exception as e:
        print(f"Error processing {image_path}: {e}")
        return None  # Handle errors gracefully

# Load Images and Labels with Parallel Processing
def load_data_parallel(rock_folder, sand_folder):
    features, labels = [], []
    rock_images = [os.path.join(rock_folder, f) for f in os.listdir(rock_folder) if f.endswith(('.jpg', '.png', '.jpeg'))]
    sand_images = [os.path.join(sand_folder, f) for f in os.listdir(sand_folder) if f.endswith(('.jpg', '.png', '.jpeg'))]

    print("Extracting features using parallel processing...")
    with ProcessPoolExecutor() as executor:
        rock_features = list(tqdm(executor.map(extract_features_from_path, rock_images), total=len(rock_images), desc="Processing rock images"))
        sand_features = list(tqdm(executor.map(extract_features_from_path, sand_images), total=len(sand_images), desc="Processing sand images"))

    for feature in rock_features:
        if feature is not None:
            features.append(feature)
            labels.append('rock')

    for feature in sand_features:
        if feature is not None:
            features.append(feature)
            labels.append('sand')

    return np.array(features), np.array(labels)

# Train the Model
def train_model(features, labels, model_save_path):
    print("Splitting data into training and testing sets...")
    X_train, X_test, y_train, y_test = train_test_split(features, labels, test_size=0.2, random_state=42)

    print("Training the model...")
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    print("Evaluating the model...")
    y_pred = model.predict(X_test)
    print(f"Accuracy: {accuracy_score(y_test, y_pred):.2f}")
    print("Classification Report:")
    print(classification_report(y_test, y_pred))

    print(f"Saving the model to {model_save_path}...")
    joblib.dump(model, model_save_path)
    return model

# Classify Images and Save CSV Report
def classify_images_parallel(input_folder, output_rock_folder, csv_output_path, model, batch_size=500):
    os.makedirs(output_rock_folder, exist_ok=True)

    # Gather input images and skip already classified ones
    image_files = [
        os.path.join(input_folder, f)
        for f in os.listdir(input_folder)
        if f.endswith(('.jpg', '.png', '.jpeg'))
    ]
    print(f"Classifying {len(image_files)} images...")

    if not image_files:
        print("No new images to classify. Exiting.")
        return

    classifications = []

    # Create batches
    batches = [image_files[i:i + batch_size] for i in range(0, len(image_files), batch_size)]

    # Process in parallel
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
        for results in tqdm(
            executor.map(lambda batch: classify_batch(batch, model, output_rock_folder), batches),
            total=len(batches),
            desc="Classifying batches",
            unit="batch"
        ):
            classifications.extend(results)

    # Save classification results to CSV
    df = pd.DataFrame(classifications, columns=["Image Name", "Classification"])
    df.to_csv(csv_output_path, index=False)
    print(f"Classification report saved to {csv_output_path}")


# Function to classify a batch of images (Only copy rock images)
def classify_batch(batch, model, output_rock_folder):
    results = []
    for img_path in batch:
        try:
            features = extract_features_from_path(img_path)
            if features is not None:
                prediction = model.predict([features])[0]
                img_name = os.path.basename(img_path)
                results.append((img_name, prediction))

                # Only copy rock images
                if prediction == 'rock':
                    shutil.copy(img_path, os.path.join(output_rock_folder, img_name))
        except Exception as e:
            print(f"Error processing {img_path}: {e}")
    return results

# Wrapper function for multiprocessing
def classify_batch_wrapper(args):
    batch, model, output_rock_folder = args
    return classify_batch(batch, model, output_rock_folder)

def classify_images_parallel(input_folder, output_rock_folder, csv_output_path, model, batch_size=500):
    os.makedirs(output_rock_folder, exist_ok=True)

    # Gather input images and skip already classified ones
    image_files = [
        os.path.join(input_folder, f)
        for f in os.listdir(input_folder)
        if f.endswith(('.jpg', '.png', '.jpeg'))
    ]
    print(f"Classifying {len(image_files)} images...")

    if not image_files:
        print("No new images to classify. Exiting.")
        return

    classifications = []

    # Create batches
    batches = [image_files[i:i + batch_size] for i in range(0, len(image_files), batch_size)]
    batch_args = [(batch, model, output_rock_folder) for batch in batches]  # Prepare arguments for multiprocessing

    # Process in parallel
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
        for results in tqdm(
            executor.map(classify_batch_wrapper, batch_args),
            total=len(batches),
            desc="Classifying batches",
            unit="batch"
        ):
            classifications.extend(results)

    # Save classification results to CSV
    df = pd.DataFrame(classifications, columns=["Image Name", "Classification"])
    df.to_csv(csv_output_path, index=False)
    print(f"Classification report saved to {csv_output_path}")


# Use OpenCV threading optimally
cv2.setNumThreads(0)  # Allow OpenCV to use its own threading

if __name__ == "__main__":
    # Paths
    rock_folder = r"D:\AUV\BOEM-CLB\rocks"
    sand_folder = r"D:\AUV\BOEM-CLB\sand"
    input_folder = r"D:\AUV\BOEM-CLB\SH-24-01_DIVE011_20240920_P.Sherman\Images"
    output_rock_folder = r"D:\AUV\BOEM-CLB\SH-24-01_DIVE011_20240920_P.Sherman\Rocks"
    csv_output_path = r"D:\AUV\BOEM-CLB\SH-24-01_DIVE011_20240920_P.Sherman"
    model_save_path = "rock_sand_model.pkl"

    # Load Data
    print("Loading training data...")
    features, labels = load_data_parallel(rock_folder, sand_folder)

    # Train Model
    model = train_model(features, labels, model_save_path)

    # Classify Images
    classify_images_parallel(input_folder, output_rock_folder, csv_output_path, model)
