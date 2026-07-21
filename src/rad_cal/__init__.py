# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""
Radiometric Re-Calibration module init
"""

import os

AUX_PP1_DATASET: str | None = os.environ.get("AUX_PP1_DATASET")
GETASSE_DEM_FOLDER: str | None = os.environ.get("GETASSE_DEM_FOLDER")

__version__ = "1.0.0.dev0"
