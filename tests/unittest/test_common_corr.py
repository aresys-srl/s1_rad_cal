# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""Unit tests for corrections common functionalities"""

from pathlib import Path

import pytest
from perseo_core.timing.precise_datetime import PreciseDateTime

from s1_rad_cal.corrections.common import apply_roll_correction, get_aux_files


class TestApplyRollCorrection:
    @pytest.mark.parametrize(
        "roll, mission_id, az_time, expected",
        [
            (1.0, "S1D", PreciseDateTime.fromisoformat("2026-07-24T13:43:00"), 1.0),
            (1.0, "S1C", PreciseDateTime.fromisoformat("2026-07-24T13:43:00"), 1.0),
            (1.0, "S1D", PreciseDateTime.fromisoformat("2024-07-24T13:43:00"), 1.03),
            (1.0, "S1C", PreciseDateTime.fromisoformat("2024-07-24T13:43:00"), 1.0),
        ],
    )
    def test_apply_roll_correction(self, roll, mission_id, az_time, expected):
        assert apply_roll_correction(roll, mission_id, az_time) == expected


class TestGetAuxFiles:
    def create_product_manifest(
        self,
        path: Path,
        instrument_config_id: int,
    ):
        path.joinpath("manifest.safe").write_text(
            f"""
            <root xmlns:s1sarl1="http://www.esa.int/safe/sentinel-1.0/sentinel-1/sar/level-1">
                <s1sarl1:instrumentConfigurationID>
                    {instrument_config_id}
                </s1sarl1:instrumentConfigurationID>
            </root>
            """
        )

    def create_aux_manifest(
        self,
        path: Path,
        instrument_config_id: int,
        validity: str,
        aux_type: str,
    ):
        if aux_type == "pp1":
            namespace = "http://www.esa.int/safe/sentinel-1.0/sentinel-1/auxiliary/sar"
            tag = "instrumentConfigurationId"
        else:
            namespace = "http://www.esa.int/safe/sentinel-1.0/sentinel-1/auxiliary/sar"
            tag = "instrumentConfigurationId"

        path.joinpath("manifest.safe").write_text(
            f"""
            <root xmlns:s1auxsar="{namespace}">
                <s1auxsar:{tag}>{instrument_config_id}</s1auxsar:{tag}>
                <s1auxsar:validity>{validity}</s1auxsar:validity>
            </root>
            """
        )

    def create_aux_xml_files(self, path: Path):
        data = path / "data"
        data.mkdir()

        (data / "aux-cal-test.xml").write_text("<xml/>")
        (data / "aux-pp1-test.xml").write_text("<xml/>")

    def test_get_aux_files_returns_correct_paths(self, tmp_path):

        product = tmp_path / "product"
        aux_pp1 = tmp_path / "S1D_aux_pp1"
        aux_cal = tmp_path / "S1D_aux_cal"

        product.mkdir()
        aux_pp1.mkdir()
        aux_cal.mkdir()

        self.create_product_manifest(product, 123)

        validity = "2024-01-02T00:00:00"

        self.create_aux_manifest(
            aux_pp1,
            instrument_config_id=123,
            validity=validity,
            aux_type="pp1",
        )

        self.create_aux_manifest(
            aux_cal,
            instrument_config_id=123,
            validity=validity,
            aux_type="cal",
        )

        self.create_aux_xml_files(aux_pp1)
        self.create_aux_xml_files(aux_cal)

        acquisition_time = PreciseDateTime.fromisoformat("2024-01-02T00:00:00")

        aux_cal_xml, aux_pp1_xml = get_aux_files(
            product,
            aux_pp1,
            aux_cal,
            acquisition_time,
            "S1D",
        )

        assert aux_cal_xml.name == "aux-cal-test.xml"
        assert aux_pp1_xml.name == "aux-pp1-test.xml"

    def test_get_aux_files_fails_for_wrong_pp1_instrument_id(self, tmp_path):

        product = tmp_path / "product"
        aux_pp1 = tmp_path / "S1D_aux_pp1"
        aux_cal = tmp_path / "S1D_aux_cal"

        product.mkdir()
        aux_pp1.mkdir()
        aux_cal.mkdir()

        self.create_product_manifest(product, 123)

        validity = "2024-01-02T00:00:00"

        self.create_aux_manifest(
            aux_pp1,
            instrument_config_id=999,
            validity=validity,
            aux_type="pp1",
        )

        self.create_aux_manifest(
            aux_cal,
            instrument_config_id=123,
            validity=validity,
            aux_type="cal",
        )

        self.create_aux_xml_files(aux_pp1)
        self.create_aux_xml_files(aux_cal)

        acquisition_time = PreciseDateTime.fromisoformat("2024-01-02T00:00:00")

        with pytest.raises(
            ValueError,
            match="instrument config ids differ",
        ):
            get_aux_files(
                product,
                aux_pp1,
                aux_cal,
                acquisition_time,
                "S1D",
            )

    def test_get_aux_files_fails_when_product_before_aux_validity(
        self,
        tmp_path,
    ):

        product = tmp_path / "product"
        aux_pp1 = tmp_path / "S1D_aux_pp1"
        aux_cal = tmp_path / "S1D_aux_cal"

        product.mkdir()
        aux_pp1.mkdir()
        aux_cal.mkdir()

        self.create_product_manifest(product, 123)

        self.create_aux_manifest(
            aux_pp1,
            instrument_config_id=123,
            validity="2025-01-02T00:00:00",
            aux_type="pp1",
        )

        self.create_aux_manifest(
            aux_cal,
            instrument_config_id=123,
            validity="2025-01-02T00:00:00",
            aux_type="cal",
        )

        self.create_aux_xml_files(aux_pp1)
        self.create_aux_xml_files(aux_cal)

        acquisition_time = PreciseDateTime.fromisoformat("2024-01-02T00:00:00")

        with pytest.raises(
            ValueError,
            match="outside of AUX_PP1 time validity",
        ):
            get_aux_files(
                product,
                aux_pp1,
                aux_cal,
                acquisition_time,
                "S1D",
            )

    def test_get_aux_files_fails_when_sensor_names_differ_aux_pp1(
        self,
        tmp_path,
    ):
        product = tmp_path / "product"
        aux_pp1 = tmp_path / "S1C_aux_pp1"
        aux_cal = tmp_path / "S1D_aux_cal"

        product.mkdir()
        aux_pp1.mkdir()
        aux_cal.mkdir()

        self.create_product_manifest(product, 123)

        self.create_aux_manifest(
            aux_pp1,
            instrument_config_id=123,
            validity="2024-01-02T00:00:00",
            aux_type="pp1",
        )

        self.create_aux_manifest(
            aux_cal,
            instrument_config_id=123,
            validity="2024-01-02T00:00:00",
            aux_type="cal",
        )

        self.create_aux_xml_files(aux_pp1)
        self.create_aux_xml_files(aux_cal)

        acquisition_time = PreciseDateTime.fromisoformat("2024-01-02T00:00:00")

        with pytest.raises(
            ValueError,
            match="sensor names differ!",
        ):
            get_aux_files(
                product,
                aux_pp1,
                aux_cal,
                acquisition_time,
                "S1D",
            )

    def test_get_aux_files_fails_when_sensor_names_differ_aux_cal(
        self,
        tmp_path,
    ):
        product = tmp_path / "product"
        aux_pp1 = tmp_path / "S1D_aux_pp1"
        aux_cal = tmp_path / "S1C_aux_cal"

        product.mkdir()
        aux_pp1.mkdir()
        aux_cal.mkdir()

        self.create_product_manifest(product, 123)

        self.create_aux_manifest(
            aux_pp1,
            instrument_config_id=123,
            validity="2024-01-02T00:00:00",
            aux_type="pp1",
        )

        self.create_aux_manifest(
            aux_cal,
            instrument_config_id=123,
            validity="2024-01-02T00:00:00",
            aux_type="cal",
        )

        self.create_aux_xml_files(aux_pp1)
        self.create_aux_xml_files(aux_cal)

        acquisition_time = PreciseDateTime.fromisoformat("2024-01-02T00:00:00")

        with pytest.raises(
            ValueError,
            match="sensor names differ!",
        ):
            get_aux_files(
                product,
                aux_pp1,
                aux_cal,
                acquisition_time,
                "S1D",
            )
