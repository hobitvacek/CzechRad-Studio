"""Create QGIS memory layers from portable CzechRad import analysis."""

from dataclasses import dataclass
from pathlib import Path

from qgis.PyQt.QtCore import QMetaType
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
from ..missions.aggregation import summarize_stable_stop


@dataclass(frozen=True, slots=True)
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
    if display_unit not in {"usvh", "cpm"}:
        raise ValueError(f"unsupported radiation display unit: {display_unit}")
    field_name = "dose_usvh" if display_unit == "usvh" else "cpm"
    bands = RADIATION_BANDS if display_unit == "usvh" else CPM_BANDS
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
            QgsField("timestamp", QMetaType.Type.QString),
            QgsField("device", QMetaType.Type.QString),
            QgsField("cpm", QMetaType.Type.Int),
            QgsField("dose_usvh", QMetaType.Type.Double),
            QgsField("fast_usvh", QMetaType.Type.Double),
            QgsField("counts", QMetaType.Type.Int),
            QgsField("total", QMetaType.Type.Int),
            QgsField("satellites", QMetaType.Type.Int),
            QgsField("hdop", QMetaType.Type.Double),
            QgsField("samples", QMetaType.Type.Int),
            QgsField("aggregated", QMetaType.Type.Bool),
            QgsField("cpm_min", QMetaType.Type.Int),
            QgsField("cpm_max", QMetaType.Type.Int),
        ]
    )
    layer.updateFields()

    summaries = []
    collapsed_measurements = set()
    if collapse_stops:
        for candidate in analysis.stop_candidates:
            summary = summarize_stable_stop(candidate)
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
                round(summary.average_cpm),
                summary.dose_rate_usvh,
                None,
                None,
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
    if not analysis.stop_candidates and not analysis.location_losses:
        return None

    layer = QgsVectorLayer("Point?crs=EPSG:4326", name, "memory")
    provider = layer.dataProvider()
    provider.addAttributes(
        [
            QgsField("kind", QMetaType.Type.QString),
            QgsField("start_utc", QMetaType.Type.QString),
            QgsField("end_utc", QMetaType.Type.QString),
            QgsField("minutes", QMetaType.Type.Double),
            QgsField("radius_m", QMetaType.Type.Double),
            QgsField("records", QMetaType.Type.Int),
        ]
    )
    layer.updateFields()

    features = []
    for candidate in analysis.stop_candidates:
        feature = QgsFeature(layer.fields())
        feature.setGeometry(
            QgsGeometry.fromPointXY(
                QgsPointXY(candidate.center_longitude, candidate.center_latitude)
            )
        )
        feature.setAttributes(
            [
                "stop_candidate",
                candidate.start.isoformat(),
                candidate.end.isoformat(),
                candidate.duration.total_seconds() / 60,
                candidate.radius_p95_m,
                len(candidate.measurements),
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
    display_unit: str = "usvh",
) -> CreatedLayers:
    """Add a track and optional candidate layer to the current project."""

    if not analysis.geometry_measurements:
        raise ValueError("LOG neobsahuje žádný bod s použitelnou GPS polohou")

    project = project or QgsProject.instance()
    stem = Path(track_path).stem
    track = _track_layer(
        analysis,
        f"CzechRad {stem}",
        collapse_stops=collapse_stops,
        display_unit=display_unit,
    )
    candidates = _candidate_layer(analysis, f"CzechRad návrhy {stem}")
    project.addMapLayer(track)
    if candidates is not None:
        project.addMapLayer(candidates)
    return CreatedLayers(track=track, candidates=candidates)

