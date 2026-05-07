# Seasonal Forecast Daily Products

## Intent
_This code was generated with the help of AI coding assistants. All code has been reviewed by a human_

This package takes as input NetCDF files (.nc) generated as part of the CFS Seasonal forecast v2. The intent is to provide day or week scale outputs in support of long term probabilistic projections as requested by Canadian agencies.

In its present form, the outputs are centred on Ontario with a small buffer. This can be modified relatively easily in the plotting scripts.

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
python scripts/generate_daily_maps.py
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
python scripts/generate_difference_maps.py
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
python scripts/generate_weekly_averaged_maps.py
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

### Complete Map Suite

| Product | Count | Scale | Time Coverage |
|---------|-------|-------|----------------|
| CanESM5 daily FWI | 92 | 0-50 | May 1 - Jul 31, 2026 |
| GEM5.2-NEMO daily FWI | 92 | 0-50 | May 1 - Jul 31, 2026 |
| Difference (CanESM5 - GEM5) | 92 | ±20 | May 1 - Jul 31, 2026 |
| CanESM5 weekly average | 13 | 0-50 | 13-week periods |
| GEM5.2-NEMO weekly average | 13 | 0-50 | 13-week periods |
| **Total Maps** | **302** | — | — |

## Important Notes

### Validation Status
**CAUTION:** These products are **unverified** and should not be used without:
- Full knowledge of seasonal forecast characteristics and limitations
- Expert interpretation by qualified meteorologists
- Understanding of model initialization and ensemble nature

### Spatial Domain
- **Primary region:** Ontario + 150 km buffer
- **Reference boundaries:** Manitoba and Quebec shown for context
- **Coordinate system:** WGS84 (EPSG:4326)
- **Data resolution:** ~0.8° × 0.8° (cropped to 24×18 grid over Ontario region)

### Temporal Information
- **Initialization date:** Extracted from filename pattern `_init<YYYYMMDDHH>`
- **Forecast period:** 3 months from initialization (May 1 - July 31, 2026)
- **Ensemble:** 20 members per model, displayed as ensemble mean
- **Time step:** Daily in source data, aggregated to weekly windows

### File Naming Conventions
- **Daily maps:** `{MODEL}_{YYYY-MM-DD}_FWI_map.png`
  - Example: `CanESM5.1p1bc_2026-05-01_FWI_map.png`
- **Difference maps:** `FWI_Difference_{YYYY-MM-DD}_map.png`
  - Example: `FWI_Difference_2026-05-01_map.png`
- **Weekly maps:** `{MODEL}_{YYYY-MM-DD}_to_{YYYY-MM-DD}_FWI_week.png`
  - Example: `CanESM5.1p1bc_2026-05-01_to_2026-05-08_FWI_week.png`

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

