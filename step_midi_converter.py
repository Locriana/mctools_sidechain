from mido import Message, MidiFile, MidiTrack, MetaMessage
from collections import defaultdict
import math

'''
This file is included only as an experimental feature.
'''

class StepSequencerMIDIConverter:
    PPQN = 480
    MAX_STEPS = 128

    STEP_TICKS = {
        "16th": PPQN // 4,   # 120
        "8th":  PPQN // 2,   # 240
    }

    def events_to_midi(
        self,
        events,
        filename,
        tempo_bpm=120,
        step_granulation="16th",
    ):
        step_ticks = self.STEP_TICKS[step_granulation]

        mid = MidiFile(ticks_per_beat=self.PPQN)
        track = MidiTrack()
        mid.tracks.append(track)

        track.append(MetaMessage("set_tempo",
                                 tempo=self.bpm_to_tempo(tempo_bpm),
                                 time=0))

        # Collect note on/off events in absolute ticks
        timeline = []

        active_notes = {}  # note -> off_tick

        for ev in events:
            note = ev["note"]
            velocity = ev["velocity"]
            step_idx = ev["step_idx"]
            start_cents = ev["start"]
            length_cents = ev["length"]

            base_tick = step_idx * step_ticks
            start_tick = base_tick + round(start_cents / 100 * step_ticks)
            start_tick = max(0, start_tick)

            length_ticks = round(length_cents / 100 * step_ticks)
            end_tick = start_tick + length_ticks

            max_tick = self.MAX_STEPS * step_ticks
            if end_tick > max_tick:
                end_tick = max_tick

            # Force note-off if overlapping
            if note in active_notes and active_notes[note] > start_tick:
                timeline.append((active_notes[note], "off", note, velocity))

            timeline.append((start_tick, "on", note, velocity))
            timeline.append((end_tick, "off", note, velocity))
            active_notes[note] = end_tick

        # Sort and convert to delta time
        timeline.sort(key=lambda x: (x[0], x[1] == "off"))

        last_tick = 0
        for tick, kind, note, velocity in timeline:
            delta = tick - last_tick
            last_tick = tick

            if kind == "on":
                track.append(Message(
                    "note_on",
                    note=note,
                    velocity=velocity,
                    time=delta,
                    channel=0
                ))
            else:
                track.append(Message(
                    "note_off",
                    note=note,
                    velocity=velocity,
                    time=delta,
                    channel=0
                ))

        mid.save(filename)

    def midi_to_events(self, filename):
        mid = MidiFile(filename)
        step_ticks = self.STEP_TICKS["16th"]

        events = []
        note_on_map = {}

        abs_tick = 0

        for msg in mid.tracks[0]:
            abs_tick += msg.time

            if msg.type == "note_on" and msg.velocity > 0:
                note_on_map[msg.note] = (abs_tick, msg.velocity)

            elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
                if msg.note not in note_on_map:
                    continue

                start_tick, velocity = note_on_map.pop(msg.note)
                duration_ticks = abs_tick - start_tick

                step_idx = round(start_tick / step_ticks)
                step_start_tick = step_idx * step_ticks

                start_cents = round(
                    (start_tick - step_start_tick) / step_ticks * 100
                )
                start_cents = max(-50, min(99, start_cents))

                length_cents = round(duration_ticks / step_ticks * 100)
                if step_idx >= self.MAX_STEPS:
                    continue

                events.append({
                    "note": msg.note,
                    "step_idx": step_idx,
                    "velocity": velocity,
                    "start": start_cents,
                    "length": length_cents,
                    "substep": 0,
                })

        return events

    @staticmethod
    def bpm_to_tempo(bpm):
        return int(60_000_000 / bpm)
