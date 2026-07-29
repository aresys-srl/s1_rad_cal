# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""Unit tests for core functionalities"""

from pathlib import Path

import numpy as np
import pytest

import rad_cal.core.look_angles as look_angles
from rad_cal.core.look_angles import (
    _antimeridian_safe_lon_bounds,
    _compute_footprint_from_times,
    _look_angles_from_ecef_positions,
    compute_terrain_corrected_look_angles,
    load_dem_from_sar_times,
    project_dem_to_raster,
)


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

    def test_angles_radians(self, monkeypatch):
        monkeypatch.setattr(
            look_angles,
            "compute_nadir_from_sensor_positions",
            lambda sensor_positions: np.array([[0.0, 0.0, -1.0]]),
        )
        sensor = np.array([[0.0, 0.0, 100.0]])
        ground = np.array([[[0.0, 0.0, 0.0], [100.0, 0.0, 100.0]]])
        angles = _look_angles_from_ecef_positions(sensor, ground, radians=True)

        assert angles.shape == (1, 2)
        np.testing.assert_allclose(angles, [[0.0, np.pi / 2]], atol=1e-12)

    def test_angles_degrees(self, monkeypatch):
        monkeypatch.setattr(
            look_angles,
            "compute_nadir_from_sensor_positions",
            lambda sensor_positions: np.array([[0.0, 0.0, -1.0]]),
        )
        sensor = np.array([[0.0, 0.0, 100.0]])
        ground = np.array([[[0.0, 0.0, 0.0], [100.0, 0.0, 100.0]]])

        angles = _look_angles_from_ecef_positions(sensor, ground, radians=False)

        np.testing.assert_allclose(angles, [[0.0, 90.0]], atol=1e-12)

    def test_radian_degree_consistency(self):
        sensor = np.array([[0.0, 100.0, 100.0]])
        ground = np.array([[[0.0, 0.0, 0.0], [100.0, 0.0, 100.0]]])
        rad = _look_angles_from_ecef_positions(sensor, ground)
        deg = _look_angles_from_ecef_positions(
            sensor,
            ground,
            radians=False,
        )
        np.testing.assert_allclose(np.rad2deg(rad), deg)

    def test_multiple_sensor_positions(self, monkeypatch):
        # Two independent azimuth lines, each with its own nadir direction.
        monkeypatch.setattr(
            look_angles,
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

        angles = _look_angles_from_ecef_positions(sensor, ground, radians=False)

        assert angles.shape == (2, 1)
        np.testing.assert_allclose(angles, [[0.0], [0.0]], atol=1e-10)


class TestProjectDemToRaster:
    def test_raises_on_dem_axis_shape_mismatch(self):
        dem_values = np.zeros((2, 3))
        lat_axis = np.array([0.0, 1.0])
        lon_axis = np.array([0.0, 1.0])  # wrong length: DEM has 3 lon samples
        with pytest.raises(ValueError, match="Mismatch between DEM and latitude/longitude axis"):
            project_dem_to_raster(
                dem_values=dem_values,
                dem_lat_axis=lat_axis,
                dem_lon_axis=lon_axis,
                trajectory=object(),
                range_times=np.array([0.0, 1.0]),
                azimuth_times=np.array([0.0, 1.0]),
            )

    def test_grid_mapping_and_interpolation(self, monkeypatch):
        """
        Build a 2x2 DEM whose 4 points are placed (via a fully-controlled fake
        ``inverse_geocoding_monostatic``) exactly on the 4 nodes of a 2x2
        azimuth/range raster grid, so bilinear interpolation should reproduce
        each DEM point's (fake) ECEF coordinate exactly at the corresponding
        grid node.
        """
        dem_lat_axis = np.array([0.0, 1.0])
        dem_lon_axis = np.array([0.0, 2.0])
        dem_values = np.array([[0.0, 10.0], [20.0, 30.0]])  # heights

        # Identity-like stand-in for llh2xyz: "ecef" == [lat_rad, lon_rad, height]
        monkeypatch.setattr(look_angles, "llh2xyz", lambda llh: np.asarray(llh, dtype=float))

        # DEM points are ravelled (indexing="ij") in this order:
        #   0: (lat=0, lon=0, h=0)   1: (lat=0, lon=2, h=10)
        #   2: (lat=1, lon=0, h=20)  3: (lat=1, lon=2, h=30)
        # Place them exactly at the 4 raster grid nodes below.
        fake_az_time = np.array([10.0, 10.0, 11.0, 11.0])
        fake_rg_time = np.array([100.0, 101.0, 100.0, 101.0])

        def fake_inverse_geocoding(trajectory, ground_points, doppler_frequencies, wavelength, az_initial_time_guesses):
            assert ground_points.shape == (4, 3)
            return fake_az_time, fake_rg_time

        monkeypatch.setattr(look_angles, "inverse_geocoding_monostatic", fake_inverse_geocoding)

        azimuth_times = np.array([10.0, 11.0])
        range_times = np.array([100.0, 101.0])

        ecef_grid = project_dem_to_raster(
            dem_values=dem_values,
            dem_lat_axis=dem_lat_axis,
            dem_lon_axis=dem_lon_axis,
            trajectory=object(),  # unused directly; only forwarded
            range_times=range_times,
            azimuth_times=azimuth_times,
        )

        assert ecef_grid.shape == (2, 2, 3)

        expected = np.array(
            [
                [
                    [np.deg2rad(0.0), np.deg2rad(0.0), 0.0],
                    [np.deg2rad(0.0), np.deg2rad(2.0), 10.0],
                ],
                [
                    [np.deg2rad(1.0), np.deg2rad(0.0), 20.0],
                    [np.deg2rad(1.0), np.deg2rad(2.0), 30.0],
                ],
            ]
        )
        np.testing.assert_allclose(ecef_grid, expected, atol=1e-8)

    def test_forwards_doppler_and_wavelength(self, monkeypatch):
        """Ensure doppler_frequency/wavelength are forwarded, not silently dropped."""
        dem_lat_axis = np.array([0.0, 1.0])
        dem_lon_axis = np.array([0.0, 1.0])
        dem_values = np.zeros((2, 2))

        monkeypatch.setattr(look_angles, "llh2xyz", lambda llh: np.asarray(llh, dtype=float))

        captured = {}

        def fake_inverse_geocoding(trajectory, ground_points, doppler_frequencies, wavelength, az_initial_time_guesses):
            captured["doppler_frequencies"] = doppler_frequencies
            captured["wavelength"] = wavelength
            # Spread the 4 DEM points across the 2x2 raster grid nodes so the
            # triangulation is non-degenerate (points can't all coincide).
            return np.array([0.0, 0.0, 1.0, 1.0]), np.array([0.0, 1.0, 0.0, 1.0])

        monkeypatch.setattr(look_angles, "inverse_geocoding_monostatic", fake_inverse_geocoding)

        project_dem_to_raster(
            dem_values=dem_values,
            dem_lat_axis=dem_lat_axis,
            dem_lon_axis=dem_lon_axis,
            trajectory=object(),
            range_times=np.array([0.0, 1.0]),
            azimuth_times=np.array([0.0, 1.0]),
            doppler_frequency=1234.5,
            wavelength=0.03,
        )

        assert captured["doppler_frequencies"] == 1234.5
        assert captured["wavelength"] == 0.03


class TestComputeTerrainCorrectedLookAngles:
    def test_composes_projection_and_look_angles(self, monkeypatch):
        ground_points = np.array(
            [
                [[0.0, 0.0, 0.0]],
                [[100.0, 0.0, 0.0]],
            ]
        )
        monkeypatch.setattr(
            look_angles,
            "project_dem_to_raster",
            lambda **kwargs: ground_points,
        )
        monkeypatch.setattr(
            look_angles,
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

        monkeypatch.setattr(look_angles, "direct_geocoding_monostatic", fake_direct_geocoding)
        monkeypatch.setattr(look_angles, "xyz2llh", lambda ecef: np.asarray(ecef, dtype=float))

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
                azimuth_times[0] - look_angles.AZIMUTH_MARGIN_SEC,
                azimuth_times[-1] + look_angles.AZIMUTH_MARGIN_SEC,
            ]
        )
        np.testing.assert_allclose(position_calls[0], expected_az)
        np.testing.assert_allclose(velocity_calls[0], expected_az)

        # range margin applied before calling direct_geocoding_monostatic
        expected_rg = [
            range_times[0] - look_angles.RANGE_MARGIN_SEC,
            range_times[-1] + look_angles.RANGE_MARGIN_SEC,
        ]
        np.testing.assert_allclose(captured_geocoding_kwargs["range_times"], expected_rg)
        assert captured_geocoding_kwargs["look_direction"] == "RIGHT"
        assert captured_geocoding_kwargs["wavelength"] == 0.05


class TestLoadDemFromSarTimes:
    def test_footprint_converted_to_roi_and_forwarded(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            look_angles,
            "_compute_footprint_from_times",
            lambda **kwargs: (10.0, 179.0, 5.0, 6.0),  # start_lat, start_lon, size_lat, size_lon
        )

        captured = {}
        sentinel_dem = object()

        def fake_get_dem_roi(**kwargs):
            captured.update(kwargs)
            return sentinel_dem

        monkeypatch.setattr(look_angles, "get_dem_roi", fake_get_dem_roi)

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
            look_angles,
            "_compute_footprint_from_times",
            lambda **kwargs: (0.0, 0.0, 1.0, 1.0),
        )
        captured = {}
        monkeypatch.setattr(
            look_angles,
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
