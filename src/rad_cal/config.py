# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""
Rad-Cal Tool configuration
--------------------------
"""

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Corrections:
    eap: bool = True
    processing_gain: bool = True
    absolute_calibration: bool = True
    denoising: bool = False


@dataclass
class Config:
    l1_product: Path
    aux_pp1: Path
    aux_cal: Path
    output: Path

    corrections: Corrections


def from_toml(path: str | Path) -> Config:
    with open(path, "rb") as f:
        cfg = tomllib.load(f)

    return Config(
        l1_product=Path(cfg["input"]["l1_product"]),
        aux_pp1=Path(cfg["input"]["aux_pp1"]),
        aux_cal=Path(cfg["input"]["aux_cal"]),
        output=Path(cfg["output"]["directory"]),
        corrections=Corrections(
            eap=cfg["corrections"]["eap"],
            processing_gain=cfg["corrections"]["processing_gain"],
            absolute_calibration=cfg["corrections"]["absolute_calibration"],
            denoising=cfg["corrections"]["denoising"],
        ),
    )
