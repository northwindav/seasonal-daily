# Shared utility functions for FWI map generation scripts.
# Consolidates common functions used across all mapping scripts

import re
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
import geopandas as gpd

# Get the init date from the filename. Everything breaks if the filenames don't contain this
def parse_init_date_from_filename(filename):

    match = re.search(r'_init(\d{10})', filename)
    if match:
        date_str = match.group(1)
        return datetime.strptime(date_str, '%Y%m%d%H')
    return None

# Create the color map to be used across all maps. 
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

# Colormap for difference maps
def create_difference_colormap():

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

# Color map for stddev maps
def create_stddev_colormap():

    colors = [
        (0.0, '#ffffff'),      # White at stddev 0
        (0.25, '#ffffcc'),     # Light yellow at stddev 5
        (0.5, '#ff9933'),      # Orange at stddev 10
        (1.0, '#cc0000'),      # Red at stddev 20
    ]
    
    n_bins = 256
    cmap = LinearSegmentedColormap.from_list('fwi_stddev', colors, N=n_bins)
    return cmap

# Create a caropy projection based on arguments contain for the region in the YAML file. 
# Limited options for now, and will likely need to be expanded. 
def create_projection_from_config(projection_config):

    try:
        import cartopy.crs as ccrs
    except ImportError:
        print("Warning: cartopy not available, using PlateCarree projection")
        import cartopy.crs as ccrs
        return ccrs.PlateCarree()
    
    if projection_config is None:
        return ccrs.PlateCarree()
    
    proj_type = projection_config.get('type', 'PlateCarree')
    
    if proj_type == 'LambertConformal':
        central_lat = projection_config.get('central_latitude', 0)
        central_lon = projection_config.get('central_longitude', 0)
        std_parallels = projection_config.get('standard_parallels', [30, 60])
        return ccrs.LambertConformal(
            central_latitude=central_lat,
            central_longitude=central_lon,
            standard_parallels=std_parallels
        )
    elif proj_type == 'Mercator':
        return ccrs.Mercator()
    elif proj_type == 'Stereographic':
        central_lat = projection_config.get('central_latitude', 70)
        central_lon = projection_config.get('central_longitude', -95)
        return ccrs.Stereographic(
            central_latitude=central_lat,
            central_longitude=central_lon
        )
    else:
        print(f"Unknown projection type: {proj_type}, using PlateCarree")
        return ccrs.PlateCarree()

# Get provincial boundaries based on the provinces specified for the region, in the YAML file
def load_provincial_boundaries(province_names=None):

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
            # Load specified provinces with flexible name matching
            for prov_name in province_names:
                prov_data = canada[canada['name'] == prov_name]
                
                if len(prov_data) == 0:
                    # Try alternate spellings/variations. Accent is required for PQ
                    if prov_name in ['Québec', 'Quebec']:
                        # Try both Quebec and Québec
                        for alt_name in ['Québec', 'Quebec']:
                            prov_data = canada[canada['name'] == alt_name]
                            if len(prov_data) > 0:
                                break
                    elif prov_name == 'Newfoundland and Labrador':
                        # Try alternate spellings for Newfoundland
                        for alt_name in ['Newfoundland and Labrador', 'Newfoundland & Labrador', 'Newfoundland', 'Labrador']:
                            prov_data = canada[canada['name'] == alt_name]
                            if len(prov_data) > 0:
                                break
                
                if len(prov_data) > 0:
                    # Store using the original requested name for consistency
                    provinces[prov_name] = prov_data
        
        return provinces
    except Exception as e:
        print(f"Warning: Could not load provincial boundaries: {e}")
        return {}


def setup_map_axes(lat, lon, projection=None):

    import matplotlib.pyplot as plt
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
    
    if projection is None:
        projection = ccrs.PlateCarree()
    
    fig = plt.figure(figsize=(14, 10))
    ax = plt.axes(projection=projection)
    
    # Set extent
    ax.set_extent([lon.min(), lon.max(), lat.min(), lat.max()], crs=ccrs.PlateCarree())
    
    # Add geographic features
    ax.add_feature(cfeature.COASTLINE, linewidth=0.5)
    ax.add_feature(cfeature.BORDERS, linewidth=0.5)
    ax.add_feature(cfeature.LAKES, alpha=0.3)
    ax.add_feature(cfeature.RIVERS, linewidth=0.3)
    ax.gridlines(draw_labels=True, alpha=0.3)
    
    return fig, ax


def draw_province_boundaries(ax, provinces):
 
    import cartopy.crs as ccrs
    
    if not provinces or len(provinces) == 0:
        return
    
    # Define colors and styles for each province/territory
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
        'Nova Scotia': {'color': 'salmon', 'linestyle': '--', 'linewidth': 1.5},
        'Prince Edward Island': {'color': 'lightsalmon', 'linestyle': '--', 'linewidth': 1.5},
        'Yukon': {'color': 'gray', 'linestyle': ':', 'linewidth': 1},
        'Northwest Territories': {'color': 'darkgray', 'linestyle': ':', 'linewidth': 1},
        'Nunavut': {'color': 'silver', 'linestyle': ':', 'linewidth': 1},
    }
    
    # Draw each province
    for prov_name, prov_gdf in provinces.items():
        style = province_styles.get(prov_name, {'color': 'black', 'linestyle': '--', 'linewidth': 1})
        
        for idx, row in prov_gdf.iterrows():
            ax.add_geometries([row.geometry], crs=ccrs.PlateCarree(),
                             facecolor='none', edgecolor=style['color'],
                             linewidth=style['linewidth'], linestyle=style['linestyle'],
                             label=prov_name if idx == 0 else '')
    
    ax.legend(loc='upper left', fontsize=9)


def configure_colorbar(im, ax, label, ticks):
    
    import matplotlib.pyplot as plt
    
    cbar = plt.colorbar(im, ax=ax, orientation='vertical', pad=0.02, shrink=0.8)
    cbar.set_label(label, rotation=270, labelpad=20)
    cbar.set_ticks(ticks)
    return cbar

# Footer contains the warning about unverified products, and the timestamp of when the map was generated.
def add_map_footer(fig, init_date=None, model_name=None, custom_message='', separator='  |  '):
  
    from datetime import datetime
    import matplotlib.pyplot as plt
    
    # Generate UTC timestamp
    now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    
    # Build footer
    footer_lines = []
    
    if init_date:
        footer_lines.append(f'Init: {init_date.strftime("%Y-%m-%d %H:00 UTC")}')
    
    footer_lines.append(f'Generated: {now_str}')
    
    if custom_message:
        footer_lines.append(custom_message)
    
    # Add caution message
    footer_lines.append('CAUTION: These products are unverified and should not be used without full knowledge of the seasonal forecast products, including expert interpretation.')
    
    footer_text = separator.join(footer_lines)
    fig.text(0.5, 0.01, footer_text, ha='center', fontsize=7, style='italic', wrap=True)
    plt.tight_layout(rect=[0, 0.03, 1, 1])


# Handles some edge cases including wrapping, use of negative longitudes...
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

# Hard-coded 3 month maximum. We really, really don't recommend using anything further out.
def get_3month_window(init_date):

    start_date = init_date
    end_date = init_date + timedelta(days=91)  # ~3 months
    return start_date, end_date


def convert_time_to_datetime(time_coords):
    
    return [pd.Timestamp(t).to_pydatetime() for t in time_coords]


def save_and_close_map(fig, filename):
    
    import os
    import matplotlib.pyplot as plt
    
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    fig.savefig(filename, dpi=100, bbox_inches='tight')
    plt.close(fig)
    return filename

# Plotting and transformation happens here
# Args:
# ax: map axes to plot on
# lon, lat: longitude and latitude arrays
# data: 2D array of FWI values to plot
# cmap: colormap to use for plotting
# norm: normalization for the colormap (e.g., mcolors.Normalize)
# levels: optional contour levels to use for contourf
# transform: cartopy transform for the data (defaults to PlateCarree if None)
def plot_contourf_data(ax, lon, lat, data, cmap, norm, levels=None, transform=None):
  
    import cartopy.crs as ccrs
    
    if transform is None:
        transform = ccrs.PlateCarree()
    
    if levels is None:
        levels = np.linspace(data.min(), data.max(), 21)
    
    return ax.contourf(lon, lat, data, levels=levels, cmap=cmap, norm=norm, transform=transform)

