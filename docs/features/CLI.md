---
icon: material/console
title: "CLI"
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

```bash title="CLI Entry Point"
rad-cal [--config/-c] [--help/-h]
```

This is the entry point for the console script. The configuration needed to perform the analysis must be provided
using the ``--config/-c`` argument.

## Configuration file setup for CLI tool

In order to launch the rad-cal tool from command line, user must provide a configuration file.
The configuration file lets the user select which correction to apply for the radiometric calibration of the input product.
Refer to the [radiometric corrections](corrections.md) for further information.

The .toml configuration file is organized in sections:

-**input**: here the path to the needed input files must be provided

-**output**: here the path to the output folder must be provided

-**corrections**: here the user can select which corrections to apply

Here an example of the needed .toml configuration file is provided:

```toml title="General Configuration"
[input]
l1_product = "path/to/sentinel1/L1/product.SAFE"
aux_pp1 = "path/to/AUX_PP1.SAFE"
aux_cal = "path/to/AUX_CAL.SAFE"

[output]
directory = "path/where/output/is/stored"

[corrections]
eap = true                      # whether to apply elevation antenna pattern correction
processing_gain = true          # whether to apply processing gain correction
absolute_calibration = true     # whether to apply absolute calibration correction
```