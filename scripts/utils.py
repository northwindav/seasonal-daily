"""
Shared utility functions for FWI map generation scripts.

This module consolidates common functions used across daily, difference, and weekly
map generation scripts to maintain a single source of truth and reduce code duplication.
"""

import re
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
import geopandas as gpd


def parse_init_date_from_filename(filename):
    """
    Extract model initialization date from filename pattern.
    
    Expected pattern: *_init<YYYYMMDDHH>.nc
    
    Args:
        filename (str): NetCDF filename
        
    Returns:
        datetime: Initialization datetime, or None if pattern not found
    """
    match = re.search(r'_init(\d{10})', filename)
    if match:
        date_str = match.group(1)
        return datetime.strptime(date_str, '%Y%m%d%H')
    return None


def create_fwi_colormap():
    """
    Create a custom colormap for FWI values (0 to 50 scale).
    
    Color progression:
    - Blue at FWI 0
    - Green around FWI 12.5
    - Yellow at FWI 15 (explicit threshold for caution level)
    - Orange around FWI 30
    - Purple at FWI 50
    
    Returns:
        LinearSegmentedColormap: Custom FWI colormap
    """
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


def create_difference_colormap():
    """
    Create a custom colormap for FWI difference values (±20 scale).
    
    Color progression for CanESM5 - GEM5.2-NEMO differences:
    - Purple at -20 (GEM5 higher than CanESM5)
    - Blue at -10
    - White at 0 (no difference)
    - Yellow at +10
    - Red at +20 (CanESM5 higher than GEM5)
    
    Returns:
        LinearSegmentedColormap: Custom difference colormap
    """
    colors = [
        (0.0, '#8B008B'),      # Purple at -20
        (0.25, '#1f77b4'),     # Blue at -10
        (0.5, '#ffffff'),      # White at 0
        (0.75, '#ffff00'),     # Yellow at +10
        (1.0, '#d62728'),      # Red at +20
    ]
    
    n_bins = 256
    cmap = LinearSegmentedColormap.from_list('fwi_difference', colors, N=n_bins)
    return cmap


def create_stddev_colormap():
    """
    Create a custom colormap for ensemble standard deviation values (0 to 20 scale).
    
    Represents ensemble member disagreement/uncertainty:
    - White at 0 (high confidence, members agree)
    - Light yellow at 5
    - Orange at 10 (moderate uncertainty)
    - Red at 20 (high uncertainty, members disagree widely)
    
    Returns:
        LinearSegmentedColormap: Custom standard deviation colormap
    """
    colors = [
        (0.0, '#ffffff'),      # White at stddev 0
        (0.25, '#ffffcc'),     # Light yellow at stddev 5
        (0.5, '#ff9933'),      # Orange at stddev 10
        (1.0, '#cc0000'),      # Red at stddev 20
    ]
    
    n_bins = 256
    cmap = LinearSegmentedColormap.from_list('fwi_stddev', colors, N=n_bins)
    return cmap


def load_provincial_boundaries(province_names=None):
    """
    Load provincial/territorial boundaries from Natural Earth data.
    
    Downloads and caches Natural Earth 10m admin1 boundaries. Can be filtered
    to specific provinces/territories.
    
    Args:
        province_names (list, optional): List of province names to load.
            If None, defaults to ['Ontario', 'Manitoba', 'Québec'].
            Use '*' to load all Canadian provinces/territories.
            
    Returns:
        dict: GeoDataFrames keyed by province name, or empty dict if load fails
    """
    if province_names is None:
        province_names = ['Ontario', 'Manitoba', 'Québec']
    
    try:
        ne_url = "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_1_states_provinces.zip"
        admin1 = gpd.read_file(ne_url)
        
        canada = admin1[admin1['admin'] == 'Canada']
        
        provinces = {}
        
        # Special handling for '*' to load all Canadian provinces
        if province_names == ['*']:
            for idx, row in canada.iterrows():
                prov_name = row['name']
                if prov_name not in provinces:
                    provinces[prov_name] = gpd.GeoDataFrame([row], crs='EPSG:4326')
        else:
            # Load specified provinces
            for prov_name in province_names:
                prov_data = canada[canada['name'] == prov_name]
                if len(prov_data) > 0:
                    provinces[prov_name] = prov_data
                else:
                    # Try alternate spelling for Québec
                    if prov_name == 'Québec':
                        prov_data = canada[canada['name'] == 'Quebec']
                        if len(prov_data) > 0:
                            provinces[prov_name] = prov_data
        
        return provinces
    except Exception as e:
        print(f"Warning: Could not load provincial boundaries: {e}")
        return {}


def crop_to_region(ds, bounds):
    """
    Crop xarray dataset to specified lat/lon bounds.
    
    Handles both -180 to 180 and 0 to 360 longitude conventions.
    Properly handles wrapping at dateline.
    
    Args:
        ds (xarray.Dataset): Input dataset with 'lat' and 'lon' dimensions
        bounds (dict): Bounding box with keys: 'lat_min', 'lat_max', 'lon_min', 'lon_max'
        
    Returns:
        xarray.Dataset: Cropped dataset
    """
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


def get_3month_window(init_date):
    """
    Get the 3-month forecast window from initialization date.
    
    Limited to 3 months because:
    - Sub-monthly visualization of seasonal forecasts is unvalidated
    - Seasonal products only share month 1-3 publicly
    - Low confidence in later forecast times
    
    Args:
        init_date (datetime): Model initialization date
        
    Returns:
        tuple: (start_date, end_date) as datetime objects
    """
    start_date = init_date
    end_date = init_date + timedelta(days=91)  # ~3 months
    return start_date, end_date


def convert_time_to_datetime(time_coords):
    """
    Convert xarray time coordinates to Python datetime objects.
    
    Handles numpy datetime64 objects that xarray uses internally.
    
    Args:
        time_coords (numpy.ndarray): xarray time coordinate array
        
    Returns:
        list: List of Python datetime objects
    """
    return [pd.Timestamp(t).to_pydatetime() for t in time_coords]
