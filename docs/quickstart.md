---
icon: lucide/zap
title: "Quickstart"
tags:
    - python
    - tutorial
---

# Minimal Tutorial
``s1-rad-cal`` can be used in a python script. A minimal tutorial can be found here:

```py
from s1_rad_cal.config import Config
from s1_rad_cal.main import run

if __name__ == "__main__":
    run(
        l1_product_path="path/to/sentinel-1/product",
        aux_cal_path="path/to/aux/cal,
        aux_pp1_path="path/to/aux/pp1",
        output_path="path/to/output/folder",
        config=Config()
    )

```

``s1-rad-cal`` can also be used from [command line](features\CLI.md).

!!! warning "Requirement"

    In order to run ``s1-rad-cal``, user must provide a local collection of ``AUX_PP1`` files. 
    See [processing gain correction](features/corrections.md#processing-gain) for more information.

