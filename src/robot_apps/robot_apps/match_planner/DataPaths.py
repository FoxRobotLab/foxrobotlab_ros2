"""Shared resource paths for the modular match planner."""

import os

from ament_index_python.packages import get_package_share_directory


# ------------------- Package Resource Paths -------------------
# Resolve installed robot_apps resources so launch/install layouts work.
basePath = os.path.join(
    get_package_share_directory("robot_apps"),
    "apps",
    "match_planner",
) + os.sep

# graphMapData = "map/olinGraph.txt"
graphMapData = "res/map/cellGraph.txt"
mapLineData = "res/map/olinNewMap.txt"
cellMapData = "res/map/mapToCells.txt"
