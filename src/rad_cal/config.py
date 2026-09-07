# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""
Rad-Cal Tool configuration
--------------------------
"""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class EAPCorrection:
    enabled: bool = True
    dem: Path | None = None


@dataclass
class TerrainFlattening:
    enabled: bool = False
    dem: Path | None = None


@dataclass
class Denoising:
    enabled: bool = False
    external_noise_vector_folder: Path | None = None


@dataclass
class Corrections:
    eap: EAPCorrection = field(default_factory=EAPCorrection)
    processing_gain: bool = True
    absolute_calibration: bool = True
    terrain_flattening: TerrainFlattening = field(default_factory=TerrainFlattening)
    denoising: Denoising = field(default_factory=Denoising)


@dataclass
class Config:
    l1_product: Path
    aux_pp1: Path
    aux_cal: Path
    output: Path

    corrections: Corrections


def from_toml(path: str | Path) -> Config:

    file = Path(path)
    if not file.is_file():
        raise FileNotFoundError(f"Input file {file} does not exist")
    if file.suffix != ".toml":
        raise ValueError(f"Input file {file} is not a .toml configuration file")

    with open(path, "rb") as f:
        cfg = tomllib.load(f)

    corrections_cfg = cfg["corrections"]
    eap_cfg = corrections_cfg["eap"]
    terrain_flattening_cfg = corrections_cfg["terrain_flattening"]
    denoising_cfg = corrections_cfg["denoising"]

    eap_dem = eap_cfg.get("dem", None)
    terrain_flattening_dem = terrain_flattening_cfg.get("dem", None)

    if eap_dem is not None:
        eap_dem = Path(eap_dem)
    if terrain_flattening_dem is not None:
        terrain_flattening_dem = Path(terrain_flattening_dem)

    return Config(
        l1_product=Path(cfg["input"]["l1_product"]),
        aux_pp1=Path(cfg["input"]["aux_pp1"]),
        aux_cal=Path(cfg["input"]["aux_cal"]),
        output=Path(cfg["output"]["directory"]),
        corrections=Corrections(
            eap=EAPCorrection(
                enabled=eap_cfg["enabled"],
                dem=eap_dem,
            ),
            processing_gain=corrections_cfg["processing_gain"],
            absolute_calibration=corrections_cfg["absolute_calibration"],
            terrain_flattening=TerrainFlattening(
                enabled=terrain_flattening_cfg["enabled"],
                dem=terrain_flattening_dem,
            ),
            denoising=Denoising(
                enabled=denoising_cfg["enabled"],
                external_noise_vector_folder=denoising_cfg.get(
                    "ext_noise_vector_folder",
                    None,
                ),
            ),
        ),
    )
