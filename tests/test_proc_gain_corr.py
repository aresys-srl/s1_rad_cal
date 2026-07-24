# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""Unit tests for processing gain correction computation"""

from pathlib import Path

import pytest

import rad_cal.corrections.proc_gain as pg

TEST_DATA = "data/AUX_PP1/S1C_AUX_PP1_V20241204T000000_G20241204T092526.SAFE/data/s1c-aux-pp1.xml"


@pytest.mark.parametrize(
    "swath,pol,expected",
    [
        ("IW1", "HH", 10712874.26),
        ("IW1", "HV", 10712874.26),
        ("IW1", "VV", 10712874.26),
        ("IW1", "VH", 10712874.26),
    ],
)
def test_get_processing_gain_from_aux_pp1_string(swath, pol, expected):
    assert pg.get_processing_gain_from_aux_pp1(TEST_DATA, swath, pol) == pytest.approx(expected)


@pytest.mark.parametrize(
    "swath,pol,expected",
    [
        ("IW1", "HH", 10712874.26),
        ("IW1", "HV", 10712874.26),
        ("IW1", "VV", 10712874.26),
        ("IW1", "VH", 10712874.26),
    ],
)
def test_get_processing_gain_from_aux_pp1_string_path(swath, pol, expected):
    assert pg.get_processing_gain_from_aux_pp1(Path(TEST_DATA), swath, pol) == pytest.approx(expected)


def test_compute_processing_gain_correction(monkeypatch):
    values = [8.0, 4.0]

    def mock_get_processing_gain_from_aux_pp1(*args, **kwargs):
        return values.pop(0)

    monkeypatch.setattr(
        pg,
        "get_processing_gain_from_aux_pp1",
        mock_get_processing_gain_from_aux_pp1,
    )

    correction = pg.compute_processing_gain_correction(
        Path("new.xml"),
        Path("old.xml"),
        swath="IW1",
        polarization="HH",
    )

    assert correction == 2.0
