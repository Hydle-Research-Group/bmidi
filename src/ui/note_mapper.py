import bpy
from bpy.types import Panel

from src.engine.event import EventTrigger
from src.engine.helpers import get_channel_items


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
        frame.trigger = EventTrigger.BeforeStart
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
