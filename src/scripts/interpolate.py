import os
import sys
import traceback
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pykrige.ok import OrdinaryKriging
from pandas.errors import EmptyDataError

import matplotlib.patches as patches
import matplotlib.path as mpath

import matplotlib.cm as cm
import matplotlib.colors as mcolors
import matplotlib.colorbar as colorbar

import geojson
from shapely.geometry import LineString, mapping

# === Function to generate and save a vertical colorbar as a PNG/SVG ===
def generate_colorbar_png(vmin, vmax, cmap_name, label, out_path):
    fig, ax = plt.subplots(figsize=(1.2, 5))
    cmap = plt.colormaps[cmap_name]

    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
    cb = colorbar.ColorbarBase(ax, cmap=cmap, norm=norm, orientation='vertical')
    cb.set_label(label)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches='tight', dpi=150)
    plt.close(fig)

# === Required CSV Columns ==
REQUIRED_COLUMNS = {'X', 'Y', 'nitrogen', 'phosphorus', 'potassium'}

# === Function to validate CSV input ===
def validate_input_data(df):
    if df.empty:
        error_exit("CSV file is empty.")

    # Check required columns
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        error_exit(f"Missing columns in CSV. Required columns: {REQUIRED_COLUMNS}, but missing: {missing}")

    # Check numeric types
    for col in REQUIRED_COLUMNS:
        if not pd.api.types.is_numeric_dtype(df[col]):
            error_exit(f"Column '{col}' contains non-numeric values.")

    # Drop rows with NaN in critical columns
    df.dropna(subset=REQUIRED_COLUMNS, inplace=True)
    if df.empty:
        error_exit("All rows have NaN values in required columns.")

    # At least two valid points
    if df.shape[0] < 2:
        error_exit("Not enough valid data points to perform interpolation (minimum 2 required).")

    # Non-fatal warnings
    if df.duplicated(subset=['X', 'Y']).any():
        print("WARNING: Duplicate coordinates detected.")
    for nutrient in ['nitrogen', 'phosphorus', 'potassium']:
        if df[nutrient].nunique() == 1:
            print(f"WARNING: All values for {nutrient} are the same.")
        if df[nutrient].max() > 10000 or df[nutrient].min() < -1000:
            print(f"WARNING: Extreme values in {nutrient} (check for outliers).")

    if not df[(df['X'] > df['X'].min()) & (df['X'] < df['X'].max()) &
        (df['Y'] > df['Y'].min()) & (df['Y'] < df['Y'].max())].any().any():
        print("WARNING: All points lie on the boundary — interpolation inside may be unreliable.")

    return df

# === Function to print error message and exit ===
def error_exit(message):
    sys.stderr.write(f"ERROR: {message}\n")
    sys.exit(1)

# === MAIN EXECUTION BLOCK ===
try:
    # ⬇️ Read input file paths from command-line arguments
    plot_file = sys.argv[1]   # GeoJSON file for plot boundary
    sample_file = sys.argv[2] # CSV file containing nutrient data
    output_file = sys.argv[3] # Output file for final visualization

    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    # Check if sample file exists
    if not os.path.exists(sample_file):
        error_exit(f"Sample file does not exist: {sample_file}")

    # Read and validate the CSV
    try:
        df = pd.read_csv(sample_file)
    except EmptyDataError:
        error_exit("CSV file is empty or has no parsable content.")

    df = validate_input_data(df)

    x = df['X'].dropna().values
    y = df['Y'].dropna().values

    # === Kriging Interpolation Function ===
    def interpolate(variable):
        z = df[variable].dropna().values
        if len(z) != len(x):
            error_exit(f"Mismatch in length of coordinate and nutrient values for {variable}")
        try:
            grid_x = np.linspace(min(x), max(x), 100)
            grid_y = np.linspace(min(y), max(y), 100)
            OK = OrdinaryKriging(x, y, z, variogram_model='linear', verbose=False, enable_plotting=False)
            zi, _ = OK.execute("grid", grid_x, grid_y)
        except Exception as e:
            error_exit(f"Kriging failed for {variable}: {str(e)}")
        zi = np.nan_to_num(np.array(zi), nan=0.0)
        original_min, original_max = zi.min(), zi.max()
        zi_norm = (zi - original_min) / (original_max - original_min) if original_max > original_min else np.ones_like(zi) * 0.5
        X_grid, Y_grid = np.meshgrid(grid_x, grid_y)
        return zi_norm, original_min, original_max, X_grid, Y_grid, zi

    # Interpolate all nutrients
    z_n, min_n, max_n, grid_x, grid_y, predictions_N = interpolate('nitrogen')
    z_p, min_p, max_p, _, _, predictions_P = interpolate('phosphorus')
    z_k, min_k, max_k, _, _, predictions_K = interpolate('potassium')
    
    # Generate and save individual colorbars
    os.makedirs("output", exist_ok=True)
    # === Generate colorbar legends for nutrients ===
    generate_colorbar_png(min_n, max_n, 'Reds', 'Nitrogen (mg/kg)', 'output/legend-nitrogen.svg')
    generate_colorbar_png(min_p, max_p, 'Greens', 'Phosphorus (mg/kg)', 'output/legend-phosphorus.svg')
    # generate_colorbar_png(min_k, max_k, 'Blues', 'Potassium (mg/kg)', 'output/legend-potassium.svg')
    generate_colorbar_png(min_k, max_k, 'YlOrBr', 'Potassium (mg/kg)', 'output/legend-potassium.svg')

   
   # === Create RGB-stacked visualization ===
    rgb = np.dstack((z_n, z_p, z_k))
    # Create figure
    plt.figure(figsize=(8, 6))  

    # Assume grid_x, grid_y are 2D meshgrid and predictions_N, predictions_P, predictions_K are 2D arrays
    contour_levels = 10  # number of contour levels (you can customize this)

    # Draw contours
    # Nitrogen
    cs_N = plt.contourf(grid_x, grid_y, predictions_N, levels=contour_levels, cmap='Reds', alpha=0.6)
       
    # Phosphorus
    cs_P = plt.contourf(grid_x, grid_y, predictions_P, levels=contour_levels, cmap='Greens', alpha=0.5)
        
    # Potassium
    # cs_K = plt.contourf(grid_x, grid_y, predictions_K, levels=contour_levels, cmap='Blues', alpha=0.4)
    cs_K = plt.contourf(grid_x, grid_y, predictions_K, levels=contour_levels, cmap='YlOrBr', alpha=0.4)
   
    # Outline contours
    plt.contour(grid_x, grid_y, predictions_N, levels=contour_levels, colors='darkred', linewidths=0.5)
    plt.contour(grid_x, grid_y, predictions_P, levels=contour_levels, colors='darkgreen', linewidths=0.5)
    # plt.contour(grid_x, grid_y, predictions_K, levels=contour_levels, colors='darkblue', linewidths=0.5)
    plt.contour(grid_x, grid_y, predictions_K, levels=contour_levels, colors='goldenrod', linewidths=0.5)
   
    plt.title("Interpolated Nutrient Levels (R: N, G: P, Y: K)")
    plt.xlabel("X")
    plt.ylabel("Y")

    # === Overlay polygon boundary/polygon edge ===
    import json
    if not os.path.exists(plot_file):
        error_exit(f"Plot file does not exist: {plot_file}")

    with open(plot_file, 'r') as f:
        try:
            geojson = json.load(f)
            coords = geojson['features'][0]['geometry']['coordinates'][0]
            xs, ys = zip(*coords)          
            plt.plot(xs, ys, color='red', linewidth=3, linestyle='--',label='Plot Boundary')
            print(f"Boundary X range: {min(xs)} to {max(xs)}")
            print(f"Boundary Y range: {min(ys)} to {max(ys)}")
            print(f"Grid X range: {grid_x.min()} to {grid_x.max()}")
            print(f"Grid Y range: {grid_y.min()} to {grid_y.max()}")

        except Exception as e:
            print(f"WARNING: Could not parse polygon for overlay:- {e}")

    # === Overlay data points with labels ===
    for i, row in df.iterrows():
        plt.scatter(row['X'], row['Y'], color='black', s=20, marker='x')  
   
        plt.text(row['X'] + 0.0002, row['Y'] + 0.0002, f"N:{row['nitrogen']},P:{row['phosphorus']},K:{row['potassium']}",
         fontsize=7, color='black', ha='left', va='bottom', alpha=0.8,bbox=dict(facecolor='white', alpha=0.8, edgecolor='none', pad=2))
        plt.legend(loc='upper right')
        
    # === Add individual colorbars for each nutrient on right side ===
    from mpl_toolkits.axes_grid1 import make_axes_locatable
    import matplotlib.cm as cm
    import matplotlib.colors as mcolors
    
    # Access the current axis and prepare for extra colorbars
    ax = plt.gca()
    divider = make_axes_locatable(ax)
    
    # For Nitrogen (Red)
    cax_n = divider.append_axes("right", size="2%", pad=0.4)
    cmap_n = cm.Reds
    norm_n = mcolors.Normalize(vmin=min_n, vmax=max_n)
    cb_n = plt.colorbar(cm.ScalarMappable(norm=norm_n, cmap=cmap_n), cax=cax_n)
    cb_n.set_label("Nitrogen (mg/kg)", fontsize=8)
    
    # For Phosphorus (Green)
    cax_p = divider.append_axes("right", size="2%", pad=0.6)
    cmap_p = cm.Greens
    norm_p = mcolors.Normalize(vmin=min_p, vmax=max_p)
    cb_p = plt.colorbar(cm.ScalarMappable(norm=norm_p, cmap=cmap_p), cax=cax_p)
    cb_p.set_label("Phosphorus (mg/kg)", fontsize=8)
    
    # For Potassium (Blue)
    cax_k = divider.append_axes("right", size="2%", pad=0.7)
    # cmap_k = cm.Blues
    cmap_k = cm.YlOrBr
    norm_k = mcolors.Normalize(vmin=min_k, vmax=max_k)
    cb_k = plt.colorbar(cm.ScalarMappable(norm=norm_k, cmap=cmap_k), cax=cax_k)
    cb_k.set_label("Potassium (mg/kg)", fontsize=8)

    # === Save final visualization ===
    plt.savefig(output_file, format="svg")  

    # === Print bounds of the interpolated area (used in frontend) ===
    bounds = [[float(min(y)), float(min(x))], [float(max(y)), float(max(x))]]
    print(f"BOUNDS_JSON:{bounds}")

# === Catch all errors during processing ===
except Exception as e:
    error_msg = f"Interpolation failed: {str(e)}\n"
    sys.stderr.write(error_msg)
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)






    