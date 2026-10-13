from types import SimpleNamespace

import arepytools.timing.precisedatetime as att
import numpy as np
import pytest
from arepytools.io import metadata as mtd
from arepytools.io.metadata import EPolarization, ESideLooking
from perseo_quality.core.generic_dataclasses import SARRadiometricQuantity

from rad_cal.utils import (
    _compile_dataset_info,
    create_pf_metadata,
)


class TestCompileDatasetInfo:
    @pytest.fixture
    def fake_metadata(self):
        return SimpleNamespace(
            general_info=SimpleNamespace(
                mission_id="S1A",
            ),
            dataset_info=SimpleNamespace(
                image_type="SLC", projection="GROUND_RANGE", side_looking=ESideLooking.right_looking, fc_hz=0.0
            ),
        )

    def test_compile_dataset_info(self, fake_metadata):

        dataset_info = mtd.DataSetInfo(
            acquisition_mode_i="IW",
            image_quantity="BETA",
        )

        result = _compile_dataset_info(
            arepytools_dataset_info=dataset_info,
            metadata=fake_metadata,
        )

        assert result.description == "Radiometric Re-Calibrated Data"
        assert result.sensor_name == "S1A"
        assert result.image_type == "SLC"
        assert result.projection == "GROUND_RANGE"
        assert result.acquisition_station == ""
        assert result.processing_center == ""
        assert result.processing_software == "rad-cal"
        assert result.side_looking.value == "RIGHT"


class TestCreatePfMetadata:
    @pytest.fixture
    def fake_metadata(self):
        return SimpleNamespace(
            raster_info=SimpleNamespace(
                lines=SimpleNamespace(length=100, start=att.PreciseDateTime(), step=1),
                samples=SimpleNamespace(length=200, start=0, step=1),
                data_type="FLOAT32",
            ),
            general_info=SimpleNamespace(
                polarization=SimpleNamespace(
                    value=EPolarization.vv,
                ),
                mission_id="S1A",
                product_type=SimpleNamespace(value="SLC"),
                start_time=att.PreciseDateTime(),
            ),
            dataset_info=SimpleNamespace(
                acquisition_mode="IW",
                image_type="SLC",
                projection="GROUND_RANGE",
                side_looking=ESideLooking.right_looking,
                fc_hz=0.0,
            ),
            sampling_constants=SimpleNamespace(
                range_freq_hz=0.0,
                range_bandwidth_freq_hz=0.0,
                azimuth_freq_hz=0.0,
                azimuth_bandwidth_freq_hz=0.0,
            ),
            swath_info=SimpleNamespace(
                acquisition_start_time=att.PreciseDateTime(),
                prf=0.0,
            ),
            burst_info=SimpleNamespace(
                num=4,
                range_start_times=np.zeros(4),
                azimuth_start_times=np.zeros(4),
                lines_per_burst=10,
            ),
            state_vectors=SimpleNamespace(
                positions=np.array(
                    [
                        [1, 2, 3],
                        [4, 5, 6],
                    ]
                ),
                velocities=np.array(
                    [
                        [0.1, 0.2, 0.3],
                        [0.4, 0.5, 0.6],
                    ]
                ),
                time_axis=np.array([10.0, 20.0]),
            ),
        )

    def test_create_pf_metadata(self, fake_metadata, tmp_path):

        raster_file = tmp_path / "channel.slc"

        result = create_pf_metadata(
            metadata=fake_metadata,
            channel_raster_file=raster_file,
            swath="IW1",
            output_quantity=SARRadiometricQuantity.BETA_NOUGHT,
            is_grd=False,
        )

        assert isinstance(result, mtd.MetaData)

        raster_info = result.get_raster_info()

        assert raster_info.lines == 100
        assert raster_info.samples == 200
        assert raster_info.file_name == "channel.slc"

    def test_create_pf_metadata_dataset_info(
        self,
        fake_metadata,
        tmp_path,
    ):

        result = create_pf_metadata(
            metadata=fake_metadata,
            channel_raster_file=tmp_path / "channel.slc",
            swath="IW2",
            output_quantity=SARRadiometricQuantity.BETA_NOUGHT,
            is_grd=False,
        )

        dataset_info = result.get_dataset_info()

        assert dataset_info.description == ("Radiometric Re-Calibrated Data")
        assert dataset_info.sensor_name == "S1A"
        assert dataset_info.processing_software == "rad-cal"
        assert dataset_info.side_looking.value == "RIGHT"

    def test_create_pf_metadata_state_vectors(
        self,
        fake_metadata,
        tmp_path,
    ):

        result = create_pf_metadata(
            metadata=fake_metadata,
            channel_raster_file=tmp_path / "channel.slc",
            swath="IW1",
            output_quantity=SARRadiometricQuantity.BETA_NOUGHT,
            is_grd=False,
        )

        state_vectors = result.get_state_vectors()

        np.testing.assert_array_equal(
            state_vectors.position_vector,
            fake_metadata.state_vectors.positions,
        )

        np.testing.assert_array_equal(
            state_vectors.velocity_vector,
            fake_metadata.state_vectors.velocities,
        )

        assert state_vectors._t_ref_utc == 10.0
        assert state_vectors._dt_sv_s == 10.0
