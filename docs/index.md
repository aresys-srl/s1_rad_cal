---
icon: lucide/sparkles
title: "Overview"
tags:
    - radiometry
    - radiometric re-calibration
---

# Rad-Cal Tool

``rad-cal`` is the Aresys' radiometric re-calibration tool for Sentinel-1 L1 SLC and GRD products.

## Corrections

This tool applies a set of radiometric corrections to Sentinel-1 Level-1 products in order to improve the consistency and accuracy of radar backscatter measurements. The supported corrections are:

- Absolute calibration constant correction
- Processing gain correction
- Elevation antenna pattern (EAP) correction

Each correction requires auxiliary information provided by Sentinel-1 calibration products. Refer to the [radiometric corrections](features\corrections.md) for further information.

## Thermal De-Noising

This tool can remove thermal noise annotated in products metadata through the noise vectors. Refer to [thermal de-noising](features\denoising.md) for further information.

## Local Incidence Angle

This tool, if provided with a digital elevation model (DEM), can perform a terrain-based radiometric quantity conversion: it can indeed compute the local incidence angle $\theta_{LIN}$ -i.e. the angle 
between the radar beam and the line perpendicular to the local terrain surface- by projecting the DEM data into SAR space. While accounting for local terrain surface, effects such as *shadowing* or *layover* are neglected, so this radiometric conversion does not aim to substitute proper terrain
flattening as mentioned in  *Flattening Gamma: Radiometric Terrain Correction for SAR Imagery* ([Small, 2011](#small2011)).

## References

<a id="small2011"></a>

Small, D. (2011). *Flattening Gamma: Radiometric Terrain Correction for SAR Imagery*. 
IEEE Transactions on Geoscience and Remote Sensing, 49, 3081–3093.  
[https://doi.org/10.1109/TGRS.2011.2120616](https://doi.org/10.1109/TGRS.2011.2120616)
