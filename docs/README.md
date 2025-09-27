SL Renamer
===========

A Blender addon to rename mesh and physics LOD files and objects to match Second Life naming conventions.

Structure

- `sl_renamer/` - addon package
  - `core.py` - core renaming logic and Blender operators
  - `ui/panel.py` - UI panel
- `docs/` - documentation

Installation

Copy the `sl_renamer` folder into Blender's addons directory or install via "Install Add-on From File" in Blender's preferences.

Usage

Open the 3D Viewport, Sidebar -> SL Renamer. Provide a base name, select a target directory (optional), enable "Rename Files" to change files on disk, and click "Rename LODs and Phys".

Notes

This initial version makes simple assumptions about selection ordering and file names. Always test on backups before running on important files.
