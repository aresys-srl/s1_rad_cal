# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""Unit tests for config utilities"""

from pathlib import Path

import pytest

from rad_cal.config import Config, ElevationSource, from_toml


def test_from_toml(tmp_path):
    config_file = tmp_path / "config.toml"

    config_file.write_text(
        """
[input]
l1_product = "product.SAFE"
aux_pp1 = "aux_pp1.xml"
aux_cal = "aux_cal.xml"

[output]
directory = "output"

[corrections]
processing_gain = true
absolute_calibration = true
denoising = false

[corrections.eap]
enabled = true
elevation_source = "dem"
"""
    )

    cfg = from_toml(config_file)

    assert isinstance(cfg, Config)

    assert cfg.l1_product == Path("product.SAFE")
    assert cfg.aux_pp1 == Path("aux_pp1.xml")
    assert cfg.aux_cal == Path("aux_cal.xml")
    assert cfg.output == Path("output")

    assert cfg.corrections.eap.enabled is True
    assert cfg.corrections.eap.elevation_source is ElevationSource.DEM
    assert cfg.corrections.processing_gain is True
    assert cfg.corrections.absolute_calibration is True
    assert cfg.corrections.denoising is False


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

[corrections]
denoising = true
"""
    )

    with pytest.raises(KeyError):
        from_toml(config_file)
