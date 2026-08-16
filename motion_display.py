import matplotlib.pyplot as plt
import numpy as np


# A class for displaying up to 8 motion plots using Matplotlib.
# Each plot can have different colors and labels. The display area shows
# values from 0-128 on both axes with configurable grid spacing.
class MotionDisplay:
    def __init__(self):
        # Initialize the MotionDisplay with empty plot storage.
        self.plots = {}  # Dictionary to store plot data indexed by plot_idx
        
    def add_plot(self, motion_steps, plot_idx, name, color):
        '''
        Add or update a plot with motion data.
        
        Parameters:
        -----------
        motion_steps : list
            List of 1024 samples (integers 0-127 or -1 for empty)
        plot_idx : int
            Index of the plot (0-7) for identification and updates
        name : str
            Short name for the plot legend
        color : tuple
            RGB color tuple with values 0-255, e.g., (255, 0, 0) for red
        '''
        if not (0 <= plot_idx <= 7):
            raise ValueError("plot_idx must be between 0 and 7")
        
        input_len = len(motion_steps)
        if input_len < 1024:
          print(f"input len={input_len}, adding empty steps to fill up to 1024")
          while( len(motion_steps) < 1024 ):
            motion_steps.append(-1)
            
            # raise ValueError("motion_steps must contain exactly 1024 samples")
        
        # Normalize color from 0-255 to 0-1 for matplotlib
        normalized_color = tuple(c / 255.0 for c in color)
        
        # Process motion_steps to handle -1 values (forward fill)
        processed_steps = self._forward_fill(motion_steps)
        
        # Store the plot data
        self.plots[plot_idx] = {
            'data': processed_steps,
            'name': name,
            'color': normalized_color
        }
    
    def _forward_fill(self, motion_steps):
        '''
        Replace -1 values with the last valid value (forward fill).
        
        Parameters:
        -----------
        motion_steps : list
            List of samples with possible -1 values
            
        Returns:
        --------
        list : Processed samples with -1 values filled
        '''
        processed = motion_steps.copy()
        last_valid = 0  # Default to 0 if we start with -1
        
        for i in range(len(processed)):
            if processed[i] == -1:
                processed[i] = last_valid
            else:
                last_valid = processed[i]
        
        return processed
    
    def plot(self):
        """
        Generate and display all plots that have been added.
        
        Creates a matplotlib figure with proper grid, labels, and legend.
        """
        if not self.plots:
            print("No plots to display. Use add_plot() to add data first.")
            return
        
        # Create figure and axis
        fig, ax = plt.subplots(figsize=(12, 8))
        
        # Create x-axis values: 1024 samples spanning 0 to 128
        # Each integer (0-128) contains 8 samples
        x_values = np.linspace(0, 128, 1024)
        
        # Plot each stored plot
        for plot_idx in sorted(self.plots.keys()):
            plot_data = self.plots[plot_idx]
            ax.plot(x_values, 
                   plot_data['data'], 
                   color=plot_data['color'],
                   label=plot_data['name'],
                   linewidth=3.0)
        
        # Set axis limits
        ax.set_xlim(0, 128)
        ax.set_ylim(0, 127)
        
        # Set y-axis ticks every 4 values
        y_ticks = np.arange(0, 128, 4)
        ax.set_yticks(y_ticks)
        
        # Set x-axis ticks at integers 0 to 128
        x_ticks = np.arange(0, 129, 1)
        ax.set_xticks(x_ticks)
        
        # Configure grid
        # Major grid (darker gray) at integer positions on x-axis
        ax.grid(True, which='major', axis='x', color='#666666', 
                linestyle='-', linewidth=0.8, alpha=0.7)
        ax.grid(True, which='major', axis='y', color='#CCCCCC', 
                linestyle='-', linewidth=0.5, alpha=0.5)
        
        # Minor grid (lighter gray) for the 1/8 divisions on x-axis
        # 7 minor ticks between each major tick (creating 8 slots)
        ax.set_xticks(np.arange(0, 128 + 1/8, 1/8), minor=True)
        ax.grid(True, which='minor', axis='x', color='#CCCCCC', 
                linestyle='-', linewidth=0.3, alpha=0.3)
        
        # Rotate x-axis labels by 90 degrees
        plt.setp(ax.get_xticklabels(), rotation=90)
        
        # Labels
        ax.set_xlabel('Step', fontsize=12)
        ax.set_ylabel('Value', fontsize=12)
        ax.set_title('Motion Display', fontsize=14, fontweight='bold')
        
        # Add legend
        ax.legend(loc='best', fontsize=10)
        
        # Adjust layout to prevent label cutoff
        plt.tight_layout()
        
        # Display the plot
        plt.show()


# A synthetic example
if __name__ == "__main__":
    # Create some example data
    motion_samples_ch1 = [i % 128 for i in range(1024)]
    motion_samples_ch2 = [127 - (i % 128) for i in range(1024)]
    
    # Add some -1 values to test forward fill
    for i in range(100, 150):
        motion_samples_ch1[i] = -1
    
    color_ch1 = (255, 0, 0)  # Red
    color_ch2 = (0, 255, 255)  # Cyan
    
    # Create display and add plots
    motion_disp = MotionDisplay()
    motion_disp.add_plot(motion_samples_ch1, 0, "Channel one", color_ch1)
    motion_disp.add_plot(motion_samples_ch2, 1, "Channel two", color_ch2)
    motion_disp.plot()
    
