import mido


class MidiNote:
    """
    A single MIDI note occuring when a MIDI note is played.

    - `start`: the time the note starts
    - `duration`: the note duration
    - `note`: the specific MIDI note (MIDI numbers 0-127)
    - `channel`: the specific MIDI channel (MIDI numbers 0-15)
    - `velocity`: the velocity of the note (in the range 0-127)
    """

    def __init__(
        self, start: float, duration: float, note: int, channel: int, velocity: float
    ):
        self._start = start
        self._duration = duration
        self._note = note
        self._channel = channel
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

    def channel(self) -> int:
        """
        Returns the specific MIDI channel (MIDI numbers 0-15.)
        """

        return self._channel

    def velocity(self) -> float:
        """
        Returns the velocity of the note (in the range 0-127.)
        """

        return self._velocity


def parse_midi(path: str) -> list[MidiNote]:
    midi = mido.MidiFile(path)

    current_time = 0.0
    active_notes = {}
    notes = []

    for msg in midi:
        current_time += msg.time

        if msg.type == "note_on" and msg.velocity > 0:
            active_notes[(msg.note, msg.channel)] = (
                current_time,
                msg.velocity / 127.0,
            )

        elif msg.type in ("note_off", "note_on") and msg.velocity == 0:
            key = (msg.note, msg.channel)

            if key in active_notes:
                start_time, velocity = active_notes.pop(key)

                notes.append(
                    MidiNote(
                        start_time,
                        current_time - start_time,
                        msg.note,
                        msg.channel,
                        velocity,
                    )
                )

    return notes
