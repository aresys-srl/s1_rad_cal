# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""Rad-cal CLI"""

from pathlib import Path

import typer

from rad_cal.config import from_toml
from rad_cal.main import run

app = typer.Typer(name="rad-cal", help="Apply radiometric calibration corrections.")

config_option = typer.Option(..., "--config", "-c", help="Path to the TOML configuration file.")


@app.command()
def process(config: Path = config_option):
    """
    Run radiometric calibration.
    """

    cfg = from_toml(config)
    run(cfg)


if __name__ == "__main__":
    app()
