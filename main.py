from bpy.types import Object
import imp
def initialize():
    import sys
    import importlib
    from pathlib import Path

    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    import src.note
    import src.event
    import src.controller

    importlib.reload(src.note)
    importlib.reload(src.event)
    importlib.reload(src.controller)

initialize()

bl_info = {
    "name": "bmidi",
    "author": "Keller Hydle",
    "version": (0, 0, 1),
    "blender": (5, 0, 0),
    "location": "3D Viewport > Sidebar > bmidi",
    "description": "Automatic MIDI-data keyframing for Blender objects",
    "category": "Development"
}

import mido
import bpy
import math
from collections import defaultdict
from src.event import Event, EventTrigger
from src.controller import BaseController

def get_midi_channel_ranges(midi_path: str):
    ranges = defaultdict(lambda: [127, 0])

    try:
        mid = mido.MidiFile(midi_path)
    except Exception:
        return {}

    for track in mid.tracks:
        for msg in track:
            if msg.type == "note_on" and msg.velocity > 0:
                ch = msg.channel + 1  # mido is 0–15
                ranges[ch][0] = min(ranges[ch][0], msg.note)
                ranges[ch][1] = max(ranges[ch][1], msg.note)

    # Remove unused channels
    return {
        ch: (mn, mx)
        for ch, (mn, mx) in ranges.items()
        if mn <= mx
    }

def get_channel_items(_, context):
    scene = context.scene

    if scene.bmidi_midi_file:
        channels = get_midi_channel_ranges(scene.bmidi_midi_file)

        if channels:
            return [(str(ch), str(ch), "") for ch in sorted(channels)]

    return []

def process_note_list(expr: str) -> list[int]:
    notes = []

    for i in expr.strip().split(","):
        if "-" in i:
            start, end = i.split("-")
            notes.extend(range(int(start), int(end) + 1))
        else:
            notes.append(int(i))

    return notes

class BMIDI_Event(bpy.types.PropertyGroup):
    time: bpy.props.FloatProperty(
        name="Time",
        description="Time in seconds relative to the MIDI note",
        default=0.0,
        soft_min=0.0,
    )
    trigger: bpy.props.EnumProperty(
        name="Trigger",
        items=[
            (
                EventTrigger.BeforeStart,
                "Before MIDI Note Starts",
                "Execute this event before the MIDI note starts",
            ),
            (
                EventTrigger.AfterStart,
                "After MIDI Note Starts",
                "Execute this event after the MIDI note starts",
            ),
            (
                EventTrigger.BeforeEnd,
                "Before MIDI Note Ends",
                "Execute this event before the MIDI note ends",
            ),
            (
                EventTrigger.AfterEnd,
                "After MIDI Note Ends",
                "Execute this event after the MIDI note ends",
            ),
        ],
        default=EventTrigger.BeforeStart,
    )
    action: bpy.props.EnumProperty(
        name="Action",
        items=[
            ("location.x", "Move X", ""),
            ("location.y", "Move Y", ""),
            ("location.z", "Move Z", ""),
            ("rotation_euler.x", "Rotate X", ""),
            ("rotation_euler.y", "Rotate Y", ""),
            ("rotation_euler.z", "Rotate Z", ""),
            ("scale.x", "Scale X", ""),
            ("scale.y", "Scale Y", ""),
            ("scale.z", "Scale Z", ""),
            ("data.energy", "Power Light", "Applies only to light objects"),
            ("data.spot_size", "Angle Spotlight", "Applies only to spot light objects"),
        ],
    )
    amount: bpy.props.FloatProperty(
        name="Amount",
        description="Number of units the action completes",
        default=0.0,
    )

class BMIDI_Item(bpy.types.PropertyGroup):
    enabled: bpy.props.BoolProperty(
        name="Enabled",
        description="Generate keyframes for this item",
        default=True
    )
    object_prefix: bpy.props.StringProperty(name="Object Prefix")
    note_range_start: bpy.props.IntProperty(
        name="Note Range Start",
        min=0,
        max=127,
        default=0
    )
    note_range_end: bpy.props.IntProperty(
        name="Note Range End",
        min=0,
        max=127,
        default=127
    )
    use_block_list: bpy.props.BoolProperty(
        name="Use Block List",
        description="Block certain notes from being key-framed",
        default=False
    )
    blocked_notes: bpy.props.StringProperty(
        name="Blocked Notes",
        description="Comma separated MIDI notes",
        default=""
    )
    channel: bpy.props.EnumProperty(
        name="Channel",
        items=get_channel_items,
    )
    events: bpy.props.CollectionProperty(
        type=BMIDI_Event,
    )
    active_event: bpy.props.IntProperty(
        default=0,
    )

class BMIDI_UL_items(bpy.types.UIList):
    def draw_item(
        self, context, layout, data, item, icon,
        active_data, active_propname, index
    ):
        row = layout.row(align=True)
        row.prop(item, "object_prefix", text="", emboss=False, icon="SOUND")
        row.prop(item, "enabled", text="")

class BMIDI_UL_item_events(bpy.types.UIList):
    def draw_item(
        self, context, layout, data, item, icon,
        active_data, active_propname, index
    ):
        row = layout.row(align=True)
        row.prop(item, "time", text="")
        row.prop(item, "trigger", text="")
        row.prop(item, "action", text="")
        row.prop(item, "amount", text="")

class VIEW_3D_OT_add_item(bpy.types.Operator):
    """Add a new item"""
    bl_idname = "bmidi_items.add_item"
    bl_label = "Add Item"

    def execute(self, context):
        context.scene.bmidi_items.add()
        context.scene.bmidi_active_item = len(context.scene.bmidi_items) - 1

        return {'FINISHED'}

class VIEW_3D_OT_remove_item(bpy.types.Operator):
    """Remove the selected item"""
    bl_idname = "bmidi_items.remove_item"
    bl_label = "Remove Item"

    def execute(self, context):
        idx = context.scene.bmidi_active_item
        context.scene.bmidi_items.remove(idx)
        context.scene.bmidi_active_item = max(0, idx - 1)

        return {'FINISHED'}

class VIEW_3D_OT_duplicate_item(bpy.types.Operator):
    """Duplicate the selected item"""
    bl_idname = "bmidi_items.duplicate_item"
    bl_label = "Duplicate Item"

    def execute(self, context):
        items = context.scene.bmidi_items
        idx = context.scene.bmidi_active_item

        if idx < 0 or idx >= len(items):
            return {'CANCELLED'}

        src = items[idx]

        # create new item
        items.add()
        dst = items[-1]

        for prop in src.bl_rna.properties:
            if prop.identifier in {"rna_type", "events"}:
                continue

            setattr(
                dst,
                prop.identifier,
                getattr(src, prop.identifier)
            )

        # copy events
        for src_event in src.events:
            dst_event = dst.events.add()

            for prop in src_event.bl_rna.properties:
                if prop.identifier == "rna_type":
                    continue

                setattr(
                    dst_event,
                    prop.identifier,
                    getattr(src_event, prop.identifier)
                )
        dst.object_prefix = f"{src.object_prefix} (COPY)"
        items.move(len(items) - 1, idx + 1)
        context.scene.bmidi_active_item = idx + 1

        if len(dst.events) > 0:
            dst.active_event = 0

        return {'FINISHED'}

class VIEW_3D_OT_add_event(bpy.types.Operator):
    """Add a new event"""
    bl_idname = "bmidi_items.add_event"
    bl_label = "Add Event"

    def execute(self, context):
        scene = context.scene
        item = scene.bmidi_items[scene.bmidi_active_item]

        item.events.add()
        item.active_event = len(item.events) - 1

        return {'FINISHED'}

class VIEW_3D_OT_remove_event(bpy.types.Operator):
    """Remove the selected event"""
    bl_idname = "bmidi_items.remove_event"
    bl_label = "Remove Event"

    def execute(self, context):
        scene = context.scene
        item = scene.bmidi_items[scene.bmidi_active_item]

        idx = item.active_event

        if idx < 0 or idx >= len(item.events):
            return {'CANCELLED'}

        item.events.remove(idx)

        item.active_event = min(
            idx,
            max(0, len(item.events) - 1)
        )

        return {'FINISHED'}

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
            return {'CANCELLED'}

        item.events.move(idx, new)
        item.active_event = new

        return {'FINISHED'}

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
            return {'CANCELLED'}

        item.events.move(idx, new)
        item.active_event = new

        return {'FINISHED'}

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
            return {'CANCELLED'}

        src = events[idx]

        events.add()
        dst = events[-1]

        for prop in src.bl_rna.properties:
            if prop.identifier == "rna_type":
                continue

            setattr(dst, prop.identifier, getattr(src, prop.identifier))

        events.move(len(events) - 1, idx + 1)

        item.active_event = idx + 1

        return {'FINISHED'}

class VIEW_3D_OT_generate_keyframes(bpy.types.Operator):
    """
    Clears object animation data and generates the keyframes for all items
    """
    bl_idname = "bmidi.generate_keyframes"
    bl_label = "Generate Keyframes"

    def execute(self, context):
        context.scene.frame_set(-1)
        midi_file = context.scene.bmidi_midi_file

        if not midi_file:
            self.report({'ERROR'}, "No MIDI file selected")
            return {'CANCELLED'}

        for item in context.scene.bmidi_items:
            if not item.enabled:
                continue

            events = []

            for e in item.events:
                needs_radians = True if e.action in ("rotation_euler.x", "rotation_euler.y", "rotation_euler.z", "data.spot_size") else False

                events.append(Event(e.time, True if e.trigger == "BEFORE" else False, e.action, math.radians(e.amount) if needs_radians else e.amount))

            channel = int(item.channel) - 1

            note_start = item.note_range_start
            note_end = item.note_range_end + 1 # 0 - 128
            blocked_notes = process_note_list(item.blocked_notes) if item.use_block_list else []
            notes = [i for i in range(note_start, note_end) if i not in blocked_notes]

            controller = BaseController(item.object_prefix, midi_file, events, notes, channel)
            controller.generate_keyframes()

        return {'FINISHED'}

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
            obj_list.sort(key=lambda o: (o.scale.x, o.scale.y, o.location.z), reverse=True)

        for note, obj in zip(notes, obj_list):
            obj.name = f"{prefix}{note}"

        return {'FINISHED'}

class VIEW_3D_PT_bmidi_panel(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "bmidi"
    bl_label = "bmidi"

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

        row = layout.row()
        row.template_list(
            "BMIDI_UL_items",
            "",
            scene,
            "bmidi_items",
            scene,
            "bmidi_active_item"
        )

        col = row.column(align=True)
        col.operator("bmidi_items.add_item", icon="ADD", text="")
        col.operator("bmidi_items.remove_item", icon="REMOVE", text="")
        col.separator()
        col.operator("bmidi_items.duplicate_item", icon="DUPLICATE", text="")

        if scene.bmidi_items:
            item = scene.bmidi_items[scene.bmidi_active_item]

            layout.prop(item, "object_prefix", text="Object Prefix")

            row = layout.row()
            row.template_list(
                "BMIDI_UL_item_events",
                "",
                item,
                "events",
                item,
                "active_event"
            )

            col = row.column(align=True)
            col.operator("bmidi_items.add_event", icon="ADD", text="")
            col.operator("bmidi_items.remove_event", icon="REMOVE", text="")
            col.separator()
            col.operator("bmidi_items.move_event_up", icon="TRIA_UP", text="")
            col.operator("bmidi_items.move_event_down", icon="TRIA_DOWN", text="")
            col.separator()
            col.operator("bmidi_items.duplicate_event", icon="DUPLICATE", text="")

            layout.prop(item, "note_range_start")
            layout.prop(item, "note_range_end")
            layout.prop(item, "use_block_list")

            if item.use_block_list:
                layout.prop(item, "blocked_notes")


            layout.separator()
            layout.prop(item, "channel")

        layout.separator()
        layout.operator("bmidi.generate_keyframes", icon="MODIFIER")

class VIEW_3D_PT_bmidi_rename_panel(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "bmidi"
    bl_label = "bmidi Rename™"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.prop(scene, "bmidi_rename_prefix")
        layout.prop(scene, "bmidi_rename_type")
        layout.prop(scene, "bmidi_rename_notes")

        layout.separator()
        layout.operator("bmidi.rename_selected", icon="TEXT")

def register():
    bpy.utils.register_class(BMIDI_Event)
    bpy.utils.register_class(BMIDI_Item)
    bpy.utils.register_class(BMIDI_UL_items)
    bpy.utils.register_class(BMIDI_UL_item_events)

    # item config
    bpy.types.Scene.bmidi_items = bpy.props.CollectionProperty(
        type=BMIDI_Item
    )
    bpy.types.Scene.bmidi_active_item = bpy.props.IntProperty()
    bpy.types.Scene.bmidi_midi_file = bpy.props.StringProperty(
        name="MIDI File",
        subtype="FILE_PATH",
    )

    # rename elements
    bpy.types.Scene.bmidi_rename_prefix = bpy.props.StringProperty(
        name="Object Prefix",
    )
    bpy.types.Scene.bmidi_rename_type = bpy.props.EnumProperty(
        name="Rename Type",
        items=[
            ("location_smallest", "Location (Smallest -> Biggest)", "Rename items based on their location (smallest to biggest)"),
            ("location_biggest", "Location (Biggest -> Smallest)", "Rename items based on their location (biggest to smallest)"),
            ("scale_smallest", "Scale (Smallest -> Biggest)", "Rename items based on their scale (smallest to biggest)"),
            ("scale_biggest", "Scale (Biggest -> Smallest)", "Rename items based on their scale (biggest to smallest)"),
        ]
    )
    bpy.types.Scene.bmidi_rename_notes = bpy.props.StringProperty(
        name="Rename To Notes",
        description="Comma separated MIDI notes",
    )

    bpy.utils.register_class(VIEW_3D_PT_bmidi_panel)
    bpy.utils.register_class(VIEW_3D_PT_bmidi_rename_panel)
    bpy.utils.register_class(VIEW_3D_OT_add_item)
    bpy.utils.register_class(VIEW_3D_OT_add_event)
    bpy.utils.register_class(VIEW_3D_OT_remove_item)
    bpy.utils.register_class(VIEW_3D_OT_remove_event)
    bpy.utils.register_class(VIEW_3D_OT_move_event_up)
    bpy.utils.register_class(VIEW_3D_OT_move_event_down)
    bpy.utils.register_class(VIEW_3D_OT_duplicate_item)
    bpy.utils.register_class(VIEW_3D_OT_duplicate_event)
    bpy.utils.register_class(VIEW_3D_OT_generate_keyframes)
    bpy.utils.register_class(VIEW_3D_OT_rename_selected)

def unregister():
    bpy.utils.unregister_class(BMIDI_UL_items)
    bpy.utils.unregister_class(VIEW_3D_PT_bmidi_panel)
    bpy.utils.unregister_class(VIEW_3D_PT_bmidi_rename_panel)
    bpy.utils.unregister_class(VIEW_3D_OT_add_item)
    bpy.utils.unregister_class(VIEW_3D_OT_add_event)
    bpy.utils.unregister_class(VIEW_3D_OT_remove_item)
    bpy.utils.unregister_class(VIEW_3D_OT_remove_event)
    bpy.utils.unregister_class(VIEW_3D_OT_move_event_up)
    bpy.utils.unregister_class(VIEW_3D_OT_move_event_down)
    bpy.utils.unregister_class(VIEW_3D_OT_duplicate_item)
    bpy.utils.unregister_class(VIEW_3D_OT_duplicate_event)
    bpy.utils.unregister_class(VIEW_3D_OT_generate_keyframes)
    bpy.utils.unregister_class(VIEW_3D_OT_rename_selected)

if __name__ == "__main__":
    register()
