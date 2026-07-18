"""Detect candidates for indoor or otherwise GPS-obscured measurement."""

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from datetime import datetime, timedelta

from ..core.models import CzechRadMeasurement
from ..importer.validation import validate_measurement


@dataclass(frozen=True, slots=True)
class LocationLossEpisode:
    """A continuous candidate period without a trusted GPS position.

    Loss of GPS does not prove that the user entered a building. The UI should
    present this object as a suggestion and let the user confirm its meaning.
    """

    start: datetime
    end: datetime
    measurements: tuple[CzechRadMeasurement, ...]
    entry_anchor: CzechRadMeasurement
    exit_anchor: CzechRadMeasurement

    @property
    def duration(self) -> timedelta:
        """Duration bounded by the last and next trusted map positions."""

        return self.exit_anchor.timestamp - self.entry_anchor.timestamp


def detect_location_loss_episodes(
    track_measurements: tuple[CzechRadMeasurement, ...],
    matched_nogps: tuple[CzechRadMeasurement, ...],
    *,
    bridge_tolerance: timedelta = timedelta(minutes=2),
    anchor_tolerance: timedelta = timedelta(minutes=5),
) -> tuple[LocationLossEpisode, ...]:
    """Return internal GPS-loss candidates with trusted entry/exit anchors.

    Brief GPS recoveries are bridged because a single visit inside a building
    can contain intermittent fixes near doors or windows. Initial acquisition
    and final loss are not classified as indoor candidates because they lack
    two trusted boundary positions.
    """

    if bridge_tolerance < timedelta(0):
        raise ValueError("bridge_tolerance must not be negative")
    if anchor_tolerance < timedelta(0):
        raise ValueError("anchor_tolerance must not be negative")
    if not track_measurements:
        return ()

    expected_date = min(item.timestamp for item in track_measurements).date()
    combined = sorted(
        (*track_measurements, *matched_nogps), key=lambda item: item.timestamp
    )
    validations = {
        id(item): validate_measurement(item, expected_date=expected_date)
        for item in combined
    }
    trusted = [item for item in combined if validations[id(item)].has_geometry]
    if len(trusted) < 2:
        return ()

    trusted_times = [item.timestamp for item in trusted]
    first_trusted = trusted[0].timestamp
    last_trusted = trusted[-1].timestamp
    obscured = [
        item
        for item in combined
        if first_trusted < item.timestamp < last_trusted
        and not validations[id(item)].has_geometry
        and validations[id(item)].usable_without_location
    ]
    if not obscured:
        return ()

    groups: list[list[CzechRadMeasurement]] = [[obscured[0]]]
    for measurement in obscured[1:]:
        if measurement.timestamp - groups[-1][-1].timestamp <= bridge_tolerance:
            groups[-1].append(measurement)
        else:
            groups.append([measurement])

    episodes: list[LocationLossEpisode] = []
    for group in groups:
        entry_index = bisect_left(trusted_times, group[0].timestamp) - 1
        exit_index = bisect_right(trusted_times, group[-1].timestamp)
        if entry_index < 0 or exit_index >= len(trusted):
            continue
        entry_anchor = trusted[entry_index]
        exit_anchor = trusted[exit_index]
        if (
            group[0].timestamp - entry_anchor.timestamp > anchor_tolerance
            or exit_anchor.timestamp - group[-1].timestamp > anchor_tolerance
        ):
            continue
        episodes.append(
            LocationLossEpisode(
                start=group[0].timestamp,
                end=group[-1].timestamp,
                measurements=tuple(group),
                entry_anchor=entry_anchor,
                exit_anchor=exit_anchor,
            )
        )

    return tuple(episodes)

