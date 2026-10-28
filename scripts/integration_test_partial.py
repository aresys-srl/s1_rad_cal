import json
import os
from pathlib import Path

import netCDF4
import numpy as np
from perseo_quality.core.generic_dataclasses import SARRadiometricQuantity
from sct_radiometric_analysis.main import full_average_elevation_profiles_analysis

from s1_rad_cal.config import Config
from s1_rad_cal.main import run

REGISTRY_PATH = "tests/integration_tests/test_registry.json"

if __name__ == "__main__":
    with open(REGISTRY_PATH, "r", encoding="UTF-8") as f_in:
        test_config = json.load(f_in)
    radcal_config = Config()
    radcal_config.corrections.denoising.enabled = True
    os.makedirs("output", exist_ok=True)
    output_path = Path("output")
    run(
        l1_product_path=test_config["partial_processing"]["product"],
        aux_pp1_path=test_config["partial_processing"]["aux_pp1"],
        aux_cal_path=test_config["partial_processing"]["aux_cal"],
        output_path=output_path,
        config=radcal_config,
    )
    output_netcdf_file, output_kpi_file = full_average_elevation_profiles_analysis(
        product=output_path.joinpath("PF"),
        output_radiometric_quantity=SARRadiometricQuantity.GAMMA_NOUGHT,
        output_directory=output_path,
        config=None,
        graphs=False,
    )

    nc = netCDF4.Dataset(output_path.joinpath("AVERAGE_GAMMA_NOUGHT_profiles_PF.nc"))
    nc_ref = netCDF4.Dataset(test_config["partial_processing"]["reference_output"])
    for swath in nc.groups.keys():
        for polarization in nc[swath].groups.keys():
            np.testing.assert_allclose(
                actual=nc[swath][polarization]["radiometric_profiles"][:].data,
                desired=nc_ref[swath][polarization]["radiometric_profiles"][:].data,
                atol=1e-5,
                rtol=1e-5,
            )
