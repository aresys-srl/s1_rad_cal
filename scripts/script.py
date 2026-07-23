from pathlib import Path

from rad_cal.main import run

if __name__ == "__main__":
    l1_product_path = Path(
        r"C:\Users\marco.spadoni\Downloads\S1C_IW_SLC__1SSV_20260625T083150_20260625T083221_008259_01054C_3F3E.SAFE"
    )
    aux_pp1_path_new = Path(r"C:\Users\marco.spadoni\Downloads\S1D_AUX_PP1_V20260319T000000_G20260603T073733.SAFE")
    aux_cal_path_new = Path(r"C:\Users\marco.spadoni\Downloads\S1D_AUX_CAL_V20260319T000000_G20260603T113322.SAFE")
    run(
        l1_product_path=l1_product_path,
        aux_cal_path_new=aux_cal_path_new,
        aux_pp1_path_new=aux_pp1_path_new,
        output_path=r"C:\Users\marco.spadoni\Downloads",
    )
