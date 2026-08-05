# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""Unit tests for core functionalities"""

from pathlib import Path

import numpy as np
import pytest

import rad_cal.core.angles as compute_angles
import rad_cal.core.common as angles_common
from rad_cal.core.angles import (
    _look_angles_from_ecef_positions,
    compute_terrain_corrected_look_angles,
    compute_terrain_normal,
)
from rad_cal.core.common import _antimeridian_safe_lon_bounds, _compute_footprint_from_times, load_dem_from_sar_times

from .reference import compute_terrain_normal_numeric


class TestLookAnglesFromEcefPositions:
    def test_raises_on_bad_sensor_shape(self):
        sensor = np.zeros(3)  # missing the leading L dimension
        ground = np.zeros((1, 1, 3))
        with pytest.raises(ValueError, match="sensor_pos_ecef must have shape"):
            _look_angles_from_ecef_positions(sensor, ground)

    def test_raises_on_bad_ground_shape(self):
        sensor = np.zeros((2, 3))
        ground = np.zeros((2, 3))  # missing the M dimension
        with pytest.raises(ValueError, match="ground_pos_ecef must have shape"):
            _look_angles_from_ecef_positions(sensor, ground)

    def test_raises_on_azimuth_dimension_mismatch(self):
        sensor = np.zeros((2, 3))
        ground = np.zeros((3, 1, 3))  # L=3 vs sensor's L=2
        with pytest.raises(ValueError, match="Azimuth dimension mismatch"):
            _look_angles_from_ecef_positions(sensor, ground)

    def test_angles(self, monkeypatch):
        monkeypatch.setattr(
            compute_angles,
            "compute_nadir_from_sensor_positions",
            lambda sensor_positions: np.array([[0.0, 0.0, -1.0]]),
        )
        sensor = np.array([[0.0, 0.0, 100.0]])
        ground = np.array([[[0.0, 0.0, 0.0], [100.0, 0.0, 100.0]]])
        angles = _look_angles_from_ecef_positions(sensor, ground)

        assert angles.shape == (1, 2)
        np.testing.assert_allclose(angles, [[0.0, np.pi / 2]], atol=1e-12)

    def test_multiple_sensor_positions(self, monkeypatch):
        # Two independent azimuth lines, each with its own nadir direction.
        monkeypatch.setattr(
            compute_angles,
            "compute_nadir_from_sensor_positions",
            lambda sensor_positions: np.array([[0.0, 0.0, -1.0], [0.0, -1.0, 0.0]]),
        )
        sensor = np.array([[0.0, 0.0, 100.0], [0.0, 100.0, 0.0]])
        ground = np.array(
            [
                [[0.0, 0.0, 0.0]],
                [[0.0, 0.0, 0.0]],
            ]
        )

        angles = _look_angles_from_ecef_positions(sensor, ground)

        assert angles.shape == (2, 1)
        np.testing.assert_allclose(angles, [[0.0], [0.0]], atol=1e-10)


class TestComputeTerrainCorrectedLookAngles:
    def test_composes_projection_and_look_angles(self, monkeypatch):
        ground_points = (
            np.array(
                [
                    [[0.0, 0.0, 0.0]],
                    [[100.0, 0.0, 0.0]],
                ],
            ),
            None,
        )
        monkeypatch.setattr(
            compute_angles,
            "_geocode_dem_to_sar_raster",
            lambda **kwargs: ground_points,
        )
        monkeypatch.setattr(
            compute_angles,
            "compute_nadir_from_sensor_positions",
            lambda sensor_positions: np.array([[0.0, 0.0, -1.0], [0.0, 0.0, -1.0]]),
        )

        class FakeTrajectory:
            def position(self, times):
                assert len(times) == 2
                return np.array([[0.0, 0.0, 100.0], [100.0, 0.0, 100.0]])

        angles_deg = compute_terrain_corrected_look_angles(
            dem_values=np.zeros((1, 1)),
            dem_lat_axis=np.array([0.0]),
            dem_lon_axis=np.array([0.0]),
            trajectory=FakeTrajectory(),
            range_times=np.array([0.0]),
            azimuth_times=np.array([0.0, 1.0]),
            radians=False,
        )

        assert angles_deg.shape == (2, 1)

    def test_radians_degrees_consistency(self, monkeypatch):
        ground_points = (
            np.array(
                [
                    [[0.0, 0.0, 0.0]],
                    [[100.0, 0.0, 0.0]],
                ],
            ),
            None,
        )
        monkeypatch.setattr(
            compute_angles,
            "_geocode_dem_to_sar_raster",
            lambda **kwargs: ground_points,
        )
        monkeypatch.setattr(
            compute_angles,
            "compute_nadir_from_sensor_positions",
            lambda sensor_positions: np.array([[0.0, 0.0, -1.0], [0.0, 0.0, -1.0]]),
        )

        class FakeTrajectory:
            def position(self, times):
                assert len(times) == 2
                return np.array([[0.0, 0.0, 100.0], [100.0, 0.0, 100.0]])

        angles_deg = compute_terrain_corrected_look_angles(
            dem_values=np.zeros((1, 1)),
            dem_lat_axis=np.array([0.0]),
            dem_lon_axis=np.array([0.0]),
            trajectory=FakeTrajectory(),
            range_times=np.array([0.0]),
            azimuth_times=np.array([0.0, 1.0]),
            radians=False,
        )

        angles_rad = compute_terrain_corrected_look_angles(
            dem_values=np.zeros((1, 1)),
            dem_lat_axis=np.array([0.0]),
            dem_lon_axis=np.array([0.0]),
            trajectory=FakeTrajectory(),
            range_times=np.array([0.0]),
            azimuth_times=np.array([0.0, 1.0]),
            radians=True,
        )
        np.testing.assert_allclose(angles_deg, np.rad2deg(angles_rad), atol=1e-10)


class TestComputeFootprintFromTimes:
    def test_footprint_bounds_and_margins(self, monkeypatch):
        position_calls = []
        velocity_calls = []

        class FakeTrajectory:
            def position(self, times):
                position_calls.append(np.asarray(times).copy())
                return np.zeros((len(times), 3))

            def velocity(self, times):
                velocity_calls.append(np.asarray(times).copy())
                return np.zeros((len(times), 3))

        captured_geocoding_kwargs = {}

        def fake_direct_geocoding(**kwargs):
            captured_geocoding_kwargs.update(kwargs)
            # Two footprint corner points, encoded so that our identity-like
            # xyz2llh fake can read them back as [lat_rad, lon_rad, height].
            return np.array(
                [
                    [np.deg2rad(10.0), np.deg2rad(20.0), 0.0],
                    [np.deg2rad(15.0), np.deg2rad(25.0), 0.0],
                ]
            )

        monkeypatch.setattr(angles_common, "direct_geocoding_monostatic", fake_direct_geocoding)
        monkeypatch.setattr(angles_common, "xyz2llh", lambda ecef: np.asarray(ecef, dtype=float))

        azimuth_times = np.array([100.0, 200.0])
        range_times = np.array([0.001, 0.002])

        footprint = _compute_footprint_from_times(
            range_times=range_times,
            azimuth_times=azimuth_times,
            trajectory=FakeTrajectory(),
            wavelength=0.05,
            doppler_frequency=0.0,
            look_direction="RIGHT",
        )

        start_lat, start_lon, size_lat, size_lon = footprint
        np.testing.assert_allclose([start_lat, start_lon, size_lat, size_lon], [10.0, 20.0, 5.0, 5.0])

        # azimuth margin applied on both ends before calling trajectory.position/velocity
        expected_az = np.array(
            [
                azimuth_times[0] - angles_common.AZIMUTH_MARGIN_SEC,
                azimuth_times[-1] + angles_common.AZIMUTH_MARGIN_SEC,
            ]
        )
        np.testing.assert_allclose(position_calls[0], expected_az)
        np.testing.assert_allclose(velocity_calls[0], expected_az)

        # range margin applied before calling direct_geocoding_monostatic
        expected_rg = [
            range_times[0] - angles_common.RANGE_MARGIN_SEC,
            range_times[-1] + angles_common.RANGE_MARGIN_SEC,
        ]
        np.testing.assert_allclose(captured_geocoding_kwargs["range_times"], expected_rg)
        assert captured_geocoding_kwargs["look_direction"] == "RIGHT"
        assert captured_geocoding_kwargs["wavelength"] == 0.05


class TestLoadDemFromSarTimes:
    def test_footprint_converted_to_roi_and_forwarded(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            angles_common,
            "_compute_footprint_from_times",
            lambda **kwargs: (10.0, 179.0, 5.0, 6.0),  # start_lat, start_lon, size_lat, size_lon
        )

        captured = {}
        sentinel_dem = object()

        def fake_get_dem_roi(**kwargs):
            captured.update(kwargs)
            return sentinel_dem

        monkeypatch.setattr(angles_common, "get_dem_roi", fake_get_dem_roi)

        result = load_dem_from_sar_times(
            dem=str(tmp_path / "dem_tiles"),
            trajectory=object(),
            range_times=np.array([0.0, 1.0]),
            azimuth_times=np.array([0.0, 1.0]),
            look_direction="LEFT",
        )

        assert result is sentinel_dem
        assert captured["lat_start_deg"] == 10.0
        assert captured["lon_start_deg"] == 179.0
        assert captured["lat_size_deg"] == pytest.approx(5.0)
        assert captured["lon_size_deg"] == pytest.approx(6.0)
        assert captured["dem"] == Path(str(tmp_path / "dem_tiles"))

    def test_dem_path_like_input_accepted(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            angles_common,
            "_compute_footprint_from_times",
            lambda **kwargs: (0.0, 0.0, 1.0, 1.0),
        )
        captured = {}
        monkeypatch.setattr(
            angles_common,
            "get_dem_roi",
            lambda **kwargs: captured.update(kwargs) or None,
        )

        load_dem_from_sar_times(
            dem=tmp_path,  # a Path, not a str
            trajectory=object(),
            range_times=np.array([0.0, 1.0]),
            azimuth_times=np.array([0.0, 1.0]),
            look_direction="RIGHT",
        )

        assert captured["dem"] == tmp_path


class TestAntimeridianSafeLonBounds:
    def test_no_crossing_positive_lons(self):
        lon_start, lon_size = _antimeridian_safe_lon_bounds(lon_a_deg=10.0, lon_b_deg=12.0)
        assert lon_start == pytest.approx(10.0)
        assert lon_size == pytest.approx(2.0)

    def test_no_crossing_negative_lons(self):
        lon_start, lon_size = _antimeridian_safe_lon_bounds(lon_a_deg=-50.0, lon_b_deg=-40.0)
        assert lon_start == pytest.approx(-50.0)
        assert lon_size == pytest.approx(10.0)

    def test_no_crossing_straddling_prime_meridian(self):
        # crosses lon=0 but not the antimeridian -> should NOT be treated as wraparound
        lon_start, lon_size = _antimeridian_safe_lon_bounds(lon_a_deg=-5.0, lon_b_deg=5.0)
        assert lon_start == pytest.approx(-5.0)
        assert lon_size == pytest.approx(10.0)

    def test_crossing_antimeridian_matches_get_dem_roi_example(self):
        # mirrors the get_dem_roi(lon=179, lon_size=2) example from the review
        lon_start, lon_size = _antimeridian_safe_lon_bounds(lon_a_deg=179.0, lon_b_deg=-179.0)
        assert lon_start == pytest.approx(179.0)
        assert lon_size == pytest.approx(2.0)

    def test_crossing_is_order_independent(self):
        result_ab = _antimeridian_safe_lon_bounds(lon_a_deg=179.0, lon_b_deg=-179.0)
        result_ba = _antimeridian_safe_lon_bounds(lon_a_deg=-179.0, lon_b_deg=179.0)
        assert result_ab == pytest.approx(result_ba)

    def test_no_crossing_is_order_independent(self):
        result_ab = _antimeridian_safe_lon_bounds(lon_a_deg=10.0, lon_b_deg=12.0)
        result_ba = _antimeridian_safe_lon_bounds(lon_a_deg=12.0, lon_b_deg=10.0)
        assert result_ab == pytest.approx(result_ba)

    def test_identical_lons_returns_zero_size(self):
        lon_start, lon_size = _antimeridian_safe_lon_bounds(lon_a_deg=42.0, lon_b_deg=42.0)
        assert lon_start == pytest.approx(42.0)
        assert lon_size == pytest.approx(0.0)

    def test_wide_crossing_near_antimeridian(self):
        # larger gap across the seam: e.g. 170 and -170 -> wrap arc is 20 deg
        lon_start, lon_size = _antimeridian_safe_lon_bounds(lon_a_deg=170.0, lon_b_deg=-170.0)
        assert lon_start == pytest.approx(170.0)
        assert lon_size == pytest.approx(20.0)

    def test_antipodal_tie_does_not_raise(self):
        # direct_size == wrap_size == 180 -> tie-break branch; just check it's self-consistent
        lon_start, lon_size = _antimeridian_safe_lon_bounds(lon_a_deg=0.0, lon_b_deg=180.0)
        assert lon_size == pytest.approx(180.0)
        assert lon_start in (0.0, 180.0)

    def test_result_reconstructs_the_shorter_arc(self):
        # sanity check: lon_start + lon_size should land on (or wrap to) the other input,
        # confirming the returned arc actually spans the two inputs
        lon_start, lon_size = _antimeridian_safe_lon_bounds(lon_a_deg=179.0, lon_b_deg=-179.0)
        wrapped_end = (lon_start + lon_size + 180.0) % 360.0 - 180.0
        assert wrapped_end == pytest.approx(-179.0)


class TestTerrainNormalComputation:
    @pytest.mark.parametrize(
        "dem_fun",
        [
            lambda lat, lon: 500.0 + 100.0 * np.sin(np.radians(4.0 * lat)),
            lambda lat, lon: 500.0 + 100.0 * np.cos(np.radians(5.0 * lon)),
            lambda lat, lon: 500.0 + 100.0 * np.sin(np.radians(4.0 * lat)) + 80.0 * np.cos(np.radians(5.0 * lon)),
            lambda lat, lon: (
                500.0
                + 100.0 * np.sin(np.radians(4.0 * lat))
                + 80.0 * np.cos(np.radians(5.0 * lon))
                + 40.0 * np.sin(np.radians(3.0 * (lat + lon)))
            ),
        ],
    )
    def test_compute_terrain_normal_matches_numerical(self, dem_fun):
        """Semi-analytical normals should match the numerical reference."""

        lat = np.linspace(40.0, 41.0, 101)
        lon = np.linspace(10.0, 11.0, 151)

        lat_grid, lon_grid = np.meshgrid(lat, lon, indexing="ij")
        dem = dem_fun(lat_grid, lon_grid)

        normal = compute_terrain_normal(dem, lat, lon)
        normal_ref = compute_terrain_normal_numeric(dem, lat, lon)

        # Ignore the outermost pixels, where np.gradient uses one-sided differences.
        sl = np.s_[1:-1, 1:-1]

        dot = np.sum(normal[sl] * normal_ref[sl], axis=-1)
        dot = np.clip(dot, -1.0, 1.0)

        angle_deg = np.degrees(np.arccos(dot))

        assert np.nanmax(angle_deg) < 1e-5

    def test_compute_terrain_normal_raises_for_non_monotonic_longitude(self):
        dem = np.zeros((2, 3))
        lat = np.array([45.0, 46.0])
        lon = np.array([10.0, 9.0, 11.0])

        with pytest.raises(
            ValueError,
            match=(
                r"dem_lon_axis must be monotonic increasing\. "
                r"If it crosses the antimeridian, unwrap it first"
            ),
        ):
            compute_terrain_normal(dem, lat, lon)

    def test_compute_terrain_normal_raises_for_shape_mismatch(self):
        dem = np.zeros((3, 3))
        lat = np.array([45.0, 46.0])
        lon = np.array([10.0, 11.0, 12.0])

        expected = (
            r"dem_values shape \(3, 3\) does not match "
            r"axis lengths \(2, 3\)"
        )

        with pytest.raises(ValueError, match=expected):
            compute_terrain_normal(dem, lat, lon)
