# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Stephan Preinstorfer / LiberGIS
"""CRS Overview - dock widget.

Shows every layer in the current project grouped by CRS. Groups whose
CRS is custom (user-defined) or invalid/unset are highlighted. Tables
without geometry need no CRS and are listed separately at the end.

Refresh is triggered automatically when layers are added or removed,
and manually via the "Refresh" button (e.g. after reassigning a
layer's CRS in place, which does not fire an add/remove signal).
"""

from qgis.PyQt.QtGui import QBrush, QColor
from qgis.PyQt.QtWidgets import (
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer

# --- USER_CRS_START_ID: threshold above which a CRS srsid() is a
# custom/user-defined CRS rather than one from the shipped database.
# The value itself (100000) has been stable since the feature was
# introduced, but its Python-API location has moved between QGIS
# versions (module-level constant in 3.x, Qgis.USER_CRS_START_ID in
# newer/master builds) - so we probe both, falling back to the
# documented literal value if neither is found. See
# https://qgis.org/pyqgis/3.40/core/USER_CRS_START_ID.html
try:
    from qgis import core as _qgis_core
    USER_CRS_START_ID = getattr(_qgis_core, "USER_CRS_START_ID", None)
    if USER_CRS_START_ID is None:
        from qgis.core import Qgis as _Qgis
        USER_CRS_START_ID = getattr(_Qgis, "USER_CRS_START_ID", 100000)
except ImportError:
    USER_CRS_START_ID = 100000

STATUS_OK = "OK"
STATUS_CUSTOM = "Custom"
STATUS_INVALID = "Invalid"
STATUS_NO_GEOMETRY = "n/a"

CUSTOM_CRS_COLOR = QColor(255, 235, 156)   # soft yellow
INVALID_CRS_COLOR = QColor(255, 199, 206)  # soft red

STATUS_PRIORITY = {STATUS_INVALID: 0, STATUS_CUSTOM: 1, STATUS_OK: 2}


class CrsOverviewDockWidget(QDockWidget):

    def __init__(self, iface, parent=None):
        super().__init__("CRS Overview", parent)
        self.iface = iface
        self.setObjectName("CrsOverviewDockWidget")

        self._build_ui()
        self._connect_signals()
        self.refresh()

    def _build_ui(self):
        container = QWidget()
        layout = QVBoxLayout(container)

        self.project_crs_label = QLabel("")
        self.project_crs_label.setWordWrap(True)
        layout.addWidget(self.project_crs_label)

        top_bar = QHBoxLayout()
        self.summary_label = QLabel("")
        top_bar.addWidget(self.summary_label)
        top_bar.addStretch()
        refresh_button = QPushButton("Refresh")
        refresh_button.setToolTip(
            "Manually rescan project layers (needed after reassigning a "
            "layer's CRS in place)"
        )
        refresh_button.clicked.connect(self.refresh)
        top_bar.addWidget(refresh_button)
        layout.addLayout(top_bar)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["CRS / Layer", "Type", "Status"])
        self.tree.setColumnWidth(0, 240)
        layout.addWidget(self.tree)

        self.setWidget(container)

    def _connect_signals(self):
        project = QgsProject.instance()
        project.layersAdded.connect(self._on_layers_changed)
        project.layersRemoved.connect(self._on_layers_changed)
        project.crsChanged.connect(self._on_layers_changed)

    def disconnect_signals(self):
        project = QgsProject.instance()
        try:
            project.layersAdded.disconnect(self._on_layers_changed)
            project.layersRemoved.disconnect(self._on_layers_changed)
            project.crsChanged.disconnect(self._on_layers_changed)
        except TypeError:
            # already disconnected
            pass

    def _on_layers_changed(self, *_args):
        self.refresh()

    def refresh(self):
        self.tree.clear()

        project_crs = QgsProject.instance().crs()
        project_status, project_color = self._crs_status(project_crs)
        self.project_crs_label.setText(
            f"Project CRS: {self._crs_display_text(project_crs)} "
            f"({project_status})"
        )
        self._colorize_label(self.project_crs_label, project_color)

        layers = list(QgsProject.instance().mapLayers().values())

        # group key -> {"crs": QgsCoordinateReferenceSystem, "layers": [...]}
        groups = {}
        no_geometry_layers = []

        for layer in layers:
            if not layer.isSpatial():
                # tables without geometry have no CRS by design
                no_geometry_layers.append(layer)
                continue
            crs = layer.crs()
            group_key = self._crs_group_key(crs)
            groups.setdefault(group_key, {"crs": crs, "layers": []})
            groups[group_key]["layers"].append(layer)

        custom_count = 0
        invalid_count = 0

        def sort_key(item):
            key, data = item
            status, _color = self._crs_status(data["crs"])
            return (STATUS_PRIORITY[status], data["crs"].description() or key)

        for _group_key, data in sorted(groups.items(), key=sort_key):
            crs = data["crs"]
            status, color = self._crs_status(crs)
            if status == STATUS_CUSTOM:
                custom_count += 1
            elif status == STATUS_INVALID:
                invalid_count += 1
            self._add_group(
                self._crs_display_text(crs), status, color, data["layers"]
            )

        if no_geometry_layers:
            self._add_group(
                "(no geometry)", STATUS_NO_GEOMETRY, None, no_geometry_layers
            )

        summary = f"{len(layers)} layer(s), {len(groups)} CRS group(s)"
        extra = []
        if custom_count:
            extra.append(f"{custom_count} custom")
        if invalid_count:
            extra.append(f"{invalid_count} invalid")
        if extra:
            summary += " (" + ", ".join(extra) + ")"
        if no_geometry_layers:
            summary += f", {len(no_geometry_layers)} without geometry"
        self.summary_label.setText(summary)

    def _add_group(self, label, status, color, layers):
        group_item = QTreeWidgetItem([label, "", status])
        self._colorize(group_item, color)
        self.tree.addTopLevelItem(group_item)

        for layer in sorted(layers, key=lambda lyr: lyr.name()):
            child = QTreeWidgetItem(
                [layer.name(), self._layer_type_label(layer), status]
            )
            self._colorize(child, color)
            group_item.addChild(child)

        group_item.setExpanded(True)

    @staticmethod
    def _crs_group_key(crs):
        # All invalid CRS share one group. A valid CRS without authority
        # id (e.g. an ad-hoc WKT from a layer's .prj) is keyed by its own
        # definition: QGIS leaves srsid() at 0 for all of these, so the
        # srsid cannot tell different unknown CRS apart.
        if not crs.isValid():
            return "invalid"
        if crs.authid():
            return crs.authid()
        return crs.toWkt() or crs.description()

    @staticmethod
    def _crs_status(crs):
        if not crs.isValid():
            return STATUS_INVALID, INVALID_CRS_COLOR
        # Two independent signals for "custom": a srsid in the user-CRS
        # range (registered in the local CRS database), or no authority
        # id at all (e.g. an ad-hoc WKT from a layer's .prj that was
        # never persisted, so srsid() stays unresolved/low even though
        # isValid() is True).
        if not crs.authid() or crs.srsid() >= USER_CRS_START_ID:
            return STATUS_CUSTOM, CUSTOM_CRS_COLOR
        return STATUS_OK, None

    @staticmethod
    def _layer_type_label(layer):
        # isinstance checks avoid depending on the exact QgsMapLayerType /
        # Qgis.LayerType enum spelling, which differs across QGIS 3.x/4.x.
        if isinstance(layer, QgsVectorLayer):
            return "Vector" if layer.isSpatial() else "Table"
        if isinstance(layer, QgsRasterLayer):
            return "Raster"
        return "Other"

    @staticmethod
    def _crs_display_text(crs):
        label = crs.authid() if crs.authid() else "(no authority id)"
        if not crs.isValid():
            description = "unknown / not set"
        elif crs.description():
            description = crs.description()
        else:
            # unnamed definition (e.g. a bare PROJ string): show the start
            # of it so that different unnamed CRS can be told apart
            definition = crs.toProj()
            if len(definition) > 80:
                definition = definition[:80] + "…"
            description = definition or "unnamed"
        return f"{label} — {description}"

    @staticmethod
    def _colorize(item, color):
        if color is None:
            return
        brush = QBrush(color)
        for column in range(item.columnCount()):
            item.setBackground(column, brush)

    @staticmethod
    def _colorize_label(label, color):
        if color is None:
            label.setStyleSheet("")
            return
        label.setStyleSheet(
            f"background-color: {color.name()}; padding: 2px;"
        )
