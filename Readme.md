CreateElegooNeptune3Thumbnail Post Processing Script for Cura
=============================================================

This post-processing script uses the Elegoo provided image encoding libraries to generate a preview thumbnail, on the printer.

These libraries come with Elegoo Cura. If anyone knowns more about these, let me know in an issue. If we can come up with a pure python implementation, then this could be made easier to release.

Library Installation
--------------------

I don't know how the image encoding works, so the Elegoo provided libraries are used.

These libraries come from Elegoo Cura, found at: https://www.elegoo.com/pages/3d-printing-user-support

Within the `Cura/plugins/MKS Plugin` folder you will find:
    - ColPic_X64.dll: Windows
    - libColPic.dylib: macOS
    - libColPic.so: Linux

I did not provide the libraries in this repo, because I don't know what the licensing is, and I don't know what's in them.

They must be manually copied to a "lib" folder, alongside this script. See the Readme.md in the lib folder, for special instructions for macOS.

Script Installation
-------------------

This is a script used by the PostProcessingPlugin that comes with Cura.

1. Find where user scripts are stored.

In Cura, click Help in the menu, then "Show Configuration Folder". In there, you'll see a "scripts" folder. Place CreateElegooNeptune3Thumbnail.py, and the lib folder into there. 

