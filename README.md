# Radiometric-Calibration for Sentinel-1 L1 Products

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue)](https://python.org)
[![rad-cal CI](https://github.com/aresys-srl/s1_rad_cal/actions/workflows/rad-cal.yml/badge.svg)](https://github.com/aresys-srl/s1_rad_cal/actions/workflows/rad-cal.yml)

``s1-rad-cal`` is the Aresys' radiometric re-calibration tool for Sentinel1 L1 SLC and GRD products:
it offers a set of radiometric corrections with the aim of improving consistency and accuracy of radar backscatter measurements.

## Installation

This package can be installed using ``pip``:

```
pip install s1-rad-cal
```

## Quick Start

``s1-rad-cal`` command line can be invoked in the terminal session as:

```
s1-rad-cal process [--input/-in] [--output/-out] [--config/-c] [--help]
```

Input file .json and output folder must be provided as paths, configuration is optional: if not provided, the default configuration will be used.
The input file must have the following structure:

```json
{
    "l1_product": "path/to/Sentinel-1/product",
    "aux_pp1": "path/to/aux/pp1/file/to/be/applied",
    "aux_cal": "path/to/aux/cal/file/to/be/applied"
}
```

## License

This project is licensed under the MIT License.

Copyright &copy; 2026-present Aresys S.R.L. <info@aresys.it>
