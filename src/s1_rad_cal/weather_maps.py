# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""
Weather maps utilities
----------------------
"""

import math
import tempfile
from pathlib import Path

import cdsapi
import numpy as np
import xarray as xr
from eo_products.sentinel1.reader import open_product
from perseo_core.timing import PreciseDateTime

ERA5_RESOLUTION_DEG = 0.25

REQUIRED_VARS = {
    "P": "hPa",
    "T": "K",
    "rho": "g m-3",
    "Td": "K",
}

REQUIRED_COORDS = ["latitude", "longitude"]

LIMITS = {
    "P": (500.0, 1100.0),
    "T": (180.0, 330.0),
    "Td": (180.0, 330.0),
    "rho": (0.0, 40.0),
}


def _validate_weather_dataset_structure(ds: xr.Dataset) -> None:
    for var, expected_unit in REQUIRED_VARS.items():
        if var not in ds:
            raise ValueError(f"Missing variable '{var}'")

        actual_unit = ds[var].attrs.get("units")
        if actual_unit != expected_unit:
            raise ValueError(f"{var}: expected units '{expected_unit}', got '{actual_unit}'")

    for coord in REQUIRED_COORDS:
        if coord not in ds.coords:
            raise ValueError(f"Missing coordinate '{coord}'")


def _validate_dewpoint_temperature_consistency(ds: xr.Dataset) -> None:
    if np.any(ds["Td"] > ds["T"] + 0.1):
        raise ValueError("Found Td > T")


def _validate_physical_ranges(ds: xr.Dataset) -> None:

    for var, (vmin, vmax) in LIMITS.items():
        values = ds[var].values

        if np.isnan(values).all():
            raise ValueError(f"{var} contains only NaNs")

        actual_min = np.nanmin(values)
        actual_max = np.nanmax(values)

        if actual_min < vmin or actual_max > vmax:
            raise ValueError(f"{var} outside expected range [{vmin}, {vmax}] (got [{actual_min}, {actual_max}])")


def validate_itu676_weather_dataset(ds: xr.Dataset) -> None:
    """Validate weather dataset"""

    _validate_weather_dataset_structure(ds)
    _validate_physical_ranges(ds)
    _validate_dewpoint_temperature_consistency(ds)


def download_itu676_era5_weather_data(
    north: float,
    west: float,
    south: float,
    east: float,
    time: PreciseDateTime,
    output_folder: Path,
) -> xr.Dataset:
    """Download ERA5 weather data over a geographic bounding box.

    Parameters
    ----------
    north, west, south, east : float
        Bounding box limits in degrees.
        west/east use longitudes from -180 to 180.
    time : PreciseDateTime
        Time as PreciseDateTime
    output_folder : Path
        path where to store the weather map

    Returns
    -------
    xarray.Dataset
        Gridded data with coordinates latitude and longitude.

        P       : surface pressure [hPa]
        T       : 2 m temperature [K]
        rho     : water vapour density [g/m^3]
        Td      : 2 m dewpoint temperature [K]
    """
    if not (-90 <= south <= north <= 90):
        raise ValueError("Require -90 <= south <= north <= 90.")
    if not (-180 <= west <= 180 and -180 <= east <= 180):
        raise ValueError("Longitudes must be between -180 and 180.")
    if west > east:
        raise ValueError("west must be <= east; split boxes crossing the antimeridian.")

    variables = [
        "2m_temperature",
        "2m_dewpoint_temperature",
        "surface_pressure",
    ]

    request = {
        "product_type": ["reanalysis"],
        "variable": variables,
        "year": [f"{time.year:04d}"],
        "month": [f"{time.month:02d}"],
        "day": [f"{time.day_of_the_month:02d}"],
        "time": [f"{int(time.hour_of_day):02d}:00"],
        "area": [
            math.ceil(north / ERA5_RESOLUTION_DEG) * ERA5_RESOLUTION_DEG,
            math.floor(west / ERA5_RESOLUTION_DEG) * ERA5_RESOLUTION_DEG,
            math.floor(south / ERA5_RESOLUTION_DEG) * ERA5_RESOLUTION_DEG,
            math.ceil(east / ERA5_RESOLUTION_DEG) * ERA5_RESOLUTION_DEG,
        ],
        "data_format": "netcdf",
        "download_format": "unarchived",
    }

    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "era5.nc")

        cdsapi.Client().retrieve(
            "reanalysis-era5-single-levels",
            request,
            path,
        )

        with xr.open_dataset(path, engine="netcdf4") as ds:
            ds = ds.load()

    # Handle ERA5 short names and descriptive variable names.
    aliases = {
        "t2m": ["t2m", "2m_temperature"],
        "d2m": ["d2m", "2m_dewpoint_temperature"],
        "sp": ["sp", "surface_pressure"],
    }

    def get_variable(short_name):
        for name in aliases[short_name]:
            if name in ds.data_vars:
                return ds[name]
        raise KeyError(f"Missing {short_name}. Available variables: {list(ds.data_vars)}")

    T = get_variable("t2m")
    Td = get_variable("d2m")
    P_pa = get_variable("sp")

    P = P_pa / 100.0

    # Water vapour density from dewpoint.
    # Magnus formula; dewpoint in Celsius, vapour pressure in hPa.
    Td_c = Td - 273.15
    e_hpa = 6.112 * np.exp(17.67 * Td_c / (Td_c + 243.5))

    # rho in g/m^3, temperature in K.
    rho = 216.7 * e_hpa / T

    result = xr.Dataset(
        {
            "P": P,
            "T": T,
            "rho": rho,
            "Td": Td,
        }
    )

    result["P"].attrs["units"] = "hPa"
    result["T"].attrs["units"] = "K"
    result["rho"].attrs["units"] = "g m-3"
    result["Td"].attrs["units"] = "K"

    result.attrs["time_utc"] = time.isoformat()
    result.attrs["source"] = "Copernicus ERA5 reanalysis"

    result.to_netcdf(output_folder.joinpath("weather_dataset.nc"))

    return result


def download_itu676_era5_weather_data_from_product(product_path: Path, output_folder: Path) -> xr.Dataset:
    """Download ERA5 weather data covering time and space defined by the product's acquisition time and footprint

    Parameters
    ----------
    product_path : Path
        Path to Sentinel-1 Level 1 SAFE product
    output_folder : Path
        Output folder where weather data .nc is saved

    Returns
    -------
    xr.Dataset
        Weather data as Xarray Dataset
    """
    prod = open_product(product_path)
    footprint = prod.footprint
    acq_time = prod.acquisition_time
    weather = download_itu676_era5_weather_data(
        south=footprint[0],
        north=footprint[1],
        west=footprint[2],
        east=footprint[3],
        time=acq_time,
        output_folder=output_folder,
    )
    return weather
