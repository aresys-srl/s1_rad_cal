# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""Unit tests for processing gain correction computation"""

from pathlib import Path

import pytest

import rad_cal.corrections.proc_gain as pg

TEST_DATA = "data/AUX_PP1/S1C_AUX_PP1_V20241204T000000_G20241204T092526.SAFE/data/s1c-aux-pp1.xml"
SAFE_NS = "http://www.esa.int/safe/sentinel-1.0"


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
    assert pg._get_processing_gain_from_aux_pp1(TEST_DATA, swath, pol) == pytest.approx(expected)


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
    assert pg._get_processing_gain_from_aux_pp1(Path(TEST_DATA), swath, pol) == pytest.approx(expected)


def test_compute_processing_gain_correction(monkeypatch):
    values = [8.0, 4.0]

    def mock_get_processing_gain_from_aux_pp1(*args, **kwargs):
        return values.pop(0)

    monkeypatch.setattr(
        pg,
        "_get_processing_gain_from_aux_pp1",
        mock_get_processing_gain_from_aux_pp1,
    )

    correction = pg.compute_processing_gain_correction(
        Path("new.xml"),
        Path("old.xml"),
        swath="IW1",
        polarization="HH",
    )

    assert correction == 2.0


def write_manifest(product_dir: Path, *, aux_pp1_name: str | None = None) -> None:
    """Create a minimal manifest.safe for testing."""
    if aux_pp1_name is None:
        aux_resource = ""
    else:
        aux_resource = f"""
        <safe:resource
            role="AUX_PP1"
            name="{aux_pp1_name}"
        />
        """

    manifest = f"""\
    <safe:manifest xmlns:safe="{SAFE_NS}">
        <safe:resources>
            {aux_resource}
        </safe:resources>
    </safe:manifest>
    """

    (product_dir / "manifest.safe").write_text(manifest)


def test_returns_aux_pp1_xml_path(tmp_path, monkeypatch):
    product_dir = tmp_path / "product"
    product_dir.mkdir()

    write_manifest(
        product_dir,
        aux_pp1_name="S1A_AUX_PP1_V20200101T000000_20200102T000000.xml",
    )

    aux_dataset = tmp_path / "aux_dataset"
    filename = "S1A_AUX_PP1_V20200101T000000_20200102T000000.xml"
    data_dir = aux_dataset / filename / "data"
    data_dir.mkdir(parents=True)

    expected_xml = data_dir / "aux_pp1.xml"
    expected_xml.write_text("<auxiliary-data/>")

    monkeypatch.setattr("rad_cal.corrections.proc_gain.AUX_PP1_DATASET", aux_dataset)

    result = pg.get_aux_pp1_xml_path_from_product(product_dir)

    assert result == expected_xml
    assert result.is_file()


def test_accepts_string_product_path(tmp_path, monkeypatch):
    product_dir = tmp_path / "product"
    product_dir.mkdir()

    filename = "AUX_PP1.xml"
    write_manifest(product_dir, aux_pp1_name=filename)

    data_dir = tmp_path / "aux_dataset" / filename / "data"
    data_dir.mkdir(parents=True)
    expected_xml = data_dir / "associated.xml"
    expected_xml.write_text("<auxiliary-data/>")

    monkeypatch.setattr("rad_cal.corrections.proc_gain.AUX_PP1_DATASET", tmp_path / "aux_dataset")

    result = pg.get_aux_pp1_xml_path_from_product(str(product_dir))

    assert result == expected_xml


def test_raises_when_no_aux_pp1_xml_exists(tmp_path, monkeypatch):
    product_dir = tmp_path / "product"
    product_dir.mkdir()

    filename = "AUX_PP1.xml"
    write_manifest(product_dir, aux_pp1_name=filename)

    data_dir = tmp_path / "aux_dataset" / filename / "data"
    data_dir.mkdir(parents=True)

    monkeypatch.setattr("rad_cal.corrections.proc_gain.AUX_PP1_DATASET", tmp_path / "aux_dataset")

    with pytest.raises(
        FileNotFoundError,
        match="AUX_PP1 association failed: none or more than one xml files were found!",
    ):
        pg.get_aux_pp1_xml_path_from_product(product_dir)


def test_raises_when_multiple_aux_pp1_xml_files_exist(tmp_path, monkeypatch):
    product_dir = tmp_path / "product"
    product_dir.mkdir()

    filename = "AUX_PP1.xml"
    write_manifest(product_dir, aux_pp1_name=filename)

    data_dir = tmp_path / "aux_dataset" / filename / "data"
    data_dir.mkdir(parents=True)

    (data_dir / "first.xml").write_text("<auxiliary-data/>")
    (data_dir / "second.xml").write_text("<auxiliary-data/>")

    monkeypatch.setattr("rad_cal.corrections.proc_gain.AUX_PP1_DATASET", tmp_path / "aux_dataset")

    with pytest.raises(
        FileNotFoundError,
        match="AUX_PP1 association failed: none or more than one xml files were found!",
    ):
        pg.get_aux_pp1_xml_path_from_product(product_dir)


def test_raises_when_manifest_has_no_aux_pp1_resource(tmp_path):
    product_dir = tmp_path / "product"
    product_dir.mkdir()

    write_manifest(product_dir)

    with pytest.raises(
        FileNotFoundError,
        match="AUX_PP1 association failed!",
    ):
        pg.get_aux_pp1_xml_path_from_product(product_dir)
