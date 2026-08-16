import termcolor
from midi_if import MidiIf
from sys_ex_comm import SysExComm





class TrackAndClipTools:
  def __init__(self,comm):
    self.comm = comm
    self._step_scale = ["1/8","1/16","1/32","1/4T","1/8T","1/16T"]
    self.clip_idxs = [] #clip idxes for all tracks
    for trk_idx in range(8):
      self.clip_idxs.append( self.generate_clip_base_addresses(trk_idx) )
  
  
  
  scale_1_8 = 0
  scale_1_16 = 1
  scale_1_32 = 2
  scale_1_4T = 3
  scale_1_8T = 4
  scale_1_16T = 5
  SEQ_BASE_ADDRESS = 0x20000000
  SEQ_SOUND_PARAMS_OFFS = 0x10000
  SEQ_PARAMS_OFFS  = 0x20000
  SEQ_NOTE_OFFS    = 0x30000
  SEQ_MOTION_OFFS  = 0x40000
  SEQ_PITCHBEND_OFFS = 0x50000
  STEP_SIZE        = 0x100
  SEQ_TRK_OFFSET   = 0x01080000  #this many bytes between tracks
  SEQ_CLIP_OFFSET  = 0x00080000  #this many bytes between clips
  trk_col_addr = [0x10000819, 0x10000A19, 0x10000C19, 0x10000E19,
    0x10001019, 0x10001219, 0x10001419, 0x10001619]
  SETUP_BASE_ADDR = 0x10000000
  
  TRK_BASE_ADDR = [0x21000000,0x22080000,0x23100000,0x24180000,
    0x25200000,0x26280000,0x27300000,0x28380000]
  TRK_SETTINGS_BASE_ADDR = [0x10000800, 0x10000A00, 0x10000C00, 0x10000E00,
    0x10001000, 0x10001200, 0x10001400, 0x10001600]
  SND_SRC_CFG_OFFS = 0x04 #if byte @ this offset is set to 0 -> src is track, 1 -> src is clip
  TRK_COLOR_OFFS = 0x19
  
  TRACK_COLOR_PALETTE = [
      (255, 0, 0),        # red
      (255, 140, 0),      # orange
      (255, 215, 0),      # yellow
      (34, 139, 34),      # green
      (30, 144, 255),     # blue
      (148, 0, 211),      # purple
      (255, 105, 180),    # pink
      (192, 192, 192),    # light gray
      (135, 206, 250),    # skyblue
      (255, 255, 153),    # pale yellow
      (173, 216, 230),    # pale blue
      (255, 182, 193),    # pale pink
      (255, 99, 71),      # light red
      (255, 200, 124),    # light orange
      (255, 239, 170),    # light yellow
      (144, 238, 144),    # light green
      (0, 153, 0),        # p. green
      (176, 226, 255),    # light skyblue
      (100, 149, 237),    # light blue
      (216, 191, 216),    # light purple
  ]
  
  TRACK_COLOR_NAMES = [
      "red",
      "orange",
      "yellow",
      "green",
      "blue",
      "purple",
      "pink",
      "light gray",
      "skyblue",
      "pale yellow",
      "pale blue",
      "pale pink",
      "light red",
      "light orange",
      "light yellow",
      "light green",
      "p. green",
      "light skyblue",
      "light blue",
      "light purple",
  ]
  
  #just gets the readable string with the step scale name, like 1/8 for 8th notes
  @property
  def step_scale(self):
    return self._step_scale
  
  #the valid base addresses start every 0x80000
  #except that there are "holes" in the address space
  # for the invalid midi data in which bytes have their MSB set
  def __generate_next_valid_base_address(self,previous_addr,offset=0x80000):
    next_addr = previous_addr + offset
    #correct if necessary
    while( next_addr & 0x80808080 ):
      next_addr = next_addr + offset
    return next_addr
  
  def generate_clip_base_addresses(self,trk_idx):
    CLIP1_BASE_ADDR = [0x20000000, 0x21080000, 0x22100000, 0x23180000, 0x24200000, 0x25280000, 0x26300000, 0x27380000]
    res = []
    current = CLIP1_BASE_ADDR[trk_idx]
    res.append(current)
    for clip_idx in range(15):
      current = self.__generate_next_valid_base_address(current)
      res.append(current)
    return res
    
  def get_trk_snd_source(self,trk_idx):
    addr = self.TRK_SETTINGS_BASE_ADDR[trk_idx] + self.SND_SRC_CFG_OFFS
    rxbuf = self.comm.roland_request(addr,1,debug=False)
    snd_src = rxbuf[0]
    if snd_src == 0:
      snd_src_name = "TRACK"
    elif snd_src == 1:
      snd_src_name = "CLIP"
    else:
      snd_src_name = "not recognized"
    print(f"get_trk_snd_source, trk_idx={trk_idx}, sound src code: {snd_src} which is {snd_src_name}")
    return snd_src_name
  
  def get_track_colors(self,debug=False):
    color_list = []
    color_names = []
    for i in range(8):
      color_idx = 0
      try:
        if self.comm.model_name != 'MV-1':
          addr = self.TRK_SETTINGS_BASE_ADDR[i] + self.TRK_COLOR_OFFS
          rxbuf = self.comm.roland_request(addr,1,debug=debug)
          color_idx = rxbuf[0]
        else:
          color_idx = i
      except:
        print(f'get_track_colors: communication error')
      try:
        color_list.append(self.TRACK_COLOR_PALETTE[color_idx])
        color_names.append(self.TRACK_COLOR_NAMES[color_idx])
      except:
        if debug==True:
          print(f"color value for trk_idx={i} out of range ({rxbuf}), using default")
        color_names.append("error")
        color_list.append(self.TRACK_COLOR_PALETTE[0])
    if debug==True:
      print(f"trk colors: {color_list}")
      print(f"trk color names: {color_names}")
    return color_list
  
  def get_clip_step_scale_by_idx(self,idx):
    step_scale = None
    try:
      step_scale = self.step_scale[idx]
    except:
      step_scale = "None"
    return step_scale
  
  def get_trk_base_addr(self,trk_idx,debug=False):
    if trk_idx > 7: trk_idx = 7
    return self.TRK_BASE_ADDR[trk_idx]
  
  def get_trk_color_idx(self,trk_idx,timeout=0.5,debug=False):
    buf = self.comm.roland_request(self.trk_col_addr[trk_idx],1,debug=debug)
    color_idx = buf[0]
    if debug: print(f"get_trk_color_idx res: {color_idx}")
    return color_idx
  
  
  def get_clip_base_address(self,trk_idx, clip_idx, debug=False):
    if trk_idx > 7: trk_idx = 7
    if clip_idx > 15: clip_idx = 15
    res = self.clip_idxs[trk_idx][clip_idx]
    if debug:
      print(f"get_clip_base_address ti{trk_idx} ci{clip_idx} res={termcolor.FG_DEFAULT}0x{res:02X}{termcolor.FG_DEFAULT}")
    return res
  
  def get_motion_step_base_address(self,trk_idx, clip_idx, step_idx, debug=False):
    addr = self.get_clip_base_address(trk_idx, clip_idx) + self.SEQ_MOTION_OFFS
    addr = addr + step_idx * self.STEP_SIZE
    if debug:
      print(f"get_motion_step_base_address ti{trk_idx} ci{clip_idx} addr={termcolor.FG_DEFAULT}0x{addr:02X}{termcolor.FG_DEFAULT}")
    return addr
  
  def get_seq_step_base_address(self,trk_idx, clip_idx, step_idx, debug=False):
    addr = self.get_clip_base_address(trk_idx, clip_idx,debug) + self.SEQ_NOTE_OFFS
    addr = addr + step_idx * self.STEP_SIZE
    if debug:
      print(f"get_seq_step_base_address ti{trk_idx} ci{clip_idx} addr=0x{addr:02X}")
    return addr
  
  def get_step_params(self,trk_idx, clip_idx,debug=False):
    addr = self.get_clip_base_address(trk_idx,clip_idx,debug)+self.SEQ_PARAMS_OFFS
    rxbuf = []
    rxbuf.append(1)
    rxbuf.append(8)
    rxbuf.append(0)
    try:
      rxbuf = self.comm.roland_request(addr,4,debug=debug)
      step_scale_idx = rxbuf[0]
      step_len = rxbuf[1]<<4 | rxbuf[2]
    except:
      print(f"get_clip_params: Could not read clip params from addr={addr:08X}, using default")
      rxbuf[0] = 1
      rxbuf[1] = 8
      rxbuf[2] = 0
      step_scale_idx = rxbuf[0]
      step_len = rxbuf[1]<<4 | rxbuf[2]
    step_scale = self.step_scale[step_scale_idx]
    if debug:
      print(f"get_clip_params Ti{trk_idx}, Ci{clip_idx:02d} , rxbuf: {rxbuf}, extr scale: {step_scale}, step len: {step_len}")
    return step_scale_idx, step_len
  
  def get_trk_clip_name(self,trk_idx, clip_idx=None):
    print("get_trk_clip_name")
    name = ""
    addr = 0
    if clip_idx == None:
      addr = self.get_trk_base_addr(trk_idx,debug=False)
    else:
      addr = self.get_clip_base_address(trk_idx,clip_idx,debug=False)
    
    rxbuf = self.comm.roland_request(addr,16,debug=False)
    print(f'get_trk_clip_name, rxbuf={self.comm.intlist_to_hex_str(rxbuf)}')
    name = ''.join(chr(x) for x in rxbuf)
    name = name.strip()
    if len(name) == 0:
        name = 'Untitled'
    return name
  
  def get_trk_clip_sound_params(self,trk_idx, clip_idx=None):
    params = []
    addr = 0
    if clip_idx == None:
      addr = self.get_trk_base_addr(trk_idx,debug=False)
    else:
      addr = self.get_clip_base_address(trk_idx,clip_idx,debug=False)
    
    addr = addr + self.SEQ_SOUND_PARAMS_OFFS
    
    l = self.comm.roland_request(addr,22,debug=False)
    h = self.comm.roland_request(addr+0x0408,9,debug=False)
    
    params = [
    {'Level':l[0]},
    {'Pan':l[1]},
    {'Crse':l[2]},
    {'Fine':l[3]},
    {'0x04':l[4]},
    {'0x05':l[5]},
    {'0x06':l[6]},
    {'Porta':l[7]},
    {'PortaTm': ( ((int)(l[8])<<8) | l[9]) },
    {'Cutoff':l[10]},
    {'Reso':l[11]},
    {'Attack':l[12]},
    {'Decay':l[13]},
    {'Release':l[14]},
    {'VibRate':l[15]},
    {'VibDpth':l[16]},
    {'VibDly':l[17]},
    {'OctSh':l[18]-64},
    {'0x13':l[19]},
    {'DlySnd':l[20]},
    {'RevSnd':l[21]},
    {'SysCtl1':h[0]},
    {'SysCtl2':h[1]},
    {'SysCtl3':h[2]},
    {'SysCtl4':h[3]},
    ]
    
    return params
  
  def get_trk_type(self, trk_idx, debug=False):
    addr = self.get_trk_base_addr(trk_idx) + 0x14
    rxbuf = self.comm.roland_request(addr,1,debug=debug)
    track_type_byte = rxbuf[0]
    track_type_str = ""
    if track_type_byte == 0x7F:
      track_type_str = "OFF"
    elif track_type_byte == 0:
      track_type_str = "TONE"
    elif track_type_byte == 1:
      track_type_str = "DRUM"
    else:
      track_type_str = "Other"
    return track_type_str

def disp_clip_addresses():  
  for trk_idx in range(8):
    for clip_idx in range(16):
      print(f"0x{tct.get_clip_base_address(trk_idx,clip_idx):08X}",end=" ")
    print("\n")


if __name__ == "__main__":
  print(f"running trk_clip_tools as the main module")
  
  midi = MidiIf(iface='alsa')
  comm = SysExComm(midi)
  tct = TrackAndClipTools(comm)
  
  trk_snd_srcs = []
  trk_types = []
  for trk_idx in range(8):
    try:
      trk_snd_srcs.append( tct.get_trk_snd_source(trk_idx) )
      trk_types.append( tct.get_trk_type(trk_idx) )
    except:
      print("whatever, sth went wrong")
  
  try:
    trk_colors = tct.get_track_colors(debug=True)
    print(f"trk colors: {trk_colors}")
  except:
    print("couldn't read track colors. Are we dealing with MV-1?")
    pass

  print(f"trk srcs: {trk_snd_srcs}")
  print(f"trk types: {trk_types}")
  
