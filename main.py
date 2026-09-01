def initialize():
    import importlib
    import sys
    from pathlib import Path

    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    import src.engine.controller
    import src.engine.frame
    import src.engine.helpers
    import src.engine.note
    import src.ui.node_editor

    importlib.reload(src.engine.note)
    importlib.reload(src.engine.frame)
    importlib.reload(src.ui.node_editor)
    importlib.reload(src.engine.controller)


initialize()

bl_info = {
    "name": "bmidi",
    "author": "Keller Hydle",
    "version": (0, 0, 1),
    "blender": (5, 0, 0),
    "location": "3D Viewport > Sidebar > bmidi",
    "description": "Automatic MIDI-data keyframing for Blender objects",
    "category": "Development",
}

import bpy

from src.ui.node_editor import (
    BMIDI_Frame,
    BMIDI_MIDIDataSocket,
    BMIDI_MIDIEvent,
    BMIDI_Node_FrameCollection,
    BMIDI_Node_MIDIData,
    BMIDI_Node_MIDIDataFilter,
    BMIDI_NodeTree,
    BMIDI_OT_frame_collection_add,
    BMIDI_OT_frame_collection_duplicate,
    BMIDI_OT_frame_collection_remove,
    BMIDI_OT_midi_data_generate,
    BMIDI_UL_frame_collection,
    draw_add_menu,
)


class VIEW_3D_OT_rename_selected(bpy.types.Operator):
    """
    Renames the selected items to the criteria specified
    """

    bl_idname = "bmidi.rename_selected"
    bl_label = "Rename Selected"

    def execute(self, context):
        scene = context.scene
        prefix = scene.bmidi_rename_prefix
        rename_type = scene.bmidi_rename_type
        notes = process_note_list(scene.bmidi_rename_notes)
        obj_list = bpy.context.selected_objects

        if rename_type == "location_smallest":
            obj_list.sort(key=lambda o: o.location.length)
        elif rename_type == "location_biggest":
            obj_list.sort(key=lambda o: o.location.length, reverse=True)
        elif rename_type == "scale_smallest":
            obj_list.sort(key=lambda o: (o.scale.x, o.scale.y, o.location.z))
        elif rename_type == "scale_biggest":
            obj_list.sort(
                key=lambda o: (o.scale.x, o.scale.y, o.location.z), reverse=True
            )

        for note, obj in zip(notes, obj_list):
            obj.name = f"{prefix}{note}"

        return {"FINISHED"}


class VIEW_3D_PT_bmidi_rename_panel(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "bmidi"
    bl_label = "Rename Tool"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        box = layout.box()

        box.prop(scene, "bmidi_rename_prefix")
        box.prop(scene, "bmidi_rename_type")
        box.prop(scene, "bmidi_rename_notes")

        box.separator()
        box.operator("bmidi.rename_selected", icon="TEXT")


classes = (
    BMIDI_Frame,
    BMIDI_MIDIEvent,
    BMIDI_OT_midi_data_generate,
    BMIDI_OT_frame_collection_add,
    BMIDI_OT_frame_collection_duplicate,
    BMIDI_OT_frame_collection_remove,
    BMIDI_NodeTree,
    BMIDI_MIDIDataSocket,
    BMIDI_Node_MIDIData,
    BMIDI_Node_MIDIDataFilter,
    BMIDI_Node_FrameCollection,
    BMIDI_UL_frame_collection,
    VIEW_3D_PT_bmidi_rename_panel,
    VIEW_3D_OT_rename_selected,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.NODE_MT_add.append(draw_add_menu)
    bpy.types.NODE_MT_swap.append(draw_add_menu)

    bpy.types.Scene.bmidi_rename_prefix = bpy.props.StringProperty(
        name="Object Prefix",
    )
    bpy.types.Scene.bmidi_rename_type = bpy.props.EnumProperty(
        name="Rename Type",
        items=[
            (
                "location_smallest",
                "Location (Smallest -> Biggest)",
                "Rename items based on their location (smallest to biggest)",
            ),
            (
                "location_biggest",
                "Location (Biggest -> Smallest)",
                "Rename items based on their location (biggest to smallest)",
            ),
            (
                "scale_smallest",
                "Scale (Smallest -> Biggest)",
                "Rename items based on their scale (smallest to biggest)",
            ),
            (
                "scale_biggest",
                "Scale (Biggest -> Smallest)",
                "Rename items based on their scale (biggest to smallest)",
            ),
        ],
    )
    bpy.types.Scene.bmidi_rename_notes = bpy.props.StringProperty(
        name="Rename To Notes",
        description="Comma separated MIDI notes",
    )


def unregister():
    bpy.types.NODE_MT_add.remove(draw_add_menu)
    bpy.types.NODE_MT_swap.remove(draw_add_menu)

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
