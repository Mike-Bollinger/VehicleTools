# FILE: /USBL_Nav_Smoother/USBL_Nav_Smoother/src/utils/visualization.py

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.patches import Circle
import imageio
from PIL import Image

# Animation Configuration Parameters
ANIMATION_FRAME_RATE = 4     # Frames per second for GIF animation
ANIMATION_MAX_FRAMES = 300   # Maximum number of frames to generate

def create_plots(df, output_base, original_df=None):
    """
    Create visualization plots for navigation data with optional smoothed tracks
    
    Args:
        df (DataFrame): DataFrame with navigation data (may contain multiple tracks)
        output_base (str): Base filename for output plots
        original_df (DataFrame, optional): If provided, used as the original track
    """
    import matplotlib.pyplot as plt
    import numpy as np
    import matplotlib.ticker as mticker
    
    # Consistent color scheme for all types of visualizations
    COLOR_SCHEME = {
        'Original': '#000000',      # Black
        'Window': '#1f77b4',        # Blue
        'Kalman': '#2ca02c',        # Green
        'OER': '#d62728'            # Red
    }
    
    # Create main track plot
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # Check which columns are present to determine what to plot
    columns = df.columns
    
    # Log what columns we found to help with debugging
    print(f"Columns found in dataframe: {list(columns)}")
    
    # Determine if this is a comparison dataframe or single smoothed track
    is_comparison = 'Original_Latitude' in columns
    
    # Plot original track
    if original_df is not None:
        # We have a separate original dataframe
        plt.plot(original_df['Longitude'], original_df['Latitude'], 'k-', 
                linewidth=1.5, label='Original')
        print("Plotted original track from original_df")
    elif is_comparison:
        # Original data is in the comparison columns
        plt.plot(df['Original_Longitude'], df['Original_Latitude'], 'k-', 
                linewidth=1.5, label='Original')
        print("Plotted original track from comparison columns")
    else:
        # Check if this is the original data itself
        if 'Latitude' in columns and 'Longitude' in columns and not any(c.startswith('Window_') or c.startswith('Kalman_') or c.startswith('OER_') for c in columns):
            # This is just original data
            plt.plot(df['Longitude'], df['Latitude'], 'k-', 
                    linewidth=1.5, label='Original')
            print("Plotted this dataframe as original data")
    
    # Plot Window smoothed track
    if is_comparison and 'Window_Latitude' in columns:
        plt.plot(df['Window_Longitude'], df['Window_Latitude'], '-', 
                color=COLOR_SCHEME['Window'], linewidth=2, 
                label='NCCOS Moving Window')
        print("Plotted NCCOS Moving Window from comparison columns")
    elif 'Window_Latitude' in columns:
        # Direct Window columns in a single track df
        plt.plot(df['Window_Longitude'], df['Window_Latitude'], '-', 
                color=COLOR_SCHEME['Window'], linewidth=2, 
                label='NCCOS Moving Window')
        print("Plotted NCCOS Moving Window from direct columns")
    elif not is_comparison and all(c in columns for c in ['Latitude', 'Longitude']) and df is not original_df:
        # This is a smoothed dataframe (not comparison, not original)
        # Check if we were specifically passed a Window smoothed df
        if 'window' in output_base.lower() or 'nccos' in output_base.lower():
            plt.plot(df['Longitude'], df['Latitude'], '-', 
                    color=COLOR_SCHEME['Window'], linewidth=2, 
                    label='NCCOS Moving Window')
            print("Plotted dataframe as NCCOS Window smoothed track")
    
    # Plot Kalman smoothed track
    if is_comparison and 'Kalman_Latitude' in columns:
        plt.plot(df['Kalman_Longitude'], df['Kalman_Latitude'], '-', 
                color=COLOR_SCHEME['Kalman'], linewidth=2, 
                label='TATOR Kalman Filter')
        print("Plotted TATOR Kalman Filter from comparison columns")
    elif 'Kalman_Latitude' in columns:
        # Direct Kalman columns in a single track df
        plt.plot(df['Kalman_Longitude'], df['Kalman_Latitude'], '-', 
                color=COLOR_SCHEME['Kalman'], linewidth=2, 
                label='TATOR Kalman Filter')
        print("Plotted TATOR Kalman Filter from direct columns")
    elif not is_comparison and all(c in columns for c in ['Latitude', 'Longitude']) and df is not original_df:
        # Check if we were specifically passed a Kalman smoothed df
        if 'kalman' in output_base.lower() or 'tator' in output_base.lower():
            plt.plot(df['Longitude'], df['Latitude'], '-', 
                    color=COLOR_SCHEME['Kalman'], linewidth=2, 
                    label='TATOR Kalman Filter')
            print("Plotted dataframe as TATOR Kalman smoothed track")
    
    # Plot OER smoothed track
    if is_comparison and 'OER_Latitude' in columns:
        plt.plot(df['OER_Longitude'], df['OER_Latitude'], '-', 
                color=COLOR_SCHEME['OER'], linewidth=2, 
                label='OER Moving Average')
        print("Plotted OER Moving Average from comparison columns")
    elif 'OER_Latitude' in columns:
        # Direct OER columns in a single track df
        plt.plot(df['OER_Longitude'], df['OER_Latitude'], '-', 
                color=COLOR_SCHEME['OER'], linewidth=2, 
                label='OER Moving Average')
        print("Plotted OER Moving Average from direct columns")
    elif not is_comparison and all(c in columns for c in ['Latitude', 'Longitude']) and df is not original_df:
        # Check if we were specifically passed an OER smoothed df
        if 'oer' in output_base.lower() or 'moving average' in output_base.lower():
            plt.plot(df['Longitude'], df['Latitude'], '-', 
                    color=COLOR_SCHEME['OER'], linewidth=2, 
                    label='OER Moving Average')
            print("Plotted dataframe as OER Moving Average smoothed track")
    
    # Format axes to show actual lat/long values (rounded to 5 decimal places)
    ax.xaxis.set_major_formatter(mticker.FormatStrFormatter('%.5f'))
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.5f'))
    
    # Adjust number of ticks to prevent overcrowding
    ax.xaxis.set_major_locator(mticker.MaxNLocator(5))
    ax.yaxis.set_major_locator(mticker.MaxNLocator(5))
    
    # Add labels and legend
    plt.xlabel('Longitude')
    plt.ylabel('Latitude')
    plt.title('Navigation Track Smoothing')
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.legend()
    
    # Save the main plot
    plt.tight_layout()
    plt.savefig(f"{output_base}_Track.png", dpi=300)
    plt.close(fig)
    

def create_gif(comparison_df, output_dir, base_name, frame_rate=None):
    """
    Creates animation frames showing the progression of the vehicle along the selected tracks.
    
    Args:
        comparison_df (pd.DataFrame): DataFrame with position tracks
        output_dir (str): Directory to save frames and GIF
        base_name (str): Base filename for outputs
        frame_rate (int, optional): Frame rate for GIF animation
        
    Returns:
        tuple: (frames_directory, gif_path)
    """
    # Use global frame rate if not specified
    if frame_rate is None:
        frame_rate = ANIMATION_FRAME_RATE
        
    print(f"Creating animation frames with rate {frame_rate} FPS...")
    
    # Create frames directory if it doesn't exist
    frames_dir = os.path.join(output_dir, f"{base_name}_frames")
    os.makedirs(frames_dir, exist_ok=True)
    
    # Check which models are available in the comparison_df
    has_window = 'Window_Longitude' in comparison_df.columns
    has_kalman = 'Kalman_Longitude' in comparison_df.columns
    has_oer = 'OER_Longitude' in comparison_df.columns
    
    # Determine plot boundaries with extra padding
    all_lons = [comparison_df['Original_Longitude'].min(), comparison_df['Original_Longitude'].max()]
    all_lats = [comparison_df['Original_Latitude'].min(), comparison_df['Original_Latitude'].max()]
    
    if has_window:
        all_lons.extend([comparison_df['Window_Longitude'].min(), comparison_df['Window_Longitude'].max()])
        all_lats.extend([comparison_df['Window_Latitude'].min(), comparison_df['Window_Latitude'].max()])
    
    if has_kalman:
        all_lons.extend([comparison_df['Kalman_Longitude'].min(), comparison_df['Kalman_Longitude'].max()])
        all_lats.extend([comparison_df['Kalman_Latitude'].min(), comparison_df['Kalman_Latitude'].max()])
        
    if has_oer:
        all_lons.extend([comparison_df['OER_Longitude'].min(), comparison_df['OER_Longitude'].max()])
        all_lats.extend([comparison_df['OER_Latitude'].min(), comparison_df['OER_Latitude'].max()])
    
    lon_min, lon_max = min(all_lons), max(all_lons)
    lat_min, lat_max = min(all_lats), max(all_lats)
    
    # Add padding (5% on each side)
    lon_range = lon_max - lon_min
    lat_range = lat_max - lat_min
    lon_padding = lon_range * 0.05
    lat_padding = lat_range * 0.05
    lon_min -= lon_padding
    lon_max += lon_padding
    lat_min -= lat_padding
    lat_max += lat_padding
    
    # Create frames (one per timestamp)
    frame_files = []
    
    # Determine marker size based on track length
    points_count = len(comparison_df)
    marker_size = max(50, min(200, 10000 / points_count))  # Scale marker size based on point count
    
    # Calculate time range for progress indicator
    min_time = pd.to_datetime(comparison_df['Timestamp'].min())
    max_time = pd.to_datetime(comparison_df['Timestamp'].max())
    time_range = (max_time - min_time).total_seconds()
    
    # Determine how many frames to skip to stay under the maximum
    skip_factor = 1
    if points_count > ANIMATION_MAX_FRAMES:
        skip_factor = int(points_count / ANIMATION_MAX_FRAMES) + 1
        print(f"Limiting animation to ~{ANIMATION_MAX_FRAMES} frames by using every {skip_factor}th point")
    
    # For each timestamp, create a frame
    for i, row in comparison_df.iterrows():
        # Skip frames based on skip_factor (except first and last frame)
        if i % skip_factor != 0 and i != 0 and i != len(comparison_df)-1:
            continue
            
        current_time = pd.to_datetime(row['Timestamp'])
        progress = ((current_time - min_time).total_seconds() / time_range) * 100
        
        print(f"Creating frame {i+1}/{len(comparison_df)} - Time: {current_time.strftime('%H:%M:%S')} - {progress:.1f}% complete")
        
        fig, ax = plt.subplots(figsize=(10, 8))
        
        # Format axes to show actual lat/long values (rounded to 5 decimal places)
        import matplotlib.ticker as mticker
        ax.xaxis.set_major_formatter(mticker.FormatStrFormatter('%.5f'))
        ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.5f'))
        
        # Adjust number of ticks to prevent overcrowding
        ax.xaxis.set_major_locator(mticker.MaxNLocator(5))
        ax.yaxis.set_major_locator(mticker.MaxNLocator(5))
        
        # Plot full tracks with transparency
        # Original USBL in black
        plt.plot(comparison_df['Original_Longitude'], comparison_df['Original_Latitude'], 
                 'k-', alpha=0.4, linewidth=1, label='Raw USBL Data')
        
        # Window-smoothed in blue (if present)
        if has_window:
            plt.plot(comparison_df['Window_Longitude'], comparison_df['Window_Latitude'], 
                     'b-', alpha=0.4, linewidth=1.5, label='NCCOS Moving Window')
        
        # Kalman-smoothed in green (if present)
        if has_kalman:
            plt.plot(comparison_df['Kalman_Longitude'], comparison_df['Kalman_Latitude'], 
                     'g-', alpha=0.4, linewidth=1.5, label='TATOR Kalman Filter')
                     
        # OER-smoothed in red (if present)
        if has_oer:
            plt.plot(comparison_df['OER_Longitude'], comparison_df['OER_Latitude'], 
                     'r-', alpha=0.4, linewidth=1.5, label='OER Moving Average')
        
        # Plot the tracks up to current point with full opacity
        current_df = comparison_df.iloc[:i+1]
        
        # Original USBL with marker
        plt.plot(current_df['Original_Longitude'], current_df['Original_Latitude'], 
                 'k-', linewidth=1.5)
        
        # Window-smoothed with marker (if present)
        if has_window:
            plt.plot(current_df['Window_Longitude'], current_df['Window_Latitude'], 
                     'b-', linewidth=2)
        
        # Kalman-smoothed with marker (if present)
        if has_kalman:
            plt.plot(current_df['Kalman_Longitude'], current_df['Kalman_Latitude'], 
                     'g-', linewidth=2)
                     
        # OER-smoothed with marker (if present)
        if has_oer:
            plt.plot(current_df['OER_Longitude'], current_df['OER_Latitude'], 
                     'r-', linewidth=2)
        
        # Add circular markers at current position for each track
        circle1 = plt.Circle((row['Original_Longitude'], row['Original_Latitude']), 
                            lon_range/500, color='black', alpha=1.0, zorder=10)
        ax.add_patch(circle1)
        
        if has_window:
            circle2 = plt.Circle((row['Window_Longitude'], row['Window_Latitude']), 
                                lon_range/500, color='blue', alpha=1.0, zorder=10)
            ax.add_patch(circle2)
        
        if has_kalman:
            circle3 = plt.Circle((row['Kalman_Longitude'], row['Kalman_Latitude']), 
                                lon_range/500, color='green', alpha=1.0, zorder=10)
            ax.add_patch(circle3)
            
        if has_oer:
            circle4 = plt.Circle((row['OER_Longitude'], row['OER_Latitude']), 
                                lon_range/500, color='red', alpha=1.0, zorder=10)
            ax.add_patch(circle4)
        
        # Add time indicator
        plt.annotate(f"Time: {current_time.strftime('%H:%M:%S')}", 
                    xy=(0.05, 0.95), xycoords='axes fraction',
                    bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="gray", alpha=0.8),
                    fontsize=12)
        
        # Configure plot
        plt.title(f"Navigation Track Comparison - {base_name}", fontsize=14)
        plt.xlabel('Longitude', fontsize=12)
        plt.ylabel('Latitude', fontsize=12)
        plt.grid(True, alpha=0.3)
        plt.legend(loc='lower right', fontsize=10)
        
        # Set axis limits to keep consistent view across all frames
        plt.xlim(lon_min, lon_max)
        plt.ylim(lat_min, lat_max)
        
        # Ensure equal aspect ratio if ranges are similar
        if 0.1 < lon_range/lat_range < 10:
            plt.axis('equal')
        
        # Save the frame
        frame_filename = os.path.join(frames_dir, f"frame_{i:04d}.png")
        plt.savefig(frame_filename, dpi=150)
        frame_files.append(frame_filename)
        plt.close(fig)
    
    # Create a single GIF from frames with the specified frame rate
    if frame_files:
        print(f"Creating GIF with {len(frame_files)} frames at {frame_rate} FPS...")
        gif_path = os.path.join(output_dir, f"{base_name}_Animation_{frame_rate}fps.gif")
        
        # Read all frames
        images = []
        for frame_file in frame_files:
            images.append(imageio.imread(frame_file))
        
        # Create GIF
        imageio.mimsave(gif_path, images, fps=frame_rate, loop=0)
        print(f"GIF saved at {frame_rate} FPS: {gif_path}")
        
        return frames_dir, gif_path
    else:
        print("No frames were created.")
        return None, None

# Add comparative analysis function

def create_comparative_analysis(variants, output_filename):
    """
    Create comparative visualizations for multiple model variants
    
    Args:
        variants (list): List of dictionaries with 'name' and 'data' keys
        output_filename (str): Base filename for output files
    """
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    import numpy as np
    import matplotlib.ticker as mticker
    
    # Create figure for track comparison
    fig, ax = plt.subplots(figsize=(12, 10))
    
    # Color palette for different variants
    colors = plt.cm.tab10(np.linspace(0, 1, len(variants)))
    line_styles = ['-', '--', ':', '-.', '-', '--', ':', '-.', '-', '--']
    
    # Plot each variant
    legend_elements = []
    
    for i, variant in enumerate(variants):
        color = colors[i]
        line_style = line_styles[i % len(line_styles)]
        
        # Plot line
        plt.plot(
            variant['data']['Longitude'], 
            variant['data']['Latitude'],
            linestyle=line_style,
            color=color,
            linewidth=2 if variant['name'] == 'Original' else 1.5,
            alpha=0.9 if variant['name'] == 'Original' else 0.7
        )
        
        # Add to legend
        legend_elements.append(
            Line2D([0], [0], color=color, linestyle=line_style, 
                   label=variant['name'], linewidth=2)
        )
    
    # Format axes to show actual lat/long values (rounded to 5 decimal places)
    ax.xaxis.set_major_formatter(mticker.FormatStrFormatter('%.5f'))
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.5f'))
    
    # Adjust number of ticks to prevent overcrowding
    ax.xaxis.set_major_locator(mticker.MaxNLocator(5))
    ax.yaxis.set_major_locator(mticker.MaxNLocator(5))
    
    # Complete the plot
    plt.xlabel('Longitude')
    plt.ylabel('Latitude')
    plt.title('Comparison of Navigation Smoothing Configurations')
    plt.legend(handles=legend_elements, loc='best')
    plt.grid(True, linestyle='--', alpha=0.7)
    
    # Add explanation text
    plt.figtext(
        0.5, 0.01, 
        'This plot compares different configuration variants of smoothing algorithms.\n'
        'Each line represents a different level of smoothing aggressiveness.',
        ha='center', fontsize=9
    )
    
    # Save as PNG
    plt.savefig(f"{output_filename}.png", dpi=300, bbox_inches='tight')
    
    # Create detail figure with zoomed sections if data has enough points
    if len(variants[0]['data']) > 10:
        try:
            # Create a figure with 2 subplots for zoomed sections
            fig, axs = plt.subplots(1, 2, figsize=(14, 8))
            
            # Find interesting sections to zoom in on
            # (looking for areas with more variation)
            lat_diff = np.abs(np.diff(variants[0]['data']['Latitude'].values))
            lon_diff = np.abs(np.diff(variants[0]['data']['Longitude'].values))
            combined_diff = lat_diff + lon_diff
            
            # Get indices of two most interesting sections
            if len(combined_diff) > 20:
                window_size = min(20, len(combined_diff) // 3)
                rolling_sum = np.convolve(combined_diff, np.ones(window_size), 'valid')
                interesting_idx = np.argsort(rolling_sum)[-2:]
                interesting_idx = [idx + window_size // 2 for idx in interesting_idx]
                
                # Ensure indices are in ascending order
                interesting_idx.sort()
                
                # Ensure enough separation between sections
                if len(interesting_idx) > 1 and abs(interesting_idx[1] - interesting_idx[0]) < window_size:
                    interesting_idx[1] = min(len(combined_diff) - window_size, 
                                           interesting_idx[0] + window_size * 2)
            else:
                # If not enough points, just take first and last sections
                quarter = max(5, len(combined_diff) // 4)
                interesting_idx = [quarter, len(combined_diff) - quarter]
            
            # Create subplots for each interesting section
            for subplot_idx, center_idx in enumerate(interesting_idx, 1):
                if center_idx >= len(variants[0]['data']):
                    continue
                    
                ax = axs[subplot_idx-1]
                
                # Determine zoom window
                window = 10  # points on each side
                start_idx = max(0, center_idx - window)
                end_idx = min(len(variants[0]['data']), center_idx + window)
                
                # Get coordinate ranges for plot bounds
                all_lons = []
                all_lats = []
                for variant in variants:
                    all_lons.extend(variant['data']['Longitude'].iloc[start_idx:end_idx].values)
                    all_lats.extend(variant['data']['Latitude'].iloc[start_idx:end_idx].values)
                
                # Calculate bounds with 10% padding
                lon_min, lon_max = min(all_lons), max(all_lons)
                lat_min, lat_max = min(all_lats), max(all_lats)
                lon_padding = (lon_max - lon_min) * 0.1
                lat_padding = (lat_max - lat_min) * 0.1
                
                # Plot each variant in the zoomed section
                for i, variant in enumerate(variants):
                    color = colors[i]
                    line_style = line_styles[i % len(line_styles)]
                    
                    ax.plot(
                        variant['data']['Longitude'].iloc[start_idx:end_idx],
                        variant['data']['Latitude'].iloc[start_idx:end_idx],
                        linestyle=line_style,
                        color=color,
                        linewidth=2,
                        marker='o' if variant['name'] == 'Original' else None,
                        markersize=4 if variant['name'] == 'Original' else 0
                    )
                
                # Set bounds
                ax.set_xlim(lon_min - lon_padding, lon_max + lon_padding)
                ax.set_ylim(lat_min - lat_padding, lat_max + lat_padding)
                
                # Format axes to show actual lat/long values (rounded to 5 decimal places)
                ax.xaxis.set_major_formatter(mticker.FormatStrFormatter('%.5f'))
                ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.5f'))
                
                # Adjust number of ticks to prevent overcrowding
                ax.xaxis.set_major_locator(mticker.MaxNLocator(5))
                ax.yaxis.set_major_locator(mticker.MaxNLocator(5))
                
                ax.set_xlabel('Longitude')
                ax.set_ylabel('Latitude')
                ax.set_title(f'Zoomed Section {subplot_idx}')
                ax.grid(True, linestyle='--', alpha=0.7)
            
            # Add a single legend for the whole figure
            plt.figlegend(
                handles=legend_elements, 
                loc='lower center', 
                ncol=min(5, len(variants)),
                bbox_to_anchor=(0.5, 0.02)
            )
            
            plt.suptitle('Detailed Comparison of Smoothing Configurations', fontsize=16)
            plt.tight_layout(rect=[0, 0.08, 1, 0.95])
            
            # Save the zoomed comparison
            plt.savefig(f"{output_filename}_Zoomed.png", dpi=300, bbox_inches='tight')
            
        except Exception as e:
            print(f"Error creating detailed comparison: {e}")
            # Continue even if zoomed plot fails
    
    plt.close('all')
    print(f"Comparative analysis visualizations saved to {output_filename}.png")

# Add function to create animated GIFs for configuration variants

def create_variants_gif(variants, output_filename, fps=4, dpi=100):
    """
    Create an animated GIF showing the progression through navigation tracks
    with multiple configuration variants.
    
    The animation shows the full tracks in faded colors, with a moving marker
    highlighting the current position and bringing the track to full color.
    Similar models (NCCOS, TATOR, OER) use different shades of the same color.
    
    Args:
        variants (list): List of dictionaries with 'name' and 'data' keys
        output_filename (str): Filename for output GIF
        fps (int): Frames per second for animation
        dpi (int): DPI for image quality
    """
    import matplotlib.pyplot as plt
    import matplotlib.animation as animation
    import numpy as np
    from matplotlib.lines import Line2D
    import matplotlib.colors as mcolors
    import pandas as pd
    import matplotlib.ticker as mticker
    
    # Helper functions to adjust colors
    def lighten_color(color, amount=0.5):
        """
        Lightens the given color by multiplying (1-luminosity) by the given amount.
        Input can be a matplotlib color string, hex string, or RGB tuple.
        """
        import colorsys
        import matplotlib.colors as mc
        
        try:
            c = mc.cnames[color]
        except:
            c = color
        c = colorsys.rgb_to_hls(*mc.to_rgb(c))
        return colorsys.hls_to_rgb(c[0], 1 - amount * (1 - c[1]), c[2])
    
    def darken_color(color, amount=0.5):
        """
        Darkens the given color by multiplying luminosity by the given amount.
        """
        import colorsys
        import matplotlib.colors as mc
        
        try:
            c = mc.cnames[color]
        except:
            c = color
        c = colorsys.rgb_to_hls(*mc.to_rgb(c))
        return colorsys.hls_to_rgb(c[0], max(0, c[1] * amount), c[2])
    
    # Check if we have enough data for animation
    if len(variants[0]['data']) < 5:
        print("Not enough data points for animation.")
        return
    
    # Create figure and axis with extra space for legend below
    fig, ax = plt.subplots(figsize=(10, 9))
    
    # Adjust subplot position to leave room for the legend at the bottom
    plt.subplots_adjust(bottom=0.15)
    
    # Group variants by model type and assign color families
    model_families = {
        'Original': {'color': '#000000', 'variants': []},  # Black for original
        'NCCOS': {'color': '#1f77b4', 'variants': []},     # Blue family for NCCOS
        'TATOR': {'color': '#2ca02c', 'variants': []},     # Green family for TATOR
        'OER': {'color': '#d62728', 'variants': []}        # Red family for OER
    }
    
    # Categorize variants by model family
    for variant in variants:
        if 'Original' in variant['name']:
            model_families['Original']['variants'].append(variant)
        elif 'NCCOS' in variant['name']:
            model_families['NCCOS']['variants'].append(variant)
        elif 'TATOR' in variant['name'] or 'Kalman' in variant['name']:
            model_families['TATOR']['variants'].append(variant)
        elif 'OER' in variant['name']:
            model_families['OER']['variants'].append(variant)
    
    # Get all data coordinates to determine plot bounds
    all_lons = []
    all_lats = []
    for variant in variants:
        all_lons.extend(variant['data']['Longitude'].values)
        all_lats.extend(variant['data']['Latitude'].values)
    
    # Set axis limits with a bit of padding
    lon_padding = (max(all_lons) - min(all_lons)) * 0.1
    lat_padding = (max(all_lats) - min(all_lats)) * 0.1
    
    ax.set_xlim(min(all_lons) - lon_padding, max(all_lons) + lon_padding)
    ax.set_ylim(min(all_lats) - lat_padding, max(all_lats) + lat_padding)
    
    # Format axes to show actual lat/long values (rounded to 5 decimal places)
    ax.xaxis.set_major_formatter(mticker.FormatStrFormatter('%.5f'))
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.5f'))
    
    # Adjust number of ticks to prevent overcrowding
    ax.xaxis.set_major_locator(mticker.MaxNLocator(5))
    ax.yaxis.set_major_locator(mticker.MaxNLocator(5))
    
    # Draw the full tracks in faded colors first (as background)
    for family_name, family in model_families.items():
        base_color = family['color']
        
        # Create shades for variants in this family
        num_variants = len(family['variants'])
        if num_variants > 0:
            # Create color variations based on lightness/saturation
            if family_name == 'Original':
                variant_colors = [base_color] * num_variants  # Keep original black
            else:
                if num_variants == 1:
                    variant_colors = [base_color]
                elif num_variants == 2:
                    # For 2 variants: make one lighter, one darker
                    variant_colors = [
                        mcolors.to_hex(lighten_color(base_color, 0.7)),
                        mcolors.to_hex(darken_color(base_color, 0.7))
                    ]
                else:
                    # For 3+ variants: create a gradient
                    light = mcolors.to_hex(lighten_color(base_color, 0.7))
                    dark = mcolors.to_hex(darken_color(base_color, 0.7))
                    cmap = mcolors.LinearSegmentedColormap.from_list(
                        f"{family_name}_cmap", 
                        [light, base_color, dark]
                    )
                    variant_colors = [mcolors.to_hex(cmap(i/(num_variants-1) if num_variants > 1 else 0.5)) 
                                     for i in range(num_variants)]
            
            # Draw background tracks (full track faded)
            for i, variant in enumerate(family['variants']):
                # Draw the full track in a faded color
                ax.plot(
                    variant['data']['Longitude'], 
                    variant['data']['Latitude'],
                    color=variant_colors[i],
                    linestyle='-' if family_name == 'Original' else '--',
                    linewidth=1,
                    alpha=0.25,  # Very faded
                    zorder=1
                )
                
                # Store color for later use
                variant['color'] = variant_colors[i]
    
    # Create active line objects for each variant (these will be updated in the animation)
    lines = []
    markers = []
    
    # Group variants by model type for consistent appearance
    for family_name, family in model_families.items():
        for i, variant in enumerate(family['variants']):
            # Active line (will be shown up to current frame)
            line, = ax.plot([], [], 
                          color=variant['color'],
                          linestyle='-',
                          linewidth=2.5 if family_name == 'Original' else 2.0,
                          zorder=3,
                          label=variant['name'])
            lines.append({'line': line, 'variant': variant})
            
            # Marker for current position
            marker, = ax.plot([], [], 
                            marker='o' if family_name == 'Original' else 'o',
                            color=variant['color'],
                            markersize=8 if family_name == 'Original' else 7,
                            markeredgecolor='white',
                            markeredgewidth=1,
                            alpha=1.0,
                            zorder=4)
            markers.append({'marker': marker, 'variant': variant})
    
    # Text showing timestamp (instead of progress)
    timestamp_text = ax.text(0.02, 0.98, '', transform=ax.transAxes, 
                          va='top', ha='left', fontsize=10, 
                          bbox=dict(facecolor='white', alpha=0.7, boxstyle='round'),
                          zorder=5)
    
    # Configure the plot
    ax.set_xlabel('Longitude')
    ax.set_ylabel('Latitude')
    ax.set_title('Navigation Track Smoothing Comparison')
    ax.grid(True, linestyle='--', alpha=0.7)
    
    # Create a custom legend with model family grouping
    legend_elements = []
    
    # Add legend elements by family with full model names
    for family_name, family in model_families.items():
        if len(family['variants']) > 0:
            # Add each variant with descriptive names
            for variant in family['variants']:
                variant_name = variant['name']
                
                # Ensure full model type is in the name
                if family_name == 'Original':
                    display_name = 'Original'
                elif family_name == 'NCCOS':
                    # Add "Moving Window" if not present
                    if "Moving Window" not in variant_name:
                        display_name = variant_name.replace("NCCOS", "NCCOS Moving Window")
                    else:
                        display_name = variant_name
                elif family_name == 'TATOR':
                    # Ensure "Kalman Filter" is in the name
                    if "Kalman Filter" not in variant_name:
                        display_name = variant_name.replace("TATOR", "TATOR Kalman Filter")
                    else:
                        display_name = variant_name
                elif family_name == 'OER':
                    # Add "Moving Average" if not present
                    if "Moving Average" not in variant_name:
                        display_name = variant_name.replace("OER", "OER Moving Average")
                    else:
                        display_name = variant_name
                else:
                    display_name = variant_name
                
                # For variant names, highlight the variant type more clearly
                if "Default" in display_name:
                    display_name = display_name.replace("Default", "(Default)")
                elif "More Aggressive" in display_name:
                    display_name = display_name.replace("More Aggressive", "(More Aggressive)")
                elif "Less Aggressive" in display_name:
                    display_name = display_name.replace("Less Aggressive", "(Less Aggressive)")
                
                legend_elements.append(
                    Line2D([0], [0], color=variant['color'], linestyle='-', 
                          label=display_name, linewidth=2)
                )
    
    # Add legend below the plot with more space and larger font for readability
    ax.legend(handles=legend_elements, 
             loc='upper center', 
             bbox_to_anchor=(0.5, -0.12),  # Position below the plot with more space
             ncol=min(3, len(legend_elements)),  # Fewer columns for longer text
             fontsize=8,  # Small but readable font
             framealpha=0.9,
             title_fontsize=9)
    
    # Get timestamps for synchronization - use the original data (first variant)
    timestamps = variants[0]['data']['Timestamp'].values
    # Convert to datetime if not already
    if not isinstance(timestamps[0], pd.Timestamp):
        timestamps = pd.to_datetime(timestamps)
    
    # Maximum number of frames
    max_points = len(variants[0]['data'])
    
    # Animation initialization function
    def init():
        for item in lines:
            item['line'].set_data([], [])
        for item in markers:
            item['marker'].set_data([], [])
        timestamp_text.set_text('')
        return [item['line'] for item in lines] + [item['marker'] for item in markers] + [timestamp_text]
    
    # Animation update function
    def update(frame):
        # Get timestamp for this frame
        current_timestamp = timestamps[frame]
        
        # Format timestamp for display (just time if all on same day)
        if len(timestamps) > 1 and (timestamps.max() - timestamps.min()).days > 0:
            # Multiple days, show date and time
            timestamp_str = current_timestamp.strftime('%Y-%m-%d %H:%M:%S')
        else:
            # Same day, just show time
            timestamp_str = current_timestamp.strftime('%H:%M:%S')
        
        # For each variant, update the line and marker
        for item in lines:
            line = item['line']
            variant = item['variant']
            
            # Get coordinates up to current frame
            lons = variant['data']['Longitude'].iloc[:frame+1].values
            lats = variant['data']['Latitude'].iloc[:frame+1].values
            
            # Update line data (the track so far)
            line.set_data(lons, lats)
        
        # Update marker positions (current position)
        for item in markers:
            marker = item['marker']
            variant = item['variant']
            
            if frame < len(variant['data']):
                marker.set_data(
                    [variant['data']['Longitude'].iloc[frame]],
                    [variant['data']['Latitude'].iloc[frame]]
                )
            else:
                marker.set_data([], [])
        
        # Update timestamp text
        timestamp_text.set_text(f'Time: {timestamp_str}')
        
        return [item['line'] for item in lines] + [item['marker'] for item in markers] + [timestamp_text]
    
    # Calculate appropriate number of frames to make animation ~10-15 seconds
    if max_points > 100:
        step = max(1, max_points // 60)  # Target ~60 frames for >100 points
    else:
        step = 1
    
    frames = range(0, max_points, step)
    
    # Create animation
    print(f"Creating animation with {len(frames)} frames...")
    anim = animation.FuncAnimation(
        fig, 
        update, 
        frames=frames,
        init_func=init,
        blit=True,
        interval=1000/fps  # milliseconds between frames
    )
    
    # Save as GIF
    print(f"Saving animation to {output_filename}...")
    anim.save(
        output_filename, 
        writer='pillow', 
        fps=fps, 
        dpi=dpi
    )
    
    plt.close(fig)
    print(f"Animation saved to {output_filename}")

def create_gif(df, output_filename, base_name=None, frames_dir=None, fps=4, dpi=100):
    """
    Create an animated GIF showing the progression through a navigation track with multiple models
    
    Args:
        df (DataFrame): DataFrame with multiple model coordinates
        output_filename (str): Path to save the GIF
        base_name (str, optional): Base name for title. If None, uses a generic title.
        frames_dir (str, optional): Directory to save individual frames. If None, no frames are saved.
        fps (int): Frames per second for the animation
        dpi (int): DPI for the output images
    """
    import matplotlib.pyplot as plt
    import matplotlib.animation as animation
    import numpy as np
    from matplotlib.lines import Line2D
    import os
    import matplotlib.ticker as mticker
    
    # Consistent color scheme for all types of visualizations
    COLOR_SCHEME = {
        'Original': '#000000',      # Black
        'Window': '#1f77b4',        # Blue
        'Kalman': '#2ca02c',        # Green
        'OER': '#d62728'            # Red
    }
    
    # Check if we have enough data
    if len(df) < 5:
        print("Not enough data points for animation.")
        return
    
    # Figure setup
    fig, ax = plt.subplots(figsize=(10, 9))
    
    # Adjust subplot position to leave room for the legend at the bottom
    plt.subplots_adjust(bottom=0.15)
    
    # Get all coordinates to determine plot bounds
    lons = []
    lats = []
    
    # Original track
    lons.extend(df['Original_Longitude'].values)
    lats.extend(df['Original_Latitude'].values)
    
    # Add coordinates from each model if available
    if 'Window_Longitude' in df.columns:
        lons.extend(df['Window_Longitude'].values)
        lats.extend(df['Window_Latitude'].values)
    
    if 'Kalman_Longitude' in df.columns:
        lons.extend(df['Kalman_Longitude'].values)
        lats.extend(df['Kalman_Latitude'].values)
    
    if 'OER_Longitude' in df.columns:
        lons.extend(df['OER_Longitude'].values)
        lats.extend(df['OER_Latitude'].values)
    
    # Set axis limits with a bit of padding
    lon_padding = (max(lons) - min(lons)) * 0.1
    lat_padding = (max(lats) - min(lats)) * 0.1
    
    ax.set_xlim(min(lons) - lon_padding, max(lons) + lon_padding)
    ax.set_ylim(min(lats) - lat_padding, max(lats) + lat_padding)
    
    # Format axes to show actual lat/long values (rounded to 5 decimal places)
    ax.xaxis.set_major_formatter(mticker.FormatStrFormatter('%.5f'))
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.5f'))
    
    # Adjust number of ticks to prevent overcrowding
    ax.xaxis.set_major_locator(mticker.MaxNLocator(5))
    ax.yaxis.set_major_locator(mticker.MaxNLocator(5))
    
    # Draw the full tracks in faded colors first (as background)
    # Original track
    ax.plot(df['Original_Longitude'], df['Original_Latitude'], 
            color=COLOR_SCHEME['Original'], linestyle='-', linewidth=1, alpha=0.25)
    
    # Window track if available
    if 'Window_Longitude' in df.columns:
        ax.plot(df['Window_Longitude'], df['Window_Latitude'], 
                color=COLOR_SCHEME['Window'], linestyle='-', linewidth=1, alpha=0.25)
    
    # Kalman track if available
    if 'Kalman_Longitude' in df.columns:
        ax.plot(df['Kalman_Longitude'], df['Kalman_Latitude'], 
                color=COLOR_SCHEME['Kalman'], linestyle='-', linewidth=1, alpha=0.25)
    
    # OER track if available
    if 'OER_Longitude' in df.columns:
        ax.plot(df['OER_Longitude'], df['OER_Latitude'], 
                color=COLOR_SCHEME['OER'], linestyle='-', linewidth=1, alpha=0.25)
    
    # Create line objects for each track (these will be updated during animation)
    lines = []
    markers = []
    
    # Original track
    line_orig, = ax.plot([], [], color=COLOR_SCHEME['Original'], linestyle='-', 
                        linewidth=2, label='Original')
    marker_orig, = ax.plot([], [], 'o', color=COLOR_SCHEME['Original'], 
                          markersize=8, markeredgecolor='white', markeredgewidth=1)
    lines.append(line_orig)
    markers.append(marker_orig)
    
    # NCCOS Window track if available
    if 'Window_Longitude' in df.columns:
        line_window, = ax.plot([], [], color=COLOR_SCHEME['Window'], linestyle='-', 
                              linewidth=2, label='NCCOS Moving Window')
        marker_window, = ax.plot([], [], 'o', color=COLOR_SCHEME['Window'], 
                                markersize=7, markeredgecolor='white', markeredgewidth=1)
        lines.append(line_window)
        markers.append(marker_window)
    
    # TATOR Kalman track if available
    if 'Kalman_Longitude' in df.columns:
        line_kalman, = ax.plot([], [], color=COLOR_SCHEME['Kalman'], linestyle='-', 
                              linewidth=2, label='TATOR Kalman Filter')
        marker_kalman, = ax.plot([], [], 'o', color=COLOR_SCHEME['Kalman'], 
                                markersize=7, markeredgecolor='white', markeredgewidth=1)
        lines.append(line_kalman)
        markers.append(marker_kalman)
    
    # OER Moving Average track if available
    if 'OER_Longitude' in df.columns:
        line_oer, = ax.plot([], [], color=COLOR_SCHEME['OER'], linestyle='-', 
                           linewidth=2, label='OER Moving Average')
        marker_oer, = ax.plot([], [], 'o', color=COLOR_SCHEME['OER'], 
                             markersize=7, markeredgecolor='white', markeredgewidth=1)
        lines.append(line_oer)
        markers.append(marker_oer)
    
    # Text for timestamp display
    timestamp_text = ax.text(0.02, 0.98, '', transform=ax.transAxes, 
                          va='top', ha='left', fontsize=10, 
                          bbox=dict(facecolor='white', alpha=0.7, boxstyle='round'))
    
    # Configure the plot
    ax.set_xlabel('Longitude')
    ax.set_ylabel('Latitude')
    
    # Set title based on base_name if provided
    if base_name:
        title = f"{base_name} - Navigation Track Smoothing"
    else:
        title = "Navigation Track Smoothing Comparison"
    
    ax.set_title(title)
    ax.grid(True, linestyle='--', alpha=0.7)
    
    # Add legend - moved from below the plot to the lower right within the plot
    # This ensures it's always visible and doesn't get cut off
    ax.legend(loc='lower right', fontsize=9, framealpha=0.9)
    
    # Get timestamps for time display
    timestamps = df['Timestamp'].values
    # Convert to datetime if not already
    import pandas as pd
    if not isinstance(timestamps[0], pd.Timestamp):
        timestamps = pd.to_datetime(timestamps)
    
    # Animation initialization function
    def init():
        for line in lines:
            line.set_data([], [])
        for marker in markers:
            marker.set_data([], [])
        timestamp_text.set_text('')
        return lines + markers + [timestamp_text]
    
    # Animation update function
    def update(frame):
        # Get timestamp for this frame
        current_timestamp = timestamps[frame]
        
        # Format timestamp for display
        timestamp_str = current_timestamp.strftime('%Y-%m-%d %H:%M:%S')
        
        # Update original track
        line_orig.set_data(df['Original_Longitude'].iloc[:frame+1], 
                          df['Original_Latitude'].iloc[:frame+1])
        marker_orig.set_data([df['Original_Longitude'].iloc[frame]], 
                            [df['Original_Latitude'].iloc[frame]])
        
        # Update Window track if available
        if 'Window_Longitude' in df.columns:
            line_idx = lines.index(line_window)
            lines[line_idx].set_data(df['Window_Longitude'].iloc[:frame+1], 
                                   df['Window_Latitude'].iloc[:frame+1])
            markers[line_idx].set_data([df['Window_Longitude'].iloc[frame]], 
                                     [df['Window_Latitude'].iloc[frame]])
        
        # Update Kalman track if available
        if 'Kalman_Longitude' in df.columns:
            line_idx = lines.index(line_kalman)
            lines[line_idx].set_data(df['Kalman_Longitude'].iloc[:frame+1], 
                                   df['Kalman_Latitude'].iloc[:frame+1])
            markers[line_idx].set_data([df['Kalman_Longitude'].iloc[frame]], 
                                     [df['Kalman_Latitude'].iloc[frame]])
        
        # Update OER track if available
        if 'OER_Longitude' in df.columns:
            line_idx = lines.index(line_oer)
            lines[line_idx].set_data(df['OER_Longitude'].iloc[:frame+1], 
                                   df['OER_Latitude'].iloc[:frame+1])
            markers[line_idx].set_data([df['OER_Longitude'].iloc[frame]], 
                                     [df['OER_Latitude'].iloc[frame]])
        
        # Update timestamp text
        timestamp_text.set_text(f'Time: {timestamp_str}')
        
        # Save frame if frames_dir is specified
        if frames_dir is not None:
            frame_filename = os.path.join(frames_dir, f"frame_{frame:04d}.png")
            try:
                plt.savefig(frame_filename, dpi=dpi)
            except Exception as e:
                print(f"Error saving frame {frame}: {str(e)}")
        
        return lines + markers + [timestamp_text]
    
    # Calculate appropriate number of frames
    if len(df) > 100:
        step = max(1, len(df) // 60)  # Target ~60 frames for longer tracks
    else:
        step = 1
    
    frames = range(0, len(df), step)
    
    # Create animation
    print(f"Creating animation with {len(frames)} frames...")
    
    # Create frames directory if needed
    if frames_dir is not None:
        os.makedirs(frames_dir, exist_ok=True)
        print(f"Saving individual frames to {frames_dir}")
    
    # Generate the animation
    anim = animation.FuncAnimation(fig, update, frames=frames,
                                  init_func=init, blit=True, interval=1000/fps)
    
    # Save as GIF with error handling
    print(f"Saving animation to {output_filename}...")
    try:
        anim.save(output_filename, writer='pillow', fps=fps, dpi=dpi)
        print(f"Animation saved to {output_filename}")
    except PermissionError:
        # Try to save to a temporary file first, then move it
        import tempfile
        temp_dir = tempfile.gettempdir()
        temp_filename = os.path.join(temp_dir, f"temp_animation_{os.path.basename(output_filename)}")
        
        print(f"Permission error saving to {output_filename}")
        print(f"Trying to save to temporary file: {temp_filename}")
        
        try:
            anim.save(temp_filename, writer='pillow', fps=fps, dpi=dpi)
            
            # Suggest the location of the temporary file to the user
            print(f"Animation saved to temporary file: {temp_filename}")
            print(f"Please copy this file to your desired location manually.")
            
            import tkinter as tk
            from tkinter import messagebox
            
            # Show a message box with the temporary file location
            root = tk.Tk()
            root.withdraw()  # Hide the main window
            messagebox.showinfo("Animation Saved to Temporary Location",
                               f"The animation could not be saved to the specified location due to permission issues.\n\n"
                               f"It has been saved to the following temporary location instead:\n"
                               f"{temp_filename}\n\n"
                               f"Please copy this file to your desired location manually.")
            root.destroy()
            
        except Exception as e:
            print(f"Failed to save animation to temporary file: {str(e)}")
    except Exception as e:
        print(f"Error saving animation: {str(e)}")
    
    plt.close(fig)