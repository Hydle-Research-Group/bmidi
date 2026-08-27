import bpy
import mido
from bpy.types import Object
from mathutils import Vector

from src.engine.effector import Effector
from src.engine.event import Event, EventTrigger
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

    - `midi_file`: a valid path to a midi file
    - `events`: a list of `Event` objects
    - `allowed_notes`: a list of integers (MIDI numbers 0-127) that the controller is allowed to generate
    - `channel`: an integer (MIDI channels 0-15) if `None` notes from all channels in the MIDI source are used
    """

    def __init__(
        self,
        midi_file: str,
        events: list[Event] = [],
        allowed_notes: list[int] = [],
        channel: int | None = None,
    ):
        self._notes = []
        self._events = events
        self._allowed_notes = allowed_notes

        midi = mido.MidiFile(midi_file)
        current_time = 0.0
        active_notes = {}  # start_time, velocity

        for msg in midi:
            current_time += msg.time

            if msg.type == "note_on" and msg.velocity > 0:
                if msg.note not in allowed_notes:
                    continue

                if channel is not None and msg.channel != channel:
                    continue

                active_notes[(msg.note, msg.channel)] = (
                    current_time,
                    msg.velocity / 127.0,
                )

            elif msg.type in ("note_off", "note_on") and msg.velocity == 0:
                if msg.note not in allowed_notes:
                    continue

                if channel is not None and msg.channel != channel:
                    continue

                key = (msg.note, msg.channel)
                if key in active_notes:
                    start_time, velocity = active_notes.pop(key)

                    self._notes.append(
                        MidiNote(
                            start_time, current_time - start_time, msg.note, velocity
                        )
                    )

        # first/last setting
        self._notes[0]._first = True
        self._notes[len(self._notes) - 1]._last = True

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

    def allowed_notes(self) -> list[int]:
        """
        Returns a list of integers (MIDI numbers 0-127) used by the controller.
        """

        return self._allowed_notes

    def generate_keyframes(self) -> None:
        """
        Generate the keyframes for this controller.
        """

        pass


class BaseController(Controller):
    """
    A base controller that key-frames a set of animation events based on MIDI data.

    - `object_prefix`: the object prefix
    - `midi_file`: a valid path to a midi file
    - `events`: a list of `Event` objects
    - `notes`: a list of integers (MIDI notes 0-127)
    - `channel`: an integer (MIDI channels 0-15) if `None` notes from all channels in the MIDI source are used
    """

    def __init__(
        self,
        object_prefix: str,
        midi_file: str,
        events: list[Event] = [],
        notes: list[int] = [],
        channel: int | None = None,
    ):
        super().__init__(midi_file, events, notes, channel)

        self.object_prefix = object_prefix

    def generate_keyframes(self) -> None:
        object_prefix = self.object_prefix
        events = self.events()
        fps = bpy.context.scene.render.fps

        for note in self.allowed_notes():
            target = bpy.data.objects[f"{object_prefix}{note}"]
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
                target.keyframe_insert(data_path=keyframe_prop, frame=frame)


class RoboticController(Controller):
    """
    A robotic controller that key-frames a set of arm effectors dynamically based on MIDI data.


    """

    def __init__(
        self,
        effectors: list[Effector],
        target_prefix: str,
        midi_file: str,
        events: list[Event] = [],
        notes: list[int] = [],
        channel: int | None = None,
    ):
        super().__init__(midi_file, events, notes, channel)

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

    def generate_keyframes(self):
        target_prefix = self.target_prefix
        effectors = self.effectors
        fps = bpy.context.scene.render.fps
        notes = self.notes()

        for i, note in enumerate(notes):
            target = bpy.data.objects[f"{target_prefix}{note.note()}"]
            start = note.start() * fps
            end = note.end() * fps
            next_event = None if i == len(notes) - 1 else notes[i + 1]

            # target normal
            normal = target.matrix_world.to_3x3() @ Vector((0, 0, 1))
            normal.normalize()

            # hit + target locations
            hit_location = target.location.copy()
            target_rotation = target.rotation_euler.copy()

            # move arm to default positions before
            if note.is_first():
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

            candidates = sorted(
                effectors.items(),
                key=lambda a: (target.location - a[0].location).length,
            )
            # TODO: clean up candidate/effector logic
            closest = candidates[0][0]
            move_duration = candidates[0][1][2].move_duration() * fps
            return_duration = candidates[0][1][2].return_duration() * fps
            lift = candidates[0][1][2].lift_amount()

            # the approach calculation happens after the initial movement, as we don't know the lift yet
            approach_location = hit_location + normal * lift

            # approach
            closest.location = approach_location
            closest.rotation_euler = target_rotation
            closest.keyframe_insert(data_path="location", frame=start - move_duration)
            closest.keyframe_insert(
                data_path="rotation_euler", frame=start - move_duration
            )

            # hit
            closest.location = hit_location
            closest.keyframe_insert(data_path="location", frame=start)

            # return to the resting location or lift off the note
            if next_event and next_event.duration() * fps >= return_duration:
                closest.location = effectors[closest][0]
                closest.rotation_euler = effectors[closest][1]
                closest.keyframe_insert(
                    data_path="location", frame=end + return_duration
                )
                closest.keyframe_insert(
                    data_path="rotation_euler", frame=end + return_duration
                )
            else:
                closest.location = approach_location
                closest.rotation_euler = effectors[closest][1]
                closest.keyframe_insert(data_path="location", frame=end + move_duration)
                closest.keyframe_insert(
                    data_path="rotation_euler", frame=start + move_duration
                )

            # move arm to default positions after
            if note.is_last():
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
