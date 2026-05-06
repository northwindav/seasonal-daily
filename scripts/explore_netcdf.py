"""
Explore and analyze NetCDF file structure.

This script opens both input NetCDF files and provides detailed information about
their structure, variables, dimensions, temporal coverage, and spatial bounds.
"""

import os
import re
from datetime import datetime, timedelta
import xarray as xr
import numpy as np


def parse_init_date_from_filename(filename):
    """
    Extract init date from filename pattern: *_init<YYYYMMDDHH>.nc
    
    Returns:
        datetime: initialization date, or None if pattern not found
    """
    match = re.search(r'_init(\d{10})', filename)
    if match:
        date_str = match.group(1)
        return datetime.strptime(date_str, '%Y%m%d%H')
    return None


def explore_netcdf(filepath):
    """
    Open and explore a NetCDF file.
    
    Args:
        filepath (str): Path to the NetCDF file
        
    Returns:
        dict: Summary of file contents
    """
    try:
        ds = xr.open_dataset(filepath)
    except Exception as e:
        return {'error': str(e)}
    
    summary = {
        'file': os.path.basename(filepath),
        'success': True,
        'dimensions': dict(ds.sizes),
        'variables': list(ds.data_vars),
        'coordinates': list(ds.coords),
        'attributes': dict(ds.attrs),
    }
    
    # Temporal information
    if 'time' in ds.dims:
        time_var = ds['time']
        time_vals = time_var.values
        if len(time_vals) > 0:
            summary['time_count'] = len(time_vals)
            summary['time_start'] = str(time_vals[0])
            summary['time_end'] = str(time_vals[-1])
            # Try to infer time step
            if len(time_vals) > 1:
                time_step = np.diff(time_vals[:2])[0]
                summary['time_step_nanoseconds'] = int(time_step)
                # Convert to days (roughly)
                summary['time_step_days'] = time_step / (24 * 3600 * 1e9)
    
    # Spatial information
    lat_candidates = [c for c in ds.coords if 'lat' in c.lower()]
    lon_candidates = [c for c in ds.coords if 'lon' in c.lower()]
    
    if lat_candidates and lon_candidates:
        lat_name = lat_candidates[0]
        lon_name = lon_candidates[0]
        lat_vals = ds[lat_name].values
        lon_vals = ds[lon_name].values
        
        summary['spatial_extent'] = {
            'lat_min': float(np.min(lat_vals)),
            'lat_max': float(np.max(lat_vals)),
            'lon_min': float(np.min(lon_vals)),
            'lon_max': float(np.max(lon_vals)),
            'lat_size': len(lat_vals),
            'lon_size': len(lon_vals),
        }
    
    # Check for FWI variable
    fwi_candidates = [v for v in ds.data_vars if 'fwi' in v.lower()]
    if fwi_candidates:
        fwi_var = fwi_candidates[0]
        summary['fwi_variable'] = fwi_var
        summary['fwi_shape'] = str(ds[fwi_var].shape)
        summary['fwi_dtype'] = str(ds[fwi_var].dtype)
        if 'units' in ds[fwi_var].attrs:
            summary['fwi_units'] = ds[fwi_var].attrs['units']
    
    ds.close()
    return summary


def main():
    """Main execution."""
    # Create output directory
    os.makedirs('output', exist_ok=True)
    output_file = 'output/netcdf_contents.txt'
    
    lines = []  # Collect output lines for both console and file
    
    def add_line(text=''):
        """Add a line to output (both console and file)."""
        lines.append(text)
        print(text)
    
    add_line("=" * 80)
    add_line("NetCDF File Exploration")
    add_line("=" * 80)
    
    input_dir = 'input'
    
    # Find all .nc files
    nc_files = [f for f in os.listdir(input_dir) if f.endswith('.nc')]
    
    if not nc_files:
        add_line("No .nc files found in input/ directory")
        return
    
    add_line(f"\nFound {len(nc_files)} NetCDF file(s)\n")
    
    all_summaries = []
    init_dates = []
    
    for filename in sorted(nc_files):
        filepath = os.path.join(input_dir, filename)
        add_line(f"Exploring: {filename}")
        add_line("-" * 80)
        
        # Parse init date
        init_date = parse_init_date_from_filename(filename)
        if init_date:
            add_line(f"Init date: {init_date.strftime('%Y-%m-%d %H:00 UTC')}")
            init_dates.append(init_date)
            # Calculate 3-month forecast window
            forecast_end = init_date + timedelta(days=91)  # ~3 months
            add_line(f"Forecast window (3 months): {init_date.strftime('%Y-%m-%d')} to {forecast_end.strftime('%Y-%m-%d')}")
        else:
            add_line("Init date: Could not parse from filename")
        add_line()
        
        # Explore the file
        summary = explore_netcdf(filepath)
        all_summaries.append(summary)
        
        if 'error' in summary:
            add_line(f"ERROR: {summary['error']}\n")
            continue
        
        add_line(f"Dimensions: {summary['dimensions']}")
        add_line(f"Variables: {', '.join(summary['variables'])}")
        add_line(f"Coordinates: {', '.join(summary['coordinates'])}\n")
        
        if 'time_count' in summary:
            add_line(f"Temporal coverage:")
            add_line(f"  Time steps: {summary['time_count']}")
            add_line(f"  Start: {summary['time_start']}")
            add_line(f"  End: {summary['time_end']}")
            time_step = summary.get('time_step_days', None)
            if time_step and isinstance(time_step, (int, float)):
                add_line(f"  Approx. step: {time_step:.1f} days\n")
            else:
                add_line(f"  Approx. step: {time_step}\n")
        
        if 'spatial_extent' in summary:
            extent = summary['spatial_extent']
            add_line(f"Spatial coverage:")
            add_line(f"  Latitude: {extent['lat_min']:.2f}° to {extent['lat_max']:.2f}° ({extent['lat_size']} points)")
            add_line(f"  Longitude: {extent['lon_min']:.2f}° to {extent['lon_max']:.2f}° ({extent['lon_size']} points)\n")
        
        if 'fwi_variable' in summary:
            add_line(f"FWI variable found:")
            add_line(f"  Name: {summary['fwi_variable']}")
            add_line(f"  Shape: {summary['fwi_shape']}")
            add_line(f"  Data type: {summary['fwi_dtype']}")
            if 'fwi_units' in summary:
                add_line(f"  Units: {summary['fwi_units']}")
        else:
            add_line(f"WARNING: No FWI variable found in this file")
        
        add_line()
    
    # Summary
    add_line("=" * 80)
    add_line("SUMMARY")
    add_line("=" * 80)
    add_line(f"\nTotal files explored: {len(all_summaries)}")
    add_line(f"Successful reads: {sum(1 for s in all_summaries if s.get('success'))}")
    
    if init_dates:
        add_line(f"\nCommon init date across files: {init_dates[0].strftime('%Y-%m-%d %H:00 UTC')}")
        add_line(f"Analysis window (3 months): {init_dates[0].strftime('%Y-%m-%d')} to {(init_dates[0] + timedelta(days=91)).strftime('%Y-%m-%d')}")
    
    # Check if both files have FWI
    fwi_count = sum(1 for s in all_summaries if 'fwi_variable' in s)
    add_line(f"\nFiles with FWI variable: {fwi_count}/{len(all_summaries)}")
    
    if fwi_count == len(all_summaries):
        add_line("✓ Both files contain FWI data. Ready to proceed with map generation.")
    else:
        add_line("⚠ Not all files contain FWI data. Check file contents before proceeding.")
    
    # Write to file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    add_line(f"\n\nReport saved to: {output_file}")


if __name__ == '__main__':
    main()
