---
icon: material/console
title: "CLI and Configuration"
tags:
    - CLI
    - processing
    - calibration
---

# Command Line Interface (CLI)

A command line interface has been developed to be used directly from a shell prompt to access rad-cal tool functionalities with an
easy to use approach.

The main command line tool that can be accessed using the ``rad-cal`` command in your favorite shell.

## Main CLI

Rad-cal tool command line can be invoked in the terminal session as:

``` bash title="CLI Entry Point"
rad-cal [--config/-c] [--help/-h]
```

This is the entry point for the console script. The configuration needed to perform the analysis must be provided
using the ``--config/-c`` argument.

## Configuration file

In order to launch the rad-cal tool, user must provide a configuration file.
The configuration file lets the user select which correction to apply for the radiometric calibration of the input product.
Refer to the [radiometric corrections](corrections.md) for further information.

The .toml configuration file is organized in sections:

-**input**: here the path to the needed input files must be provided

-**output**: here the path to the output folder must be provided

-**corrections**: here the user can select which corrections to apply

Here an example of the needed .toml configuration file is provided:

``` toml title="General Configuration"
[input]
l1_product = "path/to/sentinel1/L1/product.SAFE"
aux_pp1 = "path/to/AUX_PP1.SAFE"
aux_cal = "path/to/AUX_CAL.SAFE"

[output]
directory = "path/where/output/is/stored"

[corrections]
processing_gain = true          # whether to apply processing gain correction
absolute_calibration = true     # whether to apply absolute calibration correction

[corrections.eap]
enabled = true                  # whether to apply elevation antenna pattern gain correction
elevation_source = "dem"        # select "dem" in order to account for terrain-induced 
                                # variations in elevation angle, select "ellipsoid" to approximate 
                                # the Earth geoid with WGS84

[corrections.denoising]
enabled = true                  # whether to apply thermal de-noising
ext_noise_vector_folder = "optional/path/to/folder/containing/noise/files"
                                # optional, remove to use noise calibration files present in 
                                # the Sentinel-1 L1 product
```

!!! Warning

    If ``elevation_source`` is set to ``dem``, DEM tiles must be provided, see [elevation antenna pattern correction](corrections.md#elevation-antenna-pattern) for more information.

!!! Warning

    If ``ext_noise_vector_folder`` is provided, the folder must contain one xml file for each channel, having the same name and same internal format of the standard
    calibration noise xml files that are present in the Sentinel-1 product.