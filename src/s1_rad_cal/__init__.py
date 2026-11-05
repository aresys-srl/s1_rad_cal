# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""
Radiometric Re-Calibration module init
"""

import os
from pathlib import Path

AUX_PP1_DATASET = Path(os.environ.get("AUX_PP1_DATASET", "data/AUX_PP1"))

__version__ = "1.0.0"
