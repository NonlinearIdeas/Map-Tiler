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
Usage: MapTiler.py  [--tileWidth=WIDTH]
                    [--tileHeight=HEIGHT]
                    [--tileOffX=OFFX]
                    [--tileOffY=OFFY]
                    [--tileInsetX=INSETX]
                    [--tileInsetY=INSETY]
                    [--filePattern=PATTERN]
                    [--floorLayer=FLOORLAYER]
                    [--wallLayer=WALLLAYER]
                    [--portalLayer=PORTALLAYER]
                    [--doorLayer=DOORLAYER]
                    [--addNavLayers]
                    [--forceSquareTileset]
                    [--overwriteExisting]
                    [--mergeExisting]
                    [--outTileset=OUTTILESET]
                    [--outTiled=OUTTILED]
                    [--outNavPrefix=OUTNAVPRE]
                    [--verbose]
                    [<layerImage>...]

Argumnts:


Options:
    layerImage                  A list of image files to be used as
                                inputs.  They will be processed and
                                placed into the .tmx file in the
                                order entered.  Or sorted if a
                                search pattern is used.
    --tileWidth=WIDTH           The tile width in pixels.
                                [Default: 64]
    --tileHeight=HEIGHT         The tile height in pixels.
                                [Default: 64]
    --tileOffX=OFFX             Offset pixels in the image in the
                                horizontal direction.  May NOT
                                be negative.
                                [Default: 0]
    --tileOffY=OFFY             Offset pixels in the image in the
                                vertical direction.  May NOT
                                be negative.
                                [Default: 0]
    --tileInsetX=INSETX         Offset pixels from the right edge.
                                [Default: 0]
    --tileInsetY=INSETY         Offset pixels from the bottom edge.
                                [Default: 0]
    --filePattern=PATTERN       A glob pattern for image files.
    --outTileset=OUTTILESET     The output tileset image file.
                                [Default: tileset.png]
    --outTiled=OUTTILED         The output Tiled file in .tmx format.
                                [Default: tiled.tmx]
    --forceSquareTileset        If present, the tileset image will be
                                a square image.  The output tileset image
                                is always a power of 2 in size.
    --floorLayer=FLOORLAYER     Define the name for the floor layer to be
                                used in nav map generation.  See below.
    --wallLayer=WALLLAYER       Define the name for the wall layer to be
                                used in nav map generation.  See below.
    --portalLayer=PORTALLAYER   Define the name for the portal layer to be
                                used in nav map generation.  See below.
    --doorLayer=DOORLAYER       Define the name for the door layer to be
                                used in nav map generation.
    --addNavLayers              Add navigation tiles and layers to the Tiled output.
                                This will also add tiles to the tileset.
    --outNavPrefix=OUTNAVPRE    If the floorLayer, wallLayer, and portalLayer options are
                                specified, navigation data will be generated.  This
                                option specifies the prefix for the navigation output
                                csv files.
                                [Default: NAV_]
    --verbose                   If present, give output while working.
    --overwriteExisting         Overwrite output files with new files.

    --mergeExisting             Overwrite the tileset file and attempt
                                to merges the layers in the new file
                                with the existing file.  See below.


Merging and Overwriting
------------------------------------------------------------------------------
The script will check if the output files exist first.  The default
behavior IS TO FAIL if they do.  This is to prevent you from accidentally
overwriting your data files.

If the --overwriteExisting flag is set, the existing files will be overwritten
without checking.  If the --mergeExisting option is set, the script will
overwrite the tile set and attempt to merge the tiled file. Ther merge will
fail if the width/height in tiles of the layers has changed.

When failing, the original files will be preserved.

The merge operation ONLY merges new layers into the existing
file.  It does this by iterating through the existing <data>
tag of the layer (if it can find it) and updating each <tile>
element with the gid of the element from the new set.  Otherwise,
it does not touch ANY DATA.  If it cannot find the layer in the
existing file, it is added.

If you have other tilesets in the
existing file with a gid = "1", this operation will generate
bad results.

The --overwriteExisting and --mergeExisting are mutually exclusive.

Generating Navigation Data
------------------------------------------------------------------------------
TBD

Website:        http://www.NonlinearIdeas.com
Repository:     https://github.com/NonlinearIdeas/Map-Tiler
Report Issues:  https://github.com/NonlinearIdeas/Map-Tiler
License:        MIT License - See specific text in source code.
Copyright:      Copyright (c) 2014 Nonlinear Ideas Inc (contact@nlideas.com)
"""



import glob
import os
import Image
import ImageChops
import ImageDraw
import ImageFont
from lxml import etree
import docopt
import math
import datetime
import random


class MapTiler(object):
    # Transformations are numbered 0-7.  The transformations
    # each have three flags, indicating a flip across the X axis,
    # a flip across the y axis, or a diagonal flip.  These correspond
    # to three bits that are stored in Tiled GIDs for each tile
    # when it is put into the layer.
    #
    # These transformations are also equivalent to a flip along the
    # X axis (MirrorX) followed by a rotation of 0 x  90 degrees.
    #
    # There are two different "transform" approaches because the
    # PIL's transform(...) function does not perform a "Flip Diagonal",
    # while Tiled's bits do.  The former is used to determine which
    # transformation is necessary, while the second is used to
    # store it in Tiled.
    TRANSFORM_LIST = [
        # xForm, mirrorX, rot90
        (0, False, 0),
        (1, False, 1),
        (2, False, 2),
        (3, False, 3),
        (4, True, 0),
        (5, True, 1),
        (6, True, 2),
        (7, True, 3),
    ]

    TRANSFORM_DICT = {
        # xForm, flipX, flipY, flipD
        0: ( False, False, False),
        1: ( False, True, True),
        2: ( True, True, False),
        3: ( True, False, True),
        4: ( True, False, False),
        5: ( False, False, True),
        6: ( False, True, False),
        7: ( True, True, True),
    }

    FLIPPED_HORIZONTALLY_FLAG = 0x80000000
    FLIPPED_VERTICALLY_FLAG = 0x40000000
    FLIPPED_DIAGONALLY_FLAG = 0x20000000

    def __init__(self):
        pass


    # Updates the gid for a tile based on the rotation
    # and flipX flag passed in from the PyxelEdit element.
    def UpdateGIDForRotation(self, gid, xForm):
        # Constants used in Tiled to indicate flip/rotation
        flipX, flipY, flipD = MapTiler.TRANSFORM_DICT[xForm]
        if flipX:
            gid += MapTiler.FLIPPED_HORIZONTALLY_FLAG
        if flipY:
            gid += MapTiler.FLIPPED_VERTICALLY_FLAG
        if flipD:
            gid += MapTiler.FLIPPED_DIAGONALLY_FLAG
        return gid

    def ExtractTileIndex(self,gid):
        return gid & \
               MapTiler.FLIPPED_DIAGONALLY_FLAG & \
               MapTiler.FLIPPED_HORIZONTALLY_FLAG & \
               MapTiler.FLIPPED_DIAGONALLY_FLAG


    def CreateLayerFiles(self, inputFilePattern = None, fileList = []):
        if inputFilePattern:
            files = glob.glob(inputFilePattern)
            if len(files) == 0:
                print "No files found matching pattern %s." % self.inputFilePattern
                return False
            else:
                files.sort()
                fileList += files
        # If there are no files to process, we are done.
        if len(fileList) == 0:
            print "No files to process."
            return False
        self.layerFiles = []
        self.layerNames = []
        for file in fileList:
            if not os.path.exists(file):
                print "File %s does not exist."%file
                print "Unable to coninue."
                return False
            if file != self.outTilesetFile:
                self.layerFiles.append(file)
                self.layerNames.append(os.path.splitext(os.path.split(file)[1])[0])
        return True

    def CheckImageSizes(self):
        # Open the first file and get its size.
        imgFile = self.LoadCroppedImage(self.layerFiles[0])
        imageWidth, imageHeight = imgFile.size
        if imageWidth % self.tileWidth != 0:
            print "File %s's Width %d cannot be divided evenly by tile width %d." % (
                self.layerFiles[0], imageWidth, self.tileWidth)
            return False
        if imageHeight % self.tileHeight != 0:
            print "File %s's Height %d cannot be divided evenly by tile height %d." % (
                self.layerFiles[0], imageHeight, self.tileHeight)
            return False
        self.imageWidth = imageWidth
        self.imageHeight = imageHeight
        self.layerWidth = imageWidth / self.tileWidth
        self.layerHeight = imageHeight / self.tileHeight
        self.layerTiles = self.layerWidth * self.layerHeight
        for other in self.layerFiles[1:]:
            imgFile = self.LoadCroppedImage(other)
            width, height = imgFile.size
            if width != self.imageWidth or height != self.imageHeight:
                print "Image %s Size (%d x %d) does not match base size (%d x %d)" % (
                    other, width, height, self.imageWidth, self.imageHeight)
                return False
        return True

    def CalculateImageIndexFromCell(self, col, row):
        index = row * self.layerWidth + col
        return index

    def CalculateImageRowCell(self, index):
        row = index / self.layerWidth
        col = index % self.layerWidth
        return col, row

    def CalculateSubimageRect(self, index):
        row = index / self.layerWidth
        col = index % self.layerWidth
        x0 = col * self.tileWidth
        x1 = x0 + self.tileWidth
        y0 = row * self.tileHeight
        y1 = y0 + self.tileHeight
        return (x0, y0, x1, y1)

    def ExtractSubimage(self, im, index):
        rect = self.CalculateSubimageRect(index)
        ex = im.crop(rect)
        return ex

    def GetOccupiedTiles(self,layerName):
        result = []
        layerDict = self.layerDict[layerName]
        for idx in layerDict:
            tileIdx, xForm = layerDict[idx]
            if tileIdx > 0:
                result.append(idx)
        return result


    def CreateRandomColorTile(self,channelMin=64,channelMax=200,opacity=64,text=None):
        r = random.randint(channelMin,channelMax)
        g = random.randint(channelMin,channelMax)
        b = random.randint(channelMin,channelMax)
        tile = Image.new("RGBA", (self.tileWidth, self.tileHeight), (r,g,b,opacity))
        if text:
            draw = ImageDraw.Draw(tile)
            font = ImageFont.load_default()
            draw.text((4,4),text,(0,0,0),font=font)
        return tile

    def CreateRoomsLayer(self):
        floorTiles = self.GetOccupiedTiles(self.navFloorLayer)
        wallTiles = self.GetOccupiedTiles(self.navWallLayer)
        portalTiles = self.GetOccupiedTiles(self.navPortalLayer)
        doorTiles = self.GetOccupiedTiles(self.navDoorLayer)
        for idx in doorTiles:
            if idx not in portalTiles:
                portalTiles.append(idx)
        walkable = [idx for idx in floorTiles if idx not in wallTiles]
        portals = [idx for idx in portalTiles if idx not in wallTiles]
        rooms = []
        # Use a flood fill algorithm to figure out where the rooms are.
        while len(walkable) > 0:
            # Start a list for the tiles in this room.
            roomTiles = []
            # Push the first element in the walkables onto the list.
            queue = [walkable[0]]
            while len(queue) > 0:
                # Pull it off the stack
                idx = queue.pop(0)
                # It is in the room.
                roomTiles.append(idx)
                x,y = self.CalculateImageRowCell(idx)
                adjacent = [self.CalculateImageIndexFromCell(x,y+1),
                       self.CalculateImageIndexFromCell(x,y-1),
                       self.CalculateImageIndexFromCell(x+1,y),
                       self.CalculateImageIndexFromCell(x-1,y)]
                for adj in adjacent:
                    if adj in roomTiles:
                        continue
                    if adj not in walkable:
                        # Already considered or not walkable
                        continue
                    if adj in queue:
                        # Already in consideration
                        continue
                    if idx in portals and adj in portals:
                        # Don't expand beyond doors.
                        continue
                    queue.append(adj)
                # Remove it from walkable...we've looked at it now.
                walkable.remove(idx)
            rooms.append(roomTiles)
        # Cache off the rooms
        self.roomDict = {}
        for idx in xrange(len(rooms)):
            self.roomTilesDict[idx] = rooms[idx]
        # Create the layer
        layerDict = { idx:(0,0) for idx in xrange(self.layerTiles) }
        for idx in xrange(len(rooms)):
            tile = self.CreateRandomColorTile(opacity=128,text="R%d"%idx)
            tileIdx = len(self.imageDict)
            self.imageDict[tileIdx] = tile
            for roomTile in rooms[idx]:
                layerDict[roomTile] = (tileIdx,0)
        lname = self.outNavPrefix + "Rooms"
        self.layerDict[lname] = layerDict
        self.layerNames.append(lname)
        return True


    def CreateWalkableLayer(self):
        floorTiles = self.GetOccupiedTiles(self.navFloorLayer)
        wallTiles = self.GetOccupiedTiles(self.navWallLayer)
        walkable = [idx for idx in floorTiles if idx not in wallTiles]
        # Add a tile to represent a blocked cell
        walkTile = Image.new("RGBA", (self.tileWidth, self.tileHeight), (0, 0, 128, 64))
        walkTileIdx = len(self.imageDict)
        self.imageDict[walkTileIdx] = walkTile
        # Add a layer to represent the blocked layer
        lname = self.outNavPrefix + "Walkable"
        layerDict = {}
        for idx in xrange(self.layerTiles):
            if idx in walkable:
                layerDict[idx] = (walkTileIdx, 0)
            else:
                layerDict[idx] = (0, 0)
        self.layerDict[lname] = layerDict
        self.layerNames.append(lname)
        return True

    def CreateBlockingLayer(self):
        wallTiles = self.GetOccupiedTiles(self.navWallLayer)
        # Add a tile to represent a blocked cell
        blockedTile = Image.new("RGBA",(self.tileWidth,self.tileHeight), (128,0,0,64))
        blockedTileIdx = len(self.imageDict)
        self.imageDict[blockedTileIdx] = blockedTile
        # Add a layer to represent the blocked layer
        lname = self.outNavPrefix + "Blocked"
        layerDict = { idx: (0,0) for idx in xrange(self.layerTiles)}
        for idx in xrange(self.layerTiles):
            if idx in wallTiles:
                layerDict[idx] = (blockedTileIdx,0)
        self.layerDict[lname] = layerDict
        self.layerNames.append(lname)
        return True

    def CreateNavData(self):
        if not self.createNavData:
            return True
        if not self.CreateBlockingLayer():
            return False
        if not self.CreateWalkableLayer():
            return False
        if not self.CreateRoomsLayer():
            return False
        return True

    def CreateTileset(self):
        self.imageDict = {}
        self.layerDict = {}
        self.tilesCreated = 0
        self.tilesPossible = 0
        # Create an empty tile.
        # There is almost ALWAYS at least one of these.
        emptyTile = Image.new('RGBA', (self.tileWidth, self.tileHeight ), (0, 0, 0, 0))
        self.imageDict[0] = emptyTile
        self.tilesCreated += 1
        subimgIdx = 1
        tilesToProcess = len(self.layerFiles)*self.layerTiles
        tilesProcessed = 0
        lastTileMatchIndex = 0
        for fname in self.layerFiles:
            lname = os.path.split(fname)[1]
            lname = os.path.splitext(lname)[0]
            if self.verbose:
                print "Creating Subimages for layer %s" % lname
            self.layerDict[lname] = {}
            img = self.LoadCroppedImage(fname)
            foundXform = False
            for idx in xrange(self.layerTiles):
                subimg = self.ExtractSubimage(img, idx)
                foundXform = False
                col, row = self.CalculateImageRowCell(idx)
                self.tilesPossible += 1
                tilesProcessed += 1
                # A slight optimization here.  Tiles are being scanned
                # horizontally and they often repeat.  The last tile is
                # a good candidate for a match, so check this one first.
                # Some "Results"
                # Processing a small map (JanHouse.png) changed the process time from 8 seconds to 6 seconds.
                # Processing a large mpa (kmare.png) changed the process time from 14:51 to 8:48.
                #
                # This approach appears to have some merit.
                #
                xForm = self.FindImageTransformation(subimg, self.imageDict[lastTileMatchIndex])
                if xForm != None:
                    self.layerDict[lname][idx] = (lastTileMatchIndex, xForm)
                    if self.verbose:
                        print "[%5.1f%% Complete] [%5.1f%% Eff] Layer %s, Index %d (%d,%d) maps onto image %d, xForm %d." % (
                            100 * tilesProcessed / tilesToProcess,
                            100 * (1.0 - self.tilesCreated * 1.0 / self.tilesPossible),
                            lname, idx, row, col, lastTileMatchIndex, xForm )
                    continue

                for desIdx in self.imageDict.keys():
                    # Already checked this one.
                    if desIdx == lastTileMatchIndex:
                        continue
                    xForm = self.FindImageTransformation(subimg, self.imageDict[desIdx])
                    if xForm != None:
                        # We have an equivalent transformation
                        self.layerDict[lname][idx] = (desIdx, xForm)
                        if self.verbose:
                            print "[%5.1f%% Complete] [%5.1f%% Eff] Layer %s, Index %d (%d,%d) maps onto image %d, xForm %d."%(
                                100*tilesProcessed/tilesToProcess,
                                100*(1.0-self.tilesCreated*1.0/self.tilesPossible),
                                lname,idx,row,col,desIdx,xForm )
                        foundXform = True
                        lastTileMatchIndex = desIdx
                        break

                if not foundXform:
                    # Keep this one.
                    self.imageDict[subimgIdx] = subimg
                    self.layerDict[lname][idx] = (subimgIdx, 0)
                    if self.verbose:
                        print "[%5.1f%% Complete] [%5.1f%% Eff] Layer %s, Index %d (%d,%d) is a new image."%(
                            100.0 * tilesProcessed / tilesToProcess,
                            100 * (1.0 - self.tilesCreated * 1.0 / self.tilesPossible),
                            lname,idx,row,col)
                    # Increment the subimage index for the next one.
                    lastTileMatchIndex = subimgIdx
                    self.tilesCreated += 1
                    subimgIdx += 1
        return True

    def DumpTilemap(self):
        print "---------------------------------"
        print 'Tile Map'
        print "---------------------------------"
        for fname in self.layerFiles:
            lname = os.path.split(fname)[1]
            lname = os.path.splitext(lname)[0]
            print "Layer:", lname
            for idx in xrange(self.layerTiles):
                col, row = self.CalculateImageRowCell(idx)
                print " -[%d] (%d, %d) %s" % (idx, col, row, self.layerDict[lname][idx])
            print

    # Determine if two images are the same by comparing rotations and
    # reflections between them.  If a transformation can be found that
    # turns the first into the second, return it.  Otherwise return None.
    # This is NOT a trivial operation.
    def FindImageTransformation(self, im1org, im2org):
        for xForm, mirrorX, rot90 in MapTiler.TRANSFORM_LIST:
            im2 = im2org
            if mirrorX:
                im2 = im2.transpose(Image.FLIP_LEFT_RIGHT)
            if rot90 == 1:
                im2 = im2.transpose(Image.ROTATE_90)
            elif rot90 == 2:
                im2 = im2.transpose(Image.ROTATE_180)
            elif rot90 == 3:
                im2 = im2.transpose(Image.ROTATE_270)
            if im1org.size != im2.size:
                # Don't compare images that are not the same size.
                continue
            if ImageChops.difference(im1org, im2).getbbox() is None:
                # They are the same now
                return xForm
        return None

    def FindNextPowerOfTwo(self, N):
        k = 1
        while k < N:
            k = k * 2
        return k

    def ExportTileset(self):
        # How many tiles do we have?
        tileCount = len(self.imageDict)
        # Need to create a "square" image that is a power of 2
        # This helps with GPUs, etc.
        imageDimWidth = self.FindNextPowerOfTwo(math.sqrt(tileCount))
        imageDimHeight = imageDimWidth
        if self.forceSquareTileset:
            # To save on space, we'll decrement the dimension by 1 until we
            # can't fit the tiles.
            while imageDimHeight * imageDimWidth > tileCount:
                imageDimHeight = imageDimHeight / 2
            imageDimHeight = imageDimHeight * 2
        imageWidth = imageDimWidth * self.tileWidth
        imageHeight = imageDimHeight * self.tileHeight
        self.tilesetWidth = imageWidth
        self.tilesetHeight = imageHeight
        print "For %d tiles, the image size will be %d x %d tiles (%d x %d pixels)." % (
            tileCount, imageDimWidth, imageDimHeight, imageWidth, imageHeight)
        print "Efficiency = 100%%(1-Tiles Created / Tiles Possible) => 100%%(1-%d/%d) = %4.1f%%."%(
            self.tilesCreated,
            self.tilesPossible,
            100*(1.0-self.tilesCreated*1.0/self.tilesPossible))
        # Create the output image
        imgOut = Image.new('RGBA', (imageWidth, imageHeight), (0, 0, 0, 0))
        for idx in xrange(tileCount):
            row = idx / imageDimWidth
            col = idx % imageDimWidth
            x0 = col * self.tileWidth
            y0 = row * self.tileHeight
            x1 = x0 + self.tileWidth
            y1 = y0 + self.tileHeight
            imgOut.paste(self.imageDict[idx], (x0, y0, x1, y1))
        print "Saving tileset to %s." % self.outTilesetFile
        imgOut.save(self.outTilesetFile)
        return True

    def LoadCroppedImage(self,fileName):
        image = Image.open(fileName)
        w, h = image.size
        x0 = self.tileOffX
        y0 = self.tileOffY
        x1 = w - self.tileInsetX
        y1 = h - self.tileInsetY
        img = image.crop((x0, y0, x1, y1))
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        return img

    def CreateTiledFile(self):
        # Build the root node ("map")
        outRoot = etree.Element("map")
        outRoot.attrib["version"] = "1.0"
        outRoot.attrib["orientation"] = "orthogonal"
        outRoot.attrib["renderorder"] = "left-up"
        outRoot.attrib["width"] = "%s" % self.layerWidth
        outRoot.attrib["height"] = "%s" % self.layerHeight
        outRoot.attrib["tilewidth"] = "%s" % self.tileWidth
        outRoot.attrib["tileheight"] = "%s" % self.tileHeight

        # Build the tileset
        tileset = etree.SubElement(outRoot, "tileset")
        tileset.attrib["firstgid"] = "1"
        tileset.attrib["name"] = os.path.splitext(os.path.split(self.outTilesetFile)[1])[0]
        tileset.attrib["tilewidth"] = "%s" % self.tileWidth
        tileset.attrib["tileheight"] = "%s" % self.tileHeight
        # Add the image information for the tileset
        imgElem = etree.SubElement(tileset, "image")
        imgElem.attrib["source"] = self.outTilesetFile
        imgElem.attrib["width"] = "%s" % self.tilesetWidth
        imgElem.attrib["height"] = "%s" % self.tilesetHeight

        # Now iterate over the layers and pull out each one.
        for lname in self.layerNames:
            self.CreateXMLLayer(outRoot,lname)
        outTree = etree.ElementTree(outRoot)
        return outTree

    def CreateXMLLayer(self,outRoot,layerName):
        layer = etree.SubElement(outRoot, "layer")
        layer.attrib["name"] = layerName
        layer.attrib["width"] = "%s" % self.layerWidth
        layer.attrib["height"] = "%s" % self.layerHeight
        data = etree.SubElement(layer, "data")
        # In each layer, there are width x height tiles.
        for idx in xrange(self.layerTiles):
            tile = etree.SubElement(data, "tile")
            gid, xForm = self.layerDict[layerName][idx]
            if (gid == 0):
                # This is the "empty" tile
                tile.attrib["gid"] = "0"
            else:
                tile.attrib["gid"] = str(self.UpdateGIDForRotation(gid + 1, xForm))

    def MergeTiledFiles(self):
        outTree = etree.parse(self.outTiledFile)
        outRoot = outTree.getroot()
        # Find all the layers in the output tree
        layers = outRoot.findall("layer")
        outLayers = { layer.attrib['name']:layer for layer in layers }
        # For every layer that already exists, just update the GID data.
        # Otherwise, add a new layer to the tree with the data.
        for lname in self.layerNames:
            if lname in outLayers:
                if self.verbose:
                    print "Layer %s will be updated."%lname
                data = outLayers[lname].find("data")
                tiles = data.findall("tile")
                for idx in xrange(len(tiles)):
                    tile = tiles[idx]
                    gid, xForm = self.layerDict[lname][idx]
                    if (gid == 0):
                        # This is the "empty" tile
                        tile.attrib["gid"] = "0"
                    else:
                        tile.attrib["gid"] = str(self.UpdateGIDForRotation(gid + 1, xForm))
            else:
                # Regardless of "verbosity", let the user know we are
                # adding a whole new layer to their map.
                print "Layer %s DOES NOT EXIST in the existing file will be added."%lname
                self.CreateXMLLayer(outRoot, lname)
        return outTree

    def ExportTiledFile(self):
        if os.path.exists(self.outTiledFile):
            if self.mergeExisting:
                outTree = self.MergeTiledFiles()
            else:
                # Not merging, just overwriting
                outTree = self.CreateTiledFile()
        else:
            outTree = self.CreateTiledFile()
        outTree.write(self.outTiledFile, encoding="UTF-8", xml_declaration=True, pretty_print=True)
        print "Saving tiled file to %s." % self.outTiledFile
        return True

    def SecondsToHMS(self,seconds):
        hours = divmod(seconds, 3600)  # hours
        minutes = divmod(hours[1], 60)  # minutes
        return (hours[0],minutes[0],minutes[1])

    # If a merge operation is going to happen, check the existing file
    # and find out the layer width/height in tiles.  If it is not the
    # same, abort the operation.  We could check this at the end, but
    # this would mean the tile set has been created, and that could
    # take a while.
    def CheckMergingFiles(self):
        if not os.path.exists(self.outTiledFile):
            # If the file does not exist, there is nto a problem.
            return True
        if not self.mergeExisting:
            # If we are not merging, there is not a problem.
            return True
        # Load the existing file.
        inTree = etree.parse(self.outTiledFile)
        inRoot = inTree.getroot()

        # Verify the tile width/height.
        layerWidth = int(inRoot.attrib["width"])
        layerHeight = int(inRoot.attrib["height"])
        if layerWidth != self.layerWidth:
            print "Layer width in existing %s = %d which does not match new configuration width %d."%(
                self.outTiledFile,
                layerWidth,
                self.layerWidth)
            return False
        if layerHeight != self.layerHeight:
            print "Layer height in existing %s = %d which does not match new configuration width %d." % (
                self.outTiledFile,
                layerHeight,
                self.layerHeight)
            return False

        # Currently,this script produces only ONE tileset
        # and it will take some work to move them all around
        # and merge them.  So for now at least, the script will
        # fail if the tiled file contains more than one tileset.
        tilesets = inRoot.findall("tileset")
        if len(tilesets) == 0:
            print "Existing Tiled file has no tileset in it.  Cannot merge."
            return False
        if len(tilesets) > 1:
            print "Existing Tiled file has more than one tileset in it."
            return False
        images = tilesets[0].findall("image")
        if len(images) == 0:
            print "Existing tileset has no image associated with it."
            return False
        if len(images) > 1:
            print "Existing tileset is connected to more than one image."
            return False
        imageSrc = images[0].attrib['source']
        if imageSrc != self.outTilesetFile:
            print "Existing tileset uses image %s, not output image %s."%(imageSrc,self.outTilesetFile)
            return False
        return True

    def CheckExistingFiles(self):
        if self.mergeExisting and self.overwriteExisting:
            print "Cannot have options to merge and overwrite existing files."
            return False
        if os.path.exists(self.outTilesetFile):
            if not self.mergeExisting and not self.overwriteExisting:
                print "Output %s exists and would be modified.  Use options to control this."%self.outTilesetFile
                return False
        if os.path.exists(self.outTiledFile):
            if not self.mergeExisting and not self.overwriteExisting:
                print "Output %s exists and would be modified.  Use options to control this."%self.outTiledFile
                return False
        return True

    def CheckNavArguments(self):
        self.createNavData = False
        if self.navPortalLayer or self.navFloorLayer or self.navWallLayer or self.navDoorLayer:
            if self.navPortalLayer == None or self.navWallLayer == None or \
                            self.navFloorLayer == None or self.navDoorLayer == None:
                print "Must specifiy floorLayer, wallLayer, doorLayer, and portalLayer if any are specified."
                return False
            if self.navFloorLayer not in self.layerNames:
                print "Nav Floor Layer %s not in layers."%self.navFloorLayer
                return False
            if self.navWallLayer not in self.layerNames:
                print "Nav Wall Layer %s not in layers." % self.navWallLayer
                return False
            if self.navPortalLayer not in self.layerNames:
                print "Nav Portal Layer %s not in layers." % self.navPortalLayer
                return False
            self.createNavData = True
        return True

    def ProcessInputs(self,
                      tileWidth,
                      tileHeight,
                      tileOffX,
                      tileOffY,
                      tileInsetX,
                      tileInsetY,
                      fileList,
                      inputFilePattern,
                      outTilesetFile,
                      outTiledFile,
                      forceSquareTileset,
                      verbose ,
                      mergeExisting,
                      overwriteExisting,
                      floorLayer,
                      wallLayer,
                      portalLayer,
                      doorLayer,
                      outNavPrefix,
                      addNavLayers):
        self.tileOffX = tileOffX
        self.tileOffY = tileOffY
        self.tileInsetX = tileInsetX
        self.tileInsetY = tileInsetY
        self.tileWidth = tileWidth
        self.tileHeight = tileHeight
        self.outTilesetFile = outTilesetFile
        self.outTiledFile = outTiledFile
        self.forceSquareTileset = forceSquareTileset
        self.verbose = verbose
        self.mergeExisting = mergeExisting
        self.overwriteExisting = overwriteExisting
        self.startTime = datetime.datetime.now()
        self.addNavLayers = addNavLayers
        self.outNavPrefix = outNavPrefix
        self.navWallLayer = wallLayer
        self.navPortalLayer = portalLayer
        self.navFloorLayer = floorLayer
        self.navDoorLayer = doorLayer

        # Main execution path
        if not self.CheckExistingFiles():
            print "Unable to continue."
            return False
        if not self.CreateLayerFiles(inputFilePattern,fileList):
            print "Unable to continue."
            return False
        if not self.CheckNavArguments():
            print "Unable to continue."
            return False
        if not self.CheckImageSizes():
            print "Unable to continue."
            return False
        if not self.CheckMergingFiles():
            print "Unable to continue."
            return False
        if not self.CreateTileset():
            print "Unable to continue."
            return False
        if not self.CreateNavData():
            print "Unable to continue."
            return False
        # self.DumpTilemap()
        if not self.ExportTileset():
            print "Unable to continue."
            return False
        if not self.ExportTiledFile():
            print "Unable to continue."
            return False

        # Report execution time.
        self.stopTime = datetime.datetime.now()
        totalSeconds = (self.stopTime-self.startTime).total_seconds()
        h,m,s = self.SecondsToHMS(totalSeconds)
        print "Started: ",self.startTime
        print "Stopped: ",self.stopTime
        print "Total Run Time: [%d Hrs: %d Min: %d Sec]"%(h,m,s)
        return True

if __name__ == "__main__":
    arguments = docopt.docopt(__doc__)
    # When testing is done, this is where
    # test arguments are inserted.

    arguments["<layerImage>"] = ["Floors.png", "Walls.png", "Objects.png", "Doors.png", "DoorActivators.png", "Portals.png"]
    arguments["--tileWidth"] = "32"
    arguments["--tileHeight"] = "32"
#    arguments["--verbose"] = True
    arguments["--overwriteExisting"] = True
    arguments["--floorLayer"] = "Floors"
    arguments["--wallLayer"] = "Walls"
    arguments["--portalLayer"] = "Portals"
    arguments["--doorLayer"] = "Doors"


    print "-----------------------------------"
    print "Inputs:"
    args = arguments.keys()
    args.sort()
    for arg in args:
        print "%-25s %s"%(arg,arguments[arg])
    print "-----------------------------------"
    tileWidth = int(arguments['--tileWidth'])
    tileHeight = int(arguments['--tileHeight'])
    tileOffX = int(arguments['--tileOffX'])
    tileOffY = int(arguments['--tileOffY'])
    tileInsetX = int(arguments['--tileInsetX'])
    tileInsetY = int(arguments['--tileInsetY'])
    outTiled = arguments['--outTiled']
    outTileset = arguments['--outTileset']
    filePattern = arguments["--filePattern"]
    forceSquareTileset = arguments['--forceSquareTileset']
    fileList = arguments["<layerImage>"]
    verbose = arguments['--verbose']
    mergeExisting = arguments['--mergeExisting']
    overwriteExisting = arguments['--overwriteExisting']
    wallLayer = arguments['--wallLayer']
    portalLayer = arguments['--portalLayer']
    floorLayer = arguments['--floorLayer']
    doorLayer = arguments['--doorLayer']
    addNavLayers = arguments['--addNavLayers']
    outNavPrefix = arguments['--outNavPrefix']

    # Now execute the parser
    parser = MapTiler()
    parser.ProcessInputs(tileWidth,
                         tileHeight,
                         tileOffX,
                         tileOffY,
                         tileInsetX,
                         tileInsetY,
                         fileList,
                         filePattern,
                         outTileset,
                         outTiled,
                         forceSquareTileset,
                         verbose,
                         mergeExisting,
                         overwriteExisting,
                         floorLayer,
                         wallLayer,
                         portalLayer,
                         doorLayer,
                         outNavPrefix,
                         addNavLayers)
