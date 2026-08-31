import bpy

from src.engine.frame import Frame, FrameTrigger
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
    A controller object.

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
        Generate the keyframes for this controller.
        """

        pass


class NoteController(Controller):
    """
    A controller that key-frames a set of `Keyframe` objects based on specific MIDI notes.

    - `note_events`: a dictionary of MIDI notes corresponding to their frames
    - `notes`: a list of `MidiNote` objects
    - `events`: a list of `Event` objects
    - `frame_offset`: the relative offset of the generated frames
    """

    def __init__(
        self,
        note_events: dict[int, list[Frame]],
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

            for action in note_events[note.note()]:
                time = action.time() * fps
                prop = action.property()
                obj = action.object()

                if action.trigger() == FrameTrigger.BeforeStart:
                    frame = start - time
                elif action.trigger() == FrameTrigger.AfterStart:
                    frame = start + time
                elif action.trigger() == FrameTrigger.BeforeEnd:
                    frame = end - time
                elif action.trigger() == FrameTrigger.AfterEnd:
                    frame = end + time
                else:
                    frame = start

                if prop in ("data.spot_size", "data.energy"):
                    if action.relative():
                        set_prop(obj, prop, get_prop(obj, prop) + action.value())
                    else:
                        set_prop(obj, prop, action.value())

                    obj.keyframe_insert(data_path="data", frame=frame)
                else:
                    if action.relative():
                        setattr(obj, prop, getattr(obj, prop) + action.value())
                    else:
                        setattr(obj, prop, action.value())

                    obj.keyframe_insert(data_path=prop, frame=frame)
