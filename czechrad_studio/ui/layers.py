"""Create QGIS memory layers from portable CzechRad import analysis."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from qgis.core import (
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsGraduatedSymbolRenderer,
    QgsMarkerSymbol,
    QgsPointXY,
    QgsProject,
    QgsVectorLayer,
    QgsRendererRange,
)

from ..core.radiation import CPM_BANDS, RADIATION_BANDS
from ..importer.session import ImportAnalysis
from ..missions.aggregation import assess_stop_radiation, summarize_stable_stop
from ..qt_compat import FIELD_BOOL, FIELD_DOUBLE, FIELD_INT, FIELD_STRING


@dataclass(frozen=True)
class CreatedLayers:
    track: QgsVectorLayer
    candidates: QgsVectorLayer | None


def _set_marker(layer: QgsVectorLayer, color: str, size: str) -> None:
    symbol = QgsMarkerSymbol.createSimple(
        {"name": "circle", "color": color, "size": size, "outline_style": "no"}
    )
    layer.renderer().setSymbol(symbol)
    layer.triggerRepaint()


def _set_radiation_renderer(layer: QgsVectorLayer, display_unit: str) -> None:
    if display_unit not in {"device_usvh", "minute_usvh", "cpm"}:
        raise ValueError(f"unsupported radiation display unit: {display_unit}")
    field_name = {
        "device_usvh": "fast_usvh",
        "minute_usvh": "dose_usvh",
        "cpm": "cpm",
    }[display_unit]
    bands = RADIATION_BANDS if display_unit != "cpm" else CPM_BANDS
    ranges = []
    for band in bands:
        symbol = QgsMarkerSymbol.createSimple(
            {
                "name": "circle",
                "color": band.color,
                "size": "2.2",
                "outline_color": "255,255,255,170",
                "outline_width": "0.25",
            }
        )
        ranges.append(
            QgsRendererRange(band.lower, band.upper, symbol, band.label)
        )
    layer.setRenderer(QgsGraduatedSymbolRenderer(field_name, ranges))
    layer.triggerRepaint()


def _track_layer(
    analysis: ImportAnalysis,
    name: str,
    *,
    collapse_stops: bool,
    display_unit: str,
) -> QgsVectorLayer:
    layer = QgsVectorLayer("Point?crs=EPSG:4326", name, "memory")
    provider = layer.dataProvider()
    provider.addAttributes(
        [
            QgsField("timestamp", FIELD_STRING),
            QgsField("device", FIELD_STRING),
            QgsField("device_type", FIELD_STRING),
            QgsField("device_family", FIELD_STRING),
            QgsField("cpm", FIELD_INT),
            QgsField("dose_usvh", FIELD_DOUBLE),
            QgsField("fast_usvh", FIELD_DOUBLE),
            QgsField("counts", FIELD_INT),
            QgsField("total", FIELD_INT),
            QgsField("satellites", FIELD_INT),
            QgsField("hdop", FIELD_DOUBLE),
            QgsField("samples", FIELD_INT),
            QgsField("aggregated", FIELD_BOOL),
            QgsField("cpm_min", FIELD_INT),
            QgsField("cpm_max", FIELD_INT),
        ]
    )
    layer.updateFields()

    summaries = []
    collapsed_measurements = set()
    if collapse_stops:
        for candidate in analysis.stop_candidates:
            summary = summarize_stable_stop(
                candidate, analysis.geometry_measurements
            )
            if summary is not None:
                summaries.append(summary)
                collapsed_measurements.update(id(item) for item in candidate.measurements)

    features = []
    for measurement in analysis.geometry_measurements:
        if id(measurement) in collapsed_measurements:
            continue
        feature = QgsFeature(layer.fields())
        feature.setGeometry(
            QgsGeometry.fromPointXY(
                QgsPointXY(measurement.longitude, measurement.latitude)
            )
        )
        feature.setAttributes(
            [
                measurement.timestamp.isoformat(),
                measurement.device_id,
                measurement.device_type,
                measurement.device_family,
                measurement.cpm,
                measurement.dose_rate_usvh,
                measurement.interval_dose_rate_usvh,
                measurement.interval_counts,
                measurement.total_counts,
                measurement.satellites,
                measurement.hdop,
                1,
                False,
                measurement.cpm,
                measurement.cpm,
            ]
        )
        features.append(feature)

    for summary in summaries:
        feature = QgsFeature(layer.fields())
        feature.setGeometry(
            QgsGeometry.fromPointXY(QgsPointXY(summary.longitude, summary.latitude))
        )
        feature.setAttributes(
            [
                summary.start.isoformat(),
                analysis.track.measurements[0].device_id,
                analysis.track.measurements[0].device_type,
                analysis.track.measurements[0].device_family,
                round(summary.average_cpm),
                summary.dose_rate_usvh,
                summary.interval_dose_rate_usvh,
                round(summary.average_interval_counts),
                None,
                None,
                None,
                summary.sample_count,
                True,
                summary.minimum_cpm,
                summary.maximum_cpm,
            ]
        )
        features.append(feature)
    provider.addFeatures(features)
    layer.updateExtents()
    _set_radiation_renderer(layer, display_unit)
    return layer


def _candidate_layer(analysis: ImportAnalysis, name: str) -> QgsVectorLayer | None:
    elevated_stops = []
    for candidate in analysis.stop_candidates:
        assessment = assess_stop_radiation(
            candidate, analysis.geometry_measurements
        )
        if assessment is not None and assessment.elevated:
            elevated_stops.append((candidate, assessment))

    if not elevated_stops and not analysis.location_losses:
        return None

    layer = QgsVectorLayer("Point?crs=EPSG:4326", name, "memory")
    provider = layer.dataProvider()
    provider.addAttributes(
        [
            QgsField("kind", FIELD_STRING),
            QgsField("start_utc", FIELD_STRING),
            QgsField("end_utc", FIELD_STRING),
            QgsField("minutes", FIELD_DOUBLE),
            QgsField("radius_m", FIELD_DOUBLE),
            QgsField("records", FIELD_INT),
            QgsField("baseline", FIELD_DOUBLE),
            QgsField("stop_cpm", FIELD_DOUBLE),
            QgsField("increase_pct", FIELD_DOUBLE),
            QgsField("dose_usvh", FIELD_DOUBLE),
        ]
    )
    layer.updateFields()

    features = []
    for candidate, assessment in elevated_stops:
        feature = QgsFeature(layer.fields())
        feature.setGeometry(
            QgsGeometry.fromPointXY(
                QgsPointXY(candidate.center_longitude, candidate.center_latitude)
            )
        )
        feature.setAttributes(
            [
                "possible_stationary_measurement",
                candidate.start.isoformat(),
                candidate.end.isoformat(),
                candidate.duration.total_seconds() / 60,
                candidate.radius_p95_m,
                len(candidate.measurements),
                assessment.baseline_cpm,
                assessment.stop_average_cpm,
                assessment.increase_ratio * 100,
                assessment.comparison_usvh,
            ]
        )
        features.append(feature)

    for candidate in analysis.location_losses:
        anchor = candidate.entry_anchor
        feature = QgsFeature(layer.fields())
        feature.setGeometry(
            QgsGeometry.fromPointXY(QgsPointXY(anchor.longitude, anchor.latitude))
        )
        feature.setAttributes(
            [
                "gps_loss_candidate",
                candidate.start.isoformat(),
                candidate.end.isoformat(),
                candidate.duration.total_seconds() / 60,
                None,
                len(candidate.measurements),
                None,
                None,
                None,
                None,
            ]
        )
        features.append(feature)

    provider.addFeatures(features)
    layer.updateExtents()
    _set_marker(layer, "245,124,0,230", "4")
    return layer


def add_analysis_layers(
    analysis: ImportAnalysis,
    track_path: str,
    *,
    project: QgsProject | None = None,
    collapse_stops: bool = False,
    display_unit: str = "device_usvh",
) -> CreatedLayers:
    """Add a track and optional candidate layer to the current project."""

    if not analysis.geometry_measurements:
        raise ValueError("LOG neobsahuje žádný bod s použitelnou GPS polohou")

    project = project or QgsProject.instance()
    stem = Path(track_path).stem
    family = analysis.track.measurements[0].device_family
    track = _track_layer(
        analysis,
        f"{family} {stem}",
        collapse_stops=collapse_stops,
        display_unit=display_unit,
    )
    candidates = _candidate_layer(analysis, f"{family} návrhy {stem}")
    project.addMapLayer(track)
    if candidates is not None:
        project.addMapLayer(candidates)
    return CreatedLayers(track=track, candidates=candidates)
