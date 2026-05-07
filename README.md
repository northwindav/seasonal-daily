# Seasonal Forecast Daily Products

## Intent
_This code was generated with the help of AI coding assistants. All code has been reviewed by a human_

This package takes as input NetCDF files (.nc) generated as part of the CFS Seasonal forecast v2. The intent is to provide day or week scale outputs in support of long term probabilistic projections as requested by Canadian agencies.

These products are useful for better understanding the monthly seasonal outputs, including differences between model means, and standard deviations between model members. It is not intended, nor should it be used, to provide any kind of forecast for a given day or week.

_Display of outputs at the sub-monthly scale has not been validated and therefore any products generated must be used with extreme caution, and must be provided to agencies with expert interpretation and some version of this caveat._

_Furthermore, monthly outputs are only shared publicly up to month 3, with both lack of validation and low confidence making use of later forecast times unadvisable._

## Input

Two input files form the basis of this package, though it may be expanded in the future.
1. **CanESM5.1p1bc_FWI_<YYYYMMDD_start>-<YYYYMMDD_end>_init<YYYYMMDDHH_init>.nc**
2. **GEM5.2-NEMO_FWI_<YYYYMMDD_start>_<YYYYMMDD_end>_init<YYYYMMDD_init>.nc**

These files contain daily projections from each of 20 ensemble members per model, of the Fire Weather Index for Canada and some adjoining regions. While the contents extend out for 7 months, the strong recommendation from developers is to avoid using any outputs beyond 3 months. The use of a daily or weekly temporal scale also violates the intent of the seasonal forecast, and as such is a completely untested and unvalidated product that should be used with extreme caution, if at all.

## Outputs

The current version of the package is mostly exploratory in nature, and will simply seek to visualize outputs over a given spatial domain at daily or weekly time scales. Maps are static, with simple legends.

## Usage

### Environment Setup

#### 1. Create Virtual Environment
```bash
python -m venv .venv
```

#### 2. Activate Virtual Environment

**Windows (PowerShell):**
```bash
.venv\Scripts\Activate.ps1
```

**Windows (Command Prompt):**
```bash
.venv\Scripts\activate.bat
```

**macOS/Linux:**
```bash
source .venv/bin/activate
```

#### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### Scripts

#### 1. explore_netcdf.py
Verify data structure, dimensions, variables, and temporal/spatial coverage before processing.

**Usage:**
```bash
python scripts/explore_netcdf.py
```

**Output:** `output/netcdf_contents.txt` - detailed exploration report

#### 2. generate_daily_maps.py
Generates daily FWI maps for both forecast models over the 3-month forecast window.

**Usage:**
```bash
# Generate maps for default region (Canada-wide)
python scripts/generate_daily_maps.py

# Generate maps for specific region
python scripts/generate_daily_maps.py --region ontario

# Generate single date for specific region
python scripts/generate_daily_maps.py --region quebec --date 2026-05-06

# List available regions
python scripts/generate_daily_maps.py --list-regions
```

**Output:**
- 92 daily maps for CanESM5.1p1bc
- 92 daily maps for GEM5.2-NEMO
- Total: 184 daily FWI maps

**Output Location:** `output/daily/`

**Map Features:**
- Fixed FWI scale: 0-50
- Custom color gradient: blue → green → yellow (at FWI≥15) → orange → purple
- Provincial boundaries: Ontario (solid blue), Manitoba (dashed green), Quebec (dashed purple)
- Metadata footer: initialization date, generation timestamp, caution disclaimer
- Resolution: 100 DPI

#### 3. generate_difference_maps.py
Generates comparative maps showing model disagreement (CanESM5 - GEM5.2-NEMO FWI differences).

**Usage:**
```bash
# Generate difference maps for default region (Canada-wide)
python scripts/generate_difference_maps.py

# Generate difference maps for specific region
python scripts/generate_difference_maps.py --region ontario

# Generate single date for specific region
python scripts/generate_difference_maps.py --region british_columbia --date 2026-05-06
```

**Output:**
- 92 difference maps (one per day)

**Output Location:** `output/difference/`

**Map Features:**
- Fixed FWI difference scale: ±20
- Custom color gradient: purple (−20) → blue (−10) → white (0) → yellow (+10) → red (+20)
- Provincial boundaries: Ontario (solid blue), Manitoba (dashed green), Quebec (dashed purple)
- Metadata footer: initialization date, generation timestamp, caution disclaimer
- Resolution: 100 DPI

#### 4. generate_weekly_averaged_maps.py
Generates weekly averaged FWI maps using 7-day fixed windows.

**Usage:**
```bash
# Generate weekly maps for default region (Canada-wide)
python scripts/generate_weekly_averaged_maps.py

# Generate weekly maps for specific region
python scripts/generate_weekly_averaged_maps.py --region atlantic

# List available regions
python scripts/generate_weekly_averaged_maps.py --list-regions
```

**Output:**
- 13 weekly maps for CanESM5.1p1bc
- 13 weekly maps for GEM5.2-NEMO
- Total: 26 weekly averaged FWI maps

**Output Location:** `output/weekly/`

**Map Features:**
- Fixed FWI scale: 0-50 (same as daily maps)
- Custom color gradient: blue → green → yellow (at FWI≥15) → orange → purple
- Provincial boundaries: Ontario (solid blue), Manitoba (dashed green), Quebec (dashed purple)
- Title shows date range: "1-week average from YYYY-MM-DD to YYYY-MM-DD"
- Metadata footer: initialization date, generation timestamp, caution disclaimer
- Resolution: 100 DPI

#### 5. generate_stddev_maps.py
Generates daily maps showing ensemble standard deviation (forecast uncertainty).

**Usage:**
```bash
# Generate standard deviation maps for default region (Canada-wide)
python scripts/generate_stddev_maps.py

# Generate standard deviation maps for specific region
python scripts/generate_stddev_maps.py --region prairies

# Generate single date for specific region
python scripts/generate_stddev_maps.py --region northern_canada --date 2026-05-15
```

**Output:**
- 92 standard deviation maps for CanESM5.1p1bc
- 92 standard deviation maps for GEM5.2-NEMO
- Total: 184 daily ensemble standard deviation maps

**Output Location:** `output/stddev/`

**Map Features:**
- Fixed std dev scale: 0-20 FWI units
- Custom color gradient: white → yellow → orange → red (increasing uncertainty)
- Provincial boundaries: Ontario (solid blue), Manitoba (dashed green), Quebec (dashed purple)
- Shows spatial patterns of ensemble spread (higher values = greater model agreement uncertainty)
- Metadata footer: initialization date, generation timestamp, caution disclaimer
- Resolution: 100 DPI

**Interpretation:**
Higher standard deviation values indicate regions where ensemble members disagree more, representing greater forecast uncertainty. Lower values indicate higher ensemble agreement and potentially more confident forecasts.

### Complete Map Suite

| Product | Count | Scale | Time Coverage |
|---------|-------|-------|----------------|
| CanESM5 daily FWI | 92 | 0-50 | 3 months from init date |
| GEM5.2-NEMO daily FWI | 92 | 0-50 | 3 months from init date |
| Difference (CanESM5 - GEM5) | 92 | ±20 | 3 months from init date |
| CanESM5 standard deviation | 92 | 0-20 | 3 months from init date |
| GEM5.2-NEMO standard deviation | 92 | 0-20 | 3 months from init date |
| CanESM5 weekly average | 13 | 0-50 | 1-week periods, out to 3 months from init |
| GEM5.2-NEMO weekly average | 13 | 0-50 | 1-week periods, out to 3 months from init |
| **Total Maps** | **486** | — | — |

## Important Notes

### Validation Status
**CAUTION:** These products are **unverified** and should not be used without:
- Full knowledge of seasonal forecast characteristics and limitations
- Expert interpretation by qualified meteorologists
- Understanding of model initialization and ensemble nature

### Spatial Domain
- **Configurable regions:** 7 geographic regions defined in `config/regions.yaml`
- **Default region:** Canada-wide (national scope)
- **Reference boundaries:** All specified provinces shown for context; adjoining provinces included for geographic reference
- **Coordinate system:** WGS84 (EPSG:4326)
- **Data resolution:** ~0.8° × 0.8° (cropped to region-specific grid)

### Temporal Information
- **Initialization date:** Extracted from filename pattern `_init<YYYYMMDDHH>`
- **Forecast period:** 3 months from initialization (May 1 - July 31, 2026)
- **Ensemble:** 20 members per model
  - Daily/weekly FWI maps: displayed as ensemble mean
  - Standard deviation maps: displayed as ensemble spread (standard deviation across 20 members)
- **Time step:** Daily in source data, aggregated to weekly windows

### File Naming Conventions
- **Daily maps:** `{MODEL}_{REGION}_{YYYY-MM-DD}_FWI_map.png`
  - Example: `CanESM5.1p1bc_ontario_2026-05-01_FWI_map.png`
- **Difference maps:** `FWI_Difference_{REGION}_{YYYY-MM-DD}_map.png`
  - Example: `FWI_Difference_quebec_2026-05-01_map.png`
- **Standard deviation maps:** `{MODEL}_{REGION}_{YYYY-MM-DD}_STDDEV_map.png`
  - Example: `CanESM5.1p1bc_prairies_2026-05-01_STDDEV_map.png`
- **Weekly maps:** `{MODEL}_{REGION}_{YYYY-MM-DD}_to_{YYYY-MM-DD}_FWI_week.png`
  - Example: `CanESM5.1p1bc_atlantic_2026-05-01_to_2026-05-08_FWI_week.png`

*Note:* Region names are included in filenames (spaces replaced with underscores) for easy organization and identification of geographic coverage. Use `--list-regions` to see available region names.

## Regional Configuration

This system supports multiple geographic regions defined in `config/regions.yaml`. Each region has customized:
- **Spatial bounds** - Latitude/longitude bounding box
- **Provincial boundaries** - Which provinces to display on maps
- **Map projection** - Region-optimized cartographic projection

### Available Regions

| Region | Description | Area | Default |
|--------|-------------|------|---------|
| **ontario** | Ontario + buffer | Southern Ontario | ✗ |
| **quebec** | Quebec + surrounding provinces | Eastern Quebec | ✗ |
| **british_columbia** | BC and adjoining regions | Western Canada | ✗ |
| **northern_canada** | Yukon and Northwest Territories | Arctic regions | ✗ |
| **canada** | Canada-wide national scope | Full Canada | ✓ |
| **prairies** | Manitoba, Saskatchewan, Alberta | Central Canada | ✗ |
| **atlantic** | Nova Scotia, NB, PEI, NL | Atlantic Canada | ✗ |

### Map Projections

Each region uses a region-optimized map projection for improved geographic visualization:

| Region | Projection | Central Lat | Central Lon | Std. Parallels |
|--------|-----------|-------------|------------|----------------|
| ontario | Lambert Conformal Conic | 49.0°N | 85.0°W | 45°N, 55°N |
| quebec | Lambert Conformal Conic | 52.0°N | 68.0°W | 48°N, 56°N |
| british_columbia | Lambert Conformal Conic | 55.0°N | 127.0°W | 50°N, 60°N |
| northern_canada | Lambert Conformal Conic | 65.0°N | 120.0°W | 60°N, 70°N |
| canada | Lambert Conformal Conic | 62.0°N | 95.0°W | 50°N, 70°N |
| prairies | Lambert Conformal Conic | 55.0°N | 105.0°W | 50°N, 60°N |
| atlantic | Lambert Conformal Conic | 45.5°N | 59.5°W | 43°N, 48°N |

All projections use Lambert Conformal Conic, which is ideal for mid-latitude regions and preserves shape/angle better than simpler projections. Parameters (central latitude/longitude and standard parallels) are customized per region for optimal distortion characteristics.

### Using Regional Configuration

**Specify region explicitly:**
```bash
python scripts/generate_daily_maps.py --region atlantic --date 2026-05-06
```

**Use default region (Canada-wide):**
```bash
python scripts/generate_daily_maps.py
```

**List all available regions:**
```bash
python scripts/generate_daily_maps.py --list-regions
```

The region configuration file is located at `config/regions.yaml`. Regions can be customized by editing this file with new geographic bounds, provinces, or projection parameters.

## Dependencies

All required packages are listed in `requirements.txt`:
- **Data handling:** netCDF4, xarray, numpy, pandas
- **Geospatial:** geopandas, shapely, cartopy
- **Visualization:** matplotlib

Install all with:
```bash
pip install -r requirements.txt
```

## Troubleshooting

### Maps not generating
1. Verify input files exist in `input/` directory
2. Check file naming follows expected pattern with `_init<YYYYMMDDHH>`
3. Run `python scripts/explore_netcdf.py` to verify file structure
4. Ensure Python dependencies installed: `pip install -r requirements.txt`

### Provincial boundaries not appearing
- The scripts automatically download Natural Earth data on first run
- Requires internet connection for initial download
- Natural Earth data cached after first successful load

