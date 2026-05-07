# Generate weekly FWI maps based on average outputs from the 2 CFS Seasonal Forecast v2 ensembles
# Weekly outputs are for fixed 7-day periods, and are not a rolling average.
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
from matplotlib.colors import LinearSegmentedColormap
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
    create_projection_from_config,
)
from config_loader import get_region_config, get_bounds_dict, get_projection_from_region, list_regions

warnings.filterwarnings('ignore')


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


def generate_weekly_maps(input_dir='input', output_dir='output/weekly', region_bounds=None, province_names=None, buffer_km=150, region_name=None, projection_config=None, target_date=None):

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
        ds_cropped = crop_to_region(ds, region_bounds)
        
        # Extract arrays
        lat = ds_cropped['lat'].values
        lon = ds_cropped['lon'].values
        time = ds_cropped['time'].values
        fwi = ds_cropped['FWI'].values  # Shape: (time, member, lat, lon)
        
        # Convert time to datetime objects
        date_objs = convert_time_to_datetime(time)
        
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
                region_normalized = region_name.replace(' ', '_') if region_name else 'default'
                output_file = os.path.join(output_dir, f"{model_name}_{region_normalized}_{date_label_start}_to_{date_label_end}_FWI_week.png")
                
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


def main():
    """Main function to handle CLI arguments and generate weekly maps."""
    parser = argparse.ArgumentParser(
        description='Generate weekly averaged FWI maps from CFS Seasonal Forecast ensembles',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='Examples:\n'
               '  python generate_weekly_averaged_maps.py                  # Use default region (Canada-wide)\n'
               '  python generate_weekly_averaged_maps.py --region ontario # Generate for Ontario\n'
               '  python generate_weekly_averaged_maps.py --list-regions   # Show available regions'
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
        default='output/weekly',
        help='Directory to save output maps (default: output/weekly)'
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
        generate_weekly_maps(
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
