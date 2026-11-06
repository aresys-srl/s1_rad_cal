# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""Unit tests weather maps"""

import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import xarray as xr

import s1_rad_cal.weather_maps as wm


def make_valid_dataset(shape=(3, 4)) -> xr.Dataset:
    """Dataset that satisfies every validation rule."""
    lat = np.linspace(44.0, 45.0, shape[0])
    lon = np.linspace(8.0, 9.0, shape[1])
    dims = ("latitude", "longitude")

    def var(value, units):
        return xr.DataArray(np.full(shape, value, dtype=float), dims=dims, attrs={"units": units})

    return xr.Dataset(
        {
            "P": var(1013.0, "hPa"),
            "T": var(290.0, "K"),
            "Td": var(285.0, "K"),
            "rho": var(10.0, "g m-3"),
        },
        coords={"latitude": lat, "longitude": lon},
    )


def make_time(year=2024, month=3, day=7, hour=5.0):
    """Minimal stand-in for PreciseDateTime (only the used attributes)."""
    return SimpleNamespace(
        year=year,
        month=month,
        day_of_the_month=day,
        hour_of_day=hour,
        isoformat=lambda: f"{year:04d}-{month:02d}-{day:02d}T{int(hour):02d}:00:00",
    )


def make_era5_raw_dataset(descriptive_names: bool = False) -> xr.Dataset:
    """Raw dataset as returned by CDS (surface pressure in Pa)."""
    lat = np.array([44.0, 44.25, 44.5])
    lon = np.array([8.0, 8.25, 8.5, 8.75])
    shape = (len(lat), len(lon))
    dims = ("latitude", "longitude")
    names = (
        ("2m_temperature", "2m_dewpoint_temperature", "surface_pressure") if descriptive_names else ("t2m", "d2m", "sp")
    )
    return xr.Dataset(
        {
            names[0]: (dims, np.full(shape, 290.0)),
            names[1]: (dims, np.full(shape, 283.15)),
            names[2]: (dims, np.full(shape, 101325.0)),
        },
        coords={"latitude": lat, "longitude": lon},
    )


def download(tmp_path, **overrides) -> xr.Dataset:
    """Call the download function with sensible defaults."""
    kwargs = dict(north=45, west=8, south=44, east=9, time=make_time(), output_folder=tmp_path)
    kwargs.update(overrides)
    return wm.download_itu676_era5_weather_data(**kwargs)


@pytest.fixture
def valid_ds() -> xr.Dataset:
    return make_valid_dataset()


@pytest.fixture
def fake_cds(monkeypatch):
    """Patch cdsapi.Client; the fake `retrieve` writes a NetCDF file to the requested path.

    The returned object records the calls and allows swapping the dataset to be written.
    """
    state = SimpleNamespace(
        dataset=make_era5_raw_dataset(),
        calls=[],
    )

    class FakeClient:
        def retrieve(self, name, request, target):
            state.calls.append({"name": name, "request": request, "target": target})
            state.dataset.to_netcdf(target)

    monkeypatch.setattr(wm.cdsapi, "Client", FakeClient)
    return state


class TestValidateWeatherDatasetStructure:
    def test_valid_dataset_passes(self, valid_ds):
        wm._validate_weather_dataset_structure(valid_ds)

    @pytest.mark.parametrize("missing", list(wm.REQUIRED_VARS))
    def test_missing_variable_raises(self, valid_ds, missing):
        ds = valid_ds.drop_vars(missing)
        with pytest.raises(ValueError, match=f"Missing variable '{missing}'"):
            wm._validate_weather_dataset_structure(ds)

    @pytest.mark.parametrize("var", list(wm.REQUIRED_VARS))
    def test_wrong_units_raises(self, valid_ds, var):
        valid_ds[var].attrs["units"] = "wrong"
        with pytest.raises(ValueError, match=f"{var}: expected units"):
            wm._validate_weather_dataset_structure(valid_ds)

    def test_missing_units_attribute_raises(self, valid_ds):
        del valid_ds["T"].attrs["units"]
        with pytest.raises(ValueError, match="got 'None'"):
            wm._validate_weather_dataset_structure(valid_ds)

    @pytest.mark.parametrize("coord", wm.REQUIRED_COORDS)
    def test_missing_coordinate_raises(self, valid_ds, coord):
        ds = valid_ds.drop_vars(coord)
        with pytest.raises(ValueError, match=f"Missing coordinate '{coord}'"):
            wm._validate_weather_dataset_structure(ds)


class TestValidatePhysicalRanges:
    def test_valid_dataset_passes(self, valid_ds):
        wm._validate_physical_ranges(valid_ds)

    def test_boundaries_are_inclusive(self, valid_ds):
        for var, (vmin, vmax) in wm.LIMITS.items():
            valid_ds[var].values[0, 0] = vmin
            valid_ds[var].values[0, 1] = vmax
        wm._validate_physical_ranges(valid_ds)

    @pytest.mark.parametrize("var", list(wm.LIMITS))
    def test_all_nan_raises(self, valid_ds, var):
        valid_ds[var].values[:] = np.nan
        with pytest.raises(ValueError, match=f"{var} contains only NaNs"):
            wm._validate_physical_ranges(valid_ds)

    @pytest.mark.parametrize("var", list(wm.LIMITS))
    def test_below_min_raises(self, valid_ds, var):
        valid_ds[var].values[0, 0] = wm.LIMITS[var][0] - 1.0
        with pytest.raises(ValueError, match=f"{var} outside expected range"):
            wm._validate_physical_ranges(valid_ds)

    @pytest.mark.parametrize("var", list(wm.LIMITS))
    def test_above_max_raises(self, valid_ds, var):
        valid_ds[var].values[0, 0] = wm.LIMITS[var][1] + 1.0
        with pytest.raises(ValueError, match=f"{var} outside expected range"):
            wm._validate_physical_ranges(valid_ds)

    def test_partial_nans_are_ignored(self, valid_ds):
        valid_ds["T"].values[0, 0] = np.nan
        wm._validate_physical_ranges(valid_ds)


class TestValidateDewpointTemperatureConsistency:
    def test_dewpoint_lower_than_temperature_passes(self, valid_ds):
        wm._validate_dewpoint_temperature_consistency(valid_ds)

    def test_dewpoint_equal_to_temperature_passes(self, valid_ds):
        valid_ds["Td"].values[:] = valid_ds["T"].values
        wm._validate_dewpoint_temperature_consistency(valid_ds)

    def test_dewpoint_within_tolerance_passes(self, valid_ds):
        valid_ds["Td"].values[0, 0] = valid_ds["T"].values[0, 0] + 0.05
        wm._validate_dewpoint_temperature_consistency(valid_ds)

    def test_dewpoint_above_temperature_raises(self, valid_ds):
        valid_ds["Td"].values[1, 1] = valid_ds["T"].values[1, 1] + 1.0
        with pytest.raises(ValueError, match="Td > T"):
            wm._validate_dewpoint_temperature_consistency(valid_ds)


class TestValidateItu676WeatherDataset:
    def test_valid_dataset_passes(self, valid_ds):
        wm.validate_itu676_weather_dataset(valid_ds)

    def test_calls_all_checks_in_order(self, monkeypatch, valid_ds):
        calls = []
        monkeypatch.setattr(wm, "_validate_weather_dataset_structure", lambda ds: calls.append("structure"))
        monkeypatch.setattr(wm, "_validate_physical_ranges", lambda ds: calls.append("ranges"))
        monkeypatch.setattr(wm, "_validate_dewpoint_temperature_consistency", lambda ds: calls.append("dewpoint"))

        wm.validate_itu676_weather_dataset(valid_ds)

        assert calls == ["structure", "ranges", "dewpoint"]

    def test_structure_error_has_priority(self, valid_ds):
        ds = valid_ds.drop_vars("P")
        ds["T"].values[:] = 1000.0  # would also fail the range check
        with pytest.raises(ValueError, match="Missing variable 'P'"):
            wm.validate_itu676_weather_dataset(ds)

    def test_range_error_comes_before_dewpoint_error(self, valid_ds):
        valid_ds["P"].values[0, 0] = 2000.0
        valid_ds["Td"].values[:] = valid_ds["T"].values + 5.0
        with pytest.raises(ValueError, match="P outside expected range"):
            wm.validate_itu676_weather_dataset(valid_ds)


class TestDownloadInputValidation:
    @pytest.mark.parametrize(
        "kwargs, match",
        [
            (dict(north=45, south=46, west=8, east=9), "south <= north"),  # south > north
            (dict(north=91, south=44, west=8, east=9), "south <= north"),  # north out of range
            (dict(north=45, south=-91, west=8, east=9), "south <= north"),  # south out of range
            (dict(north=45, south=44, west=-181, east=9), "Longitudes"),
            (dict(north=45, south=44, west=8, east=181), "Longitudes"),
            (dict(north=45, south=44, west=10, east=9), "west must be <= east"),
        ],
    )
    def test_invalid_bounds_raise(self, kwargs, match, tmp_path, fake_cds):
        with pytest.raises(ValueError, match=match):
            download(tmp_path, **kwargs)
        assert fake_cds.calls == []


class TestDownloadRequest:
    def test_request_content(self, tmp_path, fake_cds):
        download(tmp_path, time=make_time(2024, 3, 7, 5.0), north=45.1, west=8.1, south=44.9, east=9.3)

        assert len(fake_cds.calls) == 1
        call = fake_cds.calls[0]
        req = call["request"]

        assert call["name"] == "reanalysis-era5-single-levels"
        assert req["product_type"] == ["reanalysis"]
        assert req["variable"] == ["2m_temperature", "2m_dewpoint_temperature", "surface_pressure"]
        assert req["year"] == ["2024"]
        assert req["month"] == ["03"]
        assert req["day"] == ["07"]
        assert req["time"] == ["05:00"]
        assert req["data_format"] == "netcdf"
        assert req["download_format"] == "unarchived"

    def test_area_is_snapped_outwards_to_era5_grid(self, tmp_path, fake_cds):
        download(tmp_path, north=45.1, west=8.1, south=44.9, east=9.3)
        # [north, west, south, east] expanded to the 0.25 deg grid
        assert fake_cds.calls[0]["request"]["area"] == [45.25, 8.0, 44.75, 9.5]

    def test_area_already_on_grid_is_unchanged(self, tmp_path, fake_cds):
        download(tmp_path, north=45.0, west=8.0, south=44.0, east=9.0)
        assert fake_cds.calls[0]["request"]["area"] == [45.0, 8.0, 44.0, 9.0]

    def test_area_contains_requested_box(self, tmp_path, fake_cds):
        north, west, south, east = 45.07, -3.33, 44.61, -2.01
        download(tmp_path, north=north, west=west, south=south, east=east)

        a_north, a_west, a_south, a_east = fake_cds.calls[0]["request"]["area"]
        assert a_north >= north and a_south <= south
        assert a_west <= west and a_east >= east
        for value in (a_north, a_west, a_south, a_east):
            ratio = value / wm.ERA5_RESOLUTION_DEG
            assert math.isclose(ratio, round(ratio))

    @pytest.mark.parametrize(
        "hour, expected",
        [(0.0, "00:00"), (9.0, "09:00"), (23.0, "23:00"), (13.7, "13:00")],
    )
    def test_hour_formatting_truncates_to_hour(self, hour, expected, tmp_path, fake_cds):
        download(tmp_path, time=make_time(hour=hour))
        assert fake_cds.calls[0]["request"]["time"] == [expected]


class TestDownloadOutput:
    def test_returns_expected_variables_and_units(self, tmp_path, fake_cds):
        result = download(tmp_path)

        assert set(result.data_vars) == {"P", "T", "rho", "Td"}
        for var, unit in wm.REQUIRED_VARS.items():
            assert result[var].attrs["units"] == unit
        assert "latitude" in result.coords and "longitude" in result.coords

    def test_converts_pressure_pa_to_hpa(self, tmp_path, fake_cds):
        result = download(tmp_path)
        np.testing.assert_allclose(result["P"].values, 1013.25)

    def test_temperatures_are_unchanged(self, tmp_path, fake_cds):
        result = download(tmp_path)
        np.testing.assert_allclose(result["T"].values, 290.0)
        np.testing.assert_allclose(result["Td"].values, 283.15)

    def test_water_vapour_density_from_magnus_formula(self, tmp_path, fake_cds):
        result = download(tmp_path)

        td_c = 283.15 - 273.15
        e_hpa = 6.112 * math.exp(17.67 * td_c / (td_c + 243.5))
        expected_rho = 216.7 * e_hpa / 290.0

        np.testing.assert_allclose(result["rho"].values, expected_rho, rtol=1e-9)
        # sanity: ~9.4 g/m^3 for a 10 degC dew point
        assert 9.0 < expected_rho < 10.0

    def test_result_passes_validation(self, tmp_path, fake_cds):
        wm.validate_itu676_weather_dataset(download(tmp_path))

    def test_sets_global_attributes(self, tmp_path, fake_cds):
        result = download(tmp_path, time=make_time(2024, 3, 7, 5.0))
        assert result.attrs["time_utc"] == "2024-03-07T05:00:00"
        assert result.attrs["source"] == "Copernicus ERA5 reanalysis"

    def test_writes_netcdf_in_output_folder(self, tmp_path, fake_cds):
        result = download(tmp_path)

        out = tmp_path / "weather_dataset.nc"
        assert out.exists()

        with xr.open_dataset(out) as saved:
            assert set(saved.data_vars) == {"P", "T", "rho", "Td"}
            np.testing.assert_allclose(saved["P"].values, result["P"].values)
            assert saved["P"].attrs["units"] == "hPa"
            assert saved.attrs["source"] == "Copernicus ERA5 reanalysis"

    def test_supports_descriptive_variable_names(self, tmp_path, fake_cds):
        fake_cds.dataset = make_era5_raw_dataset(descriptive_names=True)
        result = download(tmp_path)
        np.testing.assert_allclose(result["P"].values, 1013.25)
        np.testing.assert_allclose(result["T"].values, 290.0)

    def test_missing_variable_raises_keyerror(self, tmp_path, fake_cds):
        fake_cds.dataset = make_era5_raw_dataset().drop_vars("d2m")
        with pytest.raises(KeyError, match="Missing d2m"):
            download(tmp_path)

    def test_temporary_file_is_not_left_in_output_folder(self, tmp_path, fake_cds):
        download(tmp_path)
        assert sorted(p.name for p in tmp_path.iterdir()) == ["weather_dataset.nc"]
        # the file CDS wrote must live outside the output folder (temporary directory)
        assert Path(fake_cds.calls[0]["target"]).parent != tmp_path


class TestDownloadFromProduct:
    def test_forwards_footprint_and_time(self, monkeypatch, tmp_path, valid_ds):
        acq_time = make_time()
        product = SimpleNamespace(
            footprint=(44.0, 45.0, 8.0, 9.0),  # south, north, west, east
            acquisition_time=acq_time,
        )
        opened = []
        monkeypatch.setattr(wm, "open_product", lambda path: opened.append(path) or product)

        captured = {}

        def fake_download(**kwargs):
            captured.update(kwargs)
            return valid_ds

        monkeypatch.setattr(wm, "download_itu676_era5_weather_data", fake_download)

        product_path = tmp_path / "S1A_FAKE.SAFE"
        result = wm.download_itu676_era5_weather_data_from_product(product_path, tmp_path)

        assert opened == [product_path]
        assert result is valid_ds
        assert captured == {
            "south": 44.0,
            "north": 45.0,
            "west": 8.0,
            "east": 9.0,
            "time": acq_time,
            "output_folder": tmp_path,
        }

    def test_end_to_end_with_mocked_cds(self, monkeypatch, tmp_path, fake_cds):
        product = SimpleNamespace(
            footprint=(44.1, 44.9, 8.1, 8.9),
            acquisition_time=make_time(2023, 12, 31, 23.0),
        )
        monkeypatch.setattr(wm, "open_product", lambda path: product)

        result = wm.download_itu676_era5_weather_data_from_product(Path("whatever.SAFE"), tmp_path)

        req = fake_cds.calls[0]["request"]
        assert req["area"] == [45.0, 8.0, 44.0, 9.0]
        assert req["year"] == ["2023"] and req["month"] == ["12"] and req["day"] == ["31"]
        assert req["time"] == ["23:00"]
        wm.validate_itu676_weather_dataset(result)
        assert (tmp_path / "weather_dataset.nc").exists()
