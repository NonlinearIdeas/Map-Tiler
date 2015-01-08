# -------------------------------------------------------------
# License
# -------------------------------------------------------------
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated
# documentation files (the "Software"), to deal in the Software
# without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to
# whom the Software is furnished to do so, subject to the
# following conditions:
#
# The above copyright notice and this permission notice shall
# be included in all copies or substantial portions of the
# Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY
# KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
# WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
# PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
# OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# -------------------------------------------------------------


"""
Post process a Tiled (.tmx) file to generate navigation and object information
for a game.  This is part of a specific work flow where:

1. The map is generated in layers.
2. Some specific layers are present by design, if not actual name:
    Floors - Specifies all the floor tiles in the map.
    Doors - Specifies door locations.  Doors go across edges.
    Walls   - Walls block movement into a tile.
3. All other layers are treated as "Objects" unless specifically excluded (excludelayers)
    or handled explicitly (e.g. DoorActivators).
   When the processing is done, a file with all the objects in it will be created.
4. A <prefix>Rooms layer has been created identifying the tiles for specific rooms.


This script is meant to run against the output of MapTiler.py.

This script will (optionally controlled) generate the following outputs:


Usage: MapDataExtractor.py  <tiledFile>
                            [--floorLayer=FLOORS]
                            [--wallLayer=WALLS]
                            [--doorLayer=DOORS]
                            [--portalLayer=PORTALS]
                            [--navPrefix=NAVPREFIX]
                            [--outPrefix=OUTPREFIX]
                            [<excludeLayers>...]
Argumnts:
    tiledFile       The Tiled (.tmx) file that contains the Tiled data.

Options:
    --wallLayer=WALLS       The name of the layer used for walls.
                            [Default: Walls]
    --floorLayer=FLOORS     The name of the layer used for floors.
                            [Default: Floors]
    --doorLayer=DOORS       The name of the layer used for doors.
                            [Default: Doors]
    --portalLayer=PORTALS   The name of the layer used for portals.
                            [Default: Portals]
    --navPrefix=NAVPREFIX   The prefix used for navigation layers generated or manually created.
                            [Default: NAV_]
    --outPrefix=OUTPREFIX   The prefix used with all data files created.
                            [Default: NAV_]
    <excludeLayers>...      Exclude these layers from ANY processing.

Website:        http://www.NonlinearIdeas.com
Repository:     https://github.com/NonlinearIdeas/Map-Tiler
Report Issues:  https://github.com/NonlinearIdeas/Map-Tiler
License:        MIT License - See specific text in source code.
Copyright:      Copyright (c) 2015 Nonlinear Ideas Inc (contact@nlideas.com)
"""

import os
from lxml import etree
import docopt
import math

if __name__ == "__main__":
    arguments = docopt.docopt(__doc__)
    # When testing is done, this is where
    # test arguments are inserted.
    """
    arguments["<layerImage>"] = ["Floors.png",
                                 "Walls.png",
                                 "Doors.png",
                                 "DoorActivators.png",
                                 "Portals.png",
                                 "Healing.png",
                                 "Ammo.png",
                                 "Weapons.png"]
    arguments["--tileWidth"] = "32"
    arguments["--tileHeight"] = "32"
    arguments["--verbose"] = True
#    arguments["--overwriteExisting"] = True
    arguments["--mergeExisting"] = True
    arguments["--floorLayer"] = "Floors"
    arguments["--wallLayer"] = "Walls"
    arguments["--portalLayer"] = "Portals"
    arguments["--doorLayer"] = "Doors"
    """
    print "-----------------------------------"
    print "Inputs:"
    args = arguments.keys()
    args.sort()
    for arg in args:
        print "%-25s %s" % (arg, arguments[arg])
    print "-----------------------------------"
