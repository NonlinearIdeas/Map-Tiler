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
                    [--filePattern=PATTERN]
                    [--outTileset=OUTTILESET]
                    [--outTiled=OUTTILED]
                    [--forceSquareTileset]
                    [<layerImage>...]

Arguments:


Options:
    layerImage                 A list of image files to be used as
                                inputs.  They will be processed and
                                placed into the .tmx file in the
                                order entered.  Or sorted if a
                                search pattern is used.
    --tileWidth=WIDTH           The tile width in pixels.
                                [Default: 64]
    --tileHeight=HEIGHT         The tile height in pixels.
                                [Default: 64]
    --filePattern=PATTERN       A glob pattern for image files.
    --outTileset=OUTTILESET     The output tileset image file.
                                [Default: tileset.png]
    --outTiled=OUTTILED         The output Tiled file in .tmx format.
                                [Default: tiled.tmx]
    --forceSquareTileset        If present, the tileset image will be
                                a square image.  The output tileset image
                                is always a power of 2 in size.

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
from lxml import etree
import docopt
import math


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


    def __init__(self):
        pass


    # Updates the gid for a tile based on the rotation
    # and flipX flag passed in from the PyxelEdit element.
    def UpdateGIDForRotation(self, gid, xForm):
        # Constants used in Tiled to indicate flip/rotation
        FLIPPED_HORIZONTALLY_FLAG = 0x80000000
        FLIPPED_VERTICALLY_FLAG = 0x40000000
        FLIPPED_DIAGONALLY_FLAG = 0x20000000
        flipX, flipY, flipD = MapTiler.TRANSFORM_DICT[xForm]
        if flipX:
            gid += FLIPPED_HORIZONTALLY_FLAG
        if flipY:
            gid += FLIPPED_VERTICALLY_FLAG
        if flipD:
            gid += FLIPPED_DIAGONALLY_FLAG
        return gid


    def CreateLayerFiles(self, inputFilePattern = None, fileList = []):
        if inputFilePattern:
            files = glob.glob(inputFilePattern)
            if len(files) == 0:
                print "No files found matching pattern %s." % self.inputFilePattern
                print "Unable to continue."
                return False
            else:
                files.sort()
                fileList += files
        # If there are no files to process, we are done.
        if len(fileList) == 0:
            print "No files to process."
            print "Unable to continue."
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
        imgFile = Image.open(self.layerFiles[0])
        imageWidth, imageHeight = imgFile.size
        if imageWidth % self.tileWidth != 0:
            print "File %s's Width %d cannot be divided evenly by tile width %d." % (
                self.layerFiles[0], imageWidth, self.tileWidth)
            print "Unable to continue."
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
            imgFile = Image.open(other)
            width, height = imgFile.size
            if width != self.imageWidth or height != self.imageHeight:
                print "Image %s Size (%d x %d) does not match base size (%d x %d)" % (
                    other, width, height, self.imageWidth, self.imageHeight)
                print "Unable to continue."
                return False
        return True

    def CalculateImageIndexFromCell(self, col, row):
        index = row * self.tileWidth + col
        return index

    def CalculateImageRowCell(self, index):
        row = index / self.layerWidth
        col = index % self.layerWidth
        return row, col

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
        ex.load()
        return ex

    def CreateTileset(self):
        self.imageDict = {}
        self.layerDict = {}
        # Create an empty tile.
        # There is almost ALWAYS at least one of these.
        emptyTile = Image.new('RGBA', (self.tileWidth, self.tileHeight ), (0, 0, 0, 0))
        self.imageDict[0] = emptyTile
        self.emptyTileIndex = 0
        subimgIdx = 1
        emptyImgIdx = None
        for fname in self.layerFiles:
            lname = os.path.split(fname)[1]
            lname = os.path.splitext(lname)[0]
            print "Creating Subimages for layer %s" % lname
            self.layerDict[lname] = {}
            img = Image.open(fname)
            for idx in xrange(self.layerTiles):
                subimg = self.ExtractSubimage(img, idx)
                foundXform = False
                row, col = self.CalculateImageRowCell(idx)
                for desIdx in self.imageDict.keys():
                    xForm = self.FindImageTransformation(subimg, self.imageDict[desIdx])
                    if xForm != None:
                        # We have an equivalent transformation
                        self.layerDict[lname][idx] = (desIdx, xForm)
                        # print "Layer %s, Index %d (%d,%d) maps onto image %d, xForm %d."%(lname,idx,row,col,desIdx,xForm )
                        foundXform = True
                        break
                if not foundXform:
                    # Keep this one.
                    self.imageDict[subimgIdx] = subimg
                    self.layerDict[lname][idx] = (subimgIdx, 0)
                    # print "Layer %s, Index %d (%d,%d) is a new image."%(lname,idx,row,col)
                    # Increment the subimage index for the next one.
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
                row, col = self.CalculateImageRowCell(idx)
                print " -[%d] (%d, %d) %s" % (idx, col, row, self.layerDict[lname][idx])
            print

    # For each image, a single number will be computed that will be used as an "image metric".
    # The number will be based on the histogram, which makes it rotation/flipping invariant.
    # The number will be an integer so that numerical issues with the LSBs will not affect
    # the outcome (in general).
    # This number is NOT meant to be a method to compare if two images are the same.  It is
    # meant to be used to determine that two images are NOT the same (culling) so that a
    # second computationally more expensive test may be performed.
    def CalculateImageMetric(self, image):
        histogram = image.histogram()
        hSum = sum(histogram)
        return int(hSum)

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
        print "For %d tiles, the image size will be %d x %d tiles (%d x %d pixels)" % (
            tileCount, imageDimWidth, imageDimHeight, imageWidth, imageHeight
        )
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

    def ExportTiledFile(self):
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
            layer = etree.SubElement(outRoot, "layer")
            layer.attrib["name"] = lname
            layer.attrib["width"] = "%s" % self.layerWidth
            layer.attrib["height"] = "%s" % self.layerHeight
            data = etree.SubElement(layer, "data")
            # In each layer, there are width x height tiles.
            for idx in xrange(self.layerTiles):
                tile = etree.SubElement(data, "tile")
                gid, xForm = self.layerDict[lname][idx]
                if (gid == 0):
                    # This is the "empty" tile
                    tile.attrib["gid"] = "0"
                else:
                    tile.attrib["gid"] = str(self.UpdateGIDForRotation(gid + 1, xForm))

        outTree = etree.ElementTree(outRoot)
        if os.path.exists(self.outTiledFile):
            os.remove(self.outTiledFile)
        outTree.write(self.outTiledFile, encoding="UTF-8", xml_declaration=True, pretty_print=True)
        print "Saving tiled file to %s." % self.outTiledFile

    def ProcessInputs(self,
                      tileWidth=64,
                      tileHeight=64,
                      fileList = [],
                      inputFilePattern="*.png",
                      outTilesetFile="tileset.png",
                      outTiledFile="tiled.tmx",
                      forceSquareTileset=True):
        self.tileWidth = tileWidth
        self.tileHeight = tileHeight
        self.outTilesetFile = outTilesetFile
        self.outTiledFile = outTiledFile
        self.forceSquareTileset = forceSquareTileset
        if not self.CreateLayerFiles(inputFilePattern,fileList):
            return False
        if not self.CheckImageSizes():
            return False
        if not self.CreateTileset():
            return False
        # self.DumpTilemap()
        self.ExportTileset()
        self.ExportTiledFile()
        return True

if __name__ == "__main__":
    arguments = docopt.docopt(__doc__)
    print "-----------------------------------"
    print "Inputs:"
    args = arguments.keys()
    args.sort()
    for arg in args:
        print "%-25s %s"%(arg,arguments[arg])
    print "-----------------------------------"
    tileWidth = int(arguments['--tileWidth'])
    tileHeight = int(arguments['--tileHeight'])
    outTiled = arguments['--outTiled']
    outTileset = arguments['--outTileset']
    fileNames = arguments["<layerImage>"]
    filePattern = arguments["--filePattern"]
    forceSquareTileset = arguments['--forceSquareTileset']
    fileList = arguments["<layerImage>"]
    # Now execute the parser
    parser = MapTiler()
    parser.ProcessInputs(tileWidth,tileHeight,fileList,filePattern,outTileset,outTiled)
