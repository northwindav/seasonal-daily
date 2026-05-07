# Generate weekly FWI maps based on average outputs from the 2 CFS Seasonal Forecast v2 ensembles
# Weekly outputs are for fixed 7-day periods, and are not a rolling average.
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


def parse_init_date_from_filename(filename):

    match = re.search(r'_init(\d{10})', filename)
    if match:
        date_str = match.group(1)
        return datetime.strptime(date_str, '%Y%m%d%H')
    return None


def create_fwi_colormap():

    colors = [
        (0.0, '#0000FF'),      # Blue at 0
        (0.25, '#00AA00'),     # Green at 5
        (0.3, '#FFFF00'),      # Yellow at 15
        (0.6, '#FF8800'),      # Orange at 30
        (1.0, '#8B008B'),      # Purple at 50
    ]
    
    n_bins = 256
    cmap = LinearSegmentedColormap.from_list('fwi_daily', colors, N=n_bins)
    return cmap


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
                # Try alternate spelling
                if prov_name == 'Québec':
                    prov_data = canada[canada['name'] == 'Quebec']
                    if len(prov_data) > 0:
                        provinces[prov_name] = prov_data
        
        return provinces
    except Exception as e:
        print(f"Warning: Could not load provincial boundaries: {e}")
        return {}


def get_ontario_bounds(buffer_km=150):
  
    ont_lat_min, ont_lat_max = 41.7, 56.9
    ont_lon_min, ont_lon_max = -95.2, -74.3
    
    # Rough conversion: 1 degree ~ 111 km
    buffer_deg = buffer_km / 111.0
    
    bounds = {
        'lat_min': ont_lat_min - buffer_deg,
        'lat_max': ont_lat_max + buffer_deg,
        'lon_min': ont_lon_min - buffer_deg,
        'lon_max': ont_lon_max + buffer_deg,
    }
    
    return bounds


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


def get_weekly_windows(start_date, end_date):
   
    windows = []
    current = start_date
    week_num = 1
    
    while current < end_date:
        window_start = current
        window_end = current + timedelta(days=7)
        
        # Clip to analysis window
        window_end = min(window_end, end_date)
        
        label = f"Week {week_num}: {window_start.strftime('%Y-%m-%d')} to {window_end.strftime('%Y-%m-%d')}"
        windows.append((window_start, window_end, label))
        
        current = window_end
        week_num += 1
    
    return windows


def create_fwi_map(fwi_data, lat, lon, model_name, window_start, window_end, filename, init_date=None, provinces=None):

    fig = plt.figure(figsize=(14, 10))
    ax = plt.axes(projection=ccrs.PlateCarree())
    
    ax.set_extent([lon.min(), lon.max(), lat.min(), lat.max()], crs=ccrs.PlateCarree())
    
    ax.add_feature(cfeature.COASTLINE, linewidth=0.5)
    ax.add_feature(cfeature.BORDERS, linewidth=0.5)
    ax.add_feature(cfeature.LAKES, alpha=0.3)
    ax.add_feature(cfeature.RIVERS, linewidth=0.3)
    ax.gridlines(draw_labels=True, alpha=0.3)
    
    # Plot FWI data with fixed 0-50 scale and custom colormap
    cmap = create_fwi_colormap()
    norm = mcolors.Normalize(vmin=0, vmax=50)
    
    im = ax.contourf(lon, lat, fwi_data, levels=[0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50],
                     cmap=cmap, norm=norm, transform=ccrs.PlateCarree())
    
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
    
    # Colorbar with fixed ticks
    cbar = plt.colorbar(im, ax=ax, orientation='vertical', pad=0.02, shrink=0.8)
    cbar.set_label('Fire Weather Index (FWI)', rotation=270, labelpad=20)
    cbar.set_ticks(np.arange(0, 51, 5))
    
    # Title with date range
    date_str_start = window_start.strftime('%Y-%m-%d')
    date_str_end = window_end.strftime('%Y-%m-%d')
    title_str = f'{model_name}: 1-week Average FWI - {date_str_start} to {date_str_end}'
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


def generate_weekly_maps(input_dir='input', output_dir='output/weekly', buffer_km=150):

    # Load provincial boundaries
    print("Loading provincial boundaries...")
    provinces = load_provincial_boundaries()
    if provinces:
        print(f"  Loaded: {', '.join(provinces.keys())}")
    print()
    
    ontario_bounds = get_ontario_bounds(buffer_km=buffer_km)
    print(f"Ontario bounds + {buffer_km}km buffer:")
    print(f"  Latitude: {ontario_bounds['lat_min']:.2f}° to {ontario_bounds['lat_max']:.2f}°")
    print(f"  Longitude: {ontario_bounds['lon_min']:.2f}° to {ontario_bounds['lon_max']:.2f}°")
    print()
    
    nc_files = sorted([f for f in os.listdir(input_dir) if f.endswith('.nc')])
    
    if not nc_files:
        print("No .nc files found in input directory")
        return
    
    # Determine 3-month window
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
    
    # Get weekly windows
    windows = get_weekly_windows(start_date, end_date)
    print(f"Generated {len(windows)} weekly windows\n")
    
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
        
        # Convert time to datetime objects
        date_objs = [pd.Timestamp(t).to_pydatetime() for t in time]
        
        # Average across ensemble members
        fwi_mean = np.nanmean(fwi, axis=1)  # Average ensemble members
        
        # Extract model name from filename for title display
        if 'CanESM5' in filename:
            model_name = 'CanESM5.1p1bc'
        elif 'GEM5' in filename:
            model_name = 'GEM5.2-NEMO'
        else:
            model_name = filename.split('_')[0]
        
        # Process each weekly window
        for win_start, win_end, label in windows:
            # Find indices within window
            indices = [i for i, d in enumerate(date_objs) if win_start <= d < win_end]
            
            if indices:
                # Average FWI across the week
                fwi_weekly = np.nanmean(fwi_mean[indices], axis=0)
                
                # Create output path with date range
                date_label_start = win_start.strftime('%Y-%m-%d')
                date_label_end = win_end.strftime('%Y-%m-%d')
                output_file = os.path.join(output_dir, f"{model_name}_{date_label_start}_to_{date_label_end}_FWI_week.png")
                
                # Create map
                try:
                    create_fwi_map(fwi_weekly, lat, lon, model_name, win_start, win_end, output_file, 
                                  init_date=init_date, provinces=provinces)
                    print(f"  ✓ {date_label_start} to {date_label_end}")
                except Exception as e:
                    print(f"  ✗ {date_label_start} to {date_label_end}: {e}")
        
        ds.close()
        print()
    
    print(f"Weekly maps saved to: {output_dir}")


if __name__ == '__main__':
    generate_weekly_maps()
