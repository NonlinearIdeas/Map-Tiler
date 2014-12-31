Map-Tiler
=========

A Python script to take a series of images/layers and turn them into a Tiled file along with a tileset.

I was working on a project and created a map with multiple layers (floor, walls, doors, objects, etc.) in a vector art program.
When I wanted to import this into a tilemap program (Pyxel Editor, Tiled), I found that while they could both chop up the images
into tiles (and PyxelEdit could even merge duplicates), it DID NOT AUTOMATICALLY CREATE LAYERS FOR THE IMAGES.  So I had to 
create the art, then manually create the orientation of the tiles in the second tool.  That seems a bit...inefficient.

Currently, it will do the following:

1. Import a series of images by a (glob) pattern.  The pattern can be "*.png", or include a full path with wildcards.

2. Verify all the images are the same size.

3. Verify they are an even multiple of the tileWidth and tileHeight.

4. Chop up the images into a tileset of tileWidth x tileHeight size, removing duplicates.  Duplicates are
   checked based on the eight cardinal "flips" that Tiled uses (flipX, flipY, flipDiagonal).

5. Generate an output tileset (named as an input).

6. Generate an output Tiled file (named as an input).

See the notes on check-ins to see future work and plans.
