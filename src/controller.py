import mido
import bpy
from src.event import Event

def get_prop(obj, prop_path: str):
    root, attr = prop_path.split(".")
    return getattr(getattr(obj, root), attr)

def set_prop(obj, prop_path: str, value):
    root, attr = prop_path.split(".")
    container = getattr(obj, root)
    setattr(container, attr, value)

class Controller:
    def __init__(self, midi_file: str, events: list[Event] = [], notes: list[int] = [], channel: int | None = None):
        self._midi_events = []
        self._events = events
        self._notes = notes

        midi = mido.MidiFile(midi_file)
        current_time = 0.0
        active_notes = {} # start_time, velocity

        for msg in midi:
            current_time += msg.time

            if msg.type == "note_on" and msg.velocity > 0:
                if msg.note not in notes:
                    continue

                if channel is not None and msg.channel != channel:
                    continue

                active_notes[(msg.note, msg.channel)] = ( current_time, msg.velocity / 127.0 )

            elif msg.type in ("note_off", "note_on") and msg.velocity == 0:
                if msg.note not in notes:
                    continue

                if channel is not None and msg.channel != channel:
                    continue

                key = (msg.note, msg.channel)
                if key in active_notes:
                    start_time, velocity = active_notes.pop(key)

                    self._midi_events.append({
                        "note": msg.note,
                        "start": start_time,
                        "duration": current_time - start_time,
                        "velocity": velocity,
                    })

    def midi_events(self) -> list[dict[str, float]]:
        return self._midi_events

    def events(self) -> list[Event]:
        return self._events

    def notes(self) -> list[int]:
        return self._notes

    def generate_keyframes(self) -> None:
        pass

class BaseController(Controller):
    """
    """
    def __init__(self, object_prefix: str, midi_file: str, events: list[Event] = [], notes: list[int] = [], channel: int | None = None):
        super().__init__(midi_file, events, notes, channel)

        self.object_prefix = object_prefix

    def generate_keyframes(self) -> None:
        object_prefix = self.object_prefix
        midi_events = self.midi_events()
        events = self.events()
        fps = bpy.context.scene.render.fps

        for i, e in enumerate(midi_events):
            target = bpy.data.objects[f"{object_prefix}{e['note']}"]
            start = e["start"] * fps
            # duration = e["duration"] * fps
            # velocity = 1 + (1 - e["velocity"]) * 1.5

            for event in events:
                prop = event.property()
                keyframe_prop = prop.split(".")[0]

                set_prop(target, prop, event.amount())
                target.keyframe_insert(
                    data_path=keyframe_prop,
                    frame=start - event.time() if event.before_note() else start + event.time()
                )

# class RoboticController(Controller):
#     """
#     Represents a robotic arm that will move to hit specified targets (notes)

#     Targets are represented with the format `<object_prefix><note_number>`, for example, a drum head might be named `Snare25`
#     """
#     def __init__(
#         self,
#         midi_file: str,
#         control_object: str,
#         target_object_prefix: str,
#         pullback_amount: float,
#         pullback_axis: str,
#         notes: list[int] = [],
#         channel: int | None = None,
#     ):
#         super().__init__(midi_file, notes, channel)

#         self.control_object = bpy.data.objects[control_object]
#         self.target_object_prefix = target_object_prefix
#         self.pullback_amount = pullback_amount
#         self.pullback_axis = pullback_axis

#         self.control_object.animation_data_clear()

#     def generate_keyframes(self):
#         events = self.midi_events()
#         fps = bpy.context.scene.render.fps
#         control = self.control_object
#         target_object_prefix = self.target_object_prefix
#         pullback = self.pullback_amount
#         axis = self.pullback_axis
#         base = control.location.copy()

#         offset_vec = mathutils.Vector(
#             (
#                 pullback if axis == "x" else 0,
#                 pullback if axis == "y" else 0,
#                 pullback if axis == "z" else 0,
#             )
#         )

#         first_frame = True

#         for i, e in enumerate(events):
#             next_event = events[i + 1] if i + 1 < len(events) else None

#             target = bpy.data.objects[f"{target_object_prefix}{e['note']}"]
#             start = e["start"] * fps
#             # velocity = 1 + (1 - e["velocity"]) * 1.5

#             if next_event:
#                 duration = (next_event["start"] * fps) - start
#             else:
#                 duration = e["duration"] * fps

#             pullback_frames = duration * 0.2
#             strike_frames = duration * 0.3
#             rebound_frames = duration * 0.2
#             pullback_start = start - pullback_frames
#             strike_mid = start - (strike_frames * 0.5)
#             impact = start
#             rebound_end = start + rebound_frames

#             if first_frame:
#                 first_frame = False

#                 # initial
#                 control.location = base
#                 control.keyframe_insert(
#                     data_path="location",
#                     frame=pullback_start - duration
#                 )

#             # move up
#             control.location = control.location + offset_vec
#             control.keyframe_insert(
#                 data_path="location",
#                 frame=pullback_start
#             )

#             # across
#             control.location = target.location + offset_vec
#             control.keyframe_insert(
#                 data_path="location",
#                 frame=strike_mid
#             )

#             # hit
#             control.location = target.location
#             control.keyframe_insert(
#                 data_path="location",
#                 frame=impact
#             )

#             rebound_end = start + rebound_frames

#             # look ahead for the next event and animate the transition (if no next event, return to base)
#             if next_event:
#                 next_target = bpy.data.objects[f"{target_object_prefix}{next_event['note']}"]
#                 next_start = next_event["start"] * fps

#                 next_hover_pos = next_target.location + offset_vec

#                 control.location = target.location + offset_vec
#                 control.keyframe_insert(
#                     data_path="location",
#                     frame=rebound_end
#                 )

#                 next_pullback_frames = (next_event["duration"] * fps) * 0.2
#                 next_pullback_start = next_start - next_pullback_frames

#                 control.location = next_hover_pos
#                 control.keyframe_insert(
#                     data_path="location",
#                     frame=next_pullback_start
#                 )
#             else:
#                 # final reset
#                 control.location = base
#                 control.keyframe_insert(data_path="location", frame=rebound_end + (fps * 1.0))

# class PositionalController(Controller):
#     """
#     Represents an object that will move to certain positions based on what note is being played

#     Targets are represented with the format `<object_prefix><note_number>`, for example, a drum head might be named `Snare25`
#     """
#     def __init__(
#         self,
#         midi_file: str,
#         object_name: str,
#         object_property: str,
#         min_position: float,
#         max_position: float,
#         notes: list[int] = [],
#         channel: int | None = None,
#     ):
#         super().__init__(midi_file, notes, channel)

#         self.object = bpy.data.objects[object_name]
#         self.object_property = object_property
#         self.min_position = min_position
#         self.max_position = max_position

#         self.object.animation_data_clear()

#     def generate_keyframes(self):
#         events = self.midi_events()
#         fps = bpy.context.scene.render.fps
#         obj = self.object
#         prop = self.object_property
#         keyframe_prop = prop.split(".")[0]
#         min = self.min_position
#         max = self.max_position

#         first_frame = True

#         for i, e in enumerate(events):
#             next_event = events[i + 1] if i + 1 < len(events) else None
#             start = e["start"] * fps
#             duration = e["duration"] * fps
#             velocity_scale = 1 + (1 - e["velocity"]) * 1.5

#             note = e["note"]
#             position = min + (note / 127) * (max - min)

#             if first_frame:
#                 first_frame = False

#                 set_prop(obj, prop, min + (63.5 / 127) * (max - min))
#                 obj.keyframe_insert(
#                     data_path=keyframe_prop,
#                     frame=start - (duration * velocity_scale)
#                 )

#             if next_event:
#                 set_prop(obj, prop, position)
#                 obj.keyframe_insert(
#                     data_path=keyframe_prop,
#                     frame=start
#                 )

#                 # hold position ~until next event
#                 obj.keyframe_insert(
#                     data_path=keyframe_prop,
#                     frame=(next_event["start"] * fps) - (duration * 0.5)
#                 )
#             else:
#                 set_prop(obj, prop, min + (63.5 / 127) * (max - min))
#                 obj.keyframe_insert(
#                     data_path=keyframe_prop,
#                     frame=start + (duration * velocity_scale)
#                 )
