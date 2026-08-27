class Event:
    """
    A single event occurring when a MIDI note is played.

    - `time`: the relative time (in seconds)
    - `trigger`: the `EventTrigger` that determines when the note plays
    - `property`: the [Blender object property](https://docs.blender.org/api/current/bpy.props.html) of the event
    - `amount`: the unit amount `property` is adjusted
    """

    def __init__(self, time: float, trigger: str, property: str, amount: float):
        self._time = time
        self._trigger = trigger
        self._property = property
        self._amount = amount

    def time(self) -> float:
        """
        Returns the relative time of the event in seconds.
        """

        return self._time

    def trigger(self) -> str:
        """
        Returns the `EventTrigger` of the event
        """

        return self._trigger

    def property(self) -> str:
        """
        Returns the Blender object property of the event.
        """

        return self._property

    def amount(self) -> float:
        """
        Returns the unit amount that the event's property is adjusted.
        """

        return self._amount


class EventTrigger:
    BeforeStart = "BEFORE_START"
    BeforeEnd = "BEFORE_END"
    AfterStart = "AFTER_END"
    AfterEnd = "AFTER_END"
