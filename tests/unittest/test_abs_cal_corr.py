# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""Unit tests for absolute calibration correction computation"""

from pathlib import Path
from unittest.mock import patch

from s1_rad_cal.corrections.abs_cal import compute_absolute_calibration_correction


def test_compute_absolute_calibration_correction():
    compute_absolute_calibration_correction.cache_clear()

    with patch(
        "s1_rad_cal.corrections.abs_cal._get_abs_cal_constant_from_cal_file",
        side_effect=[20.0, 10.0],
    ):
        result = compute_absolute_calibration_correction(
            Path("new.xml"),
            Path("original.xml"),
        )

    assert result == 2.0
