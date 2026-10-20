# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Stephan Preinstorfer / LiberGIS
"""CRS Overview - main plugin class.

Adds a toggleable dock widget (docked right by default) that lists all
layers in the current project grouped by CRS, highlighting groups whose
CRS is custom (user-defined) or invalid/unset.
"""

import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .crs_overview_dockwidget import CrsOverviewDockWidget

PLUGIN_DIR = os.path.dirname(__file__)


class CrsOverviewPlugin:

    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dock_widget = None

    def initGui(self):
        icon = QIcon(os.path.join(PLUGIN_DIR, "icon.png"))
        self.action = QAction(icon, "CRS Overview", self.iface.mainWindow())
        self.action.setCheckable(True)
        self.action.setStatusTip(
            "Show/hide the CRS Overview panel (layers grouped by CRS)"
        )
        self.action.triggered.connect(self._toggle_dock_widget)

        self.iface.addToolBarIcon(self.action)
        # Added directly (not via addPluginToMenu) so the icon actually
        # shows: addPluginToMenu wraps a single action in its own
        # icon-less submenu, and it's that submenu's own icon - not the
        # action's - that the Plugins dropdown displays.
        self.iface.pluginMenu().addAction(self.action)

        self.dock_widget = CrsOverviewDockWidget(self.iface)
        self.dock_widget.setVisible(False)
        # keep the toolbar/menu checkmark in sync if the user closes the
        # dock via its own close button rather than the action
        self.dock_widget.visibilityChanged.connect(self.action.setChecked)
        self.iface.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self.dock_widget
        )

    def _toggle_dock_widget(self, checked):
        self.dock_widget.setVisible(checked)
        if checked:
            # bring the panel to the front if it is tabbed behind another
            # panel (setVisible alone leaves it hidden behind that tab)
            self.dock_widget.raise_()
            self.dock_widget.refresh()

    def unload(self):
        if self.action is not None:
            self.iface.pluginMenu().removeAction(self.action)
            self.iface.removeToolBarIcon(self.action)

        if self.dock_widget is not None:
            self.dock_widget.disconnect_signals()
            self.iface.removeDockWidget(self.dock_widget)
            self.dock_widget.deleteLater()
            self.dock_widget = None

        if self.action is not None:
            # the action is parented to the QGIS main window, so it would
            # otherwise stay alive after every unload/reload
            self.action.deleteLater()
            self.action = None
