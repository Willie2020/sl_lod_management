import bpy
import os
from bpy.props import (
    StringProperty,
    BoolProperty,
    EnumProperty,
    PointerProperty,
    CollectionProperty,
    IntProperty,
)

# Naming templates adapted for Second Life: base + LOD/PHYS suffixes
DEFAULT_TEMPLATES = {
    # Second Life prefers LOD0 (highest), LOD1, LOD2 and a separate physics mesh
    'mesh_lod0': "{base}_LOD0",
    'mesh_lod1': "{base}_LOD1",
    'mesh_lod2': "{base}_LOD2",
    'phys': "{base}_PHYS",
}


def apply_template(base, template_key):
    tpl = DEFAULT_TEMPLATES.get(template_key, "{base}")
    return tpl.format(base=base)


def _bl_log(msg: str):
    """Log a message into Blender's Text Editor (SL_Renamer_Log) and print to console.

    This ensures logs are visible inside Blender (open Text Editor -> SL_Renamer_Log)
    and also printed to the system console.
    """
    try:
        # append to or create a text datablock
        txt = bpy.data.texts.get('SL_Renamer_Log')
        if txt is None:
            txt = bpy.data.texts.new('SL_Renamer_Log')
        txt.write(msg + "\n")
    except Exception:
        # ignore text buffer errors
        pass
    try:
        print(msg)
    except Exception:
        pass


class SLRenamerProperties(bpy.types.PropertyGroup):
    base_name: StringProperty(
        name="Base Name",
        description="Base name to use for renamed objects/files",
        default=""
    )
    target_dir: StringProperty(
        name="Target Directory",
        description="Directory to rename files in (optional)",
        default="",
        subtype='DIR_PATH'
    )
    rename_files: BoolProperty(
        name="Rename Files",
        description="Also rename files on disk in the target directory",
        default=False
    )
    dry_run: BoolProperty(
        name="Dry Run",
        description="Don't actually rename files on disk; only show what would happen",
        default=True
    )
    export_format: EnumProperty(
        name="Export Format",
        description="Choose export format for export tools",
        items=[
            ('GLB', 'glb (glTF Binary)', ''),
            ('DAE', 'dae (COLLADA)', ''),
        ],
        default='GLB'
    )
    export_scope: EnumProperty(
        name="Export Scope",
        description="Which objects to export",
        items=[
            ('SELECTION', 'Selection', ''),
            ('ITEMS', 'Items list', ''),
            ('BASES', 'Bases list', ''),
        ],
        default='SELECTION'
    )
    export_mode: EnumProperty(
        name="Export Mode",
        description="Export each object individually or export as one group file",
        items=[
            ('INDIVIDUAL', 'Individual files', 'Export each object to its own file'),
            ('GROUP', 'Single group file', 'Export all selected objects into one file'),
        ],
        default='INDIVIDUAL'
    )
    # allow selecting modifier types to apply during export
    export_modifiers: EnumProperty(
        name="Modifiers to Apply",
        description="Choose modifier types to apply when exporting (multi-select)",
        options={'ENUM_FLAG'},
        items=[
            ('SUBSURF', 'Subdivision', ''),
            ('MIRROR', 'Mirror', ''),
            ('ARRAY', 'Array', ''),
            ('BOOLEAN', 'Boolean', ''),
            ('ARMATURE', 'Armature', ''),
            ('BEVEL', 'Bevel', ''),
            ('SOLIDIFY', 'Solidify', ''),
            ('DECIMATE', 'Decimate', ''),
            ('TRIANGULATE', 'Triangulate', ''),
            ('REMESH', 'Remesh', ''),
            ('SKIN', 'Skin', ''),
            ('LATTICE', 'Lattice', ''),
            ('WELD', 'Weld', ''),
            ('SHRINKWRAP', 'Shrinkwrap', ''),
        ],
        default=set(),
    )
    apply_export_modifiers: BoolProperty(
        name="Apply Selected Modifiers",
        description="If enabled, only the modifiers selected above will be applied to temp copies during export",
        default=False,
    )


class SLRenamerItem(bpy.types.PropertyGroup):
    """An item in the UI list referencing a Blender object and its chosen LOD type"""
    obj: PointerProperty(
        name="Object",
        type=bpy.types.Object,
    )
    lod: EnumProperty(
        name="LOD",
        description="LOD/Type to assign to this item",
        items=[
            ('LOD0', 'High (LOD0)', ''),
            ('LOD1', 'Medium (LOD1)', ''),
            ('LOD2', 'Low (LOD2)', ''),
            ('PHYS', 'Physics (PHYS)', ''),
        ],
        default='LOD0'
    )
    is_base: BoolProperty(
        name="Base",
        description="Mark this item as the reference/base object for its group",
        default=False,
    )
    # pointer to an explicit base object entry (optional)
    base_ref: PointerProperty(
        name="Base Ref",
        type=bpy.types.Object,
    )



class SLRenamerBase(bpy.types.PropertyGroup):
    """Represents an original/base object that can be referenced by other items"""
    obj: PointerProperty(name="Object", type=bpy.types.Object)
    lod0_obj: PointerProperty(name="LOD0", type=bpy.types.Object)
    lod1_obj: PointerProperty(name="LOD1", type=bpy.types.Object)
    lod2_obj: PointerProperty(name="LOD2", type=bpy.types.Object)
    phys_obj: PointerProperty(name="PHYS", type=bpy.types.Object)




class OBJECT_OT_rename_lods(bpy.types.Operator):
    bl_idname = "object.sl_rename_lods"
    bl_label = "Rename LODs and Phys"
    bl_description = "Rename selected objects (or all) to Second Life LOD/phys naming"

    def execute(self, context):
        props = context.scene.sl_renamer_props
        # Determine base name and (preferably) base object.
        base = props.base_name.strip()
        base_obj = None

        # Prefer explicit Bases list if present and a base there matches selection context
        scene_bases = getattr(context.scene, 'sl_renamer_bases', None)
        sel = list(context.selected_objects) if context.selected_objects else []
        if scene_bases and len(scene_bases) > 0:
            # If any base entry exists that is different from selected objects, prefer it when appropriate
            for b in scene_bases:
                if not b.obj:
                    continue
                # If user selected other objects (secondaries), prefer that base
                if any(o != b.obj for o in sel):
                    base_obj = b.obj
                    break
            # else fallback to first registered base
            if base_obj is None:
                base_obj = scene_bases[0].obj

        # If we still don't have a base object, look inside the selection for a LOD0 object
        if base_obj is None:
            for obj in sel or list(context.scene.objects):
                if 'LOD0' in obj.name.upper() or obj.name.upper().endswith('_LOD0'):
                    base_obj = obj
                    break

        # As a last resort, search the whole scene for a LOD0 object
        if base_obj is None:
            for obj in context.scene.objects:
                if 'LOD0' in obj.name.upper() or obj.name.upper().endswith('_LOD0'):
                    base_obj = obj
                    break

        # If we found a base object, derive its base name
        if base_obj is not None:
            bname = base_obj.name
            for sfx in ['_LOD0', '_LOD1', '_LOD2', '_PHYS']:
                if bname.upper().endswith(sfx):
                    base = bname[:-len(sfx)]
                    break
            if not base:
                base = bname

        if not base:
            self.report({'ERROR'}, "Base name is empty and no suitable candidate found")
            return {'CANCELLED'}

        sel = list(context.selected_objects) if context.selected_objects else list(context.scene.objects)
        # Heuristic: try to detect objects named with LOD0/LOD1/LOD2/PHYS or use selection order
        name_map = {}
        keywords = ['lod0', 'lod1', 'lod2', 'phys']
        # If a base object was found, exclude it from the list of secondary candidates
        candidates = [o for o in sel if o is not base_obj]

        # first pass: assign any objects that already contain LOD/PHYS in their names
        used_objs = set()
        for obj in candidates:
            lname = obj.name.lower()
            for kw in keywords:
                if kw in lname and kw not in name_map:
                    name_map[kw] = obj
                    used_objs.add(obj)
                    break

        # second pass: fill remaining slots in preferred order (LOD1, LOD2, PHYS) from remaining candidates
        remaining_keys = [k for k in ['lod1', 'lod2', 'phys'] if k not in name_map]
        ci = 0
        for obj in candidates:
            if obj in used_objs:
                continue
            if ci >= len(remaining_keys):
                break
            kw = remaining_keys[ci]
            name_map[kw] = obj
            used_objs.add(obj)
            ci += 1

        # ensure LOD0 is set: prefer existing LOD0 object, else the base_obj (if present)
        if 'lod0' not in name_map:
            # try candidates first
            for obj in candidates:
                if 'lod0' in obj.name.lower():
                    name_map['lod0'] = obj
                    break
            # fall back to base_obj if available (we don't rename base, but ensure mapping exists)
            if 'lod0' not in name_map and base_obj is not None:
                name_map['lod0'] = base_obj

        # apply names
        mapping = {
            'lod0': apply_template(base, 'mesh_lod0'),
            'lod1': apply_template(base, 'mesh_lod1'),
            'lod2': apply_template(base, 'mesh_lod2'),
            'phys': apply_template(base, 'phys'),
        }

        for kw, obj in name_map.items():
            new_name = mapping.get(kw, f"{base}_{kw}")
            obj.name = new_name
            if getattr(obj, 'data', None):
                try:
                    obj.data.name = new_name
                except Exception:
                    pass

        # Optionally rename files on disk
        if props.rename_files and props.target_dir:
            rename_files_on_disk(props.target_dir, base, dry_run=props.dry_run)

        self.report({'INFO'}, "SL Renamer: Rename complete (check console for details)")
        return {'FINISHED'}


class OBJECT_OT_validate_for_sl(bpy.types.Operator):
    bl_idname = "object.sl_validate_for_sl"
    bl_label = "Validate for SL Upload"
    bl_description = "Check selected objects / LODs for common Second Life upload issues"

    def execute(self, context):
        objs = context.selected_objects if context.selected_objects else list(context.scene.objects)
        issues = []

        # Helper: collect mesh data names and material names per object
        for obj in objs:
            mesh = getattr(obj, 'data', None)
            if mesh is None:
                continue
            # Check mesh data name for spaces/special chars
            if any(ch.isspace() for ch in mesh.name) or any(ord(c) > 127 for c in mesh.name):
                issues.append(f"Mesh data name '{mesh.name}' contains spaces or non-ascii characters")

            # Materials
            mat_names = [m.name for m in getattr(mesh, 'materials', []) if m]
            if len(mat_names) > 8:
                issues.append(f"Mesh '{mesh.name}' has {len(mat_names)} materials (limit 8 recommended)")

        # Check LOD parent relationships by name suffixes
        # Build map of base names found (strip _LOD* and _PHYS)
        name_buckets = {}
        for obj in objs:
            mesh = getattr(obj, 'data', None)
            if not mesh:
                continue
            lname = mesh.name
            base = lname
            for sfx in ["_LOD0", "_LOD1", "_LOD2", "_PHYS"]:
                if lname.endswith(sfx):
                    base = lname[:-len(sfx)]
                    break
            name_buckets.setdefault(base, []).append(lname)

        for base, variants in name_buckets.items():
            # If lower LOD present, ensure parent (no suffix) exists
            for sfx in ["_LOD2", "_LOD1", "_LOD0", "_PHYS"]:
                if any(v.endswith(sfx) for v in variants) and base not in [v for v in variants]:
                    issues.append(f"Base/high LOD mesh '{base}' not found while '{sfx}' variants exist: {variants}")

        if issues:
            for i in issues:
                _bl_log(f"SL Validator: {i}")
            self.report({'WARNING'}, f"Validation found {len(issues)} issue(s). See Text Editor 'SL_Renamer_Log' or system console.")
            return {'FINISHED'}

        self.report({'INFO'}, "Validation passed: no common issues found")
        return {'FINISHED'}


def rename_files_on_disk(directory, base, dry_run=True):
    if not os.path.isdir(directory):
        print(f"SL Renamer: directory not found: {directory}")
        return

    # Second Life accepted upload types are COLLADA (.dae) and glTF Binary (.glb)
    exts = ['.dae', '.glb']
    target_names = {
        'lod0': apply_template(base, 'mesh_lod0'),
        'lod1': apply_template(base, 'mesh_lod1'),
        'lod2': apply_template(base, 'mesh_lod2'),
        'phys': apply_template(base, 'phys'),
    }

    # prepare list of files
    for fname in os.listdir(directory):
        fpath = os.path.join(directory, fname)
        if not os.path.isfile(fpath):
            continue
        name_lower = fname.lower()
        for key, target in target_names.items():
            if key in name_lower:
                base_name, ext = os.path.splitext(fname)
                if ext.lower() in exts:
                    dst = os.path.join(directory, target + ext)
                    if os.path.abspath(fpath) == os.path.abspath(dst):
                        print(f"SL Renamer: skipping {fname}, already named correctly")
                        break
                    print(f"SL Renamer: will rename {fname} -> {os.path.basename(dst)}")
                    if not dry_run:
                        try:
                            os.replace(fpath, dst)
                            print(f"Renamed {fname} -> {os.path.basename(dst)}")
                        except Exception as e:
                            print(f"Failed to rename {fname} -> {os.path.basename(dst)}: {e}")
                    break


class SL_OT_export_scene(bpy.types.Operator):
    """Export selected/items/bases to GLB or DAE with optional modifier application"""
    bl_idname = "scene.sl_export_scene"
    bl_label = "Export SL Group"

    def execute(self, context):
        scene = context.scene
        props = scene.sl_renamer_props

        # Determine objects to export based on scope
        objs = []
        if props.export_scope == 'SELECTION':
            objs = list(context.selected_objects)
        elif props.export_scope == 'ITEMS':
            objs = [it.obj for it in scene.sl_renamer_items if it.obj]
        elif props.export_scope == 'BASES':
            objs = [b.obj for b in scene.sl_renamer_bases if b.obj]

        if not objs:
            self.report({'WARNING'}, 'No objects found for export')
            return {'CANCELLED'}

        # prepare modifier filter set
        mod_flags = set()
        if props.apply_export_modifiers:
            # export_modifiers is an EnumFlag; convert to set of keys
            for flag in ['SUBSURF','MIRROR','ARRAY','BOOLEAN','ARMATURE','BEVEL','SOLIDIFY','DECIMATE','TRIANGULATE','REMESH','SKIN','LATTICE','WELD','SHRINKWRAP']:
                if flag in props.export_modifiers:
                    mod_flags.add(flag)

        export_format = props.export_format
        export_mode = props.export_mode
        target_dir = props.target_dir or bpy.path.abspath("//")

        # ensure directory exists
        if export_mode == 'INDIVIDUAL' and not os.path.isdir(target_dir):
            try:
                os.makedirs(target_dir, exist_ok=True)
            except Exception as e:
                self.report({'ERROR'}, f'Cannot create target directory: {e}')
                return {'CANCELLED'}

        # helper to apply modifiers to a temporary copy object
        def _prepare_object_for_export(obj):
            # duplicate the object (data copy) to avoid changing original, then apply selected modifiers
            tmp = obj.copy()
            if obj.data:
                tmp.data = obj.data.copy()
            # link to the scene collection to ensure export operators can see it
            try:
                scene.collection.objects.link(tmp)
            except Exception:
                try:
                    context.collection.objects.link(tmp)
                except Exception:
                    bpy.context.scene.collection.objects.link(tmp)

            if props.apply_export_modifiers and mod_flags:
                # apply selected modifiers on the tmp object
                prev_active = bpy.context.view_layer.objects.active
                try:
                    bpy.context.view_layer.objects.active = tmp
                    for m in list(tmp.modifiers):
                        mtype = m.type.upper()
                        if mtype in mod_flags:
                            try:
                                bpy.ops.object.modifier_apply(modifier=m.name)
                            except Exception:
                                pass
                finally:
                    try:
                        bpy.context.view_layer.objects.active = prev_active
                    except Exception:
                        pass
            return tmp

        # perform export
        exported_files = []
        if export_mode == 'GROUP':
            # export all objects into a single file
            # create a temporary collection and link duplicates into it
            tmp_collection = bpy.data.collections.new('SL_Renamer_Export_Temp')
            context.scene.collection.children.link(tmp_collection)
            tmp_objs = []
            for o in objs:
                if not o:
                    continue
                tmp = _prepare_object_for_export(o)
                tmp_collection.objects.link(tmp)
                tmp_objs.append(tmp)

            out_name = os.path.join(target_dir, f"sl_export.{export_format.lower()}")
            print(f"SL Export: exporting group to {out_name}")
            # select only the tmp objects
            prev_selected = list(bpy.context.selected_objects)
            try:
                bpy.ops.object.select_all(action='DESELECT')
            except Exception:
                pass
            for o in tmp_objs:
                try:
                    o.select_set(True)
                except Exception:
                    pass
            if tmp_objs:
                try:
                    bpy.context.view_layer.objects.active = tmp_objs[0]
                except Exception:
                    pass

            if not props.dry_run:
                if export_format == 'GLB':
                    bpy.ops.export_scene.gltf(filepath=out_name, export_format='GLB', export_selected=True)
                else:
                    bpy.ops.wm.collada_export(filepath=out_name, selected=True)
            exported_files.append(out_name)

            # restore selection
            try:
                bpy.ops.object.select_all(action='DESELECT')
            except Exception:
                pass
            for o in prev_selected:
                try:
                    o.select_set(True)
                except Exception:
                    pass

            # cleanup: remove temporary objects and collection
            for o in tmp_objs:
                try:
                    bpy.data.objects.remove(o, do_unlink=True)
                except Exception:
                    pass
            try:
                scene.collection.children.unlink(tmp_collection)
                bpy.data.collections.remove(tmp_collection)
            except Exception:
                pass
        else:
            # individual exports per object
            for o in objs:
                if not o:
                    continue
                tmp_created = False
                if props.apply_export_modifiers and mod_flags:
                    tmp = _prepare_object_for_export(o)
                    tmp_created = True
                else:
                    tmp = o

                base_name = _derive_base_from_name(o.name)
                filename = f"{base_name}.{export_format.lower()}"
                out_name = os.path.join(target_dir, filename)
                print(f"SL Export: exporting {o.name} -> {out_name}")

                # select only tmp for export
                prev_selected = list(bpy.context.selected_objects)
                try:
                    bpy.ops.object.select_all(action='DESELECT')
                except Exception:
                    pass
                try:
                    tmp.select_set(True)
                    bpy.context.view_layer.objects.active = tmp
                except Exception:
                    pass

                if not props.dry_run:
                    if export_format == 'GLB':
                        bpy.ops.export_scene.gltf(filepath=out_name, export_format='GLB', export_selected=True)
                    else:
                        bpy.ops.wm.collada_export(filepath=out_name, selected=True)
                exported_files.append(out_name)

                # restore selection
                try:
                    bpy.ops.object.select_all(action='DESELECT')
                except Exception:
                    pass
                for so in prev_selected:
                    try:
                        so.select_set(True)
                    except Exception:
                        pass

                # if we created a temporary copy, remove it
                if tmp_created:
                    try:
                        bpy.data.objects.remove(tmp, do_unlink=True)
                    except Exception:
                        pass

        self.report({'INFO'}, f"Exported {len(exported_files)} file(s) (dry_run={props.dry_run})")
        return {'FINISHED'}


# --- New operators and helpers for the selectable list UI ---


class SL_OT_add_selected_to_list(bpy.types.Operator):
    bl_idname = "scene.sl_add_selected_to_list"
    bl_label = "Add Selected"
    bl_description = "Add selected objects to the SL Renamer list"

    def execute(self, context):
        scene = context.scene
        props = scene.sl_renamer_props
        coll = scene.sl_renamer_items
        for obj in context.selected_objects:
            # avoid duplicates
            if any(it.obj == obj for it in coll):
                continue
            it = coll.add()
            it.obj = obj
            # heuristic: set lod based on name
            lname = (obj.name or '').upper()
            if lname.endswith('_PHYS') or 'PHYS' in lname:
                it.lod = 'PHYS'
            elif lname.endswith('_LOD0') or 'LOD0' in lname:
                it.lod = 'LOD0'
            elif lname.endswith('_LOD1') or 'LOD1' in lname:
                it.lod = 'LOD1'
            elif lname.endswith('_LOD2') or 'LOD2' in lname:
                it.lod = 'LOD2'
            else:
                it.lod = 'LOD0'
            # mark as base if the object's name doesn't already include a LOD/PHYS suffix
            # (comment/heuristic in original code hinted at this but did not set the flag)
            if not any(s in lname for s in ('_PHYS', 'PHYS', '_LOD0', 'LOD0', '_LOD1', 'LOD1', '_LOD2', 'LOD2')):
                it.is_base = True
            else:
                it.is_base = False
            it.base_ref = None
        # keep index valid
        scene.sl_renamer_index = len(coll) - 1
        return {'FINISHED'}


class SL_OT_remove_from_list(bpy.types.Operator):
    bl_idname = "scene.sl_remove_from_list"
    bl_label = "Remove"
    bl_description = "Remove selected item from the SL Renamer list"

    @classmethod
    def poll(cls, context):
        return len(context.scene.sl_renamer_items) > 0

    def execute(self, context):
        scene = context.scene
        idx = scene.sl_renamer_index
        coll = scene.sl_renamer_items
        if 0 <= idx < len(coll):
            coll.remove(idx)
            scene.sl_renamer_index = min(max(0, idx - 1), len(coll) - 1)
        return {'FINISHED'}



class SL_OT_add_base(bpy.types.Operator):
    bl_idname = "scene.sl_add_base"
    bl_label = "Add Base"
    bl_description = "Add selected object(s) to the Bases list"

    def execute(self, context):
        scene = context.scene
        bases = scene.sl_renamer_bases
        for obj in context.selected_objects:
            if any(b.obj == obj for b in bases):
                continue
            b = bases.add()
            b.obj = obj
        return {'FINISHED'}


class SL_OT_remove_base(bpy.types.Operator):
    bl_idname = "scene.sl_remove_base"
    bl_label = "Remove Base"
    bl_description = "Remove selected base from the Bases list"

    def execute(self, context):
        scene = context.scene
        idx = scene.sl_renamer_base_index
        bases = scene.sl_renamer_bases
        if 0 <= idx < len(bases):
            bases.remove(idx)
            scene.sl_renamer_base_index = min(max(0, idx - 1), len(bases) - 1)
        return {'FINISHED'}


class SL_OT_assign_to_base(bpy.types.Operator):
    bl_idname = "scene.sl_assign_to_base"
    bl_label = "Assign to Base"
    bl_description = "Assign selected list items to the chosen base"

    def execute(self, context):
        scene = context.scene
        base_idx = scene.sl_renamer_base_index
        if not (0 <= base_idx < len(scene.sl_renamer_bases)):
            self.report({'WARNING'}, "No base selected to assign to")
            return {'CANCELLED'}
        base_obj = scene.sl_renamer_bases[base_idx].obj
        if not base_obj:
            self.report({'WARNING'}, "Selected base has no object")
            return {'CANCELLED'}

        # assign selected items in the items list (by index selection) or selection in 3D view
        for it in scene.sl_renamer_items:
            if it.obj in context.selected_objects:
                it.base_ref = base_obj

        self.report({'INFO'}, f"Assigned selected items to base {base_obj.name}")
        return {'FINISHED'}


class SL_OT_assign_selected_to_base_row(bpy.types.Operator):
    """Assign selected Items to this base (called from the Bases list row)"""
    bl_idname = "scene.sl_assign_selected_to_base_row"
    bl_label = "Assign Selected To This Base"

    base_index: IntProperty()

    def execute(self, context):
        scene = context.scene
        bases = getattr(scene, 'sl_renamer_bases', [])
        idx = self.base_index
        if not (0 <= idx < len(bases)):
            self.report({'WARNING'}, "Invalid base index")
            return {'CANCELLED'}
        base_obj = bases[idx].obj
        if not base_obj:
            self.report({'WARNING'}, "Selected base has no object")
            return {'CANCELLED'}

        # assign selected objects in the 3D view or the active item in the Items list
        sel = set(context.selected_objects)
        active_idx = getattr(scene, 'sl_renamer_index', None)
        for i, it in enumerate(getattr(scene, 'sl_renamer_items', [])):
            if not it.obj:
                continue
            if it.obj in sel or (active_idx is not None and i == active_idx):
                it.base_ref = base_obj

        self.report({'INFO'}, f"Assigned selected items to base {base_obj.name}")
        return {'FINISHED'}


class SL_OT_assign_selected_to_base_slot(bpy.types.Operator):
    """Assign the active selection (or active Items list item) to a named slot on the selected base"""
    bl_idname = "scene.sl_assign_selected_to_base_slot"
    bl_label = "Assign to Base Slot"

    base_index: IntProperty()
    slot_name: bpy.props.StringProperty()

    def execute(self, context):
        scene = context.scene
        bases = getattr(scene, 'sl_renamer_bases', [])
        idx = self.base_index
        if not (0 <= idx < len(bases)):
            self.report({'WARNING'}, "Invalid base index")
            return {'CANCELLED'}
        base = bases[idx]
        base_obj = base.obj
        if not base_obj:
            self.report({'WARNING'}, "Selected base has no object")
            return {'CANCELLED'}

        # choose target object from selection or active Items item
        sel = list(context.selected_objects)
        target = None
        if sel:
            target = sel[0]
        else:
            ai = getattr(scene, 'sl_renamer_index', None)
            if ai is not None and 0 <= ai < len(getattr(scene, 'sl_renamer_items', [])):
                target = scene.sl_renamer_items[ai].obj

        if not target:
            self.report({'WARNING'}, 'No object selected to assign to slot')
            return {'CANCELLED'}

        # set the slot
        if self.slot_name == 'lod0':
            base.lod0_obj = target
        elif self.slot_name == 'lod1':
            base.lod1_obj = target
        elif self.slot_name == 'lod2':
            base.lod2_obj = target
        elif self.slot_name == 'phys':
            base.phys_obj = target
        else:
            self.report({'WARNING'}, f'Unknown slot {self.slot_name}')
            return {'CANCELLED'}

        self.report({'INFO'}, f'Assigned {target.name} to base slot {self.slot_name}')
        return {'FINISHED'}


def _derive_base_from_name(name):
    if not name:
        return ''
    lname = name
    for sfx in ["_LOD0", "_LOD1", "_LOD2", "_PHYS"]:
        if lname.endswith(sfx):
            return lname[:-len(sfx)]
    return lname


class SL_OT_apply_list_renames(bpy.types.Operator):
    bl_idname = "scene.sl_apply_list_renames"
    bl_label = "Apply List Renames"
    bl_description = "Apply/correct naming for items in the list"

    def execute(self, context):
        scene = context.scene
        props = scene.sl_renamer_props
        items = scene.sl_renamer_items

        # If a base entry is currently selected in the Bases list, auto-assign
        # selected items (by 3D selection or by the active Items list index) to that base
        base_idx = getattr(scene, 'sl_renamer_base_index', None)
        if base_idx is not None and 0 <= base_idx < len(getattr(scene, 'sl_renamer_bases', [])):
            base_entry = scene.sl_renamer_bases[base_idx]
            base_obj = base_entry.obj
            if base_obj:
                # collect selected objects from 3D view and active item
                sel_objs = set(context.selected_objects)
                active_item_idx = getattr(scene, 'sl_renamer_index', None)

                # Build explicit group for the selected base: items that either have base_ref==base_obj,
                # are selected in the viewport, or are the active item; exclude the base object itself.
                explicit_group = []
                for idx, it in enumerate(items):
                    if not it.obj:
                        continue
                    if it.obj == base_obj:
                        # don't include the base object itself
                        continue
                    if getattr(it, 'base_ref', None) == base_obj or it.obj in sel_objs or (active_item_idx is not None and idx == active_item_idx):
                        # ensure the item records the base_ref for clarity
                        it.base_ref = base_obj
                        explicit_group.append(it)

                if explicit_group:
                    # derive base name from the base object
                    base_name = _derive_base_from_name(base_obj.name)
                    print(f"SL Renamer: Applying renames for selected base '{base_obj.name}' -> base_name '{base_name}'")
                    for it2 in explicit_group:
                        obj2 = it2.obj
                        tpl_key = {
                            'LOD0': 'mesh_lod0',
                            'LOD1': 'mesh_lod1',
                            'LOD2': 'mesh_lod2',
                            'PHYS': 'phys'
                        }.get(it2.lod, 'mesh_lod0')
                        target_name = apply_template(base_name, tpl_key)
                        print(f"SL Renamer: {obj2.name} -> {target_name}")
                        try:
                            obj2.name = target_name
                        except Exception:
                            pass
                        if getattr(obj2, 'data', None):
                            try:
                                obj2.data.name = target_name
                            except Exception:
                                pass
                    # Optionally rename files on disk for this base
                    if props.rename_files and props.target_dir and base_name:
                        rename_files_on_disk(props.target_dir, base_name, dry_run=props.dry_run)
                    # remove those items from further processing by clearing their base_ref marker from the temporary set
                    # (they'll be skipped later because they now belong to an explicit group)
                    # Continue to also process any other non-selected groups below
        # Build grouping keyed by an explicit base object if provided
        groups_by_baseobj = {}

        # First, map any item that has an explicit base_ref to that base object
        for it in items:
            if not it.obj:
                continue
            if getattr(it, 'base_ref', None):
                base_obj = it.base_ref
                groups_by_baseobj.setdefault(base_obj, []).append(it)

        # Next, include items that correspond to registered Bases entries (scene.sl_renamer_bases)
        bases_lookup = {b.obj: b for b in getattr(scene, 'sl_renamer_bases', []) if b.obj}
        for it in items:
            if not it.obj:
                continue
            # if already assigned via base_ref, skip
            if getattr(it, 'base_ref', None):
                continue
            # if the item's object matches a base entry, use that base
            if it.obj in bases_lookup:
                groups_by_baseobj.setdefault(it.obj, []).append(it)

        # Now collect remaining items not yet grouped and group them by derived key
        remaining = [it for it in items if it.obj and it not in [x for v in groups_by_baseobj.values() for x in v]]
        groups_by_key = {}
        for it in remaining:
            key = _derive_base_from_name(it.obj.name)
            groups_by_key.setdefault(key, []).append(it)

        # Merge groups: process explicit base_obj groups first, then key-based groups
        # Helper to process a list of group_items and perform renaming
        def _process_group(group_items, explicit_base_obj=None, derived_key=None):
            # determine base_obj/name for this group: prefer explicit_base_obj, then any is_base, then LOD0, then derived key
            base_obj = explicit_base_obj
            base_name = None

            if base_obj is None:
                for it2 in group_items:
                    if it2.is_base and it2.obj:
                        base_obj = it2.obj
                        break

            if base_obj is None:
                for it2 in group_items:
                    if it2.lod == 'LOD0' and it2.obj:
                        base_obj = it2.obj
                        break

            if base_obj is not None:
                base_name = _derive_base_from_name(base_obj.name)
            else:
                base_name = derived_key or (group_items[0].obj.name if group_items and group_items[0].obj else '')

            # apply names for members; skip renaming the base object itself
            for it2 in group_items:
                obj2 = it2.obj
                if not obj2:
                    continue

                if base_obj is not None and obj2 == base_obj:
                    # leave base object name as-is
                    continue

                tpl_key = {
                    'LOD0': 'mesh_lod0',
                    'LOD1': 'mesh_lod1',
                    'LOD2': 'mesh_lod2',
                    'PHYS': 'phys'
                }.get(it2.lod, 'mesh_lod0')

                target_name = apply_template(base_name, tpl_key)
                try:
                    obj2.name = target_name
                except Exception:
                    pass
                if getattr(obj2, 'data', None):
                    try:
                        obj2.data.name = target_name
                    except Exception:
                        pass

            # Optionally rename files on disk for this base
            if props.rename_files and props.target_dir and base_name:
                rename_files_on_disk(props.target_dir, base_name, dry_run=props.dry_run)

        # Process explicit base_obj groups
        # First, process explicit slot mappings defined per-base (if present)
        for b in getattr(scene, 'sl_renamer_bases', []):
            if not b.obj:
                continue
            base_name = _derive_base_from_name(b.obj.name)
            slot_map = [
                ('lod0', getattr(b, 'lod0_obj', None)),
                ('lod1', getattr(b, 'lod1_obj', None)),
                ('lod2', getattr(b, 'lod2_obj', None)),
                ('phys', getattr(b, 'phys_obj', None)),
            ]
            any_slot = False
            for slot_key, tgt_obj in slot_map:
                if tgt_obj:
                    any_slot = True
                    tpl_key = {
                        'lod0': 'mesh_lod0',
                        'lod1': 'mesh_lod1',
                        'lod2': 'mesh_lod2',
                        'phys': 'phys'
                    }[slot_key]
                    target_name = apply_template(base_name, tpl_key)
                    print(f"SL Renamer (slots): {tgt_obj.name} -> {target_name}")
                    try:
                        tgt_obj.name = target_name
                    except Exception:
                        pass
                    if getattr(tgt_obj, 'data', None):
                        try:
                            tgt_obj.data.name = target_name
                        except Exception:
                            pass
            if any_slot and props.rename_files and props.target_dir and base_name:
                rename_files_on_disk(props.target_dir, base_name, dry_run=props.dry_run)

        # Then process explicit base_obj groups collected earlier
        for base_obj, group_items in list(groups_by_baseobj.items()):
            _process_group(group_items, explicit_base_obj=base_obj)

        # Process key-based groups
        for key, group_items in groups_by_key.items():
            _process_group(group_items, explicit_base_obj=None, derived_key=key)

        self.report({'INFO'}, "Applied list renames (check console for details)")
        return {'FINISHED'}


class SL_OT_check_material_subset(bpy.types.Operator):
    bl_idname = "scene.sl_check_material_subset"
    bl_label = "Check Materials Subset"
    bl_description = "Check that materials on LODs are subsets of the reference (LOD0) materials"

    def execute(self, context):
        scene = context.scene
        items = scene.sl_renamer_items
        # group items by base
        groups = {}
        for it in items:
            obj = it.obj
            if not obj or not getattr(obj, 'data', None):
                continue
            base = _derive_base_from_name(obj.data.name) if not scene.sl_renamer_props.base_name.strip() else scene.sl_renamer_props.base_name.strip()
            groups.setdefault(base, []).append((it.lod, obj))

        issues = []
        for base, members in groups.items():
            # find reference materials from LOD0 if present
            ref_mats = None
            for lod, obj in members:
                if lod == 'LOD0':
                    ref_mats = [m.name for m in getattr(obj.data, 'materials', []) if m]
                    break
            # fallback: use the member with most materials
            if ref_mats is None:
                best = None
                best_count = -1
                for lod, obj in members:
                    mats = [m.name for m in getattr(obj.data, 'materials', []) if m]
                    if len(mats) > best_count:
                        best_count = len(mats)
                        best = mats
                ref_mats = best or []

            ref_set = set(ref_mats)
            for lod, obj in members:
                mats = [m.name for m in getattr(obj.data, 'materials', []) if m]
                mats_set = set(mats)
                if not mats_set.issubset(ref_set):
                    diff = mats_set - ref_set
                    issues.append(f"Object '{obj.name}' (LOD {lod}) has materials not in reference: {sorted(list(diff))}")

        if issues:
            for i in issues:
                _bl_log(f"SL Material Check: {i}")
            self.report({'WARNING'}, f"Found {len(issues)} material issue(s). See Text Editor 'SL_Renamer_Log' or system console.")
            return {'FINISHED'}

        self.report({'INFO'}, "Material subset check passed")
        return {'FINISHED'}


def register():
    bpy.utils.register_class(SLRenamerProperties)
    bpy.types.Scene.sl_renamer_props = bpy.props.PointerProperty(type=SLRenamerProperties)

    # register list item type and collection on Scene
    bpy.utils.register_class(SLRenamerItem)
    bpy.types.Scene.sl_renamer_items = CollectionProperty(type=SLRenamerItem)
    bpy.types.Scene.sl_renamer_index = IntProperty(default=0)

    # register bases collection
    bpy.utils.register_class(SLRenamerBase)
    bpy.types.Scene.sl_renamer_bases = CollectionProperty(type=SLRenamerBase)
    bpy.types.Scene.sl_renamer_base_index = IntProperty(default=0)

    # register operators
    bpy.utils.register_class(OBJECT_OT_rename_lods)
    bpy.utils.register_class(OBJECT_OT_validate_for_sl)
    bpy.utils.register_class(SL_OT_add_selected_to_list)
    bpy.utils.register_class(SL_OT_remove_from_list)
    bpy.utils.register_class(SL_OT_apply_list_renames)
    bpy.utils.register_class(SL_OT_check_material_subset)
    bpy.utils.register_class(SL_OT_add_base)
    bpy.utils.register_class(SL_OT_remove_base)
    bpy.utils.register_class(SL_OT_assign_to_base)
    bpy.utils.register_class(SL_OT_assign_selected_to_base_row)
    bpy.utils.register_class(SL_OT_assign_selected_to_base_slot)
    bpy.utils.register_class(SL_OT_export_scene)


def unregister():
    # unregister operators
    bpy.utils.unregister_class(OBJECT_OT_rename_lods)
    bpy.utils.unregister_class(OBJECT_OT_validate_for_sl)
    bpy.utils.unregister_class(SL_OT_add_selected_to_list)
    bpy.utils.unregister_class(SL_OT_remove_from_list)
    bpy.utils.unregister_class(SL_OT_apply_list_renames)
    bpy.utils.unregister_class(SL_OT_check_material_subset)
    bpy.utils.unregister_class(SL_OT_add_base)
    bpy.utils.unregister_class(SL_OT_remove_base)
    bpy.utils.unregister_class(SL_OT_assign_to_base)
    try:
        bpy.utils.unregister_class(SL_OT_assign_selected_to_base_row)
    except Exception:
        pass
    try:
        bpy.utils.unregister_class(SL_OT_assign_selected_to_base_slot)
    except Exception:
        pass
    try:
        bpy.utils.unregister_class(SL_OT_export_scene)
    except Exception:
        pass

    # remove scene properties
    try:
        del bpy.types.Scene.sl_renamer_items
    except Exception:
        pass
    try:
        del bpy.types.Scene.sl_renamer_index
    except Exception:
        pass
    try:
        del bpy.types.Scene.sl_renamer_bases
    except Exception:
        pass
    try:
        del bpy.types.Scene.sl_renamer_base_index
    except Exception:
        pass
    try:
        del bpy.types.Scene.sl_renamer_props
    except Exception:
        pass

    # unregister classes
    bpy.utils.unregister_class(SLRenamerItem)
    bpy.utils.unregister_class(SLRenamerProperties)
    bpy.utils.unregister_class(SLRenamerBase)
