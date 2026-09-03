from typing import Any

from bpy.types import Object


class Frame:
    """
    A single frame occurring on a specific object.

    - `object`: the object
    - `time`: the relative time (in seconds)
    - `trigger`: the `FrameTrigger` that determines when the frame occurs
    - `property`: the [Blender object property](https://docs.blender.org/api/current/bpy.props.html) of the event
    - `value`: the value `property` is set to
    - `relative`: if the property is adjusted from an original value
    - `is_rotation`: if the property is a rotation property
    """

    def __init__(
        self,
        object: Object,
        time: float,
        trigger: str,
        property: str,
        value: Any,
        relative: bool = False,
        is_rotation: bool = False,
    ):
        self._object = object
        self._time = time
        self._trigger = trigger
        self._property = property
        self._value = value
        self._relative = relative
        self._is_rotation = is_rotation

    def object(self) -> Object:
        """
        Returns the frame's object.
        """

        return self._object

    def time(self) -> float:
        """
        Returns the relative time of the frame in seconds.
        """

        return self._time

    def trigger(self) -> str:
        """
        Returns the `FrameTrigger` of the frame.
        """

        return self._trigger

    def property(self) -> str:
        """
        Returns the property of the frame.
        """

        return self._property

    def value(self) -> Any:
        """
        Returns the value of the frame.
        """

        return self._value

    def relative(self) -> bool:
        """
        Returns if the frame is relative.
        """

        return self._relative

    def is_rotation(self) -> bool:
        """
        Returns if the frame is a rotation.
        """

        return self._relative


class FrameTrigger:
    BeforeStart = "BEFORE_START"
    BeforeEnd = "BEFORE_END"
    AfterStart = "AFTER_END"
    AfterEnd = "AFTER_END"
