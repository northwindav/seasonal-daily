# Generate daily FWI standard deviation maps based on outputs from the 2 CFS Seasonal Forecast v2 ensembles
# Supports multiple regions (Ontario, BC, Canada-wide, etc.)
# Shows the ensemble uncertainty for each day across the 20 ensemble members
# Outputs are limited to the first 3 months of the forecast.

import os
import argparse
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
    create_stddev_colormap,
    load_provincial_boundaries,
    crop_to_region,
    get_3month_window,
    convert_time_to_datetime,
    create_projection_from_config,
)
from config_loader import get_region_config, get_bounds_dict, get_projection_from_region, list_regions

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
# - stddev_data: numpy.ndarray. 2D array containing FWI standard deviation for a single day, cropped to the ROI.
# - lat and lon: numpy.ndarray
# - date_str: string for the title (e.g., '2026-05-06')
# - filename: output file name for the png
# - ontario_bounds: dict containing the ROI boundaries
# - model_name: str containing the name of the forecast model
# - init_date: datetime object for the model initialization date
# - provinces: dict of geodataframes for the provinces to plot
def create_stddev_map(stddev_data, lat, lon, date_str, filename, ontario_bounds=None, model_name=None, init_date=None, provinces=None, projection=None):

    if projection is None:
        projection = ccrs.PlateCarree()
    
    fig = plt.figure(figsize=(14, 10))
    ax = plt.axes(projection=projection)
    
    # Set extent
    ax.set_extent([lon.min(), lon.max(), lat.min(), lat.max()], crs=ccrs.PlateCarree())
    
    # Add features. 
    # Cities are not included by default but can be accessed via cartopy's Natural Earth features.
    ax.add_feature(cfeature.COASTLINE, linewidth=0.5)
    ax.add_feature(cfeature.BORDERS, linewidth=0.5)
    ax.add_feature(cfeature.LAKES, alpha=0.3)
    ax.add_feature(cfeature.RIVERS, linewidth=0.3)
    ax.gridlines(draw_labels=True, alpha=0.3)
    
    # Plot standard deviation data with custom colormap and fixed scale (0-20)
    cmap = create_stddev_colormap()
    norm = mcolors.Normalize(vmin=0, vmax=20)
    
    im = ax.contourf(lon, lat, stddev_data, levels=np.arange(0, 21, 2), cmap=cmap, norm=norm,
                     transform=ccrs.PlateCarree())
    
    # Plot actual provincial boundaries
    # Define colors/styles for specific provinces, generic style for others
    if provinces:
        province_styles = {
            'Ontario': {'color': 'darkblue', 'linestyle': '-', 'linewidth': 2},
            'Manitoba': {'color': 'darkgreen', 'linestyle': '--', 'linewidth': 1.5},
            'Québec': {'color': 'indigo', 'linestyle': '--', 'linewidth': 1.5},
            'Quebec': {'color': 'indigo', 'linestyle': '--', 'linewidth': 1.5},
            'British Columbia': {'color': 'purple', 'linestyle': '--', 'linewidth': 1.5},
            'Alberta': {'color': 'brown', 'linestyle': '--', 'linewidth': 1.5},
            'Saskatchewan': {'color': 'orange', 'linestyle': '--', 'linewidth': 1.5},
            'New Brunswick': {'color': 'red', 'linestyle': '--', 'linewidth': 1.5},
            'Newfoundland and Labrador': {'color': 'pink', 'linestyle': '--', 'linewidth': 1.5},
            'Yukon': {'color': 'gray', 'linestyle': ':', 'linewidth': 1},
            'Northwest Territories': {'color': 'darkgray', 'linestyle': ':', 'linewidth': 1},
        }
        
        # Draw each province
        for prov_name, prov_gdf in provinces.items():
            # Get style for this province, or use a default
            style = province_styles.get(prov_name, {'color': 'black', 'linestyle': '--', 'linewidth': 1})
            
            for idx, row in prov_gdf.iterrows():
                ax.add_geometries([row.geometry], crs=ccrs.PlateCarree(),
                                 facecolor='none', edgecolor=style['color'], 
                                 linewidth=style['linewidth'], linestyle=style['linestyle'],
                                 label=prov_name if idx == 0 else '')
    
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
    cbar.set_label('Ensemble Std Dev (FWI)', rotation=270, labelpad=20)
    cbar.set_ticks(np.arange(0, 21, 2))
    
    # Build title with model name and init date
    title_str = f'Daily FWI Standard Deviation - {date_str}'
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

# Calling function for generating the standard deviation maps.
# - input_dir (str): Directory containing input .nc files
# - output_dir (str): Directory to save output maps
# - region_bounds (dict): Bounding box with lat_min, lat_max, lon_min, lon_max
# - province_names (list): Names of provinces to load and plot
# - buffer_km (float): Buffer size in kilometers (mainly for display/info)
# - target_date (datetime, optional): If specified, only generate map for this date
def generate_stddev_maps(input_dir='input', output_dir='output/stddev', region_bounds=None, province_names=None, buffer_km=150, region_name=None, projection_config=None, target_date=None):

    # Load provincial boundaries once
    print("Loading provincial boundaries...")
    provinces = load_provincial_boundaries(province_names=province_names)
    if provinces:
        print(f"  Loaded: {', '.join(provinces.keys())}")
    print()
    
    # Use provided bounds or fall back to Ontario
    if region_bounds is None:
        region_bounds = get_ontario_bounds(buffer_km=buffer_km)
    
    print(f"Region bounds:")
    print(f"  Latitude: {region_bounds['lat_min']:.2f}° to {region_bounds['lat_max']:.2f}°")
    print(f"  Longitude: {region_bounds['lon_min']:.2f}° to {region_bounds['lon_max']:.2f}°")
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
        ds_cropped = crop_to_region(ds, region_bounds)
        
        # Extract arrays
        lat = ds_cropped['lat'].values
        lon = ds_cropped['lon'].values
        time = ds_cropped['time'].values
        fwi = ds_cropped['FWI'].values  # Shape: (time, member, lat, lon)
        
        # Debugging info
        print(f"  Cropped dimensions: time={fwi.shape[0]}, members={fwi.shape[1]}, lat={fwi.shape[2]}, lon={fwi.shape[3]}")
        
        # Generate map for each timestep
        # Compute standard deviation across ensemble members
        fwi_stddev = np.nanstd(fwi, axis=1) 
        
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
                stddev_daily = fwi_stddev[tidx]
                
                # Create output path
                model_name = filename.split('_')[0]
                region_normalized = region_name.replace(' ', '_') if region_name else 'default'
                output_file = os.path.join(output_dir, f"{model_name}_{region_normalized}_{date_str}_STDDEV_map.png")
                
                # Create map
                try:
                    projection = create_projection_from_config(projection_config)
                    create_stddev_map(stddev_daily, lat, lon, date_str, output_file, 
                                    ontario_bounds=region_bounds, model_name=model_name, 
                                    init_date=init_date, provinces=provinces, projection=projection)
                    print(f"    ✓ {date_str}")
                except Exception as e:
                    print(f"    ✗ {date_str}: {e}")


def main():
    """Main function to handle CLI arguments and generate standard deviation maps."""
    parser = argparse.ArgumentParser(
        description='Generate daily FWI standard deviation maps from CFS Seasonal Forecast ensembles',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='Examples:\n'
               '  python generate_stddev_maps.py                  # Use default region (Canada-wide)\n'
               '  python generate_stddev_maps.py --region ontario # Generate for Ontario\n'
               '  python generate_stddev_maps.py --list-regions   # Show available regions'
    )
    parser.add_argument(
        '--region',
        type=str,
        default=None,
        help='Region to generate maps for (default: Canada-wide). Use --list-regions to see options.'
    )
    parser.add_argument(
        '--list-regions',
        action='store_true',
        help='List all available regions and exit'
    )
    parser.add_argument(
        '--input-dir',
        type=str,
        default='input',
        help='Directory containing input NetCDF files (default: input)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='output/stddev',
        help='Directory to save output maps (default: output/stddev)'
    )
    
    args = parser.parse_args()
    
    # Handle --list-regions
    if args.list_regions:
        print("Available regions:")
        regions_list = list_regions()
        for name, description, is_default in regions_list:
            default_marker = " [DEFAULT]" if is_default else ""
            print(f"  {name:20} {description}{default_marker}")
        return
    
    # Load region configuration
    try:
        region_config, region_name = get_region_config(args.region)
        bounds = get_bounds_dict(region_config)
        provinces = region_config.get('provinces', None)
        buffer_km = region_config.get('buffer_km', 150)
        projection_config = get_projection_from_region(region_config)
        
        print(f"Region: {region_name}\n")
        
        # Parse target date if provided
        target_date = None
        
        # Generate maps with region-specific configuration
        generate_stddev_maps(
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            region_bounds=bounds,
            province_names=provinces,
            buffer_km=buffer_km,
            region_name=region_name,
            projection_config=projection_config,
            target_date=target_date
        )
    except ValueError as e:
        print(f"Error: {e}", file=__import__('sys').stderr)
        print(f"\nUse --list-regions to see available options", file=__import__('sys').stderr)
        exit(1)


if __name__ == '__main__':
    main()
