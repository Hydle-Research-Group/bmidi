from collections import defaultdict

import mido


def get_midi_channel_ranges(midi_path: str):
    ranges = defaultdict(lambda: [127, 0])

    try:
        mid = mido.MidiFile(midi_path)
    except Exception:
        return {}

    for track in mid.tracks:
        for msg in track:
            if msg.type == "note_on" and msg.velocity > 0:
                ch = msg.channel + 1  # mido is 0–15
                ranges[ch][0] = min(ranges[ch][0], msg.note)
                ranges[ch][1] = max(ranges[ch][1], msg.note)

    # Remove unused channels
    return {ch: (mn, mx) for ch, (mn, mx) in ranges.items() if mn <= mx}
