import mido
from bpy.types import Object
from mathutils import Vector


def initialize():
    import importlib
    import sys
    from pathlib import Path

    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    import src.engine.controller
    import src.engine.effector
    import src.engine.event
    import src.engine.frame
    import src.engine.helpers
    import src.engine.note
    import src.ui.controllers
    import src.ui.note_mapper
    import src.ui.robotic_systems

    importlib.reload(src.engine.note)
    importlib.reload(src.engine.frame)
    importlib.reload(src.engine.event)
    importlib.reload(src.engine.effector)
    importlib.reload(src.ui.robotic_systems)
    importlib.reload(src.ui.controllers)
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

from src.engine.controller import BaseController, NoteController, RoboticController
from src.engine.effector import Effector
from src.engine.event import Event
from src.engine.frame import Frame
from src.engine.helpers import get_midi_channel_ranges
from src.engine.note import MidiNote
from src.ui.controllers import (
    BMIDI_Controller,
    BMIDI_Event,
    BMIDI_UL_controller_events,
    BMIDI_UL_controllers,
)
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
from src.ui.robotic_systems import (
    BMIDI_Robotic_Effector,
    BMIDI_Robotic_System,
    BMIDI_UL_robotic_effectors,
    BMIDI_UL_robotic_systems,
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


class VIEW_3D_OT_add_item(bpy.types.Operator):
    """Add a new item"""

    bl_idname = "bmidi_items.add_item"
    bl_label = "Add Item"

    def execute(self, context):
        context.scene.bmidi_items.add()
        context.scene.bmidi_active_item = len(context.scene.bmidi_items) - 1

        return {"FINISHED"}


class VIEW_3D_OT_remove_item(bpy.types.Operator):
    """Remove the selected item"""

    bl_idname = "bmidi_items.remove_item"
    bl_label = "Remove Item"

    def execute(self, context):
        idx = context.scene.bmidi_active_item
        context.scene.bmidi_items.remove(idx)
        context.scene.bmidi_active_item = max(0, idx - 1)

        return {"FINISHED"}


class VIEW_3D_OT_duplicate_item(bpy.types.Operator):
    """Duplicate the selected item"""

    bl_idname = "bmidi_items.duplicate_item"
    bl_label = "Duplicate Item"

    def execute(self, context):
        items = context.scene.bmidi_items
        idx = context.scene.bmidi_active_item

        if idx < 0 or idx >= len(items):
            return {"CANCELLED"}

        src = items[idx]

        # create new item
        items.add()
        dst = items[-1]

        for prop in src.bl_rna.properties:
            if prop.identifier in {"rna_type", "events"}:
                continue

            setattr(dst, prop.identifier, getattr(src, prop.identifier))

        # copy events
        for src_event in src.events:
            dst_event = dst.events.add()

            for prop in src_event.bl_rna.properties:
                if prop.identifier == "rna_type":
                    continue

                setattr(dst_event, prop.identifier, getattr(src_event, prop.identifier))

        dst.object_prefix = f"{src.object_prefix} (COPY)"
        items.move(len(items) - 1, idx + 1)
        context.scene.bmidi_active_item = idx + 1

        if len(dst.events) > 0:
            dst.active_event = 0

        return {"FINISHED"}


class VIEW_3D_OT_add_event(bpy.types.Operator):
    """Add a new event"""

    bl_idname = "bmidi_items.add_event"
    bl_label = "Add Event"

    def execute(self, context):
        scene = context.scene
        item = scene.bmidi_items[scene.bmidi_active_item]

        item.events.add()
        item.active_event = len(item.events) - 1

        return {"FINISHED"}


class VIEW_3D_OT_remove_event(bpy.types.Operator):
    """Remove the selected event"""

    bl_idname = "bmidi_items.remove_event"
    bl_label = "Remove Event"

    def execute(self, context):
        scene = context.scene
        item = scene.bmidi_items[scene.bmidi_active_item]

        idx = item.active_event

        if idx < 0 or idx >= len(item.events):
            return {"CANCELLED"}

        item.events.remove(idx)

        item.active_event = min(idx, max(0, len(item.events) - 1))

        return {"FINISHED"}


class VIEW_3D_OT_move_event_up(bpy.types.Operator):
    """Move the selected event up the list"""

    bl_idname = "bmidi_items.move_event_up"
    bl_label = "Move Event Up"

    def execute(self, context):
        scene = context.scene
        item = scene.bmidi_items[scene.bmidi_active_item]

        idx = item.active_event
        new = idx - 1

        if new < 0:
            return {"CANCELLED"}

        item.events.move(idx, new)
        item.active_event = new

        return {"FINISHED"}


class VIEW_3D_OT_move_event_down(bpy.types.Operator):
    """Move the selected event down the list"""

    bl_idname = "bmidi_items.move_event_down"
    bl_label = "Move Event Down"

    def execute(self, context):
        scene = context.scene
        item = scene.bmidi_items[scene.bmidi_active_item]

        idx = item.active_event
        new = idx + 1

        if new >= len(item.events):
            return {"CANCELLED"}

        item.events.move(idx, new)
        item.active_event = new

        return {"FINISHED"}


class VIEW_3D_OT_duplicate_event(bpy.types.Operator):
    """Duplicate the selected event"""

    bl_idname = "bmidi_items.duplicate_event"
    bl_label = "Duplicate Event"

    def execute(self, context):
        scene = context.scene
        item = scene.bmidi_items[scene.bmidi_active_item]
        events = item.events

        idx = item.active_event

        if idx < 0 or idx >= len(events):
            return {"CANCELLED"}

        src = events[idx]

        events.add()
        dst = events[-1]

        for prop in src.bl_rna.properties:
            if prop.identifier == "rna_type":
                continue

            setattr(dst, prop.identifier, getattr(src, prop.identifier))

        events.move(len(events) - 1, idx + 1)

        item.active_event = idx + 1

        return {"FINISHED"}


class BMIDI_OT_add_robotic_system(bpy.types.Operator):
    """Add a new robotic system"""

    bl_idname = "bmidi_robotic_systems.add"
    bl_label = "Add Robotic System"

    def execute(self, context):
        scene = context.scene

        system = scene.bmidi_robotic_systems.add()
        system.target_prefix = f"System {len(scene.bmidi_robotic_systems)}"

        scene.bmidi_active_system = len(scene.bmidi_robotic_systems) - 1

        return {"FINISHED"}


class BMIDI_OT_remove_robotic_system(bpy.types.Operator):
    """Remove the selected robotic system"""

    bl_idname = "bmidi_robotic_systems.remove"
    bl_label = "Remove Robotic System"

    def execute(self, context):
        scene = context.scene

        systems = scene.bmidi_robotic_systems
        idx = scene.bmidi_active_system

        if idx < 0 or idx >= len(systems):
            return {"CANCELLED"}

        systems.remove(idx)

        if systems:
            scene.bmidi_active_system = min(
                idx,
                len(systems) - 1,
            )
        else:
            scene.bmidi_active_system = 0

        return {"FINISHED"}


class BMIDI_OT_duplicate_robotic_system(bpy.types.Operator):
    """Duplicate the selected robotic system"""

    bl_idname = "bmidi_robotic_systems.duplicate"
    bl_label = "Duplicate Robotic System"

    def execute(self, context):
        scene = context.scene
        systems = scene.bmidi_robotic_systems
        idx = scene.bmidi_active_system

        if idx < 0 or idx >= len(systems):
            return {"CANCELLED"}

        src = systems[idx]

        systems.add()
        dst = systems[-1]

        for prop in src.bl_rna.properties:
            if prop.identifier in {
                "rna_type",
                "effectors",
            }:
                continue

            setattr(
                dst,
                prop.identifier,
                getattr(src, prop.identifier),
            )

        for src_effector in src.effectors:
            dst_effector = dst.effectors.add()

            for prop in src_effector.bl_rna.properties:
                if prop.identifier == "rna_type":
                    continue

                setattr(
                    dst_effector,
                    prop.identifier,
                    getattr(src_effector, prop.identifier),
                )

        dst.target_prefix = f"{src.target_prefix} (COPY)"

        systems.move(
            len(systems) - 1,
            idx + 1,
        )

        scene.bmidi_active_system = idx + 1

        if dst.effectors:
            dst.active_effector = 0

        return {"FINISHED"}


class BMIDI_OT_add_robotic_effector(bpy.types.Operator):
    """Add an effector to the selected robotic system"""

    bl_idname = "bmidi_robotic_effectors.add"
    bl_label = "Add Effector"

    def execute(self, context):
        scene = context.scene
        system = scene.bmidi_robotic_systems[scene.bmidi_active_system]

        system.effectors.add()
        system.active_effector = len(system.effectors) - 1

        return {"FINISHED"}


class BMIDI_OT_remove_robotic_effector(bpy.types.Operator):
    """Remove the selected effector"""

    bl_idname = "bmidi_robotic_effectors.remove"
    bl_label = "Remove Effector"

    def execute(self, context):
        scene = context.scene

        system = scene.bmidi_robotic_systems[scene.bmidi_active_system]
        idx = system.active_effector

        system.effectors.remove(idx)

        if system.effectors:
            system.active_effector = min(
                idx,
                len(system.effectors) - 1,
            )
        else:
            system.active_effector = 0

        return {"FINISHED"}


class BMIDI_OT_duplicate_robotic_effector(bpy.types.Operator):
    """Duplicate the selected effector"""

    bl_idname = "bmidi_robotic_effectors.duplicate"
    bl_label = "Duplicate Effector"

    def execute(self, context):
        scene = context.scene
        systems = scene.bmidi_robotic_systems

        system_idx = scene.bmidi_active_system

        if system_idx < 0 or system_idx >= len(systems):
            return {"CANCELLED"}

        system = systems[system_idx]

        idx = system.active_effector

        if idx < 0 or idx >= len(system.effectors):
            return {"CANCELLED"}

        src = system.effectors[idx]

        system.effectors.add()
        dst = system.effectors[-1]

        for prop in src.bl_rna.properties:
            if prop.identifier == "rna_type":
                continue

            setattr(
                dst,
                prop.identifier,
                getattr(src, prop.identifier),
            )

        system.effectors.move(
            len(system.effectors) - 1,
            idx + 1,
        )

        system.active_effector = idx + 1

        return {"FINISHED"}


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

        for item in context.scene.bmidi_items:
            if not item.enabled:
                continue

            events = []

            for e in item.events:
                needs_radians = e.action in (
                    "rotation_euler.x",
                    "rotation_euler.y",
                    "rotation_euler.z",
                    "data.spot_size",
                )

                events.append(
                    Event(
                        e.time,
                        e.trigger,
                        e.action,
                        math.radians(e.amount) if needs_radians else e.amount,
                    )
                )

            channel = int(item.channel) - 1
            note_start = item.note_range_start
            note_end = item.note_range_end + 1  # 0 - 128
            blocked_notes = (
                process_note_list(item.blocked_notes) if item.use_block_list else []
            )

            controller = BaseController(
                item.object_prefix,
                [
                    i
                    for i in notes
                    if i.note() in range(note_start, note_end)
                    and i.note() not in blocked_notes
                    and i.channel() == channel
                ],
                events,
                frame_offset=scene.bmidi_frame_offset,
            )
            controller.generate_keyframes()

        for system in context.scene.bmidi_robotic_systems:
            channel = int(system.channel) - 1
            note_start = system.note_range_start
            note_end = system.note_range_end + 1
            blocked_notes = (
                process_note_list(system.blocked_notes) if system.use_block_list else []
            )

            controller = RoboticController(
                [
                    Effector(
                        e.effector_object,
                        e.move_duration,
                        e.return_duration,
                        e.lift_amount,
                    )
                    for e in system.effectors
                ],
                system.target_prefix,
                [
                    i
                    for i in notes
                    if i.note() in range(note_start, note_end)
                    and i.note() not in blocked_notes
                    and i.channel() == channel
                ],
                frame_offset=scene.bmidi_frame_offset,
            )
            controller.generate_keyframes()

        frames = {}
        allowed_notes = []

        for item in context.scene.bmidi_note_events:
            if not item.enabled:
                continue

            allowed_notes.append(item.note)

            for o in item.objects:
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


class VIEW_3D_PT_bmidi_control_panel(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "bmidi"
    bl_label = "Controllers"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        box = layout.box()

        header = box.row()
        header.label(
            text="Controllers",
            icon="PHYSICS",
        )

        row = box.row()
        row.template_list(
            "BMIDI_UL_controllers", "", scene, "bmidi_items", scene, "bmidi_active_item"
        )

        col = row.column(align=True)
        col.operator("bmidi_items.add_item", icon="ADD", text="")
        col.operator("bmidi_items.remove_item", icon="REMOVE", text="")
        col.separator()
        col.operator("bmidi_items.duplicate_item", icon="DUPLICATE", text="")

        if scene.bmidi_items:
            item = scene.bmidi_items[scene.bmidi_active_item]

            box = box.box()
            box.label(text="Note Controls")
            box.prop(item, "note_range_start")
            box.prop(item, "note_range_end")
            box.prop(item, "use_block_list")

            if item.use_block_list:
                box.prop(item, "blocked_notes")

            box.prop(item, "channel")

            box = layout.box()
            box.label(text="Events", icon="KEYFRAME_HLT")
            row = box.row()
            row.template_list(
                "BMIDI_UL_controller_events", "", item, "events", item, "active_event"
            )

            col = row.column(align=True)
            col.operator("bmidi_items.add_event", icon="ADD", text="")
            col.operator("bmidi_items.remove_event", icon="REMOVE", text="")
            col.separator()
            col.operator("bmidi_items.move_event_up", icon="TRIA_UP", text="")
            col.operator("bmidi_items.move_event_down", icon="TRIA_DOWN", text="")
            col.separator()
            col.operator("bmidi_items.duplicate_event", icon="DUPLICATE", text="")

            if item.events:
                event = item.events[item.active_event]

                box = box.box()
                box.label(text="Event Options")

                box.prop(event, "time")
                box.prop(event, "trigger")
                box.prop(event, "action")
                box.prop(event, "amount")


class VIEW_3D_PT_bmidi_robotic_panel(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "bmidi"
    bl_label = "Robotics"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        box = layout.box()

        header = box.row()
        header.label(
            text="Robotic Systems",
            icon="ARMATURE_DATA",
        )

        row = box.row()
        row.template_list(
            "BMIDI_UL_robotic_systems",
            "",
            scene,
            "bmidi_robotic_systems",
            scene,
            "bmidi_active_system",
            rows=3,
        )

        col = row.column(align=True)
        col.operator("bmidi_robotic_systems.add", icon="ADD", text="")
        col.operator("bmidi_robotic_systems.remove", icon="REMOVE", text="")
        col.separator()
        col.operator("bmidi_robotic_systems.duplicate", icon="DUPLICATE", text="")

        if scene.bmidi_robotic_systems:
            system = scene.bmidi_robotic_systems[scene.bmidi_active_system]

            box = box.box()
            box.label(text="Note Controls")
            box.prop(system, "note_range_start")
            box.prop(system, "note_range_end")
            box.prop(system, "use_block_list")

            if system.use_block_list:
                box.prop(system, "blocked_notes")

            box.prop(system, "channel")

            box = layout.box()
            box.label(text="System Effectors", icon="CONSTRAINT")

            row = box.row()
            row.template_list(
                "BMIDI_UL_robotic_effectors",
                "",
                system,
                "effectors",
                system,
                "active_effector",
            )

            col = row.column(align=True)
            col.operator("bmidi_robotic_effectors.add", icon="ADD", text="")
            col.operator("bmidi_robotic_effectors.remove", icon="REMOVE", text="")
            col.separator()
            col.operator("bmidi_robotic_effectors.duplicate", icon="DUPLICATE", text="")

            if system.effectors:
                effector = system.effectors[system.active_effector]

                box = box.box()
                box.label(text="Effector Options")

                box.prop(effector, "move_duration")
                box.prop(effector, "return_duration")
                box.prop(effector, "lift_amount")


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
    BMIDI_Event,
    BMIDI_Controller,
    BMIDI_Robotic_Effector,
    BMIDI_Robotic_System,
    BMIDI_UL_controllers,
    BMIDI_UL_controller_events,
    BMIDI_UL_robotic_systems,
    BMIDI_UL_robotic_effectors,
    VIEW_3D_PT_bmidi_selector_panel,
    VIEW_3D_PT_bmidi_note_mapper,
    VIEW_3D_PT_bmidi_control_panel,
    VIEW_3D_PT_bmidi_robotic_panel,
    VIEW_3D_PT_bmidi_rename_panel,
    VIEW_3D_PT_bmidi_animation_panel,
    VIEW_3D_OT_add_item,
    VIEW_3D_OT_add_event,
    VIEW_3D_OT_remove_item,
    VIEW_3D_OT_remove_event,
    VIEW_3D_OT_move_event_up,
    VIEW_3D_OT_move_event_down,
    VIEW_3D_OT_duplicate_item,
    VIEW_3D_OT_duplicate_event,
    BMIDI_OT_add_robotic_system,
    BMIDI_OT_remove_robotic_system,
    BMIDI_OT_duplicate_robotic_system,
    BMIDI_OT_add_robotic_effector,
    BMIDI_OT_remove_robotic_effector,
    BMIDI_OT_duplicate_robotic_effector,
    VIEW_3D_OT_generate_keyframes,
    VIEW_3D_OT_rename_selected,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.bmidi_items = bpy.props.CollectionProperty(
        type=BMIDI_Controller,
    )
    bpy.types.Scene.bmidi_note_events = bpy.props.CollectionProperty(
        type=BMIDI_NoteEvent,
    )
    bpy.types.Scene.bmidi_active_note_event = bpy.props.IntProperty(
        default=0,
    )
    bpy.types.Scene.bmidi_active_item = bpy.props.IntProperty(
        default=0,
    )
    bpy.types.Scene.bmidi_robotic_systems = bpy.props.CollectionProperty(
        type=BMIDI_Robotic_System,
    )
    bpy.types.Scene.bmidi_active_system = bpy.props.IntProperty(
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
