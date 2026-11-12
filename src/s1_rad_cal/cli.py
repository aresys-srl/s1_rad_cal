# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""Rad-cal CLI"""

import json
from pathlib import Path
from typing import Annotated

import typer
from perseo_core.timing import PreciseDateTime

from s1_rad_cal.config import Config, from_toml
from s1_rad_cal.main import run
from s1_rad_cal.weather_maps import download_itu676_era5_weather_data, download_itu676_era5_weather_data_from_product

app = typer.Typer(name="s1-rad-cal", help="Apply radiometric calibration corrections.")

InputOption = Annotated[Path, typer.Option("--input", "-in", help="Path to JSON input file.")]
OutputOption = Annotated[Path, typer.Option("--output", "-out", help="Path to output folder.")]
ConfigOption = Annotated[Path | None, typer.Option("--config", "-c", help="Path to the TOML configuration file.")]


@app.command()
def process(
    input_file_path: InputOption,
    output_path: OutputOption,
    config: ConfigOption = None,
):
    """
    Run radiometric calibration.
    """

    with open(input_file_path, "r", encoding="UTF-8") as f_in:
        input_file_dict = json.load(f_in)

    cfg = from_toml(config) if config is not None else Config()
    run(
        l1_product_path=input_file_dict["l1_product"],
        aux_cal_path=input_file_dict["aux_cal"],
        aux_pp1_path=input_file_dict["aux_pp1"],
        output_path=output_path,
        config=cfg,
    )


@app.command("download-era5")
def download_era5(
    north: Annotated[float, typer.Option("--north", "-n", help="Northern limit in degrees (-90 to 90).")],
    west: Annotated[float, typer.Option("--west", "-w", help="Western limit in degrees (-180 to 180).")],
    south: Annotated[float, typer.Option("--south", "-s", help="Southern limit in degrees (-90 to 90).")],
    east: Annotated[float, typer.Option("--east", "-e", help="Eastern limit in degrees (-180 to 180).")],
    time: Annotated[
        str,
        typer.Option("--time", "-t", help="UTC time, e.g. '2024-05-17 06:30:00.000'. Only the hour is used by ERA5."),
    ],
    output_path: OutputOption,
):
    """
    Download ERA5 weather data (P, T, rho, Td) over a geographic bounding box.
    """
    output_path.mkdir(parents=True, exist_ok=True)

    try:
        acq_time = PreciseDateTime.from_utc_string(time)
    except Exception as exc:
        raise typer.BadParameter(f"Cannot parse time '{time}': {exc}", param_hint="--time") from exc

    try:
        download_itu676_era5_weather_data(
            north=north, west=west, south=south, east=east, time=acq_time, output_folder=output_path
        )
    except ValueError as exc:  # invalid bounding box
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(f"Weather data saved to {output_path / 'era5_weather_region.nc'}")


@app.command("download-era5-from-product")
def download_era5_from_product(
    product_path: Annotated[
        Path,
        typer.Option("--product", "-p", exists=True, help="Path to Sentinel-1 Level 1 SAFE product."),
    ],
    output_path: OutputOption,
):
    """
    Download ERA5 weather data covering the acquisition time and footprint of a Sentinel-1 product.
    """
    output_path.mkdir(parents=True, exist_ok=True)

    download_itu676_era5_weather_data_from_product(product_path=product_path, output_folder=output_path)

    typer.echo(f"Weather data saved to {output_path / 'era5_weather_dataset.nc'}")


if __name__ == "__main__":
    app()
