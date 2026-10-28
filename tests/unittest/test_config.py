# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""Unit tests for config utilities"""

from pathlib import Path

import pytest
from perseo_quality.core.generic_dataclasses import SARRadiometricQuantity

from s1_rad_cal.config import Config, from_toml


def test_from_toml(tmp_path):
    config_file = tmp_path / "config.toml"

    config_file.write_text(
        """
[output]
radiometric_quantity = "beta"
incidence_angles_dem = "path/to/dem"

[corrections]
processing_gain = true
absolute_calibration = true

[corrections.eap]
enabled = true
dem = "path/to/dem"

[corrections.denoising]
enabled = true
"""
    )

    cfg = from_toml(config_file)

    assert isinstance(cfg, Config)
    assert cfg.corrections.eap.enabled is True
    assert cfg.corrections.eap.dem == Path("path/to/dem")
    assert cfg.corrections.processing_gain is True
    assert cfg.corrections.absolute_calibration is True
    assert cfg.corrections.denoising.enabled is True
    assert cfg.corrections.denoising.external_noise_vector_folder is None
    assert cfg.output_quantity == SARRadiometricQuantity.BETA_NOUGHT


def test_missing_correction_field(tmp_path):
    config_file = tmp_path / "bad_config.toml"

    config_file.write_text(
        """
[input]
l1_product = "product.SAFE"
aux_pp1 = "aux_pp1.xml"
aux_cal = "aux_cal.xml"

[output]
directory = "output"

[corrections.denoising]
denoising = true
"""
    )

    with pytest.raises(KeyError):
        from_toml(config_file)
