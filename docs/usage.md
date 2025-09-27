Usage examples
=============

Example 1 — quick rename (dry-run)

- Select up to four objects in Blender representing High, Medium, Low, Phys LODs.
- Open Sidebar -> SL Renamer.
- Enter base name: `chair_wood`.
- Ensure "Rename Files" is OFF and "Dry Run" is ON.
- Click "Rename LODs and Phys". Check the console for proposed file renames.

Example 2 — rename files on disk

- Prepare a backup copy of your mesh files.
- In the addon, set Target Directory to the folder with your mesh files.
- Enable "Rename Files" and set "Dry Run" OFF.
- Click the rename button.

File matching

The addon attempts to match files containing the keywords `high`, `medium`, `low`, or `phys` in their filename and will rename them to the configured templates. It recognizes common 3D file extensions (.obj, .fbx, .dae, .blend, .gltf, .glb).

Safety

- This tool will move/rename files. Work on copies when testing.
- Blender's Python console and the system console will print actions and any errors encountered.
