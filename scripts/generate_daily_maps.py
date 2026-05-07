# Generate daily FWI maps based on outputs from the 2 CFS Seasonal Forecast v2 ensembles
# Currently in exploratory state and is hard-coded for Ontario
# Outputs are also limited to the first 3 months of the forecast.

import os
import re
from datetime import datetime, timedelta
import xarray as xr
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Rectangle
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import geopandas as gpd
import warnings

warnings.filterwarnings('ignore')

# Extract model init date from the filename. Used in the footers of all maps.
def parse_init_date_from_filename(filename):
    match = re.search(r'_init(\d{10})', filename)
    if match:
        date_str = match.group(1)
        return datetime.strptime(date_str, '%Y%m%d%H')
    return None

# Hard-code the color map for consistency across models and spatial/temporal dimensions. 
# Define FWI of 15 as the starting point for yellow-ish. Adjust as needed for regional fire risk thresholds.
def create_fwi_colormap():

    colors = [
        (0.0, '#1f77b4'),      # Blue at FWI 0
        (0.25, '#2ca02c'),     # Green around FWI 12.5
        (0.3, '#ffff00'),      # Light yellow starts at FWI 15
        (0.6, '#ff7f0e'),      # Orange around FWI 30
        (1.0, '#8B008B'),      # Purple at FWI 50
    ]
    
    n_bins = 256
    cmap = LinearSegmentedColormap.from_list('fwi_custom', colors, N=n_bins)
    return cmap

# Retrieve provincial boundaries from naturalearth. 
# Currently hard-coded for only MB, ON and PQ
# Returns a geodataframe for each province selected
def load_provincial_boundaries():

    try:
        ne_url = "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_1_states_provinces.zip"
        admin1 = gpd.read_file(ne_url)
        
        canada = admin1[admin1['admin'] == 'Canada']
        
        provinces = {}
        for prov_name in ['Ontario', 'Manitoba', 'Québec']:
            prov_data = canada[canada['name'] == prov_name]
            if len(prov_data) > 0:
                provinces[prov_name] = prov_data
            else:
                # As of May 2026 the accent aigu is required
                if prov_name == 'Québec':
                    prov_data = canada[canada['name'] == 'Quebec']
                    if len(prov_data) > 0:
                        provinces[prov_name] = prov_data
        
        return provinces
    except Exception as e:
        print(f"Warning: Could not load provincial boundaries: {e}")
        return {}

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

# Crop the xarray containing the actual data, based on the bounds defined in get_ontario_bounds()
def crop_to_region(ds, bounds):

    # Crop latitude
    ds_cropped = ds.sel(lat=slice(bounds['lat_min'], bounds['lat_max']))
    
    # For longitude, need to handle 0-360 system if necessary
    lon_min, lon_max = bounds['lon_min'], bounds['lon_max']
    
    # Check if data uses -180 to 180 or 0 to 360
    lon_vals = ds['lon'].values
    if np.all(lon_vals >= 0):
        # Convert -180 to 180 bounds to 0 to 360
        lon_min = lon_min % 360
        lon_max = lon_max % 360
    
    # Handle wrapping
    if lon_min > lon_max:
        # Wrapping case (e.g., lon_min=280, lon_max=50)
        ds_cropped = ds_cropped.sel(lon=(ds_cropped.lon >= lon_min) | (ds_cropped.lon <= lon_max))
    else:
        ds_cropped = ds_cropped.sel(lon=slice(lon_min, lon_max))
    
    return ds_cropped

# We hard-code a 3-month limit since plotting at daily resolution is completely
# beyond the intent of the seasonal product, and is also unvalidated.
def get_3month_window(init_date):

    start_date = init_date
    end_date = init_date + timedelta(days=91)  # ~3 months
    return start_date, end_date

# Called for each map, and outputs a png
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
        date_objs = [pd.Timestamp(t).to_pydatetime() for t in time]
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
