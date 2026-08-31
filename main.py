import mido
from mathutils import Vector


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
    import src.ui.note_mapper

    importlib.reload(src.engine.note)
    importlib.reload(src.engine.frame)
    importlib.reload(src.ui.note_mapper)
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

import math

import bpy

from src.engine.controller import NoteController
from src.engine.frame import Frame
from src.engine.helpers import get_midi_channel_ranges
from src.engine.note import MidiNote
from src.ui.note_mapper import (
    BMIDI_Frame,
    BMIDI_NoteEvent,
    BMIDI_Object,
    BMIDI_OT_add_frame,
    BMIDI_OT_add_note_event,
    BMIDI_OT_add_object,
    BMIDI_OT_duplicate_frame,
    BMIDI_OT_duplicate_note_event,
    BMIDI_OT_remove_frame,
    BMIDI_OT_remove_note_event,
    BMIDI_OT_remove_object,
    BMIDI_UL_event_objects,
    BMIDI_UL_note_events,
    BMIDI_UL_object_frames,
    VIEW_3D_PT_bmidi_note_mapper,
)


def process_note_list(expr: str) -> list[int]:
    notes = []

    for i in expr.strip().split(","):
        if "-" in i:
            start, end = i.split("-")
            notes.extend(range(int(start), int(end) + 1))
        else:
            notes.append(int(i))

    return notes


class VIEW_3D_OT_generate_keyframes(bpy.types.Operator):
    """
    Clears object animation data and generates the keyframes for all items
    """

    bl_idname = "bmidi.generate_keyframes"
    bl_label = "Generate Keyframes"

    def execute(self, context):
        scene = context.scene
        scene.frame_set(-1)
        midi_file = scene.bmidi_midi_file

        if not midi_file:
            self.report({"ERROR"}, "No MIDI file selected")
            return {"CANCELLED"}

        midi = mido.MidiFile(midi_file)
        current_time = 0.0
        active_notes = {}  # start_time, velocity
        notes = []

        # parse the midi file
        for msg in midi:
            current_time += msg.time

            if msg.type == "note_on" and msg.velocity > 0:
                active_notes[(msg.note, msg.channel)] = (
                    current_time,
                    msg.velocity / 127.0,
                )

            elif msg.type in ("note_off", "note_on") and msg.velocity == 0:
                key = (msg.note, msg.channel)
                if key in active_notes:
                    start_time, velocity = active_notes.pop(key)

                    notes.append(
                        MidiNote(
                            start_time,
                            current_time - start_time,
                            msg.note,
                            msg.channel,
                            velocity,
                        )
                    )

        frames = {}
        allowed_notes = []

        for item in context.scene.bmidi_note_events:
            if not item.enabled:
                continue

            allowed_notes.append(item.note)

            for o in item.objects:
                o.object.animation_data_clear()

                frames.setdefault(item.note, []).extend(
                    Frame(
                        o.object,
                        f.time,
                        f.trigger,
                        f.property,
                        Vector(
                            (math.radians(f.x), math.radians(f.y), math.radians(f.z))
                        )
                        if f.property == "rotation_euler"
                        else (
                            math.radians(f.x)
                            if f.property == "data.spot_size"
                            else Vector((f.x, f.y, f.z))
                        ),
                        relative=f.relative,
                    )
                    for f in o.frames
                )

        controller = NoteController(
            frames,
            [i for i in notes if i.note() in allowed_notes],
            frame_offset=scene.bmidi_frame_offset,
        )
        controller.generate_keyframes()

        return {"FINISHED"}


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


class VIEW_3D_PT_bmidi_selector_panel(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "bmidi"
    bl_label = "MIDI File"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        box = layout.box()
        box.prop(scene, "bmidi_midi_file")

        if scene.bmidi_midi_file:
            midi_path = scene.bmidi_midi_file

            layout.separator()
            box.label(text="MIDI Information", icon="INFO")

            if midi_path:
                channel_ranges = get_midi_channel_ranges(midi_path)

                if channel_ranges:
                    for ch in sorted(channel_ranges):
                        n, z = channel_ranges[ch]
                        box.label(text=f"Channel {ch}: Notes {n}-{z}")
                else:
                    box.label(text="Error parsing midi file", icon="ERROR")
        else:
            box.label(text="No midi file selected")


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


class VIEW_3D_PT_bmidi_animation_panel(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "bmidi"
    bl_label = "Animation"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        box = layout.box()
        box.prop(scene, "bmidi_frame_offset")
        box.operator("bmidi.generate_keyframes", icon="MODIFIER")


classes = (
    BMIDI_Frame,
    BMIDI_Object,
    BMIDI_NoteEvent,
    BMIDI_OT_add_frame,
    BMIDI_OT_add_note_event,
    BMIDI_OT_add_object,
    BMIDI_OT_duplicate_note_event,
    BMIDI_OT_duplicate_frame,
    BMIDI_OT_remove_frame,
    BMIDI_OT_remove_note_event,
    BMIDI_OT_remove_object,
    BMIDI_UL_event_objects,
    BMIDI_UL_note_events,
    BMIDI_UL_object_frames,
    VIEW_3D_PT_bmidi_selector_panel,
    VIEW_3D_PT_bmidi_note_mapper,
    VIEW_3D_PT_bmidi_rename_panel,
    VIEW_3D_PT_bmidi_animation_panel,
    VIEW_3D_OT_generate_keyframes,
    VIEW_3D_OT_rename_selected,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.bmidi_note_events = bpy.props.CollectionProperty(
        type=BMIDI_NoteEvent,
    )
    bpy.types.Scene.bmidi_active_note_event = bpy.props.IntProperty(
        default=0,
    )
    bpy.types.Scene.bmidi_frame_offset = bpy.props.IntProperty(
        name="Frame Offset",
        description="Offset the generated frames by a specified amount",
        default=0,
        min=0,
    )

    bpy.types.Scene.bmidi_midi_file = bpy.props.StringProperty(
        name="MIDI File",
        subtype="FILE_PATH",
    )
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
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
