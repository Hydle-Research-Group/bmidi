import math

import bpy
from bpy.types import Context, Node, NodeOutputs, NodeSocket, NodeTree
from mathutils import Euler, Vector

from src.engine.controller import NoteController
from src.engine.frame import Frame, FrameTrigger, ObjectFrame, PrefixFrame
from src.engine.helpers import get_midi_channel_ranges
from src.engine.note import MidiNote, parse_midi


def draw_add_menu(self, context):
    layout = self.layout
    if context.space_data.tree_type != BMIDI_NodeTree.bl_idname:
        return

    self.node_operator(layout, NodeID.MidiDataNode)
    self.node_operator(layout, NodeID.MidiDataFilterNode)
    self.node_operator(layout, NodeID.FrameCollectionNode)


def create_frames(node: Node) -> list[Frame]:
    frames = []

    if node.bl_idname == NodeID.FrameCollectionNode:
        for f in node.frames:
            if f.property == "rotation_euler":
                value = Euler(
                    (
                        math.radians(f.x),
                        math.radians(f.y),
                        math.radians(f.z),
                    )
                )
            elif f.property == "data.spot_size":
                value = math.radians(f.x)
            else:
                value = Vector((f.x, f.y, f.z))

            is_rotation = f.property == "rotation_euler"

            if node.mode == "OBJECT":
                frames.append(
                    ObjectFrame(
                        node.object,
                        f.time,
                        f.trigger,
                        f.property,
                        value,
                        relative=f.relative,
                        is_rotation=is_rotation,
                    )
                )
            elif node.mode == "PREFIX":
                frames.append(
                    PrefixFrame(
                        node.prefix,
                        f.time,
                        f.trigger,
                        f.property,
                        value,
                        relative=f.relative,
                        is_rotation=is_rotation,
                    )
                )

    return frames


def create_events(
    outputs: NodeOutputs,
    notes: list[MidiNote],
) -> dict[tuple[int, int], list[Frame]]:
    events = {}

    for output in outputs:
        for link in output.links:
            node = link.to_node

            if node.bl_idname == NodeID.FrameCollectionNode:
                for n in notes:
                    key = (n.note(), n.channel())

                    if events.get(key):
                        events[key].extend(create_frames(node))
                    else:
                        events[(n.note(), n.channel())] = create_frames(node)

            elif node.bl_idname == NodeID.MidiDataFilterNode:
                filtered_notes = [
                    n
                    for n in notes
                    if n.note() == node.note and n.channel() == node.channel - 1
                ]

                events.update(
                    create_events(
                        node.outputs,
                        filtered_notes,
                    )
                )

    return events


class NodeID:
    """
    IDs for bmidi type nodes.
    """

    MidiDataNode = "MIDIDATA"
    MidiDataFilterNode = "MIDIFILTER"
    FrameCollectionNode = "FRAMECOLLECTION"


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


class BMIDI_OT_copy_from_selected(bpy.types.Operator):
    """Copy the properties from the selected object"""

    bl_idname = "bmidi_ops.copy_from_selected"
    bl_label = "Copy From Selected"

    node_name: bpy.props.StringProperty()

    def execute(self, context: Context):
        node = context.space_data.edit_tree.nodes.get(self.node_name)
        selection = context.active_object

        if selection is None:
            return {"CANCELLED"}

        if node.bl_idname == NodeID.FrameCollectionNode:
            frame = node.frames[node.active_frame]
            property = frame.property

            if property not in ("data.energy", "data.spot_size"):
                value = getattr(selection, property)
                frame.x = (
                    math.degrees(value.x) if property == "rotation_euler" else value.x
                )
                frame.y = (
                    math.degrees(value.y) if property == "rotation_euler" else value.y
                )
                frame.z = (
                    math.degrees(value.z) if property == "rotation_euler" else value.z
                )

        return {"FINISHED"}


class BMIDI_OT_midi_data_generate(bpy.types.Operator):
    """Generate keyframes from the MIDI node graph"""

    bl_idname = "bmidi_midi_data.generate_keyframes"
    bl_label = "Generate Keyframes"

    node_name: bpy.props.StringProperty()

    def execute(self, context: Context):
        context.scene.frame_set(-1)
        nodes = context.space_data.edit_tree.nodes

        node = nodes.get(self.node_name)
        midi_file = node.midi_file

        if not midi_file:
            return {"CANCELLED"}

        notes = parse_midi(midi_file)
        events = create_events(node.outputs, notes)
        controller = NoteController(
            events,
            [n for n in notes if events.get((n.note(), n.channel()))],
            frame_offset=node.frame_offset,
        )
        controller.clear_keyframes()
        controller.generate_keyframes()

        return {"FINISHED"}


class BMIDI_NodeTree(NodeTree):
    """Node editor for creating MIDI-based animations"""

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
    bl_idname = NodeID.MidiDataNode
    bl_label = "MIDI Data"

    midi_file: bpy.props.StringProperty(
        name="MIDI File",
        subtype="FILE_PATH",
    )
    midi_events: bpy.props.CollectionProperty(type=BMIDI_MIDIEvent)
    frame_offset: bpy.props.IntProperty(
        name="Frame Offset",
        description="Offset the generated frames by a set amount",
    )

    def init(self, context):
        self.outputs.new("MIDIDataSocket", "MIDI Event Data")

    def draw_buttons(self, context, layout):
        layout.prop(self, "midi_file")

        if self.midi_file:
            midi_path = self.midi_file

            layout.separator()

            box = layout.box()
            box.label(text="MIDI Information", icon="INFO")

            if midi_path:
                channel_ranges = get_midi_channel_ranges(midi_path)

                if channel_ranges:
                    for ch in sorted(channel_ranges):
                        n, z = channel_ranges[ch]
                        box.label(text=f"Channel {ch}: Notes {n}-{z}")
                else:
                    box.label(text="Error parsing midi file", icon="ERROR")

            layout.separator()
            layout.prop(self, "frame_offset")

            op = layout.operator(
                "bmidi_midi_data.generate_keyframes",
                icon="KEYFRAME",
            )
            op.node_name = self.name
        else:
            layout.label(text="No midi file selected")


class BMIDI_Node_MIDIDataFilter(BMIDI_TreeNode, Node):
    bl_idname = NodeID.MidiDataFilterNode
    bl_label = "MIDI Data Filter"

    note: bpy.props.IntProperty(
        name="Note",
        description="Filter MIDI event data containing the specified note",
        default=60,
        min=0,
        max=127,
    )
    channel: bpy.props.IntProperty(
        name="Channel",
        description="Filter MIDI event data containing the specified channel",
        default=10,
        min=1,
        max=16,
    )

    def draw_buttons(self, context, layout):
        layout.prop(self, "note")
        layout.prop(self, "channel")
        layout.separator()

    def init(self, context):
        self.inputs.new("MIDIDataSocket", "Input Event Data")

        self.outputs.new("MIDIDataSocket", "Filtered Event Data")


class BMIDI_Node_FrameCollection(BMIDI_TreeNode, Node):
    bl_idname = NodeID.FrameCollectionNode
    bl_label = "Frame Collection"

    mode: bpy.props.EnumProperty(
        name="Mode",
        items=[
            (
                "PREFIX",
                "Prefix",
                "Generate frames for a set of objects with the format [prefix][note]",
            ),
            (
                "OBJECT",
                "Object",
                "Generate frames for a single object",
            ),
        ],
        default="OBJECT",
    )
    object: bpy.props.PointerProperty(type=bpy.types.Object, name="Object")
    prefix: bpy.props.StringProperty(name="Target Prefix")
    frames: bpy.props.CollectionProperty(
        type=BMIDI_Frame,
    )
    active_frame: bpy.props.IntProperty(
        default=0,
    )

    def draw_buttons(self, context, layout):
        layout.prop(self, "mode")

        if self.mode == "OBJECT":
            layout.prop(self, "object")
        elif self.mode == "PREFIX":
            layout.prop(self, "prefix")

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
            op = row.operator(
                "bmidi_ops.copy_from_selected",
                icon="DUPLICATE",
                text="",
            )
            op.node_name = self.name

        layout.separator()

    def init(self, context):
        self.inputs.new("MIDIDataSocket", "Input Event Data")
