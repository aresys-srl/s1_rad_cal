---
icon: lucide/sparkles
title: "Overview"
tags:
    - radiometry
    - radiometric re-calibration
---

# Rad-Cal Tool

``rad-cal`` is the Aresys' radiometric re-calibration tool for Sentinel-1 L1 products.

# Corrections

This tool applies a set of radiometric corrections to Sentinel-1 Level-1 products in order to improve the consistency and accuracy of radar backscatter measurements. The supported corrections are:

- Absolute calibration constant correction
- Processing gain correction
- Elevation antenna pattern (EAP) correction

Each correction requires auxiliary information provided by Sentinel-1 calibration products. Refer to the [radiometric corrections](features\corrections.md) for further information.
