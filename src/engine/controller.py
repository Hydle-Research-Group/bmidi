import bpy
from bpy_extras import anim_utils
from mathutils import Euler

from src.engine.frame import ActionFrame, Frame, FrameTrigger, ObjectFrame, PrefixFrame
from src.engine.note import MidiNote


def get_prop(obj, prop_path: str):
    root, attr = prop_path.split(".")
    return getattr(getattr(obj, root), attr)


def set_prop(obj, prop_path: str, value):
    root, attr = prop_path.split(".")
    container = getattr(obj, root)
    setattr(container, attr, value)


class Controller:
    """
    Base class for controller objects.

    - `notes`: a list of `MidiNote` objects
    - `frame_offset`: the relative offset of the generated frames
    """

    def __init__(
        self,
        notes: list[MidiNote],
        frame_offset: int = 0,
    ):
        self._notes = notes
        self._frame_offset = frame_offset

    def notes(self) -> list[MidiNote]:
        """
        Returns a list of `MidiNote` objects generated from the MIDI source.
        """

        return self._notes

    def frame_offset(self) -> int:
        """
        Returns a the frame offset of the controller.
        """

        return self._frame_offset

    def generate_keyframes(self) -> None:
        """
        Generate the object keyframes for this controller.
        """

    def clear_keyframes(self) -> None:
        """
        Clear the object keyframes for this controller.
        """


class NoteController(Controller):
    """
    A controller that keyframes a set of `Frame` objects based on specific MIDI notes.

    - `note_events`: a dictionary of MIDI notes/channels corresponding to their frames
    - `notes`: a list of `MidiNote` objects
    - `frame_offset`: the relative offset of the generated frames
    """

    def __init__(
        self,
        note_events: dict[tuple[int, int], list[Frame]],
        notes: list[MidiNote],
        frame_offset: int = 0,
    ):
        super().__init__(notes, frame_offset)
        self.note_events = note_events

    def generate_keyframes(self):
        notes = self.notes()
        note_events = self.note_events
        fps = bpy.context.scene.render.fps
        frame_offset = self.frame_offset()

        for i, note in enumerate(notes):
            start = note.start() * fps + frame_offset
            end = note.end() * fps + frame_offset

            for frame_event in note_events[(note.note(), note.channel())]:
                time = frame_event.time() * fps
                prop = frame_event.property()

                if isinstance(frame_event, (ObjectFrame, ActionFrame)):
                    obj = frame_event.object()
                elif isinstance(frame_event, PrefixFrame):
                    obj = bpy.data.objects[f"{frame_event.prefix()}{note.note()}"]

                if frame_event.trigger() == FrameTrigger.BeforeStart:
                    frame = start - time
                elif frame_event.trigger() == FrameTrigger.AfterStart:
                    frame = start + time
                elif frame_event.trigger() == FrameTrigger.BeforeEnd:
                    frame = end - time
                elif frame_event.trigger() == FrameTrigger.AfterEnd:
                    frame = end + time
                elif frame_event.trigger() == FrameTrigger.BeforeFirstNoteStarts:
                    if i != 0:
                        continue

                    frame = start - time
                elif frame_event.trigger() == FrameTrigger.AfterLastNoteEnds:
                    if i != len(notes) - 1:
                        continue

                    frame = end + time
                else:
                    frame = start

                if isinstance(frame_event, ActionFrame):
                    channelbag = anim_utils.action_get_channelbag_for_slot(
                        frame_event.action(), obj.animation_data.action_slot
                    )

                    if not channelbag:
                        continue

                    for fcurve in channelbag.fcurves:
                        for keyframe in fcurve.keyframe_points:
                            keyframe_frame = frame + keyframe.co.x
                            value = keyframe.co.y

                            prop = obj.path_resolve(fcurve.data_path)

                            if fcurve.array_index >= 0:
                                prop[fcurve.array_index] = value
                            else:
                                setattr(
                                    obj,
                                    fcurve.data_path,
                                    value,
                                )

                            obj.keyframe_insert(
                                data_path=fcurve.data_path,
                                index=fcurve.array_index,
                                frame=keyframe_frame,
                            )

                    continue  # skip normal keyframing

                value = frame_event.value()

                if prop in ("data.spot_size", "data.energy"):
                    if frame_event.relative():
                        set_prop(obj, prop, get_prop(obj, prop) + value)
                    else:
                        set_prop(obj, prop, value)

                    obj.keyframe_insert(data_path="data", frame=frame)
                else:
                    if frame_event.relative():
                        original = getattr(obj, prop)

                        if frame_event.is_rotation():
                            setattr(
                                obj,
                                prop,
                                Euler(
                                    (
                                        original.x + value.x,
                                        original.y + value.y,
                                        original.z + value.z,
                                    ),
                                    "XYZ",
                                ),
                            )
                        else:
                            setattr(obj, prop, original + value)
                    else:
                        setattr(obj, prop, value)

                    obj.keyframe_insert(data_path=prop, frame=frame)

    def clear_keyframes(self):
        for (n, _), frames in self.note_events.items():
            for f in frames:
                if isinstance(f, ObjectFrame):
                    f.object().animation_data_clear()
                elif isinstance(f, PrefixFrame):
                    bpy.data.objects[f"{f.prefix()}{n}"].animation_data_clear()
                elif isinstance(f, ActionFrame):
                    obj = f.object()

                    if obj.animation_data and obj.animation_data.action:
                        channelbag = anim_utils.action_get_channelbag_for_slot(
                            obj.animation_data.action,
                            obj.animation_data.action_slot,
                        )

                        if channelbag:
                            channelbag.fcurves.clear()
