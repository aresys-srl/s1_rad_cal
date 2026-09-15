from rad_cal.config import from_toml
from rad_cal.main import run

if __name__ == "__main__":
    run(
        l1_product_path="C:/Users/marco.spadoni/Downloads/S1C_IW_SLC__1SDV_20260606T170556_20260606T170623_007988_0103E5_7451.SAFE",
        aux_cal_path="C:/Users/marco.spadoni/Desktop/rad-cal/S1C/S1C_AUX_CAL_V20250427T000000_G20260604T133157.SAFE",
        aux_pp1_path="C:/Users/marco.spadoni/Desktop/rad-cal/S1C/S1C_AUX_PP1_V20250224T000000_G20250521T131402.SAFE",
        output_path="C:/Users/marco.spadoni/Downloads/pf_temp",
        config=from_toml("C:/projects/rad-cal/scripts/config.toml"),
    )
