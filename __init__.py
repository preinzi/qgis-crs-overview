# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Stephan Preinstorfer / LiberGIS
"""CRS Overview - QGIS plugin entry point."""


def classFactory(iface):
    from .crs_overview import CrsOverviewPlugin
    return CrsOverviewPlugin(iface)
