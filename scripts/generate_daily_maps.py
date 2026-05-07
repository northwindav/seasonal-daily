# Generate daily FWI maps based on outputs from the 2 CFS Seasonal Forecast v2 ensembles
# Currently in exploratory state and is hard-coded for Ontario
# Outputs are also limited to the first 3 months of the forecast.

import os
from datetime import datetime, timedelta
import xarray as xr
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import Rectangle
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import warnings

from utils import (
    parse_init_date_from_filename,
    create_fwi_colormap,
    load_provincial_boundaries,
    crop_to_region,
    get_3month_window,
    convert_time_to_datetime,
)

warnings.filterwarnings('ignore')


# Define the map bounds and buffer
# Currently hard-coded for ON 
# Buffer may be expanded from 150 km if desired
# This is a crude approach, where we define a bounding box rather than creating a true buffer
# Returns: dictionary containing a buffered bounding box with coordinates in degrees
def get_ontario_bounds(buffer_km=150):

    # Ontario bounds (approximate)
    ont_lat_min, ont_lat_max = 41.7, 56.9
    ont_lon_min, ont_lon_max = -95.2, -74.3
    
    # Rough conversion: 1 degree ~ 111 km at equator, ~80 km at 45°N
    buffer_deg = buffer_km / 111.0
    
    bounds = {
        'lat_min': ont_lat_min - buffer_deg,
        'lat_max': ont_lat_max + buffer_deg,
        'lon_min': ont_lon_min - buffer_deg,
        'lon_max': ont_lon_max + buffer_deg,
    }
    
    return bounds

# Generate map for each timestep
# In:
# - fwi_data: numpy.ndarray. 2D array containing FWI data for a single day, cropped to the ROI.
# - lat and lon: numpy.ndarray
# - date_str: string for the title (e.g., '2026-05-06')
# - filename: output file name for the png
# - ontario_bounds: dict containing the ROI boundaries
# - model_name: str containing the name of the forecast model
# - initi_date: datetime object for the model initialization date
# - provinces: dict of geodataframes for the provinces to plot
def create_fwi_map(fwi_data, lat, lon, date_str, filename, ontario_bounds=None, model_name=None, init_date=None, provinces=None):

    fig = plt.figure(figsize=(14, 10))
    ax = plt.axes(projection=ccrs.PlateCarree())
    
    # Set extent
    ax.set_extent([lon.min(), lon.max(), lat.min(), lat.max()], crs=ccrs.PlateCarree())
    
    # Add features. 
    # Cities are not included by default but can be accessed via cartopy's Natural Earth features.
    ax.add_feature(cfeature.COASTLINE, linewidth=0.5)
    ax.add_feature(cfeature.BORDERS, linewidth=0.5)
    ax.add_feature(cfeature.LAKES, alpha=0.3)
    ax.add_feature(cfeature.RIVERS, linewidth=0.3)
    ax.gridlines(draw_labels=True, alpha=0.3)
    
    # Plot FWI data with custom colormap and fixed scale (0-50)
    # Change the scale here if plotting where FWI values are expected to be lower.
    cmap = create_fwi_colormap()
    norm = mcolors.Normalize(vmin=0, vmax=50)
    
    im = ax.contourf(lon, lat, fwi_data, levels=np.arange(0, 51, 5), cmap=cmap, norm=norm,
                     transform=ccrs.PlateCarree())
    
    # Plot actual provincial boundaries
    if provinces:
        # Ontario (blue solid)
        if 'Ontario' in provinces:
            for idx, row in provinces['Ontario'].iterrows():
                ax.add_geometries([row.geometry], crs=ccrs.PlateCarree(), 
                                 facecolor='none', edgecolor='darkblue', linewidth=2, 
                                 label='Ontario' if idx == 0 else '')
        
        # Manitoba (green dashed)
        if 'Manitoba' in provinces:
            for idx, row in provinces['Manitoba'].iterrows():
                ax.add_geometries([row.geometry], crs=ccrs.PlateCarree(),
                                 facecolor='none', edgecolor='darkgreen', linewidth=1.5,
                                 linestyle='--', label='Manitoba' if idx == 0 else '')
        
        # Quebec (purple dashed)
        if 'Québec' in provinces:
            for idx, row in provinces['Québec'].iterrows():
                ax.add_geometries([row.geometry], crs=ccrs.PlateCarree(),
                                 facecolor='none', edgecolor='indigo', linewidth=1.5,
                                 linestyle='--', label='Quebec' if idx == 0 else '')
    
    # Add Ontario buffer box reference if no provinces loaded
    if not provinces or len(provinces) == 0:
        if ontario_bounds:
            rect = Rectangle((ontario_bounds['lon_min'], ontario_bounds['lat_min']),
                            ontario_bounds['lon_max'] - ontario_bounds['lon_min'],
                            ontario_bounds['lat_max'] - ontario_bounds['lat_min'],
                            linewidth=2, edgecolor='blue', facecolor='none',
                            transform=ccrs.PlateCarree(), label='Ontario + buffer')
            ax.add_patch(rect)
    
    ax.legend(loc='upper left', fontsize=9)
    
    # Colorbar with fixed scale
    cbar = plt.colorbar(im, ax=ax, orientation='vertical', pad=0.02, shrink=0.8)
    cbar.set_label('Fire Weather Index (FWI)', rotation=270, labelpad=20)
    cbar.set_ticks(np.arange(0, 51, 5))
    
    # Build title with model name and init date
    title_str = f'Daily FWI Map - {date_str}'
    if model_name:
        title_str = f'{model_name}: {title_str}'
    ax.set_title(title_str, fontsize=14, fontweight='bold')
    
    # Add footer with init datetime, generation timestamp, and caution
    now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    footer_lines = []
    
    if init_date:
        footer_lines.append(f'Init: {init_date.strftime("%Y-%m-%d %H:00 UTC")}')
    
    footer_lines.append(f'Generated: {now_str}')
    footer_lines.append('CAUTION: These products are unverified and should not be used without full knowledge of the seasonal forecast products, including expert interpretation.')
    
    footer_str = '  |  '.join(footer_lines)
    
    fig.text(0.5, 0.01, footer_str, ha='center', fontsize=7, style='italic', wrap=True)
    
    plt.tight_layout(rect=[0, 0.03, 1, 1])
    
    # Save
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    plt.savefig(filename, dpi=100, bbox_inches='tight')
    plt.close()
    
    return filename

# Calling function for generating the daily maps.
# - input_dir (str): Directory containing input .nc files
# - output_dir (str): Directory to save output maps
# - buffer_km (float): Buffer around Ontario in kilometers
# - target_date (datetime, optional): If specified, only generate map for this date
def generate_daily_maps(input_dir='input', output_dir='output/daily', buffer_km=150, target_date=None):

    # Load provincial boundaries once
    print("Loading provincial boundaries...")
    provinces = load_provincial_boundaries()
    if provinces:
        print(f"  Loaded: {', '.join(provinces.keys())}")
    print()
    
    # Get Ontario bounds
    ontario_bounds = get_ontario_bounds(buffer_km=buffer_km)
    print(f"Ontario bounds + {buffer_km}km buffer:")
    print(f"  Latitude: {ontario_bounds['lat_min']:.2f}° to {ontario_bounds['lat_max']:.2f}°")
    print(f"  Longitude: {ontario_bounds['lon_min']:.2f}° to {ontario_bounds['lon_max']:.2f}°")
    print()
    
    # Find all .nc files
    nc_files = sorted([f for f in os.listdir(input_dir) if f.endswith('.nc')])
    
    if not nc_files:
        print("No .nc files found in input directory")
        return
    
    # Determine 3-month window from first file
    init_date = None
    for filename in nc_files:
        init_date = parse_init_date_from_filename(filename)
        if init_date:
            break
    
    if not init_date:
        print("Could not determine init date from filenames")
        return
    
    start_date, end_date = get_3month_window(init_date)
    print(f"Processing 3-month window: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print()
    
    # Process each file
    for filename in nc_files:
        filepath = os.path.join(input_dir, filename)
        print(f"Processing: {filename}")
        
        try:
            ds = xr.open_dataset(filepath)
        except Exception as e:
            print(f"  Error opening file: {e}")
            continue
        
        # Crop to region
        ds_cropped = crop_to_region(ds, ontario_bounds)
        
        # Extract arrays
        lat = ds_cropped['lat'].values
        lon = ds_cropped['lon'].values
        time = ds_cropped['time'].values
        fwi = ds_cropped['FWI'].values  # Shape: (time, member, lat, lon)
        
        # Debugging info
        print(f"  Cropped dimensions: time={fwi.shape[0]}, members={fwi.shape[1]}, lat={fwi.shape[2]}, lon={fwi.shape[3]}")
        
        # Generate map for each timestep
        # Average across ensemble members
        fwi_mean = np.nanmean(fwi, axis=1) 
        
        # Filter to 3-month window
        # Convert time coordinates to datetime objects
        date_objs = convert_time_to_datetime(time)
        for tidx, date_obj in enumerate(date_objs):
            # Check if within 3-month window
            if start_date <= date_obj <= end_date:
                # If target_date specified, only process that date
                if target_date and date_obj.date() != target_date.date():
                    continue
                
                date_str = date_obj.strftime('%Y-%m-%d')
                fwi_daily = fwi_mean[tidx]
                
                # Create output path
                model_name = filename.split('_')[0]
                output_file = os.path.join(output_dir, f"{model_name}_{date_str}_FWI_map.png")
                
                # Create map
                try:
                    create_fwi_map(fwi_daily, lat, lon, date_str, output_file, 
                                 ontario_bounds=ontario_bounds, model_name=model_name, 
                                 init_date=init_date, provinces=provinces)
                    print(f"    ✓ {date_str}")
                except Exception as e:
                    print(f"    ✗ {date_str}: {e}")
        
        ds.close()
        print()
    
    print(f"Daily maps saved to: {output_dir}")


if __name__ == '__main__':
    # Generate maps for all dates in 3-month window (or specify target_date=datetime(2026, 5, 6) for testing)
    generate_daily_maps()
