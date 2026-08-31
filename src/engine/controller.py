import bpy
from mathutils import Vector

from src.engine.effector import Effector
from src.engine.event import Event, EventTrigger
from src.engine.frame import Frame, FrameTrigger
from src.engine.note import MidiNote


def get_prop(obj, prop_path: str):
    root, attr = prop_path.split(".")
    return getattr(getattr(obj, root), attr)


def set_prop(obj, prop_path: str, value):
    root, attr = prop_path.split(".")
    container = getattr(obj, root)
    setattr(container, attr, value)


def schedule(
    effectors: list[Effector],
    target_prefix: str,
    notes: list[MidiNote],
) -> list[tuple[Effector, bool]]:
    """
    Dynamically builds a list of `Effector` objects corresponding to each note in `notes`.
    """

    schedules = []

    skip_next = False

    for i, note in enumerate(notes):
        if skip_next:
            skip_next = False
            continue

        start = note.start()
        target_location = bpy.data.objects[f"{target_prefix}{note.note()}"].location
        next_event = None if i == len(notes) - 1 else notes[i + 1]

        candidates = sorted(
            effectors,
            key=lambda a: (target_location - a.object().location).length,
        )
        closest = candidates[0]

        # by default, append the closest target
        schedules.append((closest, False))

        # if the next event is the same note, pick a candidate and schedule it for that note
        if (
            next_event
            and next_event.note() == note.note()
            and next_event.start() - start < closest.move_duration()
            and len(candidates) >= 2
        ):
            schedules.append((candidates[1], True))
            skip_next = True

    return schedules


class Controller:
    """
    A controller object.

    - `notes`: a list of `MidiNote` objects
    - `events`: a list of `Event` objects
    - `frame_offset`: the relative offset of the generated frames
    """

    def __init__(
        self,
        notes: list[MidiNote],
        events: list[Event] = [],
        frame_offset: int = 0,
    ):
        self._notes = notes
        self._events = events
        self._frame_offset = frame_offset

    def notes(self) -> list[MidiNote]:
        """
        Returns a list of `MidiNote` objects generated from the MIDI source.
        """

        return self._notes

    def events(self) -> list[Event]:
        """
        Returns a list of `Event` objects contained in the controller.
        """

        return self._events

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


class BaseController(Controller):
    """
    A base controller that key-frames a set of animation events based on MIDI data.

    - `object_prefix`: the object prefix
    - `notes`: a list of `MidiNote` objects
    - `events`: a list of `Event` objects
    - `frame_offset`: the relative offset of the generated frames
    """

    def __init__(
        self,
        object_prefix: str,
        notes: list[MidiNote],
        events: list[Event],
        frame_offset: int = 0,
    ):
        super().__init__(
            notes,
            events,
            frame_offset,
        )

        self.object_prefix = object_prefix

    def generate_keyframes(self) -> None:
        object_prefix = self.object_prefix
        events = self.events()
        frame_offset = self.frame_offset()
        fps = bpy.context.scene.render.fps

        for note in self.notes():
            target = bpy.data.objects[f"{object_prefix}{note.note()}"]
            target.animation_data_clear()

        for note in self.notes():
            target = bpy.data.objects[f"{object_prefix}{note.note()}"]
            start = note.start() * fps
            end = note.end() * fps
            # duration = e["duration"] * fps
            # velocity = 1 + (1 - e["velocity"]) * 1.5

            for event in events:
                prop = event.property()
                keyframe_prop = prop.split(".")[0]
                time = event.time() * fps
                amount = event.amount()

                if event.trigger() == EventTrigger.BeforeStart:
                    frame = start - time
                elif event.trigger() == EventTrigger.AfterStart:
                    frame = start + time
                elif event.trigger() == EventTrigger.BeforeEnd:
                    frame = end - time
                elif event.trigger() == EventTrigger.AfterEnd:
                    frame = end + time
                else:
                    frame = start

                set_prop(target, prop, get_prop(target, prop) + amount)
                target.keyframe_insert(
                    data_path=keyframe_prop, frame=frame + frame_offset
                )


class RoboticController(Controller):
    """
    A robotic controller that key-frames a set of effectors dynamically based on MIDI data.

    - `effectors`: a list of `Effector` objects
    - `target_prefix`: the target object prefix
    - `notes`: a list of `MidiNote` objects
    - `events`: a list of `Event` objects
    - `frame_offset`: the relative offset of the generated frames
    """

    def __init__(
        self,
        effectors: list[Effector],
        target_prefix: str,
        notes: list[MidiNote],
        events: list[Event] = [],
        frame_offset: int = 0,
    ):
        super().__init__(notes, events, frame_offset)

        self.target_prefix = target_prefix
        self.effectors = {}

        for e in effectors:
            obj = e.object()
            obj.animation_data_clear()

            self.effectors[obj] = (
                obj.location.copy(),
                obj.rotation_euler.copy(),
                e,
            )

        self.schedule = schedule(effectors, target_prefix, notes)

    def generate_keyframes(self):
        target_prefix = self.target_prefix
        effectors = self.effectors
        notes = self.notes()
        frame_offset = self.frame_offset()
        fps = bpy.context.scene.render.fps
        schedule = self.schedule

        for i, note in enumerate(notes):
            effector, alternative_target = schedule[i]
            target = bpy.data.objects[
                f"{target_prefix}{note.note()}{'ALT' if alternative_target else ''}"
            ]
            start = note.start() * fps + frame_offset
            end = note.end() * fps + frame_offset
            next_event = None if i == len(notes) - 1 else notes[i + 1]

            # target normal
            normal = target.matrix_world.to_3x3() @ Vector((0, 0, 1))
            normal.normalize()

            # hit + target locations
            hit_location = target.location.copy()
            target_rotation = target.rotation_euler.copy()

            # move arm to default positions before
            if i == 0:
                for arm, origin in effectors.items():
                    return_duration = origin[2].return_duration() * fps

                    arm.location = origin[0]
                    arm.rotation_euler = origin[1]
                    arm.keyframe_insert(
                        data_path="location", frame=start - return_duration
                    )
                    arm.keyframe_insert(
                        data_path="rotation_euler", frame=start - return_duration
                    )

            effector_object = effector.object()
            move_duration = effector.move_duration() * fps
            return_duration = effector.return_duration() * fps

            # the approach calculation happens after the initial movement, as we don't know the lift yet
            approach_location = hit_location + normal * effector.lift_amount()

            # approach
            effector_object.location = approach_location
            effector_object.rotation_euler = target_rotation
            effector_object.keyframe_insert(
                data_path="location", frame=start - move_duration
            )
            effector_object.keyframe_insert(
                data_path="rotation_euler", frame=start - move_duration
            )

            # hit
            effector_object.location = hit_location
            effector_object.keyframe_insert(data_path="location", frame=start)

            # return to the resting location or lift off the note
            if next_event and next_event.duration() * fps >= return_duration:
                effector_object.location = effectors[effector_object][0]
                effector_object.rotation_euler = effectors[effector_object][1]
                effector_object.keyframe_insert(
                    data_path="location", frame=end + return_duration
                )
                effector_object.keyframe_insert(
                    data_path="rotation_euler", frame=end + return_duration
                )
            else:
                effector_object.location = approach_location
                effector_object.rotation_euler = effectors[effector_object][1]
                effector_object.keyframe_insert(
                    data_path="location", frame=end + move_duration
                )
                effector_object.keyframe_insert(
                    data_path="rotation_euler", frame=start + move_duration
                )

            # move arm to default positions after
            if i == len(notes) - 1:
                for arm, origin in effectors.items():
                    return_duration = origin[2].return_duration() * fps

                    arm.location = origin[0]
                    arm.rotation_euler = origin[1]
                    arm.keyframe_insert(
                        data_path="location", frame=end + return_duration
                    )
                    arm.keyframe_insert(
                        data_path="rotation_euler", frame=end + return_duration
                    )


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
        events: list[Event] = [],
        frame_offset: int = 0,
    ):
        super().__init__(notes, events, frame_offset)
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
