from types import SimpleNamespace

import arepytools.timing.precisedatetime as att
import numpy as np
import pytest
from arepytools.io import metadata as mtd
from arepytools.io.metadata import EPolarization, ESideLooking
from perseo_quality.core.generic_dataclasses import SARRadiometricQuantity

from s1_rad_cal.utils import (
    C,
    DataBlock,
    _compile_dataset_info,
    build_grd_blocks,
    build_slc_blocks,
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
        assert result.processing_software == "s1-rad-cal"
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
        assert dataset_info.processing_software == "s1-rad-cal"
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


class TestDataBlock:
    def test_target_block(self):
        block = DataBlock(
            first_line=5,
            first_sample=2,
            n_lines=10,
            n_samples=20,
            azimuth_axis=np.arange(10),
            range_axis=np.arange(20),
            swath="IW1",
            index=0,
        )
        assert block.target_block == [5, 2, 10, 20]

    def test_is_frozen(self):
        block = DataBlock(0, 0, 1, 1, np.zeros(1), np.zeros(1), "IW1", 0)
        with pytest.raises(AttributeError):
            block.index = 3


class TestBuildSlcBlocks:
    @staticmethod
    def _make_metadata(num_bursts, lines_per_burst, n_lines, n_samples):
        return SimpleNamespace(
            raster_info=SimpleNamespace(
                samples=SimpleNamespace(axis=np.arange(n_samples) * 1e-8),
                lines=SimpleNamespace(axis=np.arange(n_lines) * 0.002),
            ),
            burst_info=SimpleNamespace(num=num_bursts, lines_per_burst=lines_per_burst),
        )

    def test_multiple_bursts_one_block_per_burst(self):
        metadata = self._make_metadata(num_bursts=3, lines_per_burst=10, n_lines=30, n_samples=5)

        blocks = build_slc_blocks(metadata, swath="IW2")

        assert len(blocks) == 3
        for i, block in enumerate(blocks):
            assert block.index == i
            assert block.swath == "IW2"
            assert block.first_line == i * 10
            assert block.first_sample == 0
            assert block.n_lines == 10
            assert block.n_samples == 5
            np.testing.assert_array_equal(block.azimuth_axis, metadata.raster_info.lines.axis[i * 10 : (i + 1) * 10])
            np.testing.assert_array_equal(block.range_axis, metadata.raster_info.samples.axis)

    def test_multiple_bursts_blocks_are_contiguous(self):
        metadata = self._make_metadata(num_bursts=4, lines_per_burst=7, n_lines=28, n_samples=3)

        blocks = build_slc_blocks(metadata, swath="IW1")

        assert sum(b.n_lines for b in blocks) == 28
        for prev, nxt in zip(blocks[:-1], blocks[1:], strict=True):
            assert nxt.first_line == prev.first_line + prev.n_lines

    def test_single_burst_uses_fixed_size_blocks(self):
        metadata = self._make_metadata(num_bursts=1, lines_per_burst=999, n_lines=6000, n_samples=4)

        blocks = build_slc_blocks(metadata, swath="S1")

        assert len(blocks) == 3
        assert [b.first_line for b in blocks] == [0, 2000, 4000]
        assert all(b.n_lines == 2000 for b in blocks)
        assert all(b.n_samples == 4 for b in blocks)
        assert [b.index for b in blocks] == [0, 1, 2]

    def test_single_burst_includes_remainder_block(self):
        metadata = self._make_metadata(num_bursts=1, lines_per_burst=999, n_lines=4500, n_samples=4)

        blocks = build_slc_blocks(metadata, swath="S1")

        assert [b.first_line for b in blocks] == [0, 2000, 4000]
        assert [b.n_lines for b in blocks] == [2000, 2000, 500]
        assert sum(b.n_lines for b in blocks) == 4500
        assert [b.index for b in blocks] == [0, 1, 2]
        np.testing.assert_array_equal(blocks[-1].azimuth_axis, metadata.raster_info.lines.axis[4000:])

    def test_single_burst_fewer_lines_than_block_size(self):
        metadata = self._make_metadata(num_bursts=1, lines_per_burst=999, n_lines=1500, n_samples=4)

        blocks = build_slc_blocks(metadata, swath="S1")

        assert len(blocks) == 1
        assert blocks[0].target_block == [0, 0, 1500, 4]
        np.testing.assert_array_equal(blocks[0].azimuth_axis, metadata.raster_info.lines.axis)

    def test_single_burst_no_lines_returns_empty_list(self):
        metadata = self._make_metadata(num_bursts=1, lines_per_burst=999, n_lines=0, n_samples=4)

        assert build_slc_blocks(metadata, swath="S1") == []


class TestBuildGrdBlocks:
    SWATH_XML = """<?xml version="1.0" encoding="UTF-8"?>
<product>
  <swathMerge>
    <swath>IW1</swath>
    <swathBoundsList>
      <swathBounds>
        <firstAzimuthLine>0</firstAzimuthLine>
        <lastAzimuthLine>19</lastAzimuthLine>
        <firstRangeSample>0</firstRangeSample>
        <lastRangeSample>24</lastRangeSample>
        <azimuthTime>2020-01-01T00:00:00.000000</azimuthTime>
      </swathBounds>
      <swathBounds>
        <firstAzimuthLine>20</firstAzimuthLine>
        <lastAzimuthLine>39</lastAzimuthLine>
        <firstRangeSample>0</firstRangeSample>
        <lastRangeSample>24</lastRangeSample>
        <azimuthTime>2020-01-01T00:00:01.000000</azimuthTime>
      </swathBounds>
    </swathBoundsList>
  </swathMerge>
  <swathMerge>
    <swath>IW2</swath>
    <swathBoundsList>
      <swathBounds>
        <firstAzimuthLine>0</firstAzimuthLine>
        <lastAzimuthLine>19</lastAzimuthLine>
        <firstRangeSample>25</firstRangeSample>
        <lastRangeSample>49</lastRangeSample>
        <azimuthTime>2020-01-01T00:00:00.000000</azimuthTime>
      </swathBounds>
    </swathBoundsList>
  </swathMerge>
  <swathMerge>
    <swath></swath>
    <swathBoundsList>
      <swathBounds>
        <firstAzimuthLine>0</firstAzimuthLine>
        <lastAzimuthLine>1</lastAzimuthLine>
        <firstRangeSample>0</firstRangeSample>
        <lastRangeSample>1</lastRangeSample>
        <azimuthTime>2020-01-01T00:00:00.000000</azimuthTime>
      </swathBounds>
    </swathBoundsList>
  </swathMerge>
  <swathMerge>
    <swath>IW3</swath>
  </swathMerge>
</product>
"""

    @pytest.fixture
    def metadata_file(self, tmp_path):
        path = tmp_path / "grd_metadata.xml"
        path.write_text(self.SWATH_XML)
        return path

    @pytest.fixture
    def fake_metadata(self):
        calls = []

        def evaluate_ground_to_slant(azimuth_time, ground_range):
            calls.append((azimuth_time, np.asarray(ground_range)))
            # identity-like conversion, easy to verify
            return np.asarray(ground_range) * 1.5

        return SimpleNamespace(
            raster_info=SimpleNamespace(
                samples=SimpleNamespace(axis=np.arange(50) * 10.0),
                lines=SimpleNamespace(axis=np.arange(40) * 0.002),
            ),
            coordinate_conversions=SimpleNamespace(evaluate_ground_to_slant=evaluate_ground_to_slant),
            calls=calls,
        )

    def test_number_of_blocks_and_indices(self, fake_metadata, metadata_file):
        blocks = build_grd_blocks(fake_metadata, metadata_file)

        # IW1 has 2 bounds, IW2 has 1; empty-name swath and swath without bounds list are skipped
        assert len(blocks) == 3
        assert [b.index for b in blocks] == [0, 1, 2]
        assert [b.swath for b in blocks] == ["IW1", "IW1", "IW2"]

    def test_block_geometry(self, fake_metadata, metadata_file):
        blocks = build_grd_blocks(fake_metadata, metadata_file)

        assert blocks[0].target_block == [0, 0, 20, 25]
        assert blocks[1].target_block == [20, 0, 20, 25]
        assert blocks[2].target_block == [0, 25, 20, 25]

    def test_azimuth_axis_is_sliced(self, fake_metadata, metadata_file):
        blocks = build_grd_blocks(fake_metadata, metadata_file)
        azimuth_axis = fake_metadata.raster_info.lines.axis

        np.testing.assert_array_equal(blocks[0].azimuth_axis, azimuth_axis[0:20])
        np.testing.assert_array_equal(blocks[1].azimuth_axis, azimuth_axis[20:40])
        np.testing.assert_array_equal(blocks[2].azimuth_axis, azimuth_axis[0:20])

    def test_range_axis_is_slant_time(self, fake_metadata, metadata_file):
        blocks = build_grd_blocks(fake_metadata, metadata_file)
        ground_axis = fake_metadata.raster_info.samples.axis

        for block, (first, last) in zip(blocks, [(0, 24), (0, 24), (25, 49)], strict=True):
            expected = 2 * (ground_axis[first : last + 1] * 1.5) / C
            np.testing.assert_allclose(block.range_axis, expected)
            assert block.range_axis.size == block.n_samples

    def test_conversion_called_with_central_azimuth_time(self, fake_metadata, metadata_file):
        build_grd_blocks(fake_metadata, metadata_file)

        azimuth_axis = fake_metadata.raster_info.lines.axis
        ground_axis = fake_metadata.raster_info.samples.axis

        assert len(fake_metadata.calls) == 3
        # (first_line + last_line) // 2 -> 9, 29, 9
        for (az_time, ground_range), (mid, first, last) in zip(
            fake_metadata.calls, [(9, 0, 24), (29, 0, 24), (9, 25, 49)], strict=True
        ):
            assert az_time == azimuth_axis[mid]
            np.testing.assert_array_equal(ground_range, ground_axis[first : last + 1])

    def test_no_swath_merge_returns_empty_list(self, fake_metadata, tmp_path):
        xml = tmp_path / "empty.xml"
        xml.write_text("<product></product>")

        assert build_grd_blocks(fake_metadata, xml) == []
