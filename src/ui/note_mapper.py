import math

import bpy
from bpy.types import Node, NodeSocket, NodeTree, Panel
from mathutils import Vector

from src.engine.controller import NoteController
from src.engine.frame import Frame, FrameTrigger
from src.engine.helpers import get_channel_items, get_midi_channel_ranges
from src.engine.note import MidiNote, parse_midi


def draw_add_menu(self, context):
    layout = self.layout
    if context.space_data.tree_type != BMIDI_NodeTree.bl_idname:
        return

    self.node_operator(layout, "BMIDI_Node_MIDIData")
    self.node_operator(layout, "BMIDI_Node_MIDIDataFilter")
    self.node_operator(layout, "BMIDI_Node_FrameCollection")


def get_upstream_nodes(node: Node):
    nodes = []

    for socket in node.inputs:
        for link in socket.links:
            nodes.append(link.from_node)

    return nodes


def build_frames(node) -> list[Frame]:
    if node.object is None:
        return []

    result = []

    for f in node.frames:
        value = (
            Vector(
                (
                    math.radians(f.x),
                    math.radians(f.y),
                    math.radians(f.z),
                )
            )
            if f.property == "rotation_euler"
            else (
                math.radians(f.x)
                if f.property == "data.spot_size"
                else Vector(
                    (
                        f.x,
                        f.y,
                        f.z,
                    )
                )
            )
        )

        result.append(
            Frame(
                node.object,
                f.time,
                f.trigger,
                f.property,
                value,
                relative=f.relative,
            )
        )

    return result


def resolve_notes(node: Node, midi_notes: list[MidiNote]) -> list[MidiNote]:
    upstream = get_upstream_nodes(node)

    if not upstream:
        return []

    source = upstream[0]

    if source.bl_idname == "BMIDI_Node_MIDIData":
        return midi_notes

    if source.bl_idname == "BMIDI_Node_MIDIDataFilter":
        notes = resolve_notes(source, midi_notes)

        return [
            note
            for note in notes
            if note.note() == source.note and note.channel() == int(source.channel) - 1
        ]

    return []


class BMIDI_MIDIEvent(bpy.types.PropertyGroup):
    start = bpy.props.FloatProperty()
    duration = bpy.props.FloatProperty()
    note = bpy.props.IntProperty()
    channel = bpy.props.IntProperty()
    velocity = bpy.props.IntProperty()


class BMIDI_Frame(bpy.types.PropertyGroup):
    time: bpy.props.FloatProperty(
        name="Time (s)",
        description="Time in seconds relative to the MIDI note",
        default=0.0,
        soft_min=0.0,
    )
    trigger: bpy.props.EnumProperty(
        name="Trigger",
        items=[
            (
                FrameTrigger.BeforeStart,
                "Before MIDI Note Starts",
                "Execute this event before the MIDI note starts",
            ),
            (
                FrameTrigger.AfterStart,
                "After MIDI Note Starts",
                "Execute this event after the MIDI note starts",
            ),
            (
                FrameTrigger.BeforeEnd,
                "Before MIDI Note Ends",
                "Execute this event before the MIDI note ends",
            ),
            (
                FrameTrigger.AfterEnd,
                "After MIDI Note Ends",
                "Execute this event after the MIDI note ends",
            ),
        ],
        default=FrameTrigger.BeforeStart,
    )
    property: bpy.props.EnumProperty(
        name="Property",
        items=[
            ("location", "Location", ""),
            ("rotation_euler", "Rotation Euler", ""),
            ("scale", "Scale", ""),
            ("data.energy", "Power Light", "Applies only to light objects"),
            ("data.spot_size", "Angle Spotlight", "Applies only to spot light objects"),
        ],
    )
    relative: bpy.props.BoolProperty(
        name="Relative",
        description="Adjust the property from it's current value",
        default=False,
    )
    x: bpy.props.FloatProperty(
        name="X",
    )
    y: bpy.props.FloatProperty(
        name="Y",
    )
    z: bpy.props.FloatProperty(
        name="Z",
    )


class BMIDI_UL_frame_collection(bpy.types.UIList):
    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index
    ):
        row = layout.row(align=True)
        row.prop(item, "time", text="")
        row.prop(item, "trigger", text="")


class BMIDI_OT_frame_collection_add(bpy.types.Operator):
    """Add a new frame to the selected Frame Collection node"""

    bl_idname = "bmidi_frame_collection.add_frame"
    bl_label = "Add Frame"

    node_name: bpy.props.StringProperty()

    def execute(self, context):
        node = context.space_data.edit_tree.nodes.get(self.node_name)

        if node is None:
            return {"CANCELLED"}

        frame = node.frames.add()

        frame.time = 0.0
        frame.trigger = FrameTrigger.BeforeStart
        frame.property = "location"

        frame.x = 0.0
        frame.y = 0.0
        frame.z = 0.0

        node.active_frame = len(node.frames) - 1

        return {"FINISHED"}


class BMIDI_OT_frame_collection_remove(bpy.types.Operator):
    """Remove the selected frame"""

    bl_idname = "bmidi_frame_collection.remove_frame"
    bl_label = "Remove Frame"

    node_name: bpy.props.StringProperty()

    def execute(self, context):
        node = context.space_data.edit_tree.nodes.get(self.node_name)

        if node is None:
            return {"CANCELLED"}

        idx = node.active_frame

        if idx < 0 or idx >= len(node.frames):
            return {"CANCELLED"}

        node.frames.remove(idx)

        node.active_frame = min(
            idx,
            max(0, len(node.frames) - 1),
        )

        return {"FINISHED"}


class BMIDI_OT_frame_collection_duplicate(bpy.types.Operator):
    """Duplicate the selected frame"""

    bl_idname = "bmidi_frame_collection.duplicate_frame"
    bl_label = "Duplicate Frame"

    node_name: bpy.props.StringProperty()

    def execute(self, context):
        node = context.space_data.edit_tree.nodes.get(self.node_name)

        if node is None:
            return {"CANCELLED"}

        idx = node.active_frame

        if idx < 0 or idx >= len(node.frames):
            return {"CANCELLED"}

        source = node.frames[idx]
        target = node.frames.add()

        target.time = source.time
        target.trigger = source.trigger
        target.property = source.property
        target.relative = source.relative

        target.x = source.x
        target.y = source.y
        target.z = source.z

        new_idx = len(node.frames) - 1

        while new_idx > idx + 1:
            node.frames.move(new_idx, new_idx - 1)
            new_idx -= 1

        node.active_frame = idx + 1

        return {"FINISHED"}


class BMIDI_OT_midi_data_generate(bpy.types.Operator):
    """Generate keyframes from the MIDI node graph"""

    bl_idname = "bmidi_midi_data.generate_keyframes"
    bl_label = "Generate Keyframes"

    node_name: bpy.props.StringProperty()

    def execute(self, context):
        context.scene.frame_set(-1)

        tree = context.space_data.edit_tree
        midi_node = tree.nodes.get(self.node_name)

        if midi_node is None:
            return {"CANCELLED"}

        midi_file = midi_node.midi_file

        if not midi_file:
            return {"CANCELLED"}

        notes = parse_midi(midi_file)
        allowed_notes = []

        for node in tree.nodes:
            if node.bl_idname != "BMIDI_Node_FrameCollection":
                continue

            if node.object is not None:
                node.object.animation_data_clear()

        frames = {}

        for node in tree.nodes:
            if node.bl_idname != "BMIDI_Node_FrameCollection":
                continue

            if node.object is None:
                continue

            node_notes = resolve_notes(
                node,
                notes,
            )

            node_frames = build_frames(node)

            for note in node_notes:
                allowed_notes.append(note.note())
                frames.setdefault(note.note(), []).extend(node_frames)

        controller = NoteController(
            frames,
            [n for n in notes if n.note() in allowed_notes],
            frame_offset=context.scene.bmidi_frame_offset,
        )

        controller.generate_keyframes()

        return {"FINISHED"}


class BMIDI_NodeTree(NodeTree):
    """ """

    bl_idname = "BMIDI_NodeTree"
    bl_label = "bmidi Node Editor"
    bl_icon = "NODETREE"


class BMIDI_TreeNode:
    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == "BMIDI_NodeTree"


class BMIDI_MIDIDataSocket(NodeSocket):
    """MIDI data"""

    bl_idname = "MIDIDataSocket"
    bl_label = "MIDI Data"

    def draw(self, context, layout, node, text):
        layout.label(text=text)


class BMIDI_Node_MIDIData(BMIDI_TreeNode, Node):
    bl_idname = "BMIDI_Node_MIDIData"
    bl_label = "MIDI Data"

    midi_file: bpy.props.StringProperty(
        name="MIDI File",
        subtype="FILE_PATH",
    )
    midi_events: bpy.props.CollectionProperty(type=BMIDI_MIDIEvent)

    def init(self, context):
        self.outputs.new("MIDIDataSocket", "MIDI Event Data")

    def draw_buttons(self, context, layout):
        layout.prop(self, "midi_file")

        if self.midi_file:
            midi_path = self.midi_file

            layout.separator()
            layout.label(text="MIDI Information", icon="INFO")

            if midi_path:
                channel_ranges = get_midi_channel_ranges(midi_path)

                if channel_ranges:
                    for ch in sorted(channel_ranges):
                        n, z = channel_ranges[ch]
                        layout.label(text=f"Channel {ch}: Notes {n}-{z}")
                else:
                    layout.label(text="Error parsing midi file", icon="ERROR")

            op = layout.operator(
                "bmidi_midi_data.generate_keyframes",
                icon="KEYFRAME",
            )
            op.node_name = self.name
        else:
            layout.label(text="No midi file selected")


class BMIDI_Node_MIDIDataFilter(BMIDI_TreeNode, Node):
    bl_idname = "BMIDI_Node_MIDIDataFilter"
    bl_label = "MIDI Data Filter"

    note: bpy.props.IntProperty(
        name="Note",
        description="Filter MIDI event data containing the specified note",
        default=60,
        min=0,
        max=127,
    )
    channel: bpy.props.EnumProperty(
        name="Channel",
        description="Filter MIDI event data containing the specified channel",
        items=get_channel_items,
    )

    def draw_buttons(self, context, layout):
        layout.prop(self, "note")
        layout.prop(self, "channel", text="")
        layout.separator()

    def init(self, context):
        self.inputs.new("MIDIDataSocket", "Input Event Data")

        self.outputs.new("MIDIDataSocket", "Filtered Event Data")


class BMIDI_Node_FrameCollection(BMIDI_TreeNode, Node):
    bl_idname = "BMIDI_Node_FrameCollection"
    bl_label = "Frame Collection"

    object: bpy.props.PointerProperty(type=bpy.types.Object, name="Object")
    frames: bpy.props.CollectionProperty(
        type=BMIDI_Frame,
    )
    active_frame: bpy.props.IntProperty(
        default=0,
    )

    def draw_buttons(self, context, layout):
        layout.prop(self, "object")

        row = layout.row()
        row.template_list(
            "BMIDI_UL_frame_collection",
            "",
            self,
            "frames",
            self,
            "active_frame",
        )

        buttons = row.column(align=True)

        op = buttons.operator(
            "bmidi_frame_collection.add_frame",
            icon="ADD",
            text="",
        )
        op.node_name = self.name

        op = buttons.operator(
            "bmidi_frame_collection.remove_frame",
            icon="REMOVE",
            text="",
        )
        op.node_name = self.name

        buttons.separator()

        op = buttons.operator(
            "bmidi_frame_collection.duplicate_frame",
            icon="DUPLICATE",
            text="",
        )
        op.node_name = self.name

        if not self.frames:
            return

        frame = self.frames[self.active_frame]

        box = layout.box()
        box.label(
            text="Frame Options",
            icon="PREFERENCES",
        )

        box.prop(frame, "time")
        box.prop(frame, "trigger")
        box.prop(frame, "property")

        row = box.row(align=True)
        row.prop(frame, "relative")

        if frame.property in (
            "data.spot_size",
            "data.energy",
        ):
            row.prop(
                frame,
                "x",
                text="Amount",
            )

        else:
            row.prop(frame, "x")
            row.prop(frame, "y")
            row.prop(frame, "z")

        layout.separator()

    def init(self, context):
        self.inputs.new("MIDIDataSocket", "Input Event Data")


class BMIDI_Object(bpy.types.PropertyGroup):
    object: bpy.props.PointerProperty(type=bpy.types.Object, name="Object")
    frames: bpy.props.CollectionProperty(
        type=BMIDI_Frame,
    )
    active_frame: bpy.props.IntProperty(
        default=0,
    )


class BMIDI_NoteEvent(bpy.types.PropertyGroup):
    enabled: bpy.props.BoolProperty(
        name="Enabled", description="Generate keyframes for this note", default=True
    )
    note: bpy.props.IntProperty(name="Note", min=0, max=127)
    channel: bpy.props.EnumProperty(
        name="Channel",
        items=get_channel_items,
    )
    objects: bpy.props.CollectionProperty(
        type=BMIDI_Object,
    )
    active_object: bpy.props.IntProperty(
        default=0,
    )


class BMIDI_UL_note_events(bpy.types.UIList):
    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index
    ):
        row = layout.row(align=True)
        row.prop(item, "note", text="")
        row.prop(item, "channel", text="")
        row.prop(item, "enabled", text="")


class BMIDI_UL_event_objects(bpy.types.UIList):
    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index
    ):
        row = layout.row(align=True)
        row.prop(item, "object", text="")


class BMIDI_UL_object_frames(bpy.types.UIList):
    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index
    ):
        row = layout.row(align=True)
        row.prop(item, "time", text="")
        row.prop(item, "trigger", text="")


class BMIDI_OT_add_note_event(bpy.types.Operator):
    """Add a new note event"""

    bl_idname = "bmidi_note_event.add"
    bl_label = "Add Note Event"

    def execute(self, context):
        scene = context.scene

        event = scene.bmidi_note_events.add()
        event.note = 60

        scene.bmidi_active_note_event = len(scene.bmidi_note_events) - 1

        return {"FINISHED"}


class BMIDI_OT_remove_note_event(bpy.types.Operator):
    """Remove the selected note event"""

    bl_idname = "bmidi_note_event.remove"
    bl_label = "Remove Note Event"

    def execute(self, context):
        scene = context.scene

        idx = scene.bmidi_active_note_event

        if idx < 0 or idx >= len(scene.bmidi_note_events):
            return {"CANCELLED"}

        scene.bmidi_note_events.remove(idx)

        scene.bmidi_active_note_event = min(
            idx,
            max(0, len(scene.bmidi_note_events) - 1),
        )

        return {"FINISHED"}


class BMIDI_OT_duplicate_note_event(bpy.types.Operator):
    """Duplicate the selected note event"""

    bl_idname = "bmidi_note_event.duplicate"
    bl_label = "Duplicate Note Event"

    def execute(self, context):
        scene = context.scene

        idx = scene.bmidi_active_note_event

        if idx < 0 or idx >= len(scene.bmidi_note_events):
            return {"CANCELLED"}

        source = scene.bmidi_note_events[idx]

        target = scene.bmidi_note_events.add()

        target.enabled = source.enabled
        target.note = source.note
        target.channel = source.channel

        for source_object in source.objects:
            target_object = target.objects.add()

            target_object.object = source_object.object

            for source_frame in source_object.frames:
                target_frame = target_object.frames.add()

                target_frame.time = source_frame.time
                target_frame.trigger = source_frame.trigger
                target_frame.property = source_frame.property

                target_frame.x = source_frame.x
                target_frame.y = source_frame.y
                target_frame.z = source_frame.z

            target_object.active_frame = source_object.active_frame

        target.active_object = source.active_object

        new_idx = len(scene.bmidi_note_events) - 1

        while new_idx > idx + 1:
            scene.bmidi_note_events.move(new_idx, new_idx - 1)
            new_idx -= 1

        scene.bmidi_active_note_event = idx + 1

        return {"FINISHED"}


class BMIDI_OT_add_object(bpy.types.Operator):
    """Add an object to the selected note event"""

    bl_idname = "bmidi_note_event.add_object"
    bl_label = "Add Object"

    def execute(self, context):
        scene = context.scene

        event_idx = scene.bmidi_active_note_event

        if event_idx < 0 or event_idx >= len(scene.bmidi_note_events):
            return {"CANCELLED"}

        event = scene.bmidi_note_events[event_idx]

        obj = event.objects.add()

        if context.object is not None:
            obj.object = context.object

        event.active_object = len(event.objects) - 1

        return {"FINISHED"}


class BMIDI_OT_remove_object(bpy.types.Operator):
    """Remove the selected object from the note event"""

    bl_idname = "bmidi_note_event.remove_object"
    bl_label = "Remove Object"

    def execute(self, context):
        scene = context.scene

        event_idx = scene.bmidi_active_note_event

        if event_idx < 0 or event_idx >= len(scene.bmidi_note_events):
            return {"CANCELLED"}

        event = scene.bmidi_note_events[event_idx]

        idx = event.active_object

        if idx < 0 or idx >= len(event.objects):
            return {"CANCELLED"}

        event.objects.remove(idx)

        event.active_object = min(
            idx,
            max(0, len(event.objects) - 1),
        )

        return {"FINISHED"}


class BMIDI_OT_add_frame(bpy.types.Operator):
    """Add a new frame to the selected object"""

    bl_idname = "bmidi_note_event.add_frame"
    bl_label = "Add Frame"

    def execute(self, context):
        scene = context.scene

        event_idx = scene.bmidi_active_note_event

        if event_idx < 0 or event_idx >= len(scene.bmidi_note_events):
            return {"CANCELLED"}

        event = scene.bmidi_note_events[event_idx]

        object_idx = event.active_object

        if object_idx < 0 or object_idx >= len(event.objects):
            return {"CANCELLED"}

        obj = event.objects[object_idx]

        frame = obj.frames.add()

        frame.time = 0.0
        frame.trigger = FrameTrigger.BeforeStart
        frame.property = "location"

        frame.x = 0.0
        frame.y = 0.0
        frame.z = 0.0

        obj.active_frame = len(obj.frames) - 1

        return {"FINISHED"}


class BMIDI_OT_duplicate_frame(bpy.types.Operator):
    """Duplicate the selected frame"""

    bl_idname = "bmidi_note_event.duplicate_frame"
    bl_label = "Duplicate Frame"

    def execute(self, context):
        scene = context.scene

        event_idx = scene.bmidi_active_note_event

        if event_idx < 0 or event_idx >= len(scene.bmidi_note_events):
            return {"CANCELLED"}

        event = scene.bmidi_note_events[event_idx]

        object_idx = event.active_object

        if object_idx < 0 or object_idx >= len(event.objects):
            return {"CANCELLED"}

        obj = event.objects[object_idx]

        idx = obj.active_frame

        if idx < 0 or idx >= len(obj.frames):
            return {"CANCELLED"}

        source = obj.frames[idx]

        target = obj.frames.add()

        target.time = source.time
        target.trigger = source.trigger
        target.property = source.property
        target.relative = source.relative

        target.x = source.x
        target.y = source.y
        target.z = source.z

        new_idx = len(obj.frames) - 1

        while new_idx > idx + 1:
            obj.frames.move(new_idx, new_idx - 1)
            new_idx -= 1

        obj.active_frame = idx + 1

        return {"FINISHED"}


class BMIDI_OT_remove_frame(bpy.types.Operator):
    """Remove the selected frame"""

    bl_idname = "bmidi_note_event.remove_frame"
    bl_label = "Remove Frame"

    def execute(self, context):
        scene = context.scene

        event_idx = scene.bmidi_active_note_event

        if event_idx < 0 or event_idx >= len(scene.bmidi_note_events):
            return {"CANCELLED"}

        event = scene.bmidi_note_events[event_idx]

        object_idx = event.active_object

        if object_idx < 0 or object_idx >= len(event.objects):
            return {"CANCELLED"}

        obj = event.objects[object_idx]

        idx = obj.active_frame

        if idx < 0 or idx >= len(obj.frames):
            return {"CANCELLED"}

        obj.frames.remove(idx)

        obj.active_frame = min(
            idx,
            max(0, len(obj.frames) - 1),
        )

        return {"FINISHED"}


class VIEW_3D_PT_bmidi_note_mapper(Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "bmidi"
    bl_label = "Note Mapper"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        main = layout.split(factor=0.5, align=True)
        left = main.column()

        box = left.box()

        header = box.row()
        header.label(
            text="Notes",
            icon="KEYFRAME_HLT",
        )

        list_row = box.row()
        list_row.template_list(
            "BMIDI_UL_note_events",
            "",
            scene,
            "bmidi_note_events",
            scene,
            "bmidi_active_note_event",
        )

        buttons = list_row.column(align=True)
        buttons.operator("bmidi_note_event.add", icon="ADD", text="")
        buttons.operator("bmidi_note_event.remove", icon="REMOVE", text="")
        buttons.separator()
        buttons.operator("bmidi_note_event.duplicate", icon="DUPLICATE", text="")

        if not scene.bmidi_note_events:
            return

        event = scene.bmidi_note_events[scene.bmidi_active_note_event]

        box = left.box()

        header = box.row()
        header.label(
            text="Objects",
            icon="OBJECT_DATA",
        )

        list_row = box.row()
        list_row.template_list(
            "BMIDI_UL_event_objects",
            "",
            event,
            "objects",
            event,
            "active_object",
        )

        buttons = list_row.column(align=True)
        buttons.operator(
            "bmidi_note_event.add_object",
            icon="ADD",
            text="",
        )
        buttons.operator(
            "bmidi_note_event.remove_object",
            icon="REMOVE",
            text="",
        )

        if not event.objects:
            return

        obj = event.objects[event.active_object]

        right = main.column()

        box = right.box()

        header = box.row()
        header.label(
            text="Frames",
            icon="KEYFRAME",
        )

        list_row = box.row()
        list_row.template_list(
            "BMIDI_UL_object_frames",
            "",
            obj,
            "frames",
            obj,
            "active_frame",
        )

        buttons = list_row.column(align=True)
        buttons.operator(
            "bmidi_note_event.add_frame",
            icon="ADD",
            text="",
        )
        buttons.operator(
            "bmidi_note_event.remove_frame",
            icon="REMOVE",
            text="",
        )
        buttons.separator()
        buttons.operator(
            "bmidi_note_event.duplicate_frame",
            icon="DUPLICATE",
            text="",
        )

        if not obj.frames:
            return

        frame = obj.frames[obj.active_frame]

        box = right.box()

        box.label(
            text="Frame Options",
            icon="PREFERENCES",
        )

        box.prop(frame, "time")
        box.prop(frame, "trigger")
        box.prop(frame, "property")

        row = box.row(align=True)
        row.prop(frame, "relative")

        if frame.property in ("data.spot_size", "data.energy"):
            row.prop(frame, "x", text="Amount")
        else:
            row.prop(frame, "x")
            row.prop(frame, "y")
            row.prop(frame, "z")
