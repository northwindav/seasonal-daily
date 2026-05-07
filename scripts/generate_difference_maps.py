# Generate difference FWI maps based on average outputs from the 2 CFS Seasonal Forecast v2 ensembles
# Supports multiple regions (Ontario, BC, Canada-wide, etc.)
# Outputs are limited to the first 3 months of the forecast.

import os
import argparse
from datetime import datetime, timedelta
import xarray as xr
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import warnings

from utils import (
    parse_init_date_from_filename,
    create_difference_colormap,
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

# Calculate the difference between the 20-member average from each model and create a map for each date in the 3-month window.
# Arguments:
# - diff_data: 2D array of FWI differences for a single date (CanESM5 - GEM5)
# - lat, lon: 1D arrays of latitude and longitude values
# - date_str: String representation of the date for the title
# - filename: string, Output filename for the PNG
# - ontario_bounds: Dictionary containing Ontario bounds for reference
# - init_date: datetime object, Initialization date of the forecast
# - provinces: Dictionary of GeoDataFrames for provinces
def create_difference_map(diff_data, lat, lon, date_str, filename, ontario_bounds=None, init_date=None, provinces=None, projection=None):

    if projection is None:
        projection = ccrs.PlateCarree()
    
    fig = plt.figure(figsize=(14, 10))
    ax = plt.axes(projection=projection)
    
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
# - region_bounds: Bounding box with lat_min, lat_max, lon_min, lon_max
# - province_names: Names of provinces to load and plot
# - buffer_km: Buffer size in kilometers (mainly for display/info)
# - target_date: If specified, only generate map for this date
def generate_difference_maps(input_dir='input', output_dir='output/difference', region_bounds=None, province_names=None, buffer_km=150, region_name=None, projection_config=None, target_date=None):

    # Load provincial boundaries
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
            ds_cropped = crop_to_region(ds, region_bounds)
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
    date_objs = convert_time_to_datetime(time)
    
    # Calculate median across ensemble members
    canesm_median = np.nanmedian(canesm_fwi, axis=1)  # Median ensemble members
    gem5_median = np.nanmedian(gem5_fwi, axis=1)
    
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
        
        # Compute difference (CanESM5 - GEM5) using medians
        diff_data = canesm_median[tidx] - gem5_median[tidx]
        
        region_normalized = region_name.replace(' ', '_') if region_name else 'default'
        output_file = os.path.join(output_dir, f"FWI_Difference_{region_normalized}_{date_str}_map.png")
        
        # Create map
        try:
            projection = create_projection_from_config(projection_config)
            create_difference_map(diff_data, lat, lon, date_str, output_file,
                                ontario_bounds=region_bounds, init_date=init_date,
                                provinces=provinces, projection=projection)
            print(f"  ✓ {date_str}")
        except Exception as e:
            print(f"  ✗ {date_str}: {e}")
    
    print()
    print(f"Difference maps saved to: {output_dir}")


def main():
    """Main function to handle CLI arguments and generate difference maps."""
    parser = argparse.ArgumentParser(
        description='Generate FWI difference maps (CanESM5 - GEM5.2-NEMO) from CFS Seasonal Forecast ensembles',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='Examples:\n'
               '  python generate_difference_maps.py                  # Use default region (Canada-wide)\n'
               '  python generate_difference_maps.py --region ontario # Generate for Ontario\n'
               '  python generate_difference_maps.py --list-regions   # Show available regions'
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
        default='output/difference',
        help='Directory to save output maps (default: output/difference)'
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
        generate_difference_maps(
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
