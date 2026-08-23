class Event:
    """
    A single event occuring when a MIDI note is played.

    - `time`: the relative time (in seconds)
    - `before_note`: `True` if the event occurs before a note, otherwise `False`
    - `property`: the [Blender object property](https://docs.blender.org/api/current/bpy.props.html) of the event
    - `amount`: the unit amount `property` is adjusted
    """

    def __init__(self, time: float, before_note: bool, property: str, amount: float):
        self._time = time
        self._before_note = before_note
        self._property = property
        self._amount = amount

    def time(self) -> float:
        """
        Returns the relative time of the event (in seconds.)
        """

        return self._time

    def before_note(self) -> bool:
        """
        Returns if the event occurs before a note (`True`) or after (`False`)
        """

        return self._before_note

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
