bl_info = {
    "name": "SL Renamer",
    "author": "",
    "version": (0, 1, 0),
    "blender": (4, 3, 0),
    "location": "View3D > Sidebar > SL Renamer",
    "description": "Rename physics and LOD files/objects to match Second Life naming conventions",
    "category": "Object",
}

import traceback

try:
    from . import core
    from .ui import panel
except Exception as e:
    print("SL Renamer: failed to import submodules:")
    traceback.print_exc()
    # re-raise so Blender's addon loader still sees the failure
    raise

classes = []


def register():
    core.register()
    panel.register()


def unregister():
    panel.unregister()
    core.unregister()
