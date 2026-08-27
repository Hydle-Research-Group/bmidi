from collections import defaultdict

import bpy

from src.engine.event import EventTrigger
from src.engine.helpers import get_channel_items


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


class BMIDI_Controller(bpy.types.PropertyGroup):
    enabled: bpy.props.BoolProperty(
        name="Enabled", description="Generate keyframes for this item", default=True
    )
    object_prefix: bpy.props.StringProperty(
        name="Target Prefix",
        description="The prefix of the note target",
    )
    note_range_start: bpy.props.IntProperty(
        name="Note Range Start", min=0, max=127, default=0
    )
    note_range_end: bpy.props.IntProperty(
        name="Note Range End", min=0, max=127, default=127
    )
    use_block_list: bpy.props.BoolProperty(
        name="Use Block List",
        description="Block certain notes from being key-framed",
        default=False,
    )
    blocked_notes: bpy.props.StringProperty(
        name="Blocked Notes", description="Comma separated MIDI notes", default=""
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


class BMIDI_UL_controllers(bpy.types.UIList):
    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index
    ):
        row = layout.row(align=True)
        row.prop(item, "object_prefix", text="")
        row.prop(item, "enabled", text="")


class BMIDI_UL_controller_events(bpy.types.UIList):
    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index
    ):
        row = layout.row(align=True)
        row.prop(item, "time", text="")
        row.prop(item, "trigger", text="")
        row.prop(item, "action", text="")
        row.prop(item, "amount", text="")
