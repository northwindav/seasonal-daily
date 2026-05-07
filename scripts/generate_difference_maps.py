# Generate difference FWI maps based on average outputs from the 2 CFS Seasonal Forecast v2 ensembles
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
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import geopandas as gpd
import warnings

warnings.filterwarnings('ignore')

# Get init date from filename pattern: *_init<YYYYMMDDHH>.nc
def parse_init_date_from_filename(filename):
    match = re.search(r'_init(\d{10})', filename)
    if match:
        date_str = match.group(1)
        return datetime.strptime(date_str, '%Y%m%d%H')
    return None

# Hard-code the color map for consistency across models and spatial/temporal dimensions. 
# Define FWI of 15 as the starting point for yellow-ish. Adjust as needed for regional fire risk thresholds.
def create_difference_colormap():

    colors = [
        (0.0, '#8B008B'),      # Purple at -10
        (0.25, '#1f77b4'),     # Blue at -5
        (0.5, '#ffffff'),      # White at 0
        (0.75, '#ffff00'),     # Yellow at +5
        (1.0, '#d62728'),      # Red at +10
    ]
    
    n_bins = 256
    cmap = LinearSegmentedColormap.from_list('fwi_difference', colors, N=n_bins)
    return cmap

# Retrieve provincial boundaries from naturalearth. 
# Currently hard-coded for only MB, ON and PQ
# Returns a geodataframe for each province selected
def load_provincial_boundaries():
    try:
        ne_url = "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_1_states_provinces.zip"
        admin1 = gpd.read_file(ne_url)
        
        # Filter for Canada
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

    ont_lat_min, ont_lat_max = 41.7, 56.9
    ont_lon_min, ont_lon_max = -95.2, -74.3
    
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
  
    ds_cropped = ds.sel(lat=slice(bounds['lat_min'], bounds['lat_max']))
    
    lon_min, lon_max = bounds['lon_min'], bounds['lon_max']
    
    # Check if data uses -180 to 180 or 0 to 360
    lon_vals = ds['lon'].values
    if np.all(lon_vals >= 0):
        lon_min = lon_min % 360
        lon_max = lon_max % 360
    
    # Handle wrapping
    if lon_min > lon_max:
        ds_cropped = ds_cropped.sel(lon=(ds_cropped.lon >= lon_min) | (ds_cropped.lon <= lon_max))
    else:
        ds_cropped = ds_cropped.sel(lon=slice(lon_min, lon_max))
    
    return ds_cropped


def get_3month_window(init_date):

    start_date = init_date
    end_date = init_date + timedelta(days=91)
    return start_date, end_date

# Calculate the difference between the 20-member average from each model and create a map for each date in the 3-month window.
# Arguments:
# - diff_data: 2D array of FWI differences for a single date (CanESM5 - GEM5)
# - lat, lon: 1D arrays of latitude and longitude values
# - date_str: String representation of the date for the title
# - filename: string, Output filename for the PNG
# - ontario_bounds: Dictionary containing Ontario bounds for reference
# - init_date: datetime object, Initialization date of the forecast
# - provinces: Dictionary of GeoDataFrames for provinces
def create_difference_map(diff_data, lat, lon, date_str, filename, ontario_bounds=None, init_date=None, provinces=None):

    fig = plt.figure(figsize=(14, 10))
    ax = plt.axes(projection=ccrs.PlateCarree())
    
    # Set extent
    ax.set_extent([lon.min(), lon.max(), lat.min(), lat.max()], crs=ccrs.PlateCarree())
    
    # Add features
    ax.add_feature(cfeature.COASTLINE, linewidth=0.5)
    ax.add_feature(cfeature.BORDERS, linewidth=0.5)
    ax.add_feature(cfeature.LAKES, alpha=0.3)
    ax.add_feature(cfeature.RIVERS, linewidth=0.3)
    ax.gridlines(draw_labels=True, alpha=0.3)
    
    # Plot difference data with custom colormap
    # Values range from -20 to +20, centered at 0
    cmap = create_difference_colormap()
    norm = mcolors.Normalize(vmin=-20, vmax=20)
    
    im = ax.contourf(lon, lat, diff_data, levels=np.arange(-20, 21, 2), cmap=cmap, norm=norm,
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
    
    ax.legend(loc='upper left', fontsize=9)
    
    # Colorbar
    cbar = plt.colorbar(im, ax=ax, orientation='vertical', pad=0.02, shrink=0.8)
    cbar.set_label('FWI Difference (CanESM5 - GEM5.2-NEMO)', rotation=270, labelpad=20)
    cbar.set_ticks(np.arange(-20, 21, 2))
    
    # Title
    title_str = f'Daily FWI Difference (CanESM5 - GEM5.2-NEMO): {date_str}'
    ax.set_title(title_str, fontsize=14, fontweight='bold')
    
    # Add footer
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

# Calling function for the generation of each map
# Args:
# - input_dir: Directory containing input .nc files
# - output_dir: Output directory for maps
# - buffer_km: Buffer around Ontario in kilometers
# - target_date: If specified, only generate map for this date
def generate_difference_maps(input_dir='input', output_dir='output/difference', buffer_km=150, target_date=None):

    # Load provincial boundaries
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
    
    if len(nc_files) < 2:
        print("Error: Need at least 2 NetCDF files for comparison")
        return
    
    # Determine 3-month window and init date
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
    
    # Load both files
    file_data = {}
    for filename in nc_files:
        filepath = os.path.join(input_dir, filename)
        print(f"Loading: {filename}")
        
        try:
            ds = xr.open_dataset(filepath)
            ds_cropped = crop_to_region(ds, ontario_bounds)
            file_data[filename] = {
                'ds': ds_cropped,
                'lat': ds_cropped['lat'].values,
                'lon': ds_cropped['lon'].values,
                'time': ds_cropped['time'].values,
                'fwi': ds_cropped['FWI'].values,
            }
        except Exception as e:
            print(f"  Error: {e}")
            return
    
    print()
    
    # Identify CanESM5 and GEM5 files
    canesm_file = None
    gem5_file = None
    
    for filename in file_data.keys():
        if 'CanESM' in filename:
            canesm_file = filename
        elif 'GEM5' in filename:
            gem5_file = filename
    
    if not canesm_file or not gem5_file:
        print("Error: Could not identify CanESM5 and GEM5 files")
        return
    
    print(f"CanESM5 file: {canesm_file}")
    print(f"GEM5 file: {gem5_file}")
    print()
    
    # Extract data
    canesm_fwi = file_data[canesm_file]['fwi']  # Shape: (time, member, lat, lon)
    gem5_fwi = file_data[gem5_file]['fwi']
    
    lat = file_data[canesm_file]['lat']
    lon = file_data[canesm_file]['lon']
    time = file_data[canesm_file]['time']
    
    # Convert time to datetime objects
    date_objs = [pd.Timestamp(t).to_pydatetime() for t in time]
    
    # Average across ensemble members
    canesm_mean = np.nanmean(canesm_fwi, axis=1)  # Average ensemble members
    gem5_mean = np.nanmean(gem5_fwi, axis=1)
    
    # Process each date
    print("Generating difference maps...")
    for tidx, date_obj in enumerate(date_objs):
        # Check if within 3-month window
        if not (start_date <= date_obj <= end_date):
            continue
        
        # If target_date specified, only process that date
        if target_date and date_obj.date() != target_date.date():
            continue
        
        date_str = date_obj.strftime('%Y-%m-%d')
        
        # Compute difference (CanESM5 - GEM5)
        diff_data = canesm_mean[tidx] - gem5_mean[tidx]
        
        output_file = os.path.join(output_dir, f"FWI_Difference_{date_str}_map.png")
        
        # Create map
        try:
            create_difference_map(diff_data, lat, lon, date_str, output_file,
                                ontario_bounds=ontario_bounds, init_date=init_date,
                                provinces=provinces)
            print(f"  ✓ {date_str}")
        except Exception as e:
            print(f"  ✗ {date_str}: {e}")
    
    print()
    print(f"Difference maps saved to: {output_dir}")


if __name__ == '__main__':
    # Generate maps for all dates in 3-month window (or specify target_date=datetime(2026, 5, 6) for testing)
    generate_difference_maps()
