from rad_cal.config import from_toml
from rad_cal.main import run

if __name__ == "__main__":
    run(config=from_toml("C:/projects/rad-cal/scripts/config.toml"))
