SL Renamer — Quick Start
=========================

This is a small Blender add-on that helps rename mesh and physics LODs to match Second Life naming conventions.

Quick setup (user-friendly)
---------------------------

1. Install the add-on

    - Open Blender.
    - Go to Edit → Preferences → Add-ons.
    - Click "Install..." and select the `sl_renamer` folder (or the ZIP if you exported one).
    - Enable the add-on by checking its box in the Add-ons list.

2. Open the SL Renamer panel

    - In the 3D Viewport, open the right-hand Sidebar (press N if hidden).
    - Look for the "SL Renamer" tab or panel.

3. Use the tool

    - Enter a Base Name: this will be used as the prefix for renamed objects/files.
    - Select LOD levels or objects you want to rename (use Blender's selection tools in Object Mode).
    - (Optional) Choose a target folder if you want files on disk renamed as well.
    - Toggle "Rename Files" if you want the add-on to rename files on disk (off by default — safe).
    - Click the button labeled "Rename LODs and Phys" (or similar) to perform the renaming.

Safety tips
-----------

    - The add-on tries to be safe by default. If you enable file renames, consider testing on a copy of your files first.
    - If you have many objects, work on a small sample first to confirm the results match your expectations.

Troubleshooting
---------------

    - If the panel does not appear, ensure the add-on is enabled in Preferences and you are in Object Mode with at least one object selected.
    - If file renames fail due to permissions or missing files, try running Blender with appropriate permissions or check the target directory path.

Want to learn more?
-------------------

See `docs/usage.md` for more detailed usage examples and screenshots.

Enjoy — and always keep backups of important assets before running bulk renames.
