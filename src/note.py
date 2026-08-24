class MidiNote:
    """
    A single MIDI note occuring when a MIDI note is played.

    - `start`: the time the note starts
    - `duration`: the note duration
    - `note`: the specific MIDI note (MIDI numbers 0-127)
    - `velocity`: the velocity of the note (in the range 0-127)
    """

    def __init__(self, start: float, duration: float, note: int, velocity: float):
        self._start = start
        self._duration = duration
        self._note = note
        self._velocity = velocity

    def start(self) -> float:
        """
        Returns the starting time of the note.
        """

        return self._start

    def end(self) -> float:
        """
        Returns the ending time of the note.
        """

        return self._start + self._duration

    def duration(self) -> float:
        """
        Returns the duration of the note.
        """

        return self._duration

    def note(self) -> int:
        """
        Returns the specific MIDI note (MIDI numbers 0-127.)
        """

        return self._note

    def velocity(self) -> float:
        """
        Returns the velocity of the note (in the range 0-127.)
        """

        return self._velocity
