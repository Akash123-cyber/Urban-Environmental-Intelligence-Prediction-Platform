import math
from typing import Optional


def compute_sub_index(conc: float, breakpoints: list[tuple[float, float, int, int]]) -> Optional[int]:
    if conc is None or math.isnan(conc) or conc < 0:
        return None
    for bp_low, bp_high, i_low, i_high in breakpoints:
        if bp_low <= conc <= bp_high:
            # Linear interpolation formula
            return int(round(((i_high - i_low) / (bp_high - bp_low)) * (conc - bp_low) + i_low))
    # Above max breakpoint
    if conc > breakpoints[-1][1]:
        return breakpoints[-1][3]
    return None


# Indian National Air Quality Index (CPCB) Breakpoints
PM25_BREAKPOINTS = [
    (0, 30, 0, 50),
    (31, 60, 51, 100),
    (61, 90, 101, 200),
    (91, 120, 201, 300),
    (121, 250, 301, 400),
    (251, 500, 401, 500),
]

PM10_BREAKPOINTS = [
    (0, 50, 0, 50),
    (51, 100, 51, 100),
    (101, 250, 101, 200),
    (251, 350, 201, 300),
    (351, 430, 301, 400),
    (431, 600, 401, 500),
]


def calculate_aqi(pm25: Optional[float], pm10: Optional[float]) -> Optional[int]:
    si_pm25 = compute_sub_index(pm25, PM25_BREAKPOINTS) if pm25 is not None else None
    si_pm10 = compute_sub_index(pm10, PM10_BREAKPOINTS) if pm10 is not None else None

    indices = [si for si in (si_pm25, si_pm10) if si is not None]
    if not indices:
        return None
    return max(indices)


def is_anomaly(pm25: Optional[float], pm10: Optional[float], aqi: Optional[int]) -> bool:
    """Flag extreme physical or sensor spike anomalies."""
    if pm25 is not None and (pm25 > 550 or pm25 < 0):
        return True
    if pm10 is not None and (pm10 > 800 or pm10 < 0):
        return True
    if aqi is not None and aqi >= 450:
        return True
    return False
