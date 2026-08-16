from time import sleep
from midi_if import MidiIf
from sys_ex_comm import SysExComm
from copy import deepcopy
from trk_clip_tools import TrackAndClipTools
from seq_tools import SeqTools
import termcolor


class ZeroSideChain:
  def __init__(self,_seq):
    self.seq = _seq
    return
  
  #returns a list of the note_nb occurences in steps represented by cents
  #eg if a note is detected at step 2, it will be on the list with the value of 200
  #and if it is at step 2 shifted +15 then it will be on the list as 215
  def detect_note(self,trk_idx,clip_idx,note_nb,steps_nb=16):
    trig_times = []
    base_sequence = seq.get_steps(trk_idx,clip_idx,start_step_idx=0,step_len=steps_nb)
    note_events = seq.decode_note_sequences(base_sequence)
    print(f"note_events decoded are shown below, the number of decoded notes is {len(note_events)}")
    seq.display_note_events(note_events)
    for event in note_events:
      if event['note'] == note_nb :
        t = event['step_idx'] * 100 + event['start']
        print(f"detected note {note_nb} at step {event['step_idx']}, in cents: {t}")
        trig_times.append(t)
    return trig_times
  

if __name__ == "__main__":
  print(f"running zero_sc as main module")
  
  # pick your preferred MIDI driver (the less faulty one)
  # midi = MidiIf(iface='mido')   # faster but in my case less reliable (probably a bug in this library)
  midi = MidiIf(iface='alsa')     # slower but works (almost) each time, however parses the midi messages poorly
  
  comm = SysExComm(midi)
  tct = TrackAndClipTools(comm)
  seq = SeqTools(comm,tct)
  sc = ZeroSideChain(seq)
  
  # config params
  
  # trigger track/clip/note
  trig_trk_idx = 0
  trig_clip_idx = 0
  trig_note = 36        # 36 MIDI note number is typically used for a kick drum in MCs
  
  # destination track/clip/knob/lane
  dst_trk_idx = 2
  dst_clip_idx = 0
  dst_lane_idx = 3
  
  #sidechain parameters
  volume_down_to = 20   # decrease volume to this level with each triggering note
  time_before_trig = 2  # start decrease volume this number of motion steps befor the triggering note
  time_hold = 6         # hold volume at the reduced level for this number of motion steps
  time_rise_back = 10   # this many motion steps to restore the volume level
  
  # steps from the clip start in the trigger track
  steps_nb = 64
  
  # choose if you want to modify the existing motion sequence or you want to start with a constant value:
  # * set it to None if you want to start with an existing motion sequence and modify it (the sequence will be read from the instrument)
  # * set it to a particular value e.g. 100 (range 0-127) to start with an empty motion sequence of the constant value
  # motion_initial_value = None
  motion_initial_value = 100
  
  # optionally smoothen the motion shape (moderate values like 1-10 make sense)
  # set to None if you'd like to leave it raw
  smooth_factor = 3
  
  # now, let's start the processing:
  
  if motion_initial_value is None:
    # read motion
    print(f'{termcolor.FG_LTCYAN}Reading Motion from Track {dst_trk_idx+1}, Clip {dst_clip_idx+1}...{termcolor.FG_DEFAULT}')
    motion_init = seq.get_motion(dst_trk_idx, dst_clip_idx, dst_lane_idx, steps_nb=steps_nb, debug=False)
  else:
    # start with a constant value (comment/uncomment if you want this option)
    print(f'{termcolor.FG_LTCYAN}Preparing an empty motion pattern with an initial value of {motion_initial_value}...{termcolor.FG_DEFAULT}')
    motion_init = seq.motion_fill_const(motion_initial_value,steps_nb=steps_nb)
  
  # preserve the initial motion as a reference
  motion = deepcopy(motion_init)
  
  # substitute "no change" (-1) with previous values
  motion = seq.motion_forward_fill(motion)
  
  # read at which steps the triggering note (e.g. the kick) happens in the souce track/clip
  # times are in cents i.e. 1/100 of a step in the way the note sequencer works
  # this way a kick at step 11 (index 10) will have the trig time of 10*100 = 1000
  trig_note_times_cents = sc.detect_note(trig_trk_idx,trig_clip_idx,trig_note,steps_nb=steps_nb)
  
  # display times at which the triggering notes are played
  print(f'Trig note times in the trig track:   {trig_note_times_cents}')
  
  # apply the volume modification for each detected trigger note start
  for t in trig_note_times_cents:
    motion = seq.motion_duck( motion, t, volume_down_to, time_before_trig, time_hold, time_rise_back )
  
  # preserve the raw motion sequence
  motion_before_smooth = deepcopy(motion)
  
  # smoothen the motion sequence
  if smooth_factor is not None:
    motion = seq.motion_smooth( motion, smooth_factor )
  
  # display the results
  seq.motion_disp_compare(motion_init,motion_before_smooth,motion,trig_note_times_cents,plot_markers=None)
  
  # remove redundant values by inserting -1 in each step in which the motion sequence doesn't change
  # (that's based on the observed behavior of the internal editor)
  motion = seq.motion_remove_redundant(motion,initial_value=100)
  
  
  # ask if the user wants to write the motion sequence to the groovebox and optionally write it
  c = input(f"write the motion seq. to Track {dst_trk_idx+1}, Clip {dst_clip_idx+1}, lane index {dst_lane_idx}? y=yes: ")
  if( c == 'y' ):
    print(f'{termcolor.FG_LTCYAN}Writing Motion to Track {dst_trk_idx+1}, Clip {dst_clip_idx+1}, Lane idx {dst_lane_idx}{termcolor.FG_DEFAULT}')
    seq.write_motion(dst_trk_idx, dst_clip_idx, dst_lane_idx, motion, steps_nb=steps_nb, debug=False)
  else:
    print("skipping the write")
  
  print("exit, bye!")
  exit()
