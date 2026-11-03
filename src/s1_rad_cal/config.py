# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""
Rad-Cal Tool configuration
--------------------------
"""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from perseo_quality.core.generic_dataclasses import SARRadiometricQuantity

from s1_rad_cal.corrections.atmospheric_attenuation import ComputationMode


@dataclass
class EAPCorrection:
    enabled: bool = True
    dem: Path | None = None


@dataclass
class Denoising:
    enabled: bool = False
    clipping: bool = True
    external_noise_vector_folder: Path | None = None


@dataclass
class AtmosphericAttenuation:
    enabled: bool = False
    weather_dataset_path: Path | None = None
    mode: ComputationMode = "approx"


@dataclass
class Corrections:
    eap: EAPCorrection = field(default_factory=EAPCorrection)
    processing_gain: bool = True
    absolute_calibration: bool = True
    atmospheric_attenuation: AtmosphericAttenuation = field(default_factory=AtmosphericAttenuation)
    denoising: Denoising = field(default_factory=Denoising)


@dataclass
class Config:
    corrections: Corrections = field(default_factory=Corrections)
    output_quantity: SARRadiometricQuantity = SARRadiometricQuantity.BETA_NOUGHT
    incidence_angles_dem: Path | None = None


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
    denoising_cfg = corrections_cfg["denoising"]

    atmospheric_attenuation_cfg = corrections_cfg["atmospheric_attenuation"]
    weather_ds = atmospheric_attenuation_cfg.get("weather_dataset_path", None)
    if atmospheric_attenuation_cfg.get("enabled", False):
        if not weather_ds:
            raise FileNotFoundError("Please provide a weather dataset .nc file")
        if not Path(weather_ds).is_file():
            raise FileNotFoundError(f"Weather dataset file {weather_ds} does not exist")
        if Path(weather_ds).suffix != ".nc":
            raise ValueError(f"Weather dataset file {file} is not a .nc file")

    output_cfg = cfg["output"]

    eap_dem = eap_cfg.get("dem", None)
    incidence_angles_dem = output_cfg.get("incidence_angles_dem", None)
    if eap_dem is not None:
        eap_dem = Path(eap_dem)
    if incidence_angles_dem is not None:
        incidence_angles_dem = Path(incidence_angles_dem)

    radiometric_quantity = output_cfg.get("radiometric_quantity", "beta")

    return Config(
        output_quantity=SARRadiometricQuantity[f"{radiometric_quantity.upper()}_NOUGHT"],
        incidence_angles_dem=incidence_angles_dem,
        corrections=Corrections(
            eap=EAPCorrection(
                enabled=eap_cfg["enabled"],
                dem=eap_dem,
            ),
            processing_gain=corrections_cfg["processing_gain"],
            absolute_calibration=corrections_cfg["absolute_calibration"],
            atmospheric_attenuation=AtmosphericAttenuation(
                enabled=atmospheric_attenuation_cfg.get("enabled", False),
                mode=atmospheric_attenuation_cfg.get("mode", False),
                weather_dataset_path=Path(weather_ds),
            ),
            denoising=Denoising(
                enabled=denoising_cfg["enabled"],
                clipping=denoising_cfg.get("clipping", True),
                external_noise_vector_folder=denoising_cfg.get(
                    "ext_noise_vector_folder",
                    None,
                ),
            ),
        ),
    )


if __name__ == "__main__":
    configuration = from_toml("scripts/config.toml")
    print(configuration)
