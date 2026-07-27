---
icon: lucide/list-checks
tags:
    - radiometric corrections
    - radiometric re-calibration
---

# Radiometric Corrections

## Absolute Calibration Constant

The absolute calibration constant is a scaling factor used in the Sentinel-1 Level-1 processor to convert raw pixel intensity values (Digital Numbers, DN) into normalized radar backscatter values.

The calibration constants distributed with Sentinel-1 products are derived from calibration activities performed by the SAR Mission Performance Centre (SAR-MPC). Updated calibration constants are provided in the `AUX_CAL` auxiliary files available from the [SAR-MPC AUX_CAL repository](https://sar-mpc.eu/adf/aux_cal/).

The `AUX_CAL` files are required inputs for applying the updated absolute calibration correction.

## Processing gain
The processing gain is a mode- and polarization-dependent scaling factor applied during the Sentinel-1 Level-1 processing chain. It is required for accurate absolute radiometric calibration and radiometric reprocessing.

The processing gain values used during the generation of Level-1 products are not explicitly stored in the product annotations. Instead, they are recorded in the history information of the `AUX_PP1` auxiliary files.

This software automatically:

1. identifies the processing gain applied during the original Level-1 processing;
2. retrieves the updated processing gain value from a user-provided `AUX_PP1` dataset;
3. applies the required correction.

The software requires a local collection of `AUX_PP1` files to perform this automatic matching. A default dataset is included in: `data\AUX_PP1`. Users can also create their own dataset by downloading the required `AUX_PP1` files from the [SAR-MPC AUX_PP1 repository](https://sar-mpc.eu/adf/aux_pp1/).

The location of the `AUX_PP1` dataset must be provided through the `AUX_PP1_DATASET` environment variable:

```bash
export AUX_PP1_DATASET=/path/to/AUX_PP1/dataset  # linux
$env:AUX_PP1_DATASET = /path/to/AUX_PP1/dataset  # windows
```

!!! Warning
    All AUX_PP1 files must be extracted before running the software. Compressed archives are not supported directly.


## Elevation Antenna Pattern

The Sentinel-1 elevation antenna pattern (EAP) correction compensates for range-dependent variations in antenna gain.

The correction uses complex two-way antenna gain patterns provided in the `AUX_CAL` calibration files to restore accurate absolute radiometric measurements.

In addition to applying the updated EAP correction, this software accounts for terrain-induced variations in elevation angle using the [GETASSE30 Digital Elevation Model (DEM)](https://step.esa.int/main/wp-content/help/versions/9.0.0/snap/org.esa.snap.snap.help/desktop/GETASSE30ElevationModel.html).

The DEM is used to compute local elevation angles required for the EAP correction.

The location of the GETASSE30 DEM dataset must be provided through the `GETASSE_DEM_FOLDER` environment variable:

```bash
export GETASSE_DEM_FOLDER=/path/to/dem/folder  # linux
$env:GETASSE_DEM_FOLDER = /path/to/dem/folder  # windows
```

The DEM tiles must be downloaded separately and extracted before use. The software expects the raw binary tile files (e.g. `45N015E.GETASSE30`) to be available directly inside the folder specified by `GETASSE_DEM_FOLDER`. GETASSE30 tiles can be downloaded from the [ESA official archive](https://step.esa.int/auxdata/dem/GETASSE30/). 

!!! Warning
    Tiles are stored as compressed ZIP files and they need to be extracted before usage.