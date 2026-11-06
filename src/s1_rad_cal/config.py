# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""
Rad-Cal Tool configuration
--------------------------
"""

import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Callable, get_args

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


def _get_table(parent: dict[str, Any], key: str, name: str) -> dict[str, Any]:
    """Return a TOML table, or an empty one if it is missing."""
    table = parent.get(key, {})
    if not isinstance(table, dict):
        raise ValueError(f"[{name}] must be a table, got {type(table).__name__}")
    return table


def _check_unknown_keys(table: dict[str, Any], allowed: set[str], name: str) -> None:
    """Reject unknown keys, so that typos don't silently fall back to defaults."""
    unknown = set(table) - allowed
    if unknown:
        raise ValueError(f"Unknown key(s) in [{name}]: {sorted(unknown)}. Allowed keys: {sorted(allowed)}")


def _build(
    cls: type,
    table: dict[str, Any],
    name: str,
    converters: dict[str, Callable[[Any], Any]] | None = None,
):
    """Instantiate a flat dataclass using only the keys present in the table.

    Missing keys are not passed to the constructor, hence the dataclass
    default applies.
    """
    converters = converters or {}
    _check_unknown_keys(table, {f.name for f in fields(cls)}, name)
    kwargs = {key: converters.get(key, lambda v: v)(value) for key, value in table.items()}
    return cls(**kwargs)


def _to_path(value: str | None) -> Path | None:
    return Path(value) if value else None


def _to_quantity(value: str) -> SARRadiometricQuantity:
    try:
        return SARRadiometricQuantity[f"{str(value).upper()}_NOUGHT"]
    except KeyError:
        valid = [q.name.removesuffix("_NOUGHT").lower() for q in SARRadiometricQuantity]
        raise ValueError(f"Invalid radiometric_quantity {value!r}. Valid values: {valid}") from None


def _validate_atmospheric_attenuation(cfg: AtmosphericAttenuation) -> None:
    valid_modes = get_args(ComputationMode)
    if valid_modes and cfg.mode not in valid_modes:
        raise ValueError(f"Invalid atmospheric attenuation mode {cfg.mode!r}. Valid values: {list(valid_modes)}")

    if not cfg.enabled:
        return
    if cfg.weather_dataset_path is None:
        raise FileNotFoundError("Atmospheric attenuation is enabled: please provide a weather dataset .nc file")
    if not cfg.weather_dataset_path.is_file():
        raise FileNotFoundError(f"Weather dataset file {cfg.weather_dataset_path} does not exist")
    if cfg.weather_dataset_path.suffix != ".nc":
        raise ValueError(f"Weather dataset file {cfg.weather_dataset_path} is not a .nc file")


def from_toml(path: str | Path) -> Config:
    """Load the configuration from a TOML file; omitted fields use their defaults."""

    file = Path(path)
    if not file.is_file():
        raise FileNotFoundError(f"Input file {file} does not exist")
    if file.suffix != ".toml":
        raise ValueError(f"Input file {file} is not a .toml configuration file")

    with open(file, "rb") as f:
        cfg = tomllib.load(f)

    _check_unknown_keys(cfg, {"output", "corrections"}, "root")

    # [output]
    output_cfg = _get_table(cfg, "output", "output")
    _check_unknown_keys(output_cfg, {"radiometric_quantity", "incidence_angles_dem"}, "output")
    config_kwargs: dict[str, Any] = {}
    if "radiometric_quantity" in output_cfg:
        config_kwargs["output_quantity"] = _to_quantity(output_cfg["radiometric_quantity"])
    if "incidence_angles_dem" in output_cfg:
        config_kwargs["incidence_angles_dem"] = _to_path(output_cfg["incidence_angles_dem"])

    # [corrections] and its sub-tables
    corrections_cfg = _get_table(cfg, "corrections", "corrections")
    _check_unknown_keys(corrections_cfg, {f.name for f in fields(Corrections)}, "corrections")

    corrections_kwargs: dict[str, Any] = {
        key: value for key, value in corrections_cfg.items() if key in ("processing_gain", "absolute_calibration")
    }

    if "eap" in corrections_cfg:
        corrections_kwargs["eap"] = _build(
            EAPCorrection,
            _get_table(corrections_cfg, "eap", "corrections.eap"),
            "corrections.eap",
            {"dem": _to_path},
        )

    if "atmospheric_attenuation" in corrections_cfg:
        atmo = _build(
            AtmosphericAttenuation,
            _get_table(corrections_cfg, "atmospheric_attenuation", "corrections.atmospheric_attenuation"),
            "corrections.atmospheric_attenuation",
            {"weather_dataset_path": _to_path},
        )
        _validate_atmospheric_attenuation(atmo)
        corrections_kwargs["atmospheric_attenuation"] = atmo

    if "denoising" in corrections_cfg:
        corrections_kwargs["denoising"] = _build(
            Denoising,
            _get_table(corrections_cfg, "denoising", "corrections.denoising"),
            "corrections.denoising",
            {"external_noise_vector_folder": _to_path},
        )

    config_kwargs["corrections"] = Corrections(**corrections_kwargs)
    return Config(**config_kwargs)


if __name__ == "__main__":
    configuration = from_toml("scripts/config.toml")
    print(configuration)
