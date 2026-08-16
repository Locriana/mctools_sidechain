from time import sleep
from midi_if import MidiIf
from sys_ex_comm import SysExComm
from simple_roll import SimplePianoRoll
from matrix_view import MatrixView
import json
import random
from copy import deepcopy
from step_midi_converter import StepSequencerMIDIConverter
from motion_display import MotionDisplay
from trk_clip_tools import TrackAndClipTools

#for helpers
import termcolor
import colorsys
from typing import List, Tuple



SEQ_ACTIVE_NOTES = 0x10
SEQ_EMPTY_NOTE   = 0xFF
SEQ_NOTE_LIST_OFFS = 0x10
SEQ_MAX_STEP_NB = 0x80







class SeqTools:
  def __init__(self,comm,track_and_clip_tools):
    self.comm = comm
    self.tct = track_and_clip_tools
    print(f"SeqTools constructor, comm obj: {self.comm}")
    self.sequencer_base = 0x20000000 #sequencer base address
    
  # by index
  MOTION_LANE_NAMES = ["C1/FILTER (0x00)","C2/MOD  (0x10)","C3/FX (0x20)","C4/SOUND (0x30)","Ext 0x40","Ext 0x50","Ext 0x60","Ext 0x70"]
  
  '''def get_motion_step(self,trk_idx,clip_idx,param_idx,step_idx,debug=True):
    # motion = [-1]*SEQ_MAX_STEP_NB
    param_offset = param_idx * 0x10
    addr = self.tct.get_motion_step_base_address(trk_idx,clip_idx,step_idx,debug=debug) + param_offset
    #if debug==True:
    print(f"{termcolor.FG_LTCYAN}get_motion_step: step_idx=0x{step_idx:02X}, \
      param_idx=0x{param_idx:X}\
      reading motion chunk from addr={addr:08X}{termcolor.FG_DEFAULT}")
    chunk_raw = []
    try:
      chunk_raw = self.comm.roland_request(addr,16,timeout=0.1,debug=False)
    except:
      print(f"get_motion_step: cannot read motion chunk from the address {addr}, (clip_idx={clip_idx}, trk_idx={trk_idx}, step_idx={step_idx}")
      if debug==True:
        input("get_motion_step: confirm continue (enter)")
    motion = self.combine_to_bytes(chunk_raw,u2=True)
    if debug==True:
      print(f"motion chunk (step {step_idx}): {motion}")
    return motion'''
  
  
  
  def get_pitchbend_step(self,trk_idx,clip_idx,param_idx,step_idx,debug=True):
    # motion = [-1]*SEQ_MAX_STEP_NB
    addr = self.tct.get_clip_base_address(trk_idx,clip_idx,debug=debug) + self.tct.SEQ_PITCHBEND_OFFS
    if debug==True:
      print(f"get_pitchbend_step: step_idx={termcolor.FG_LTCYAN}0x{step_idx:02X}{termcolor.FG_DEFAULT}, \
reading motion chunk from addr={termcolor.FG_LTCYAN}{addr:08X}{termcolor.FG_DEFAULT}")
    chunk_raw = []
    try:
      chunk_raw = self.comm.roland_request(addr,0x10,timeout=0.1,debug=False)
      chunk_raw.extend( self.comm.roland_request(addr+0x10,0x10,timeout=0.1,debug=False) )
    except:
      print(f"get_motion_step: cannot read motion chunk from the address {addr}, (clip_idx={clip_idx}, trk_idx={trk_idx}, step_idx={step_idx}")
      if debug==True:
        input("get_motion_step: confirm continue (enter)")
    motion = self.combine_to_bytes(chunk_raw,u2=True)
    if debug==True:
      print(f"motion chunk (step {step_idx}): {motion}")
    return motion
    
  def get_motion(self,trk_idx,clip_idx,param_idx,steps_nb=SEQ_MAX_STEP_NB,debug=True):
    motion = []
    for step_idx in range(0,steps_nb):
      motion.extend( self.get_motion_step(trk_idx,clip_idx,param_idx,step_idx,debug=debug) )
    return motion
  
  def motion_fill_const(self, value, steps_nb=SEQ_MAX_STEP_NB):
    motion = [value]*steps_nb*8
    return motion
  
  def motion_forward_fill(self, motion, initial_value = 100):
    last_value = initial_value
    for index in range(len(motion)):
      if 0 <= motion[index] <= 127:
        last_value = motion[index]
      elif motion[index] == -1:
        motion[index] = last_value
    return motion
  
  def motion_remove_redundant(self, motion, initial_value = 100):
    last_value = initial_value
    for index in range(len(motion)):
      if motion[index] == last_value:
        motion[index] = -1
      else:
        last_value = motion[index]
    return motion
    
  def motion_duck(self, motion, trig_time_cents, lowest_value, n_fall, n_hold, n_rise):
    center_idx = round(trig_time_cents * 8 / 100)
    
    if len(motion) == 0:
      return motion

    if center_idx < 0 or center_idx >= len(motion):
      raise ValueError("center_idx is outside the motion range")

    if n_fall < 0 or n_hold < 0 or n_rise < 0:
      raise ValueError("n_fall, n_hold and n_rise cannot be negative")

    if n_fall + n_hold + n_rise >= len(motion):
      raise ValueError("Duck sequence must be shorter than motion")

    original_motion = motion.copy()
    motion_length = len(motion)

    fall_start_idx = (center_idx - n_fall) % motion_length
    fall_start_value = original_motion[fall_start_idx]

    if n_fall > 0:
      for step in range(n_fall + 1):
        index = (center_idx - n_fall + step) % motion_length
        ratio = step / n_fall
        limit = fall_start_value + (lowest_value - fall_start_value) * ratio
        limit = round(limit)

        if motion[index] > limit:
          motion[index] = limit
    else:
      if motion[center_idx] > lowest_value:
        motion[center_idx] = lowest_value

    for step in range(n_hold + 1):
      index = (center_idx + step) % motion_length

      if motion[index] > lowest_value:
        motion[index] = lowest_value

    rise_end_idx = (center_idx + n_hold + n_rise) % motion_length
    rise_end_value = original_motion[rise_end_idx]

    if n_rise > 0:
      for step in range(n_rise + 1):
        index = (center_idx + n_hold + step) % motion_length
        ratio = step / n_rise
        limit = lowest_value + (rise_end_value - lowest_value) * ratio
        limit = round(limit)
        if motion[index] > limit:
          motion[index] = limit
    return motion


  def motion_smooth(self, motion, n_smooth):
    if len(motion) == 0:
      return motion

    if n_smooth < 0:
      raise ValueError("n_smooth cannot be negative")

    if n_smooth == 0:
      return motion

    original_motion = motion.copy()
    motion_length = len(motion)

    for index in range(motion_length):
      weighted_sum = 0
      weight_sum = 0

      for offset in range(-n_smooth, n_smooth + 1):
        neighbour_idx = (index + offset) % motion_length
        weight = n_smooth + 1 - abs(offset)

        weighted_sum += original_motion[neighbour_idx] * weight
        weight_sum += weight

      smoothed_value = round(weighted_sum / weight_sum)

      if smoothed_value < original_motion[index]:
        motion[index] = smoothed_value
    return motion
  
  def motion_disp_compare(
    self,
    motion_initial,
    motion_raw,
    motion_smooth,
    trig_times_cents,
    plot_markers=None
  ):
    import matplotlib.pyplot as plt

    motion_length = min(
      len(motion_initial),
      len(motion_raw),
      len(motion_smooth)
    )

    if motion_length == 0:
      raise ValueError("Motion lists cannot be empty")

    initial = motion_initial[:motion_length]
    raw = motion_raw[:motion_length]
    smooth = motion_smooth[:motion_length]

    initial = self.motion_forward_fill(initial)
    raw = self.motion_forward_fill(raw)
    smooth = self.motion_forward_fill(smooth)

    # Convert motion sample indices to sequencer steps
    x_motion = []

    for index in range(motion_length):
      x_motion.append(index / 8)

    fig, axes = plt.subplots(
      3,
      1,
      figsize=(15, 7),
      sharex=True,
      sharey=True
    )
    
    plot_marker_size = 3
    if plot_markers != None:
        plot_markers = 'o'
    
    axes[0].plot(
      x_motion,
      initial,
      color="tab:blue",
      marker=plot_markers,
      markersize=plot_marker_size
    )
    axes[0].set_title("Initial Motion")

    axes[1].plot(
      x_motion,
      raw,
      color="tab:orange",
      marker=plot_markers,
      markersize=plot_marker_size
    )
    axes[1].set_title("Raw Motion")

    axes[2].plot(
      x_motion,
      smooth,
      color="tab:green",
      marker=plot_markers,
      markersize=plot_marker_size
    ) 
    axes[2].set_title("Smoothed Motion")

    # Draw trigger lines only on the Raw Motion plot
    for trig_time_cents in trig_times_cents:
      trig_position = trig_time_cents / 100

      if 0 <= trig_position <= x_motion[-1]:
        axes[1].axvline(
          x=trig_position,
          #color="tab:red",
          color="#ff00ff",
          linestyle="--",
          linewidth=3,
          alpha=1,
          zorder=10
        )

    y_ticks = list(range(0, 121, 10))
    y_ticks.append(127)

    # Display step numbers from 0 to 127
    max_step = min(127, motion_length // 8)
    x_ticks = list(range(max_step + 1))

    for ax in axes:
      ax.set_ylim(0, 127)
      ax.set_yticks(y_ticks)
      ax.set_ylabel("Motion")
      ax.grid(True)

      ax.set_xticks(x_ticks)
      ax.tick_params(
        axis="x",
        labelrotation=90,
        labelbottom=True
      )

    axes[2].set_xlabel("Step")

    axes[0].set_xlim(
      0,
      max(1, motion_length / 8)
    )

    fig.tight_layout()

    # Show the window without stopping the rest of the script
    plt.show(block=False)
    plt.pause(0.1)

    return fig, axes
      
  def get_step_fast(self,trk_idx,clip_idx,step_idx,get_16_notes=False,debug=False):
    addr = self.tct.get_seq_step_base_address(trk_idx,clip_idx,step_idx,debug) + SEQ_NOTE_LIST_OFFS
    if debug: print(f"step base address = {addr:02X}")
    '''rxbuf = self.comm.roland_request(addr,SEQ_ACTIVE_NOTES,timeout=0.1)
    sleep(0.2)
    rxbuf.extend(self.comm.roland_request(addr+SEQ_ACTIVE_NOTES,SEQ_ACTIVE_NOTES,timeout=0.1))'''
    
    '''
    Warning: this part of the code uses a dirty workaround. Here's what's going on:
    The sequencer in both MC-101 and MC-707 didn't respond to some steps (e.g. 45)
    with all the 16 programmed notes, just the first 8 notes (16 bytes).
    So I first fill the rxbuf with "empty" notes 0x0F-0x0F
    (resulting in 0xFF note value = empty)
    then I try to overwrite the empty notes with the read notes.
    If nothing gets read (len(temp)==0) then I just leave the "empty" notes
    This way the rxbuf has the constant length and can be consistently processed further
    '''
    rxbuf = [0x0F]*32
    if debug: print("*** getting lower 16 notes...")
    temp = self.comm.roland_request(addr,SEQ_ACTIVE_NOTES,timeout=0.1,debug=debug)
    if len(temp) == SEQ_ACTIVE_NOTES:
      rxbuf[0:16] = temp
    # sleep(0.1)
    if get_16_notes == True:
      if debug: print("*** getting upper 16 notes...")
      temp = self.comm.roland_request(addr+SEQ_ACTIVE_NOTES,SEQ_ACTIVE_NOTES,timeout=0.1,debug=debug)
      if len(temp) == SEQ_ACTIVE_NOTES:
        rxbuf[16:32] = temp
        # sleep(0.1)
      else:
        print(f"no active upper notes @ step idx {step_idx} @ address {addr+SEQ_ACTIVE_NOTES}")
    if debug:
      print(f"get_step_fast st{step_idx:02d} Ti{trk_idx}, Ci{clip_idx:02d}, rxbuf len={len(rxbuf)} ", end="")
      # print(f"get_step_fast st{step_idx:02d} Ti{trk_idx}, Ci{clip_idx:02d}, rxbuf len={len(rxbuf)} cntnts={self.intlist_to_hex_str(rxbuf)} ", end="")
    notes = [0]*SEQ_ACTIVE_NOTES
    res = 0
    for note_list_idx in range(0,SEQ_ACTIVE_NOTES):
      temp = rxbuf[2*note_list_idx]
      temp = temp << 4
      temp |= rxbuf[2*note_list_idx + 1]
      notes[res] = temp
      res = res + 1
    if debug:
      print(f"notes: {self.intlist_to_hex_str(notes)}")
    return notes
  
  # for visualization purposes only (not fully extracting notes, just the tones)
  def add_seq_to_roll(self,roll,trk_idx,clip_idx,loop=True,debug=True):
    print(f"add_seq_to_roll {clip_idx+1} of track {trk_idx+1}...")
    print(f"  reading color...")
    color_idx = self.tct.get_trk_color_idx(trk_idx,debug=True)
    roll.set_ch_color(trk_idx,color_idx)
    print(f"  color set to idx={color_idx}")
    step_scale, step_len = self.tct.get_step_params(trk_idx,clip_idx,debug=True)
    print(f"  clip params read: step_scale={step_scale}, step_len={step_len}")
    step_1_8 = False
    if step_scale == self.tct.scale_1_8:
      step_1_8 = True
    clip_note_list = [] # all notes in the clip
    
    # collect all notes
    for step_idx in range(step_len):
      # step_idx = roll_idx % step_len
      # if step_idx % 4 == 0: print("=",end="")
      step_note_list = self.get_step_fast(trk_idx,clip_idx,step_idx,debug=True)
      clip_note_list.append(step_note_list)
      if debug==True:
        print(f"  adding notes:  ",end="")
        print(self.intlist_to_hex_str(step_note_list))
    
    print("filling roll...")
    
    end = SEQ_MAX_STEP_NB
    if loop==False:
      end = step_len
    
    for roll_step in range(end):
      seq_note_idx = roll_step % (step_len)
      if debug==True:
        print(f"seq_note_idx={seq_note_idx}, step_len={step_len}, roll_step={roll_step}")
      step_note_list = clip_note_list[seq_note_idx]
      for note in step_note_list:
        if note < 128:
            roll.add_note(trk_idx,note,roll_step,scale_1_8 = step_1_8)
    print("add_seq_to_roll done")
    return roll
  
  def disp_roll(self,roll):
    roll.show()
  
  def intlist_to_hex_str(self,intlist):
    return f"{' '.join(f'{n:02X}' for n in intlist)}"
  
  # takes an in_list of values 0x01 0x02 0x3 0x4 ...
  # creates an out_list of values 0x12 0x34 ...
  def combine_to_bytes(self,in_list,u2=False):
    out_items = int(len(in_list) / 2)
    out_list = []
    for i in range(0,out_items):
      try:
        # -50 (-0x32) decodes to 206, so needs a fix
        item = (in_list[2*i] << 4) | in_list[2*i+1]
        # manually converting negative numbers in U2
        # I haven't figured out how to do it properly in Python
        # sorry, C/C++ background :P
        # Maybe I should have asked AI how to do that? xD
        if u2:
          if item & (1<<7):
            item = (~item) + 1
            item = item & 0xFF
            item = -item
        out_list.append( item )
      except:
        break
    return out_list
  
  def generate_empty_sequence(self,debug=False):
    sequence = []
    for i in range(0,SEQ_MAX_STEP_NB):
      sequence.append( self.generate_empty_step() )
    return sequence
  
  def generate_empty_step(self,debug=False):
    step = []
    for i in range(0,SEQ_ACTIVE_NOTES):
      step.append( self.generate_empty_component() )
    return step
  
  def generate_empty_component(self):
    component = {
      "note" : 0xFF,
      "velocity":0x50,
      "start":0,
      "end":0x50,
      "substep":0,
      "processed": False
    }
    return component
  
  #gets an 8-bit int value and splits it into lower & upper 4 bit integers
  #output is in the form of a 2-item list for extending the list to be written
  def split_value(self,value):
    value = value & 0xFF
    res = [0,0]
    res[0] = (value >> 4) & 0x0F
    res[1] = value & 0x0F
  
    return res
  
  def console_format_component(self,component):
    outstr = f"note=0x{component['note']:02X}, vel={component['velocity']:03}, start={component['start']:03}, stop={component['end']:03}, sub={component['substep']}"
    return outstr
  
  def console_format_step(self,step):
    outstr = f""
    try:
      for idx,component in enumerate(step):
        outstr = outstr + f"{idx:03} " + self.console_format_component(component)
        outstr += f"\n"
    except:
      print(f"console_format_step: error, step={step}")
      exit()
    return outstr
  
  def console_print_sequence(self,sequence,step_nb=SEQ_MAX_STEP_NB,debug=False):
    print("\n -------------- sequence -------------------")
    for step_idx in range(0,step_nb):
      print(f"*** step idx={step_idx} out of step_nb={step_nb}")
      try:
        print( self.console_format_step(sequence[step_idx]) )
      except:
        print(f"   cannot read the index={step_idx}")
        if debug==True:
          key = input("    continue_print_sequence? (n=no)")
          if key == 'n':
            break
    print("\n")
  
  #data an array of 8 substeps encoded as bytes, the length of data list must be 8,
  #otherwise only -1s will be written
  def write_one_motion_step(self,trk_idx,clip_idx,param_idx,step_idx,data,debug=False):
    print(f'{termcolor.FG_YELLOW} write_motion_step idx={step_idx}, data={self.intlist_to_hex_str(data)} {termcolor.FG_DEFAULT}')
    raw_data = []
    step_base_address = self.tct.get_motion_step_base_address(trk_idx,clip_idx,step_idx,debug=debug)
    param_address = step_base_address + 0x10 * param_idx
    if len(data) != 8:
      print(f'{termcolor.FG_RED} write_motion_step {step_idx} @ trk={trk_idx}, clip={clip_idx}, wrong len, filling with -1s{termcolor.FG_DEFAULT}')
      data = [0xFF]*8
    for v in data:
      raw_data.extend( self.split_value(v) )
    if debug: print(f'{termcolor.FG_GREEN} write_motion_step idx={step_idx}, raw_data={self.intlist_to_hex_str(raw_data)} {termcolor.FG_DEFAULT}')
    self.comm.roland_set(param_address,raw_data,debug=debug)
    return
  
  def write_motion(self,trk_idx,clip_idx,param_idx,data,steps_nb=SEQ_MAX_STEP_NB,debug=False):
    if len(data) / 8 != steps_nb:
      print(f'{termcolor.FG_RED} write_motion {step_idx} @ trk={trk_idx}, clip={clip_idx}, wrong len: steps_nb={steps_nb}, data len={len(data)}{termcolor.FG_DEFAULT}')
      return
    data_idx = 0
    for step_idx in range(steps_nb):
      step_base_address = self.tct.get_motion_step_base_address(trk_idx,clip_idx,step_idx,debug=debug)
      start_idx = data_idx
      end_idx = start_idx + 8
      if end_idx > len(data):
        print(f'{termcolor.FG_RED} write_motion {step_idx}, out of range at step_idx={step_idx}, end_idx={end_idx}, data len={len(data)}{termcolor.FG_DEFAULT}')
      data_chunk = data[start_idx:end_idx]
      self.write_one_motion_step(trk_idx,clip_idx,param_idx,step_idx,data_chunk,debug=debug)
      data_idx += 8
    return
  
  #write one step of the selected index 0..127
  def write_one_step(self,trk_idx,clip_idx,step_idx,sequence,debug=False):
    step = sequence[step_idx]
    print(f"{termcolor.FG_YELLOW}writing step {step_idx}, trk_idx={trk_idx}, clip_idx={clip_idx}{termcolor.FG_DEFAULT}")
    step_base_addr = self.tct.get_seq_step_base_address(trk_idx,clip_idx,step_idx,debug=False)
    if debug==True:
      print(f"  step base address = {step_base_addr:02X}")
      print(f"  {self.console_format_step(step)}" )
    
    note_list_l = []    # -> offset=0x10
    note_list_h = []    # -> offset=0x20
    velocity_list = []  # -> offset=0x30
    start_list_l = []   # -> offset=0x40
    start_list_h = []   # -> offset=0x50
    end_list = []       # -> offset=0x60
    substep_list = []   # -> offset=0x70
    
    for i in range(0,SEQ_ACTIVE_NOTES):
      try:
        # print(f'*** write_one_step: trying to read step i={i}...')
        component = step[i]
        # print(f'write_one_step: component={component}')
      except:
        print(f'write_one_step: empty component found @ input i={i}')
        component = self.generate_empty_component()
      
      #if debug==True:
      #  print(f"component at i={i} is: {component}") 
      
      note = self.split_value(component['note'])
      start = self.split_value(component['start'])
      if i < SEQ_ACTIVE_NOTES/2 :
        note_list_l.extend( note )
        start_list_l.extend( start )
      else:
        note_list_h.extend( note )
        start_list_h.extend( start )
      velocity_list.append( component['velocity'] )
      end_list.append( component['end'] )
      substep_list.append( component['substep'] )
      
    print(f"writing to address base: {step_base_addr:08X}")
    print(f"  note list L: {self.intlist_to_hex_str(note_list_l)}")
    print(f"  note list H: {self.intlist_to_hex_str(note_list_h)}")
    print(f"  velocities:  {self.intlist_to_hex_str(velocity_list)}")
    print(f"  start list L:{start_list_l}")
    print(f"  start list H:{start_list_h}")
    print(f"  end list:    {end_list}")
    print(f"  substep list:{substep_list}")
      
    tx_debug = True
    self.comm.roland_set(step_base_addr+0x10,note_list_l,debug=tx_debug)
    self.comm.roland_set(step_base_addr+0x20,note_list_h,debug=tx_debug)
    self.comm.roland_set(step_base_addr+0x30,velocity_list,debug=tx_debug)
    self.comm.roland_set(step_base_addr+0x40,start_list_l,debug=tx_debug)
    self.comm.roland_set(step_base_addr+0x50,start_list_h,debug=tx_debug)
    self.comm.roland_set(step_base_addr+0x60,end_list,debug=tx_debug)
    self.comm.roland_set(step_base_addr+0x70,substep_list,debug=tx_debug)
    
    return
  
  #writes a number of steps given in steps_to_write
  def write_steps(self,trk_idx,clip_idx,sequence,start_step=0,steps_to_write=SEQ_MAX_STEP_NB):
    if start_step+steps_to_write > SEQ_MAX_STEP_NB:
      print(f"write_steps: start_step+steps_to_write must be < 128, but is {start_step+steps_to_write}")
      return False
    for step_idx in range(start_step,steps_to_write):
      self.write_one_step(trk_idx,clip_idx,step_idx,sequence)
    return True
  
  def get_steps(self,trk_idx,clip_idx,start_step_idx=0,step_len=SEQ_MAX_STEP_NB,sort_lanes=False,debug=False):
    sequence = []
    for step_idx in range(start_step_idx,start_step_idx+step_len):
      sequence.append(self.get_one_step(trk_idx,clip_idx,step_idx,sort_lanes=sort_lanes,debug=debug))
    return sequence

  def get_one_step(self,trk_idx,clip_idx,step_idx,sort_lanes=False,debug=True):
    empty_step = True
    step_base_addr = self.tct.get_seq_step_base_address(trk_idx,clip_idx,step_idx,debug)
    print(f'{termcolor.FG_LTGREEN}Reading step idx={step_idx} from trk_idx={trk_idx}, clip_idx={clip_idx} {termcolor.FG_DEFAULT}')
    if debug: print(f"step base address = {step_base_addr:02X}")
    note_list_l = self.comm.roland_request(step_base_addr+0x10,16,timeout=0.1,debug=debug)
    try:
      note_list_h = self.comm.roland_request(step_base_addr+0x20,16,timeout=0.1,debug=debug)
    except:
      note_list_h = [0x0F]*16
      print(f"could not get note_list_h, leaving empty")
    note_list = self.combine_to_bytes(note_list_l)
    note_list.extend( self.combine_to_bytes(note_list_h) )
    for note in note_list:
      if note != 0xFF:
        empty_step = False
        break
    
    if empty_step == False:
      velocity_list = self.comm.roland_request(step_base_addr+0x30,16,timeout=0.1,debug=debug)
      
      start_list_l = self.comm.roland_request(step_base_addr+0x40,16,timeout=0.1,debug=debug)
      start_list_h = self.comm.roland_request(step_base_addr+0x50,16,timeout=0.1,debug=debug)
      start_list = self.combine_to_bytes(start_list_l,u2=True)
      start_list.extend( self.combine_to_bytes(start_list_h,u2=True) )
      # print(f'start_list: {start_list}')
      #convert to +/- (2's complement)
      for item in start_list:
        if item > 0x80:
          item -= 0x100
          
      end_list = self.comm.roland_request(step_base_addr+0x60,16,timeout=0.1,debug=debug)
      
      substep_list = self.comm.roland_request(step_base_addr+0x70,16,timeout=0.1,debug=debug)
    else:
      print(f' (skipping empty step_idx={step_idx})')
      velocity_list = [0x50] * 16     # fill with default values of 0x50
      start_list = [0x00] * 16        # default 0x00
      end_list = [0x50] * 16     # default 0x50
      substep_list = [0x00] * 16      # default 0x00
    
    step_lanes = []
    for i in range(0,len(note_list)):
      component = {
        "note" : note_list[i],
        "velocity":velocity_list[i],
        "start":start_list[i],
        "end":end_list[i],
        "substep":substep_list[i],
        "processed": False
      }
      step_lanes.append(component)
    
    if sort_lanes == True:
      step_lanes.sort(key=lambda p: p["note"])
    
    return step_lanes
  
  
  def extract_notes(self,trk_idx,clip_idx,debug=True):
    note_event = {
      "note": 0,      #it's just a midi note
      "velocity": 0,  #MIDI velocity
      "start": 0,     #-50 to +99 in cents
      "length": 1,    #length in steps with resolution of cents
      "substep": 0    #1/2 1/3 .. flam
    }
    return None
  
  def disp_step(self,step):
    print("step lanes:")
    for lidx,lane in enumerate(step):
      print(f"lane={lidx}: n={lane['note']:02}, v={lane['velocity']:02}, st={lane['start']:02}, en={lane['end']:02}, sb={lane['substep']}")
      
      
  def format_note_event(self,note_event):
    return (f"step={note_event['step_idx']}, note={note_event['note']:02}, v={note_event['velocity']:02}, st={note_event['start']:02}, len={note_event['length']:02}, sub={note_event['substep']},  T={note_event['tie_possible']}")
      
  def create_note_event(self,note=0xFF,velocity=0x50,step_idx=0,start_offset=0,length=80,substep=0):
    note_event = {
      "note": note,
      "step_idx": step_idx,
      "velocity": velocity,
      "start": start_offset,
      "length": length,
      "substep": substep
    }
    return note_event
  
  # Decodes note sequences from MC-707 groovebox step data.
  def decode_note_sequences(self,sequence):
    note_events = []
    
    # Iterate through all steps
    for step_idx, step in enumerate(sequence):
      # Iterate through all components in the current step
      for comp_idx, component in enumerate(step):
        # Skip if already processed or empty (note == 0xFF)
        if component["processed"] or component["note"] == 255:
            continue
        
        # Found a new note start
        note_value = component["note"]
        velocity = component["velocity"]
        start_offset = component["start"]
        substep = component["substep"]
        
        # Mark this component as processed
        component["processed"] = True
        
        # Calculate note length
        if component["end"] < 100:
          # Note ends in the same step
          length = component["end"] - start_offset
        else:
          # Note extends to next step(s)
          length = 100 - start_offset  # Length in first step
          
          # Follow the note through subsequent steps
          current_step_idx = step_idx + 1
          note_continues = True
          
          while note_continues and current_step_idx < len(sequence):
            # Find the continuation component with matching note value
            found_continuation = False
            
            for next_comp_idx, next_component in enumerate(sequence[current_step_idx]):
              if (next_component["note"] == note_value and 
                not next_component["processed"]):
                # Found the continuation
                found_continuation = True
                next_component["processed"] = True
                
                if next_component["end"] < 100:
                  # Note ends in this step
                  length += next_component["end"]
                  note_continues = False
                else:
                  # Note continues to next step
                  length += 100
                  current_step_idx += 1
              
                break
        
            if not found_continuation:
              # Couldn't find continuation - treat as ending
              note_continues = False
      
        # Create note event
        note_event = {
            "note": note_value,
            "step_idx": step_idx,
            "velocity": velocity,
            "start": start_offset,
            "length": length,
            "substep": substep
        }
        
        note_events.append(note_event)

    return note_events
    
  # Converts a decoded note_event back into a list of component dictionaries.
  def note_to_components(self,note_event):
    # Validate input, a bit of overkilll but whatever
    if not isinstance(note_event, dict):
      raise ValueError("note_event must be a dictionary")
    
    required_keys = ["note", "step_idx", "velocity", "start", "length", "substep"]
    for key in required_keys:
      if key not in note_event:
        raise ValueError(f"Missing required key: {key}")
    
    note = note_event["note"]
    step_idx = note_event["step_idx"]
    velocity = note_event["velocity"]
    start = note_event["start"]
    length = note_event["length"]
    substep = note_event["substep"]
    
    # Validate ranges
    if not (0 <= note <= 127):
        raise ValueError(f"note must be in range [0..127], got {note}")
    
    if not (0 <= step_idx <= 127):
        raise ValueError(f"step_idx must be in range [0..127], got {step_idx}")
    
    if not (0 <= velocity <= 127):
        raise ValueError(f"velocity must be in range [0..127], got {velocity}")
    
    if not (-50 <= start <= 99):
        raise ValueError(f"start must be in range [-50..99], got {start}")
    
    if length < 1:
        raise ValueError(f"length must be >= 1, got {length}")
    
    if not (0 <= substep <= 4):
        raise ValueError(f"substep must be in range [0..4], got {substep}")
    
    # Build components list
    components = []
    remaining_length = length
    current_start = start
    
    while remaining_length > 0:
      # Calculate how much of the note fits in this step
      available_in_step = 100 - current_start
      
      if remaining_length <= available_in_step:
        # Note ends in this step
        end = current_start + remaining_length
        
        # truncate to avoid jumping to another step
        if end==100:
          end = 99
        
        component = {
          "note": note,
          "velocity": velocity,
          "start": current_start,
          "end": end,
          "substep": substep,
          "processed": False
        }
        components.append(component)
        remaining_length = 0
      else:
        # Note extends to next step
        component = {
          "note": note,
          "velocity": velocity,
          "start": current_start,
          "end": 100,
          "substep": substep,
          "processed": False
        }
        components.append(component)
        remaining_length -= available_in_step
        current_start = 0  # Next sequence start at 0
    
    return components

  
  def add_components(self,sequence,start_idx,components):
    '''
    Adds components to an existing sequence. Follows the same or similar rules as the MC-707 built-in editor
    You can use the note_to_components method to get the list of components
    Adds the components from the step_idx=start_idx to step_idx<(start_idx+len(components))
    This way you can put the components in any place in the sequence where they fit
    Returns the senquence after modification
    '''
    component_idx = 0
    for step_idx in range(start_idx,start_idx+len(components)):
      print(f'add_components: step_idx={step_idx}')
      for scan_cmp_idx,component in enumerate(sequence[step_idx]):
        print(f'scan cmp idx={scan_cmp_idx}')
        if component['note'] == 0xFF: # if the component is empty
          print(f'cmp free idx={scan_cmp_idx}, cmp idx={component_idx}')
          # sequence[step_idx][scan_cmp_idx] = deepcopy(components[component_idx])
          if sequence[step_idx][scan_cmp_idx]['note'] == components[component_idx]['note']:
            print(f'warning: the added note already in the same step, resulting structure is unusable!!!')
          sequence[step_idx][scan_cmp_idx] = components[component_idx]
          component_idx += 1
          break
        
    return sequence
  
  def add_notes_to_sequence(self,sequence,note_events,debug=False):
    '''
    converts each item from the list of note_events into a list of components
    then places the components in the sequence
    follows the same or similar rules as built-in editors in MC-101/707
    '''
    for note_event in note_events:
      components = self.note_to_components(note_event)
      sequence = self.add_components(sequence,note_event['step_idx'],components)
      print(f"note event step: {note_event['step_idx']}")
      self.console_print_sequence(sequence,16)
      if debug==True:
        k = input("add_notes_to_sequence: continue? n=break")
        if k == 'n': break
    return sequence
  
  def display_note_events(self,note_events):
    for i, event in enumerate(note_events):
      note_name = midi_note_to_name(event["note"])
      print(f"Note {i+1}: step={event['step_idx']}, "
            f"note={event['note']} ({note_name}), "
            f"velocity={event['velocity']}, "
            f"start={event['start']}, "
            f"length={event['length']}, "
            f"substep={event['substep']}")

  def disp_components(self, sequence, steps_nb=128, name="note", fileName="matrix.png", color_list=None):
    
    #use random colors or provided colors
    different_color_list = []
    if color_list is None or len(color_list) < 128:
      for i in range(256):
        different_color_list.append( (random.randrange(50,200),random.randrange(50,200),random.randrange(50,200)) )
    else:
      different_color_list = color_list
      
    disp_component_field = MatrixView(xLen=steps_nb,xSize=1600,ySize=400,fontSize=12,fileName=fileName)
    for step_idx in range(0,steps_nb):
      components_field_list = [ step.get(name) for step in sequence[step_idx] ]
      
      if name == "note":
        for i,note in enumerate(components_field_list):
          if note != 0xFF:
            disp_component_field.setCell(step_idx,i,f'{note:02}',cellColor=(different_color_list[note]))
      else:
        for i,end in enumerate(components_field_list):
          if end == 0x50 or end == 0x00:
            disp_component_field.setCell(step_idx,i,f'{end:02}',cellColor=(40,0,0))
          else:
            disp_component_field.setCell(step_idx,i,f'{end:02}',cellColor=(128,0,0))
    disp_component_field.draw()

  def display_all_1byte_motion(self,seq,trk_idx,clip_idx,steps_nb=128):
    motion_disp = MotionDisplay()
    motiondata = []
    motion_colors = []
    motion_colors = [(255,0,0),(0,255,0),(0,0,255),(255,0,255),(64,64,0),(0,255,255),(0,64,64),(0,128,128)]
    
    for i in range(8):
      motiondata_oneoffset = self.get_motion(trk_idx, clip_idx, i, steps_nb=steps_nb, debug=True)
      motion_disp.add_plot(motiondata_oneoffset,i,self.MOTION_LANE_NAMES[i],motion_colors[i])
      motiondata.append( motiondata_oneoffset )
    motion_disp.plot()

  def get_motion_step(self,trk_idx,clip_idx,param_idx,step_idx,debug=True):
    # motion = [-1]*SEQ_MAX_STEP_NB
    param_offset = param_idx * 0x10
    addr = self.tct.get_motion_step_base_address(trk_idx,clip_idx,step_idx,debug=debug) + param_offset
    chunk_raw = []
    try:
      chunk_raw = self.comm.roland_request(addr,16,timeout=0.1,debug=False)
    except:
      print(f"get_motion_step: cannot read motion chunk from the address {addr}, (clip_idx={clip_idx}, trk_idx={trk_idx}, step_idx={step_idx}")
      if debug==True:
        input("get_motion_step: confirm continue (enter)")
    motion = self.combine_to_bytes(chunk_raw,u2=True)
    print(f"{termcolor.FG_LTCYAN}get_motion_step idx=0x{step_idx:02X}{termcolor.FG_DEFAULT}, trk_idx={trk_idx}, clip_idx={clip_idx}, param_idx={param_idx}")
    if debug: print(f"motion chunk={self.intlist_to_hex_str(motion)}, chunk addr={addr:08X}")
    return motion

# Test the decoder and print results in a readable format
def test_decoder(seq,sequence):
  note_events = seq.decode_note_sequences(sequence)
  
  print(f"Decoded {len(note_events)} notes:")
  print("-" * 80)
  
  for i, event in enumerate(note_events):
      note_name = midi_note_to_name(event["note"])
      print(f"Note {i+1}: step={event['step_idx']}, "
            f"note={event['note']} ({note_name}), "
            f"velocity={event['velocity']}, "
            f"start={event['start']}, "
            f"length={event['length']}, "
            f"substep={event['substep']}")
  
  return note_events


# Convert MIDI note number to note name
def midi_note_to_name(note):
    notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    octave = (note // 12) - 1
    note_name = notes[note % 12]
    return f"{note_name}{octave}"



# this is an overengineered function to generate a deterministic list of visually distinct dark RGB colors.
# however it sounds, it works quite well
def generate_dark_color_lut(
    n: int = 128,
    min_val: int = 80,
    max_val: int = 170,
    saturation: float = 0.95,
    seed: float = 0.0
) -> List[Tuple[int, int, int]]:
    assert 0 <= min_val <= max_val <= 255
    assert 0.0 <= saturation <= 1.0

    phi = 0.618033988749895

    colors = []

    v = max_val / 255.0
    v_min = min_val / 255.0

    for i in range(n):
        h = (seed + i * phi) % 1.0

        # Optional micro-modulation of brightness for extra local contrast
        vv = v_min + (v - v_min) * (0.6 + 0.4 * ((i * 7) % 10) / 9.0)

        r, g, b = colorsys.hsv_to_rgb(h, saturation, vv)
        colors.append((
            int(r * 255),
            int(g * 255),
            int(b * 255),
        ))

    return colors




def video_experiment_disp_motion():
  # pick your preferred midi driver:
  midi = MidiIf(iface='mido')   # faster but in my case less reliable (probably a bug in this library)
  # midi = MidiIf(iface='alsa')     # slower but works (almost) each time, however parses the midi messages poorly
  
  comm = SysExComm(midi)
  tct = TrackAndClipTools(comm)
  seq = SeqTools(comm,tct)
  
  trk_idx = 1
  clip_idx = 2
  steps_nb = 16
  
  seq.display_all_1byte_motion(seq,trk_idx,clip_idx,steps_nb=steps_nb)
  exit()


def video_experiment_piano_roll():
  midi = MidiIf(iface='mido')
  #midi = MidiIf(iface='alsa')
  comm = SysExComm(midi)
  tct = TrackAndClipTools(comm)
  seq = SeqTools(comm,tct)
  
  trk_idxs = [0,1,2,3]  #define which tracks to display (by inices from 0)
  clip_idxs = [0,0,0,0] #which clip in each track (by indices form 0)
  piano_roll = SimplePianoRoll()
  
  for i in range(4):
    piano_roll = seq.add_seq_to_roll(piano_roll,trk_idxs[i],clip_idxs[i],loop=False,debug=True)
  
  piano_roll.show()
  
  
def video_experiment_disp_and_mod_simple_pattern():
  # pick your preferred midi driver:
  # midi = MidiIf(iface='mido')   # faster but in my case less reliable (probably a bug in this library)
  midi = MidiIf(iface='alsa')     # slower but works (almost) each time
  
  comm = SysExComm(midi)
  tct = TrackAndClipTools(comm)
  seq = SeqTools(comm,tct)
  conv = StepSequencerMIDIConverter()
  
  #generate random colors to be assigned to different note pitches, adjust ranges to your taste
  #different_color_list = [ (random.randrange(50,200),random.randrange(20,60),random.randrange(50,200)) for i in range(128)]
  #changed to a more deterministic solution
  different_color_list = generate_dark_color_lut()
  
  output_dir_name = "outputs"
  
  # ======================================================
  # Step 1: read T2 C1 (indices from 0) into base_sequence
  # ======================================================
  base_trk_idx = 1 # means Track 2
  base_clip_idx = 0 # means Clip 1
  steps_nb = 16
  base_sequence = seq.get_steps(base_trk_idx,base_clip_idx,start_step_idx=0,step_len=steps_nb)
  
  print("The base sequence is now in the computer's memory")
  
  # ======================================================
  # Step 2: Visualize component fields of T2 C1: notes and start/end timings
  # ======================================================
  
  input(f"Press enter to generate matrices of note and time params. The subdirectory '{output_dir_name}' must be created inside the script dir.")
  
  try:
    # def disp_components(self, sequence, steps_nb=128, name="note", fileName="matrix.png"):
    seq.disp_components(base_sequence,steps_nb=16,name="note",\
      fileName=f"{output_dir_name}/base_t{base_trk_idx+1}_c{base_clip_idx+1}_notes.png", color_list=different_color_list)
    seq.disp_components(base_sequence,steps_nb=16,name="start",\
      fileName=f"{output_dir_name}/base_t{base_trk_idx+1}_c{base_clip_idx+1}_start_times.png", color_list=different_color_list)
    seq.disp_components(base_sequence,steps_nb=16,name="end",\
      fileName=f"{output_dir_name}/base_t{base_trk_idx+1}_c{base_clip_idx+1}_end_times.png", color_list=different_color_list)
  
    print(f"Initial sequence component visualizers are generated, check the {output_dir_name} dir.")
  except Exception as e:
    print(f"exception: '{e}'")
    exit()
  
  
  # ======================================================
  # Step 3: Convert from the sequence/components into note_events (more human-readable)
  # ======================================================
  
  input("Now press enter to decode them into note events")
  
  base_note_events = seq.decode_note_sequences(base_sequence)
  
  print(f"note_events decoded are shown below, the number of decoded notes is {len(base_note_events)}")
  seq.display_note_events(base_note_events)
  
  # ======================================================
  # Step 4: Clone the note events (preserve the original to be able to compare)
  # ======================================================
  
  input("Press enter to clone and modify the base_note_events object")
  
  modified_note_events = deepcopy(base_note_events)
  print("modified_note_events is now created as a copy of the base_note_events")
  
  # ======================================================
  # Step 5: Modify the modified_note_events object by creating a note and adding it
  # ======================================================
  
  # generate a new note event
  new_note_event = seq.create_note_event(step_idx=1,note=72,velocity=123,length=780)
  
  print(f"\nThe new note event is generated:")
  print(f"{json.dumps(new_note_event,indent=2)}")
  
  # append the new note event to the new sequence
  modified_note_events.append(new_note_event)
  
  print("the modified_note_events object is now actually modified:")
  seq.display_note_events(modified_note_events)
  
  # ======================================================
  # Step 6: Create the modified_sequence object and fill it with the notes
  # ======================================================
  
  input("Press enter to add the event and to gnerate a new modified_sequence")
  
  # generate an empty sequence
  modified_sequence = seq.generate_empty_sequence()
  
  # fill the sequence with the modified note events
  modified_sequence = seq.add_notes_to_sequence(modified_sequence,modified_note_events)
  
  print(f"The modified_sequence with the added notes is now generated. Creating its visualizer...")
  
  seq.disp_components(modified_sequence,steps_nb=steps_nb,name="note",
    fileName=f"{output_dir_name}/modified_seq_notes.png", color_list=different_color_list)
  
  print(f"Modified seq. visualizer done. Check the '{output_dir_name}' directory")
  
  # ======================================================
  # Step 7: Experimental - generate midi files for the base/modified sequences (experimental only!)
  # ======================================================
  
  input("Press enter to generate MIDI files from the old and the new note event lists")
  conv.events_to_midi(base_note_events,f"{output_dir_name}/base_sequence.mid")
  conv.events_to_midi(modified_note_events,f"{output_dir_name}/modified_sequence.mid")
  print("midi files created (probably :P )")
  
  # ======================================================
  # Step 8: Optional - write the modified sequence back to the groovebox
  # ======================================================
  
  #point to a new clip, be sure choose a totally empty/cleared clip:
  modified_trk_idx = 1
  modified_clip_idx = 1
  
  key = input(f"If you want, you can write the sequence to:\n\
Track{modified_trk_idx+1} (tidx={modified_trk_idx}), Clip{modified_clip_idx+1} (cidx={modified_clip_idx}).\n\
Type y to start writing: ")
  
  if key == 'y':
    print(f"writing the new sequence...")
    seq.write_steps(modified_trk_idx,modified_clip_idx,modified_sequence,start_step=0,steps_to_write=steps_nb)
  else:
    print(f"skipping the write")
    # exit()
  
  # ======================================================
  # Step 9: Generate the final visualizers
  # ======================================================
  
  input("Finally, press enter to display piano rolls for both sequences.")
  
  roll_base = SimplePianoRoll()
  roll_base = seq.add_seq_to_roll(roll_base,base_trk_idx,base_clip_idx,loop=False,debug=True)
  roll_base.show()
  
  roll_modified = SimplePianoRoll()
  roll_modified = seq.add_seq_to_roll(roll_modified,modified_trk_idx,modified_clip_idx,loop=False,debug=True)
  roll_modified.show()
  
  print("bye!")
  exit()



def video_experiment_disp_complex_pattern():
  # pick your preferred midi driver:
  # midi = MidiIf(iface='mido')   # faster but in my case less reliable (probably a bug in this library)
  midi = MidiIf(iface='alsa')     # slower but works (almost) every time
  
  comm = SysExComm(midi)
  tct = TrackAndClipTools(comm)
  seq = SeqTools(comm,tct)
  
  #generate random colors to be assigned to different note pitches, adjust ranges to your taste
  #different_color_list = [ (random.randrange(50,200),random.randrange(20,60),random.randrange(50,200)) for i in range(128)]
  #changed to a more deterministic solution
  different_color_list = generate_dark_color_lut()
  
  trk_idx = 2
  clip_idx = 2
  steps_nb = 64
  sequence = seq.get_steps(trk_idx,clip_idx,start_step_idx=0,step_len=steps_nb)
  
  roll = SimplePianoRoll()
  roll = seq.add_seq_to_roll(roll,trk_idx,clip_idx,loop=False,debug=True)
  roll.show()
  
  input("sequence is now in memory, press enter to generate the note visualizer")
  seq.disp_components(sequence,steps_nb=64,name="note",fileName=f"outputs/ti{trk_idx}ci{clip_idx}_notes.png", color_list=different_color_list)



if __name__ == "__main__":
  print(f"running seq_tools as main module")
  
  # Below, you can find the functions that I used to create the youtube video about the sequuencer,
  # and to test the ideas.
  # If you decide to run the tests below on your own as they are included here,
  # then remember to check on which tracks/clips these functions operate
  # and program something adequate to those tracks/clips first.
  # For example the uncommented disp_motion requires the motion
  # to be programmed in track 2, clip 3, and reads the first 16 steps only from that clip.
  # Or just use those functions as an inspiration to create your own code

  # video_experiment_piano_roll()
  # video_experiment_disp_and_mod_simple_pattern()
  # video_experiment_disp_complex_pattern()
  video_experiment_disp_motion()
  
  exit()

