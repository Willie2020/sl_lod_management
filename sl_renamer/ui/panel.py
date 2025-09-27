import bpy
from ..core import (
    OBJECT_OT_rename_lods,
    SL_OT_add_selected_to_list,
    SL_OT_remove_from_list,
    SL_OT_apply_list_renames,
    SL_OT_check_material_subset,
    SL_OT_add_base,
    SL_OT_remove_base,
    SL_OT_assign_to_base,
)


class SL_UL_item_list(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        # data is the owner (Scene), item is SLRenamerItem
        # item may be SLRenamerItem or SLRenamerBase
        if not getattr(item, 'obj', None):
            layout.label(text="(missing object)")
            return

        row = layout.row(align=True)
        # For base entries (SLRenamerBase), show the object and a small assign button
        # We can detect bases list usage by checking the active_propname that owns the list
        owner = active_data
        propname = active_propname
        if propname == 'sl_renamer_bases':
            row.prop(item, 'obj', text='', emboss=False)
            op = row.operator('scene.sl_assign_selected_to_base_row', text='', icon='LINKED')
            # pass the index of this base row to the operator
            op.base_index = index
        else:
            # Items list: show object, lod and base toggle
            row.prop(item, 'obj', text='', emboss=False)
            row.prop(item, 'lod', text='')
            row.prop(item, 'is_base', text='')


class SL_PT_renamer_panel(bpy.types.Panel):
    bl_label = "SL Renamer"
    bl_idname = "SL_PT_renamer_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'SL Renamer'

    def draw(self, context):
        layout = self.layout
        props = context.scene.sl_renamer_props
        scene = context.scene

        # Header
        layout.label(text="SL Renamer — Second Life naming helpers", icon='OUTLINER_OB_MESH')

        # Bases management
        box = layout.box()
        box.label(text="Bases (original/reference models)")
        brow = box.row(align=True)
        brow.template_list(
            "SL_UL_item_list",
            "sl_renamer_bases",
            scene,
            "sl_renamer_bases",
            scene,
            "sl_renamer_base_index",
            rows=4,
        )
        bops = brow.column(align=True)
        bops.operator('scene.sl_add_base', icon='ADD', text='')
        bops.operator('scene.sl_remove_base', icon='REMOVE', text='')
        box.operator('scene.sl_assign_to_base', text='Assign Selected Items to Base', icon='LINKED')

        # Per-base explicit slot pickers (appear when a base is active)
        base_idx = getattr(scene, 'sl_renamer_base_index', None)
        if base_idx is not None and 0 <= base_idx < len(getattr(scene, 'sl_renamer_bases', [])):
            active_base = scene.sl_renamer_bases[base_idx]
            slot_box = box.box()
            slot_box.label(text="Explicit match slots for active base (optional)")

            row = slot_box.row(align=True)
            row.prop(active_base, 'lod0_obj', text='LOD0')
            op = row.operator('scene.sl_assign_selected_to_base_slot', text='', icon='PLUS')
            op.base_index = base_idx
            op.slot_name = 'lod0'

            row = slot_box.row(align=True)
            row.prop(active_base, 'lod1_obj', text='LOD1')
            op = row.operator('scene.sl_assign_selected_to_base_slot', text='', icon='PLUS')
            op.base_index = base_idx
            op.slot_name = 'lod1'

            row = slot_box.row(align=True)
            row.prop(active_base, 'lod2_obj', text='LOD2')
            op = row.operator('scene.sl_assign_selected_to_base_slot', text='', icon='PLUS')
            op.base_index = base_idx
            op.slot_name = 'lod2'

            row = slot_box.row(align=True)
            row.prop(active_base, 'phys_obj', text='PHYS')
            op = row.operator('scene.sl_assign_selected_to_base_slot', text='', icon='PLUS')
            op.base_index = base_idx
            op.slot_name = 'phys'

        # Items section (objects to be renamed)
        box = layout.box()
        box.label(text="Items to rename (assign LOD/PHYS)")
        irow = box.row()
        irow.template_list(
            "SL_UL_item_list",
            "sl_renamer_items",
            scene,
            "sl_renamer_items",
            scene,
            "sl_renamer_index",
            rows=6,
        )
        iops = irow.column(align=True)
        iops.operator('scene.sl_add_selected_to_list', icon='ADD', text='')
        iops.operator('scene.sl_remove_from_list', icon='REMOVE', text='')
        box.label(text="Tip: select items in 3D view and use 'Assign Selected Items to Base' or use per-base slots.")

        # Files options
        file_box = layout.box()
        file_box.label(text="File rename options (optional)")
        file_box.prop(props, 'target_dir')
        file_box.prop(props, 'rename_files')
        file_box.prop(props, 'dry_run')
        file_box.label(text="Note: file operations only affect .dae and .glb files and respect Dry Run.")

        # Export options
        exp_box = layout.box()
        exp_box.label(text="Export (GLB/DAE)")
        exp_box.prop(props, 'export_format', text='Format')
        exp_box.prop(props, 'export_scope', text='Scope')
        exp_box.prop(props, 'export_mode', text='Mode')
        exp_box.prop(props, 'apply_export_modifiers', text='Apply Selected Modifiers')
        # show the modifiers flags only when apply_export_modifiers is True
        if props.apply_export_modifiers:
            exp_box.prop(props, 'export_modifiers', text='Modifiers')
        exp_row = exp_box.row()
        exp_row.operator('scene.sl_export_scene', text='Export', icon='EXPORT')

        # Action buttons (grouped)
        actions = layout.box()
        actions.label(text="Actions")
        row = actions.row(align=True)
        row.operator(OBJECT_OT_rename_lods.bl_idname, text="Auto-Rename Heuristic", icon='AUTOMERGE_ON')
        row.operator('scene.sl_apply_list_renames', text='Apply List Renames', icon='BORDERMOVE')
        actions.operator('scene.sl_check_material_subset', text='Check Materials Subset', icon='MATERIAL')
        actions.operator("object.sl_validate_for_sl", text="Validate for SL Upload", icon='ERROR')

        # Help / concise usage
        layout.separator()
        help_box = layout.box()
        help_box.label(text="Quick workflow")
        help_box.label(text="1) Add your original models to 'Bases' (use Add Base)")
        help_box.label(text="2) Add duplicates to 'Items' (select in 3D view, Add Selected)")
        help_box.label(text="3) For safety: set per-base slots or select items and click Assign Selected to Base")
        help_box.label(text="4) Use 'Apply List Renames' to rename assigned items. Use Dry Run first.")

def register():
    bpy.utils.register_class(SL_UL_item_list)
    bpy.utils.register_class(SL_PT_renamer_panel)


def unregister():
    bpy.utils.unregister_class(SL_PT_renamer_panel)
    bpy.utils.unregister_class(SL_UL_item_list)
