from pathlib import Path

import matplotlib.pyplot as plt
from eo_products.sentinel1.reader import open_product, read_channel_metadata

from rad_cal.core.angles import compute_terrain_corrected_incidence_angles
from rad_cal.core.common import load_dem_from_sar_times

LIGHT_SPEED = 299792458

product_path = Path(
    r"C:\Users\marco.spadoni\Downloads\S1C_IW_SLC__1SDV_20260606T170556_20260606T170623_007988_0103E5_7451.SAFE"
)
dem = Path(r"C:\projects\marco_utils\getasse_dem\tiles")
n_idx = 8

product = open_product(pf_path=product_path)
footprint = product.footprint
channel_metadata = read_channel_metadata(product.get_files_from_channel_name(product.channels_list[0])[0])

range_times = channel_metadata.raster_info.samples.axis
azimuth_times = channel_metadata.raster_info.lines.axis[0:2000]

dem_area = load_dem_from_sar_times(
    dem=dem,
    trajectory=channel_metadata.orbit,
    range_times=range_times,
    azimuth_times=azimuth_times,
    wavelength=LIGHT_SPEED / channel_metadata.dataset_info.fc_hz,
    look_direction=channel_metadata.dataset_info.side_looking,
)


incidence_angles_dem = compute_terrain_corrected_incidence_angles(
    dem_values=dem_area.values,
    dem_lat_axis=dem_area.lat.values,
    dem_lon_axis=dem_area.lon.values,
    trajectory=channel_metadata.orbit,
    range_times=range_times,
    azimuth_times=azimuth_times,
    radians=False,
)

plt.imshow(incidence_angles_dem)
plt.show()
