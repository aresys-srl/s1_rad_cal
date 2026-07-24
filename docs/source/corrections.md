---
icon: lucide/list-checks
tags:
    - radiometric corrections
    - radiometric re-calibration
---

# Radiometric Corrections

## Absolute Calibration Constant

The absolute calibration constant is a scaling factor used in Level-1 to convert raw pixel intensity values (Digital Numbers, DN) directly into normalized radar backscatter.
Absolute calibration constant annotated in the product metadata is based on calibration activities conducted by the SAR-MPC.
Up to date calibration constant for Sentinel-1 satellites is reported in the AUX_CAL files available on the [SAR-MPC website](https://sar-mpc.eu/adf/aux_cal/).
These AUX_CAL files represent some of the needed input of this tool.

## Processing gain
The processing gain \(g_{proc}\) in the Sentinel-1 SAR-MPC AUX_PP1 auxiliary file represents a mode- and polarization-dependent scaling factor applied during Level-1 processor data generation. It is critical for accurate absolute radiometric calibration and re-compensation procedures.
These specific \(g_{proc}\) gain values are regularly updated in auxiliary files but are not explicitly saved inside individual Level-1 product annotations, requiring extraction from AUX_PP1 history for precise radiometric re-analysis. This software is able to automatically detect which gain value was applied for each product, and correct for the new gain value read from the new AUX_PP1 passed as input by the user.

## Elevation Antenna Pattern

inserisci immagine con differenza elevation antenna pattern

puoi anche dividere per sezioni queste 3 cose