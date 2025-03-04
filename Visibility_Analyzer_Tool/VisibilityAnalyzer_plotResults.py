import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

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
    # Path to your results CSV file
    results_path = "D:/Visibility Analyzer Test/Outputs/results.csv"
    
    # Optional: Output folder for saving the chart
    output_folder = "D:/Visibility Analyzer Test/Outputs"
    
    plot_visibility_results(results_path, output_folder)