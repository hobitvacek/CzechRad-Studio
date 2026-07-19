"""Create QGIS memory layers from portable CzechRad import analysis."""

from dataclasses import dataclass
from pathlib import Path

from qgis.PyQt.QtCore import QMetaType
from qgis.core import (
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsMarkerSymbol,
    QgsPointXY,
    QgsProject,
    QgsVectorLayer,
)

from ..importer.session import ImportAnalysis


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


def _track_layer(analysis: ImportAnalysis, name: str) -> QgsVectorLayer:
    layer = QgsVectorLayer("Point?crs=EPSG:4326", name, "memory")
    provider = layer.dataProvider()
    provider.addAttributes(
        [
            QgsField("timestamp", QMetaType.Type.QString),
            QgsField("device", QMetaType.Type.QString),
            QgsField("cpm", QMetaType.Type.Int),
            QgsField("counts", QMetaType.Type.Int),
            QgsField("total", QMetaType.Type.Int),
            QgsField("satellites", QMetaType.Type.Int),
            QgsField("hdop", QMetaType.Type.Double),
        ]
    )
    layer.updateFields()

    features = []
    for measurement in analysis.geometry_measurements:
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
                measurement.interval_counts,
                measurement.total_counts,
                measurement.satellites,
                measurement.hdop,
            ]
        )
        features.append(feature)
    provider.addFeatures(features)
    layer.updateExtents()
    _set_marker(layer, "34,177,76,210", "2")
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
) -> CreatedLayers:
    """Add a track and optional candidate layer to the current project."""

    if not analysis.geometry_measurements:
        raise ValueError("LOG neobsahuje žádný bod s použitelnou GPS polohou")

    project = project or QgsProject.instance()
    stem = Path(track_path).stem
    track = _track_layer(analysis, f"CzechRad {stem}")
    candidates = _candidate_layer(analysis, f"CzechRad návrhy {stem}")
    project.addMapLayer(track)
    if candidates is not None:
        project.addMapLayer(candidates)
    return CreatedLayers(track=track, candidates=candidates)

