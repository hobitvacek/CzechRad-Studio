"""CzechRad radiation conversions shared by every presentation client."""

from dataclasses import dataclass


# CzechRad DATA documentation specifies 328.5 CPM per microSievert/hour.
CZECHRAD_CPM_PER_USVH = 328.5


def cpm_to_usvh(cpm: float) -> float:
    """Convert a one-minute CzechRad count to a stable dose-rate estimate."""

    if cpm < 0:
        raise ValueError("cpm must not be negative")
    return cpm / CZECHRAD_CPM_PER_USVH


def interval_counts_to_usvh(interval_counts: float) -> float:
    """Convert one five-second count to a faster, noisier dose-rate estimate."""

    if interval_counts < 0:
        raise ValueError("interval_counts must not be negative")
    return interval_counts * 12 / CZECHRAD_CPM_PER_USVH


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
