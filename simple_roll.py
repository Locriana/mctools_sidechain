from PIL import Image, ImageDraw
import matplotlib.pyplot as plt

class LedPanel:
    def __init__(self, width, height, pixel_size=3, background=(0,0,0)):
        self.width = width
        self.height = height
        self.pixel_size = pixel_size
        
        # internal LED framebuffer
        self.buffer = [
            [background for _ in range(width)]
            for _ in range(height)
        ]
        
        print(f'C3={self.__get_note_name(48)}, F#5={self.__get_note_name(78)}')
    
    def set_pixel(self, x, y, color):
        """Set a single LED color."""
        if 0 <= x < self.width and 0 <= y < self.height:
            self.buffer[y][x] = color
        else:
            raise ValueError("pixel out of range")
    
    def render(self):
        """Return a PIL Image of the panel."""
        img_w = self.width * self.pixel_size
        img_h = self.height * self.pixel_size
        
        img = Image.new("RGB", (img_w, img_h))
        draw = ImageDraw.Draw(img)
        
        for y in range(self.height):
            for x in range(self.width):
                color = self.buffer[y][x]
                px = x * self.pixel_size
                py = y * self.pixel_size
                draw.rectangle(
                    [px, py, px + self.pixel_size - 1, py + self.pixel_size - 1],
                    fill=color
                )
        line_shape = [(img_w / 2, 0), (img_w / 2, img_h - 1)]
        draw.line(line_shape,fill="gray",width=1)
        return img
    
    def save(self, path):
        self.render().save(path)
    
    '''def show(self):
        img = self.render()
        plt.imshow(img)
        plt.show()'''
        
    def __get_note_name(self,note_number):
      semitones_in_octave = 12
      octave = note_number / semitones_in_octave - 1
      note = note_number % semitones_in_octave
      note_list = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
      return f'{note_list[note]}{int(octave)}'
    
    def show(self):
        img = self.render()

        extent = [0, self.width, self.height, 0]

        plt.figure(figsize=(16, 8))
        plt.imshow(img, extent=extent)

        plt.gca().invert_yaxis()   # <- zero at the bottom
        plt.gca().tick_params(axis='x', labelrotation=90)

        plt.xticks(range(0,self.width + 1,1))
        
        y_labels = [ f"Note={note}={self.__get_note_name(note)}" for note in range(0,self.height + 1,1) ]
        # plt.yticks(y_desc)
        
        # plt.yticks(range(0,128,1),y_labels)
        plt.yticks(range(0,self.height + 1,1),y_labels)

        plt.grid(color='gray', linewidth=0.3)
        plt.show()

class SimplePianoRoll:
  def __init__(self, width=256, height=128, pixel_size=3, background=(0,0,0)):
    self.p = LedPanel(width, height, pixel_size=3)
    # the colors are interpretations of track color names in MCs
    self.roll_color_palette = [
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
        (0, 153, 0),        # pale green
        (176, 226, 255),    # light skyblue
        (100, 149, 237),    # light blue
        (216, 191, 216),    # light purple
    ]
    self.ch_colors = [ self.roll_color_palette[_] for _ in range(16) ]
    
  def set_ch_color(self,ch_idx,col_idx):
    if col_idx >= len(self.roll_color_palette): col_idx = 0
    self.ch_colors[ch_idx] = self.roll_color_palette[col_idx]
  
  def add_note(self,ch_idx,note,step,step_len=1,velocity=100,scale_1_8=0):
    for x in range(step,step+step_len):
      if scale_1_8==0: # clip time scale is 1/16
        self.p.set_pixel(x,note,self.ch_colors[ch_idx])
        self.p.set_pixel(x+128,note,self.ch_colors[ch_idx])
      else: # clip time scale is 1/8
        self.p.set_pixel(x*2,note,self.ch_colors[ch_idx])
        self.p.set_pixel(x*2+1,note,self.ch_colors[ch_idx])
      
    return
  
  def show(self):
    self.p.show()
  

if __name__ == "__main__":
    roll = SimplePianoRoll(256,128,3)
    # p = LedPanel(256, 128, pixel_size=3)

    # draw a diagonal line
    for i in range(0,20):
        roll.add_note(0,i+20,10+i*5,step_len=4,scale_1_8=1)
    for i in range(0,32):
        roll.add_note(1,i+48,25+i*3,step_len=3)

    # p.save("panel.png")
    roll.show()
    
    print('moving on, exit')

