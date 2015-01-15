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
4. A <navPrefix>Rooms layer has been created identifying the tiles for specific rooms.



This script is meant to run against the output of MapTiler.py.

This script will (optionally controlled) generate the following outputs:

NOTES:
1. You can specify the --exclude option to remove any layers from consideration
   for objects.  The --navPrefix specified layers will not be considered automatically,
   as well as the floor and wall layers.  The doors layer is used to create objects.
2. Objects found are considered to not block entry into the cell for the purpose of generating
   adjacency information.  You can specify an object as blocking by using the --blocking option
   for that layer.  This usage is highly game engine specific (i.e. if your agent wants to navigate
   to the object that is considered "blocked", then they have to navigate to an adjacent cell.  Your
   engine has to handle this).
3. An adjancency list (edges) for all the walkable nodes will be generated.  This will take into account
   walls, blocking objects, and doors.  If the edge exists, it will be marked indicating the type of
   action needed to traverse the edge.  This could be more sophisticated, but for now, you can either
   walk an edge in a room, wall through a portal between rooms, or walk through a door between rooms.
   Edge Markings:
        WALK - Just walk from cell A to cell B.
        DOOR - To go from cell A to cell B, you must go through a door.
        ROOM - Walk between two rooms, but without going through a door.  This is a portal boundary.

Usage: MapDataExtractor.py  <tiledFile>
                            [--floorLayer=FLOORS]
                            [--wallLayer=WALLS]
                            [--doorLayer=DOORS]
                            [--navPrefix=NAVPREFIX]
                            [--outFile=OUTFILE]
                            [--verbose]
                            [--exclude=LAYER ...]
                            [--blocking=LAYER ...]
                            [--binding=LAYER ...]
                            [--noDiagonalEdges]
                            [--reallyVerbose]
Argumnts:
    tiledFile       The Tiled (.tmx) file that contains the Tiled data.

Options:
    --wallLayer=WALLS       The name of the layer used for walls.
                            [Default: Walls]
    --floorLayer=FLOORS     The name of the layer used for floors.
                            [Default: Floors]
    --doorLayer=DOORS       The name of the layer used for doors.
                            [Default: Doors]
    --navPrefix=NAVPREFIX   The prefix used for navigation layers generated or manually created.
                            [Default: NAV_]
    --outFile=OUTFILE       The CSV output file with all the output data.  See below for format.
                            [Default: NavData.csv]
    --verbose               Generate output while processing.
    --reallyVerbose         Generate even more output while processing.
    --exclude=LAYER         Specifies a layer to be excluded from processing.
                            Can be specified multiple times.
    --blocking=LAYER        Specifies an object layer that will be considered as
                            blocking in navigation graph generation.
                            Can be specified multiple times.
    --binding=LAYER         Specifies an object layer that will be considered as
                            some kind of "activator" that needs to be bound to the
                            nearest object (other than something that binds).  This
                            is useful for creating door activators, etc.
                            Can be specified multiple times.
    --noDiagonalEdges       By default, the adjacent check will consider
                            diagonal edges as well.  This option restricts
                            the check to only N, S, E, W checks.

Website:        http://www.NonlinearIdeas.com
Repository:     https://github.com/NonlinearIdeas/Map-Tiler
Report Issues:  https://github.com/NonlinearIdeas/Map-Tiler
License:        MIT License - See specific text in source code.
Copyright:      Copyright (c) 2015 Nonlinear Ideas Inc (contact@nlideas.com)
"""

import os
from lxml import etree
import docopt
import csv
import string

class MapDataExtractor(object):
    # Keys used for holding output data
    KEY_WALKABLE = "Walkable"
    KEY_ROOMS = "Rooms"
    KEY_PROPERTY_ROOM = "ROOM"
    KEY_OBJECTS = "Objects"
    KEY_ADJACENCY = "Adjacency"
    KEY_EDGE_ROOM = "ROOM"
    KEY_EDGE_DOOR = "DOOR"
    KEY_EDGE_WALK = "WALK"
    CSV_EXPORT_COLUMNS = 10

    def __init__(self):
        self.Reset()

    def ExtractTileIndex(self, gid):
        FLAGS = 0x80000000 | 0x40000000 | 0x20000000
        return gid & ~FLAGS

    def CalculateCellIndex(self, col, row):
        index = row * self.layerWidth + col
        return index

    def CalculateCellColRow(self, index):
        row = index / self.layerWidth
        col = index % self.layerWidth
        return col, row

    def Reset(self):
        # Tile width and height in pixels.
        self.tileWidth = 0
        self.tileHeight = 0

        # Layer width and height in tiles.
        self.layerWidth = 0
        self.layerHeight = 0

        # The number of tiles total for a layer.
        # This is the width x height.
        self.layerTiles = 0

        # Keyed by the tile index.  Contains a dictionary
        # of properties for each tile gleaned from the Tiled file.
        self.tileMap = {}

        # Keyed by the layer name.  Each entry contains a list of the tile
        # indexes in that layer.  An index of 0 indicates the tile is
        # unpopulated.
        self.layerMap = {}

        # Original file used in the tile set.
        self.tileMapFile = ""

        # All output results are stored in this dictionary by
        # key.  Each object stored may be a different format.
        self.outputDict = {}

    def FatalError(self,message):
        print message
        print "Unable to continue."
        return False

    def LoadTiledMap(self,tiledFile):
        # Does it exist?
        if not os.path.exists(tiledFile):
            return self.FatalError("Tiled file %s does not exist."%tiledFile)

        # Load the existing file.
        inTree = etree.parse(tiledFile)
        inRoot = inTree.getroot()

        # Basic parameters
        self.tileWidth = int(inRoot.attrib["tilewidth"])
        self.tileHeight = int(inRoot.attrib["tileheight"])
        self.layerWidth = int(inRoot.attrib["width"])
        self.layerHeight = int(inRoot.attrib["height"])
        self.layerTiles = self.layerWidth*self.layerHeight

        # Tileset Information
        self.tileMap = { idx:{} for idx in xrange(self.layerTiles)}
        for tileset in inRoot.findall("tileset"):
            if tileset.attrib["firstgid"] == "1":
                self.tileMapFile = tileset.find("image").attrib["source"]
                for tile in tileset.findall("tile"):
                    id = int(tile.attrib["id"])
                    for properties in tile.findall("properties"):
                        for property in properties.findall("property"):
                            self.tileMap[id][property.attrib["name"]] = property.attrib["value"]

        # Layers
        self.layerMap = {layer.attrib['name']: {} for layer in inRoot.findall("layer")}
        for layer in inRoot.findall("layer"):
            tiles = layer.find("data").findall("tile")
            for idx in xrange(len(tiles)):
                tile = tiles[idx]
                tileID = self.ExtractTileIndex(int(tile.attrib["gid"]))
                if tileID > 0:
                    self.layerMap[layer.attrib['name']][idx] = tileID-1
        return True

    def FormatNavName(self,name):
        return self.navPrefix + name

    # Given a layer index, find the indices for the cells that
    # are adjacent to it.
    def GetAdjacentIndexes(self,layerIndex):
        col, row = self.CalculateCellColRow(layerIndex)
        adjacent = [ self.CalculateCellIndex(col + 1, row + 0),
                 self.CalculateCellIndex(col - 1, row + 0),
                 self.CalculateCellIndex(col + 0, row + 1),
                 self.CalculateCellIndex(col + 0, row - 1),
                 ]
        if self.diagonalEdges:
            adjacent += [self.CalculateCellIndex(col + 1, row + 1),
                            self.CalculateCellIndex(col + 1, row - 1),
                            self.CalculateCellIndex(col - 1, row + 1),
                            self.CalculateCellIndex(col - 1, row - 1)]
        return adjacent

    # Perform a search on the adjacent cells until we run out of cells
    # that are connected.  This is used to find all the cells associated
    # with a particular object.
    # NOTE:  This function will not remove the found indices from the
    # original passed in, it will use a local copy.
    def FindConnectedIndices(self,layerIndex,indices):
        # Make a local copy
        indices = indices[:]
        # Nothing in the result yet.
        result = []
        # Prime the pump
        queue = [layerIndex]
        # Start the pump
        while len(queue) > 0:
            next = queue.pop(0)
            result.append(next)
            # Remove from future consideration.
            if next in indices:
                indices.remove(next)
            adjacent = self.GetAdjacentIndexes(next)
            for adj in adjacent:
                # This is the most common case so it gets
                # checked first.  Avoids the other checks
                # most of the time.
                if adj not in indices:
                    continue
                if adj in queue:
                    continue
                if adj in result:
                    continue
                # Must be a keeper
                queue.append(adj)
        return result

    def DistSquared(self,idx1,idx2):
        c1,r1 = self.CalculateCellColRow(idx1)
        c2,r2 = self.CalculateCellColRow(idx2)
        return (r1-r2)*(r1-r2) + (c1-c2)*(c1-c2)


    # Given a specific index and a list of all the other
    # indices around it, find the one closest.
    def FindNearestIndex(self,layerIndex,indices):
        distSq = [(self.DistSquared(layerIndex,idx),idx) for idx in indices]
        distSq.sort()
        return distSq[0][1]

    def BeginsWithNavPrefix(self, text):
        if text[:len(self.navPrefix)] == self.navPrefix:
            return True
        return False

    def Banner(self, text):
        print
        print "---------------------------------"
        print text
        print "---------------------------------"

    def IndicesToCells(self, indices):
        result = [self.CalculateCellColRow(index) for index in indices]
        return result

    def CellsToIndices(self, cells):
        result = [self.CalculateCellIndex(col, row) for col, row in cells]
        return result

    def ExtractRoomsData(self):
        if self.verbose:
            self.Banner("Extracting Rooms")

        KEY_ROOMS = MapDataExtractor.KEY_ROOMS
        KEY_WALKABLE = MapDataExtractor.KEY_WALKABLE
        KEY_PROPERTY_ROOM = self.FormatNavName(MapDataExtractor.KEY_PROPERTY_ROOM)

        # Create an output set to hold the data.
        self.outputDict[KEY_ROOMS] = {}

        # Create a dictionary for the rooms based on the tiles that
        # have the property.
        roomDict = {}
        tileDict = {}
        indexDict = {}
        for tileID in self.tileMap:
            if self.tileMap[tileID].has_key(KEY_PROPERTY_ROOM):
                roomID = int(self.tileMap[tileID][KEY_PROPERTY_ROOM])
                tileDict[tileID] = roomID
                roomDict[roomID] = []
        # Find the rooms layer.
        navRooms = self.FormatNavName(KEY_ROOMS)
        if navRooms not in self.layerMap:
            return self.FatalError("Layer %s not found in layers."%navRooms)
        layer = self.layerMap[navRooms]
        for layerIndex in layer:
            tileID = layer[layerIndex]
            if(tileID in tileDict):
                # This means the tile in the layer is a room tile marker.
                tileType = tileDict[tileID]
                roomDict[tileType].append(layerIndex)
                indexDict[layerIndex] = tileType
        self.outputDict[KEY_ROOMS] = roomDict
        self.outputDict[KEY_WALKABLE] = indexDict
        if self.verbose:
            roomKeys = roomDict.keys()
            roomKeys.sort()
            for key in roomKeys:
                print "Room: %d"%key
                print self.IndicesToCells(roomDict[key])
                print
        return True

    def ExtractObjectsData(self):
        if self.verbose:
            self.Banner("Extracting Objects")
        # Figure out which layers to process.
        # Start with all the layer names.
        lNames = self.layerMap.keys()
        # Now start filtering out.
        lNames = [name for name in lNames if name != self.wallLayer]
        lNames = [name for name in lNames if name != self.floorLayer]
        lNames = [name for name in lNames if name not in self.excludeLayers]
        lNames = [name for name in lNames if not self.BeginsWithNavPrefix(name)]
        lNames.sort()
        # Go through each layer, creating an object set for each.
        # Store them in a dictionary by object name, with the data as a list of lists,
        # each sublist containing the indices for the object.
        subjectID = 1
        subjects = { }
        for objType in lNames:
            layer = self.layerMap[objType]
            keys = layer.keys()
            keys.sort()
            while len(keys) > 0:
                # Pop the first key.
                first = keys.pop(0)
                found = self.FindConnectedIndices(first,keys)
                # Remove the found from the keys
                keys = [key for key in keys if key not in found]
                subjects[subjectID] = [objType, found, []]
                subjectID += 1
        # Now that all the objects have been identified, do a cross
        # check of the objects with the activators and create a
        # subjectID link between an "Activator" and the object
        # closest to it that is NOT an activator.

        # Build up a master list of all the object indices EXCEPT
        # the ones used for the activators.
        subjectIndexMap = {}
        for subject in subjects:
            objType,indices,binding = subjects[subject]
            if objType in self.bindingLayers:
                continue
            for idx in indices:
                subjectIndexMap[idx] = subject
        objIndices = subjectIndexMap.keys()
        objIndices.sort()
        # Now go through the activators and search for the
        # nearest object.
        keys = subjects.keys()
        keys.sort()
        for act in self.bindingLayers:
            for subject in keys:
                objType, indices, binding = subjects[subject]
                if objType == act:
                    # Find the nearest index
                    nearest = self.FindNearestIndex(indices[0],objIndices)
                    # Bind the two together
                    bindingTo = subjectIndexMap[nearest]
                    subjects[subject][2].append(bindingTo)
                    subjects[bindingTo][2].append(subject)
        # Store off for later processing
        self.outputDict[MapDataExtractor.KEY_OBJECTS] = subjects

        if self.verbose:
            keys = subjects.keys()
            keys.sort()
            for key in keys:
                objType, indices, binding = subjects[key]
                print "-- [SubjectID: %d] [Type: %s] [BoundID: %s] %s"%(key,objType, binding,self.IndicesToCells(indices))
            print
        return True

    def ExtractAdjacencyData(self):
        if self.verbose:
            self.Banner("Extracting Adjacency Information")
        # First, we need to build up a map of all the indexes and the
        # rooms that they are attached to.
        # We do this by inverting the rooms data.
        roomDict = self.outputDict[MapDataExtractor.KEY_ROOMS]
        indexDict = {}
        for room in roomDict:
            for layerIndex in roomDict[room]:
                if indexDict.has_key(layerIndex):
                    return self.FatalError("Layer Index %s present twice in room dict."%layerIndex)
                # We are going to build up information for each index and put it into
                # this dictionary.  The first element will be the room the index is in.
                indexDict[layerIndex] = [room]
        # Now we also need to remove any indexes for objects that are marked as "blocking".
        if len(self.blockingLayers) > 0:
            if self.verbose:
                print
                print "Removing Blocked Layers"
            for lname in self.blockingLayers:
                for idx in self.layerMap[lname]:
                    if idx in indexDict:
                        if self.verbose:
                            col,row = self.CalculateCellColRow(idx)
                            print "Removing (%4d, %4d) from consideration [Blocking %s]"%(col,row,lname)
                        del indexDict[idx]

        # Build up the "doorDict". We'll need it later
        doorDict = { key:0 for key in self.layerMap[self.doorLayer].keys() if key != 0 }

        # For every layer index, look and figure out if there are adjacent cells for it.
        # Build this up as a walkable list for now.
        # In subsequent steps, we can figure out if the edge is
        # more complex.
        for layerIndex in indexDict:
            adjacentList = self.GetAdjacentIndexes(layerIndex)
            # Only keep the ones that are also in a room
            adjacentList = [adj for adj in adjacentList if adj in indexDict]
            # Now that we have a list of edges to adjacent cells, we have to
            # figure out what kind of edges they are.
            temp = []
            for adj in adjacentList:
                # We know it must at least be "walkable"
                edgeType = MapDataExtractor.KEY_EDGE_WALK
                src = layerIndex
                des = adj
                srcRoom = indexDict[src][0]
                desRoom = indexDict[des][0]
                if srcRoom != desRoom:
                    # Must be more complex
                    edgeType = MapDataExtractor.KEY_EDGE_ROOM
                    # If there is a door on both layer indices, then this must
                    # be a door edge.
                    if src in doorDict and des in doorDict:
                        edgeType = MapDataExtractor.KEY_EDGE_DOOR
                temp.append((adj,edgeType))
            indexDict[layerIndex].append(temp)
        self.outputDict[MapDataExtractor.KEY_ADJACENCY] = indexDict
        if self.verbose:
            keys = indexDict.keys()
            keys.sort()
            # To make this a little cleaner, we are going to construct to lists
            # of outputs.  One for "walking" and one for "the rest".
            walkEdges = []
            restEdges = []
            for key in keys:
                colSrc, rowSrc = self.CalculateCellColRow(key)
                roomSrc = indexDict[key][0]
                for adj,etype in indexDict[key][1]:
                    colDes, rowDes = self.CalculateCellColRow(adj)
                    roomDes = indexDict[adj][0]
                    if roomDes != roomSrc:
                        restEdges.append("(%4d, %4d) --> (%4d, %4d) [Room %d -> %d] by %s Edge." % (
                            colSrc, rowSrc, colDes, rowDes, roomSrc, roomDes, etype))
                    else:
                        walkEdges.append("(%4d, %4d) --> (%4d, %4d) [Room %d]" % (
                            colSrc, rowSrc, colDes, rowDes, roomDes))
            print
            print "Walking Edges:"
            if self.reallyVerbose:
                for item in walkEdges:
                    print item
            else:
               print "<Not Showing>"
            print
            print "Other Types of Edges"
            for item in restEdges:
                print item

        return True

    def ExportTilemapData(self,writer):
        # Export the Tilemap Data
        writer.writerow(["Tilemap", "File", self.tiledFile])
        writer.writerow(["Tilemap", "TileHeight", self.tileHeight])
        writer.writerow(["Tilemap", "TileWidth", self.tileWidth])
        writer.writerow(["Tilemap", "LayerHeight", self.layerHeight])
        writer.writerow(["Tilemap", "LayerWidth", self.layerWidth])
        writer.writerow(["Tilemap", "BlockingLayers"] + self.blockingLayers)
        writer.writerow(["Tilemap", "BindingLayers"] + self.bindingLayers)

    def ExportGraphData(self,writer):
        # Export the basic graph data
        # Indices
        indices = self.outputDict[MapDataExtractor.KEY_WALKABLE].keys()
        indices.sort()
        # Split it into chunks
        chunkCount = 0
        chunks = [indices[x:x + MapDataExtractor.CSV_EXPORT_COLUMNS]
                  for x in xrange(0, len(indices), MapDataExtractor.CSV_EXPORT_COLUMNS)]
        for chunk in chunks:
            chunkCount += len(chunk)
            writer.writerow(["Graph", "Indices"] + chunk)
        if chunkCount != len(indices):
            return self.FatalError("Chunk count = %d, but index count = %d!!!" % (chunkCount, len(indices)))
        # Adjacency
        adj = self.outputDict[MapDataExtractor.KEY_ADJACENCY]
        adjIdx = adj.keys()
        adjIdx.sort()
        for srcIdx in adjIdx:
            srcRoom = adj[srcIdx][0]
            for desIdx, edgeType in adj[srcIdx][1]:
                desRoom = adj[desIdx][0]
                writer.writerow(["Graph", "Adjacent", srcIdx, desIdx, srcRoom, desRoom, edgeType])

    def ExportRoomData(self,writer):
        # Export the Room Indices
        roomDict = self.outputDict[MapDataExtractor.KEY_ROOMS]
        rooms = roomDict.keys()
        rooms.sort()
        for room in rooms:
            indices = roomDict[room][:]
            indices.sort()
            chunkCount = 0
            chunks = [indices[x:x + MapDataExtractor.CSV_EXPORT_COLUMNS]
                      for x in xrange(0, len(indices), MapDataExtractor.CSV_EXPORT_COLUMNS)]
            for chunk in chunks:
                chunkCount += len(chunk)
                writer.writerow(["Room", "Indices", room] + chunk)
            if chunkCount != len(indices):
                return self.FatalError("Chunk count = %d, but index count = %d!!!" % (chunkCount, len(indices)))
    def ExportObjectData(self,writer):
        subjects = self.outputDict[MapDataExtractor.KEY_OBJECTS]
        keys = subjects.keys()
        keys.sort()
        for key in keys:
            objType, indices, binding = subjects[key]
            writer.writerow(["Object", "Define", key, objType])
            writer.writerow(["Object", "Indices", key] + indices)
            writer.writerow(["Object", "Binding", key] + binding)


    def ExportData(self):
        with open(self.outFile, 'wb') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["PKey","SKey","Parameters"])
            # Basic Tilemap parameters
            self.ExportTilemapData(writer)
            # Nodes and Adjacency
            self.ExportGraphData(writer)
            # Rooms
            self.ExportRoomData(writer)
            # Objects
            self.ExportObjectData(writer)

            return True
        return False

    def CheckInputs(self):
        if self.doorLayer not in self.layerMap:
            return self.FatalError("Door Layer %s not in layers." % self.doorLayer)
        if self.wallLayer not in self.layerMap:
            return self.FatalError("Wall Layer %s not in layers." % self.wallLayer)
        if self.floorLayer not in self.layerMap:
            return self.FatalError("Floor Layer %s not in layers." % self.floorLayer)
        for exclude in self.excludeLayers:
            if exclude not in self.layerMap:
                return self.FatalError("Exclude Layer %s not in layers."%exclude)
        for blocking in self.blockingLayers:
            if blocking not in self.layerMap:
                return self.FatalError("Blocking Layer %s not in layers."%blocking)
        return True

    def ProcessMap(self,
                   tiledFile,
                   floorLayer,
                   wallLayer,
                   doorLayer,
                   navPrefix,
                   outFile,
                   excludeLayers,
                   blockingLayers,
                   bindingLayers,
                   diagonalEdges,
                   verbose,
                   reallyVerbose):
        # Cache inputs
        self.tiledFile = tiledFile
        self.floorLayer = floorLayer
        self.doorLayer = doorLayer
        self.wallLayer = wallLayer
        self.navPrefix = navPrefix
        self.outFile = outFile
        self.excludeLayers = excludeLayers
        self.blockingLayers = blockingLayers
        self.bindingLayers = bindingLayers
        self.verbose = verbose
        self.diagonalEdges = diagonalEdges
        self.reallyVerbose = reallyVerbose

        # Pull in the tile map.
        if not self.LoadTiledMap(tiledFile):
            return False

        if not self.CheckInputs():
            return False

        # Extract the rooms.
        if not self.ExtractRoomsData():
            return False

        # Extract the objects.
        if not self.ExtractObjectsData():
            return False

        # Extract adjacency
        if not self.ExtractAdjacencyData():
            return False

        if not self.ExportData():
            return False

        return True

if __name__ == "__main__":
    arguments = docopt.docopt(__doc__)
    # When testing is done, this is where
    # test arguments are inserted.

    # Some temporary Arguments
    """
    arguments["<tiledFile>"] = "tiled.tmx"
    arguments["--verbose"] = True
    arguments["--binding"] = ["Activators"]
    """

    # It is a good idea to print these out so you
    # can see if you typed in something incorrectly.
    print "-----------------------------------"
    print "Inputs:"
    args = arguments.keys()
    args.sort()
    for arg in args:
        print "%-25s %s" % (arg, arguments[arg])
    print "-----------------------------------"


    # Parse the arguments
    tiledFile = arguments["<tiledFile>"]
    excludeLayers = arguments["--exclude"]
    blockingLayers = arguments["--blocking"]
    bindingLayers = arguments["--binding"]
    doorLayer = arguments["--doorLayer"]
    wallLayer = arguments["--wallLayer"]
    floorLayer = arguments["--floorLayer"]
    navPrefix = arguments["--navPrefix"]
    outFile = arguments["--outFile"]
    reallyVerbose = arguments['--reallyVerbose']
    verbose = arguments["--verbose"] or reallyVerbose
    diagonalEdges = not arguments["--noDiagonalEdges"]

    extractor = MapDataExtractor()
    extractor.ProcessMap(tiledFile,
                         floorLayer,
                         wallLayer,
                         doorLayer,
                         navPrefix,
                         outFile,
                         excludeLayers,
                         blockingLayers,
                         bindingLayers,
                         diagonalEdges,
                         verbose,
                         reallyVerbose
                         )
