"""CzechRad radiation conversions shared by every presentation client."""

from dataclasses import dataclass


# Device documentation specifies different tube calibration factors.
CZECHRAD_CPM_PER_USVH = 328.5
SAFECAST_CPM_PER_USVH = 334.0

DEVICE_CALIBRATIONS = {
    "CZRA1": CZECHRAD_CPM_PER_USVH,
    "CZRDD": CZECHRAD_CPM_PER_USVH,
    "BNRDD": SAFECAST_CPM_PER_USVH,
}

DEVICE_FAMILIES = {
    "CZRA1": "CzechRad",
    "CZRDD": "CzechRad (starší formát)",
    "BNRDD": "Safecast bGeigie Nano",
}


def calibration_for_device_type(device_type: str) -> float:
    """Return CPM per µSv/h for a supported LOG sentence type."""

    try:
        return DEVICE_CALIBRATIONS[device_type.upper()]
    except KeyError as exc:
        raise ValueError(f"unsupported device type: {device_type}") from exc


def device_family(device_type: str) -> str:
    """Return a human-readable family name for a LOG sentence type."""

    try:
        return DEVICE_FAMILIES[device_type.upper()]
    except KeyError as exc:
        raise ValueError(f"unsupported device type: {device_type}") from exc


def cpm_to_usvh(
    cpm: float, *, cpm_per_usvh: float = CZECHRAD_CPM_PER_USVH
) -> float:
    """Convert a one-minute CzechRad count to a stable dose-rate estimate."""

    if cpm < 0 or cpm_per_usvh <= 0:
        raise ValueError("cpm must not be negative")
    return cpm / cpm_per_usvh


def interval_counts_to_usvh(
    interval_counts: float, *, cpm_per_usvh: float = CZECHRAD_CPM_PER_USVH
) -> float:
    """Convert one five-second count to a faster, noisier dose-rate estimate."""

    if interval_counts < 0 or cpm_per_usvh <= 0:
        raise ValueError("interval_counts must not be negative")
    return interval_counts * 12 / cpm_per_usvh


@dataclass(frozen=True)
class RadiationBand:
    """A neutral display interval; bands are not safety classifications."""

    lower: float
    upper: float
    color: str
    label: str


RADIATION_BANDS = (
    RadiationBand(0.0, 0.10, "49,130,189,220", "0–0,10 µSv/h"),
    RadiationBand(0.10, 0.20, "49,177,76,220", "0,10–0,20 µSv/h"),
    RadiationBand(0.20, 0.50, "255,215,0,230", "0,20–0,50 µSv/h"),
    RadiationBand(0.50, 1.00, "245,124,0,230", "0,50–1,00 µSv/h"),
    RadiationBand(1.00, 1_000_000.0, "215,25,28,235", "> 1,00 µSv/h"),
)

CPM_BANDS = (
    RadiationBand(0.0, 33.0, "49,130,189,220", "0–33 CPM"),
    RadiationBand(33.0, 66.0, "49,177,76,220", "33–66 CPM"),
    RadiationBand(66.0, 164.0, "255,215,0,230", "66–164 CPM"),
    RadiationBand(164.0, 329.0, "245,124,0,230", "164–329 CPM"),
    RadiationBand(329.0, 328_500_000.0, "215,25,28,235", "> 329 CPM"),
)
