# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""Rad-cal CLI"""

import json
from pathlib import Path

import typer

from rad_cal.config import Config, from_toml
from rad_cal.main import run

app = typer.Typer(name="rad-cal", help="Apply radiometric calibration corrections.")

input_option = typer.Option(..., "--input", "-in", help="Path to JSON input file.")
output_option = typer.Option(..., "--output", "-out", help="Path to output folder.")
config_option = typer.Option(None, "--config", "-c", help="Path to the TOML configuration file.")


@app.command()
def process(
    input_file_path: Path = input_option, output_path: Path = output_option, config: Path | None = config_option
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


if __name__ == "__main__":
    app()
