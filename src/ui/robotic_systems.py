import bpy

from src.engine.helpers import get_channel_items


class BMIDI_Robotic_Effector(bpy.types.PropertyGroup):
    effector_object: bpy.props.PointerProperty(
        type=bpy.types.Object, name="Effector Object"
    )
    return_duration: bpy.props.FloatProperty(
        name="Return Duration (s)",
        description="Given time for the effector to return to the original position",
        default=1.0,
        soft_min=0.01,
    )
    move_duration: bpy.props.FloatProperty(
        name="Move Duration (s)",
        description="Given time for the effector to move",
        default=1.0,
        soft_min=0.01,
    )
    lift_amount: bpy.props.FloatProperty(
        name="Lift Amount",
        description="Number of units the effector moves away from (upon the note finishing)",
        default=0.0,
    )


class BMIDI_Robotic_System(bpy.types.PropertyGroup):
    enabled: bpy.props.BoolProperty(
        name="Enabled", description="Generate keyframes for this item", default=True
    )
    target_prefix: bpy.props.StringProperty(
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
        description="Block certain notes from being keyframed",
        default=False,
    )
    blocked_notes: bpy.props.StringProperty(
        name="Blocked Notes", description="Comma separated MIDI notes"
    )
    channel: bpy.props.EnumProperty(
        name="Channel",
        items=get_channel_items,
    )
    effectors: bpy.props.CollectionProperty(
        type=BMIDI_Robotic_Effector,
    )
    active_effector: bpy.props.IntProperty(
        default=0,
    )


class BMIDI_UL_robotic_systems(bpy.types.UIList):
    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index
    ):
        row = layout.row(align=True)
        row.prop(item, "target_prefix", text="")
        row.prop(item, "enabled", text="")


class BMIDI_UL_robotic_effectors(bpy.types.UIList):
    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index
    ):
        row = layout.row(align=True)
        row.prop(item, "effector_object", text="")
