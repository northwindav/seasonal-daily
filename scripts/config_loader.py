# Configuration loader for FWI map generation regions.
#Loads region definitions from regions.yaml and provides functions to
#retrieve and validate regional configurations.

import os
import yaml

# Pull regional definitions from the YAML config file. 
def load_regions_config(config_file='config/regions.yaml'):

    # Support both relative paths from project root and absolute paths
    if not os.path.isabs(config_file):
        # Try relative to project root
        config_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), config_file)
    
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Config file not found: {config_file}")
    
    with open(config_file, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    if not config or 'regions' not in config:
        raise ValueError("Invalid config: 'regions' key not found in YAML")
    
    return config

# Get the config for the specific region requested.
# If none, returns the default region (marked with 'default: true' in YAML).
def get_region_config(region_name=None, config_file='config/regions.yaml'):

    config = load_regions_config(config_file)
    regions = config['regions']
    
    # If no region specified, find default
    if region_name is None:
        for name, cfg in regions.items():
            if cfg.get('default', False):
                return cfg, name
        # If no default marked, raise error
        raise ValueError("No region specified and no default region defined in config")
    
    # Look up requested region (case-insensitive)
    region_lower = region_name.lower()
    if region_lower not in regions:
        available = ', '.join(regions.keys())
        raise ValueError(f"Region '{region_name}' not found. Available regions: {available}")
    
    return regions[region_lower], region_lower

# Helper function: Lists regions if user is unsure. Or just look at the YAML file.
def list_regions(config_file='config/regions.yaml'):

    config = load_regions_config(config_file)
    regions = config['regions']
    
    region_list = []
    for name, cfg in regions.items():
        description = cfg.get('description', 'No description')
        is_default = cfg.get('default', False)
        region_list.append((name, description, is_default))
    
    return region_list

# Check that all required parameters for the region are present and valid.
def validate_region_bounds(bounds):

    required_keys = ['lat_min', 'lat_max', 'lon_min', 'lon_max']
    
    for key in required_keys:
        if key not in bounds:
            raise ValueError(f"Missing required bound: {key}")
    
    lat_min, lat_max = bounds['lat_min'], bounds['lat_max']
    lon_min, lon_max = bounds['lon_min'], bounds['lon_max']
    
    # Validate latitude
    if not (-90 <= lat_min <= 90 and -90 <= lat_max <= 90):
        raise ValueError(f"Invalid latitude bounds: {lat_min} to {lat_max}")
    
    if lat_min >= lat_max:
        raise ValueError(f"Invalid latitude: lat_min ({lat_min}) >= lat_max ({lat_max})")
    
    # Validate longitude (allow -180 to 360 range for flexibility)
    if not (-180 <= lon_min <= 360 and -180 <= lon_max <= 360):
        raise ValueError(f"Invalid longitude bounds: {lon_min} to {lon_max}")
    
    return True

# Determine the bounds. This isn't straightforward given the projection requirement,
# and may require a little bit of playing around in the YAML definitions to get right. But this is the general idea.
def get_bounds_dict(region_config):
  
    bounds = region_config['bounds']
    validate_region_bounds(bounds)
    
    return {
        'lat_min': bounds['lat_min'],
        'lat_max': bounds['lat_max'],
        'lon_min': bounds['lon_min'],
        'lon_max': bounds['lon_max'],
    }

# Get the projection from YAML
def get_projection_from_region(region_config):

    if 'projection' in region_config:
        return region_config['projection']
    return None


if __name__ == '__main__':
    # Test: list all available regions
    try:
        regions = list_regions()
        print("Available regions:")
        for name, desc, is_default in regions:
            default_marker = " [DEFAULT]" if is_default else ""
            print(f"  {name}: {desc}{default_marker}")
    except Exception as e:
        print(f"Error: {e}")
