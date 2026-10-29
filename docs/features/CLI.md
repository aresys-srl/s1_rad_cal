---
icon: material/console
title: "CLI and Configuration"
tags:
    - CLI
    - processing
    - calibration
---

# Command Line Interface (CLI)

A command line interface has been developed to be used directly from a shell prompt to access ``s1-rad-cal`` tool functionalities with an
easy to use approach.

The main command line tool that can be accessed using the ``s1-rad-cal`` command in your favorite shell.

## Main CLI

``s1-rad-cal`` tool command line can be invoked in the terminal session as:

``` bash title="CLI Entry Point"
s1-rad-cal [--input/-in] [--output/-out] [--config/-c] [--help]
```

This is the entry point for the console script. Input file .json and output folder must be provided as paths, configuration is optional:
if not provided, the default configuration will be used.

## Input file .json
In order to run ``s1-rad-cal`` user must provide an input file in .json format; the structure of such file is shown here:

``` json title="Input file"
{
    "l1_product": "path/to/Sentinel-1/product",
    "aux_pp1": "path/to/aux/pp1/file/to/be/applied",
    "aux_cal": "path/to/aux/cal/file/to/be/applied"
}
```

## Configuration file

The configuration file lets the user select which correction to apply for the radiometric calibration of the input product.
Refer to the [radiometric corrections](corrections.md) for further information.

The .toml configuration file is organized in sections:

-**output**: here the user can decide the output radiometric quantity and can provide a DEM for radiometric quantity conversion.

-**corrections**: here the user can select which corrections to apply

Here an example of the needed .toml configuration file is provided:

``` toml title="General Configuration"
[output]
radiometric_quantity = "beta" # (1)!
incidence_angles_dem = "optional/path/to/dem/tiles/folder" # (2)!

[corrections]
processing_gain = true
absolute_calibration = true

[corrections.eap]
enabled = true
dem = "optional/path/to/dem/tiles/folder" # (3)!  

[corrections.denoising]
enabled = true
clipping = true
ext_noise_vector_folder = "optional/path/to/folder/containing/noise/files" # (4)!
```

1. Optional, the valid radiometric quantities are ``beta``, ``sigma``, ``gamma``. By default ``beta``

2.  Provide the path to dem tiles to use the local incidence angle for radiometric quantity conversion, otherwise remove to use the incidence angle computed on the inflated WGS84 Earth geoid

3.  Provide the path to dem tiles, otherwise remove to approximate the Earth geoid with possibly inflated WGS84

4.  Optional, remove to use noise calibration files present in the Sentinel-1 L1 product


!!! Warning

    If ``dem`` path is provided the software expects the raw binary tile files (e.g. `45N015E.GETASSE30`) to be available directly inside the folder

!!! Warning

    If ``ext_noise_vector_folder`` is provided, the folder must contain one xml file for each channel, having the same name and same internal format of the standard
    calibration noise xml files that are present in the Sentinel-1 product.