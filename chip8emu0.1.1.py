import tkinter as tk
from tkinter import filedialog
import random

# Standard CHIP-8 Fontset
FONTSET = [
    0xF0, 0x90, 0x90, 0x90, 0xF0, # 0
    0x20, 0x60, 0x20, 0x20, 0x70, # 1
    0xF0, 0x10, 0xF0, 0x80, 0xF0, # 2
    0xF0, 0x10, 0xF0, 0x10, 0xF0, # 3
    0x90, 0x90, 0xF0, 0x10, 0x10, # 4
    0xF0, 0x80, 0xF0, 0x10, 0xF0, # 5
    0xF0, 0x80, 0xF0, 0x90, 0xF0, # 6
    0xF0, 0x10, 0x20, 0x40, 0x40, # 7
    0xF0, 0x90, 0xF0, 0x90, 0xF0, # 8
    0xF0, 0x90, 0xF0, 0x10, 0xF0, # 9
    0xF0, 0x90, 0xF0, 0x90, 0x90, # A
    0xE0, 0x90, 0xE0, 0x90, 0xE0, # B
    0xF0, 0x80, 0x80, 0x80, 0xF0, # C
    0xE0, 0x90, 0x90, 0x90, 0xE0, # D
    0xF0, 0x80, 0xF0, 0x80, 0xF0, # E
    0xF0, 0x80, 0xF0, 0x80, 0x80  # F
]

# JP $200 — infinite loop at ROM base; no pixels drawn (blank screen, safe PC).
IDLE_ROM = bytes([0x12, 0x00])

class Chip8CPU:
    def __init__(self):
        self.reset()
        
    def reset(self):
        self.memory = bytearray(4096)
        self.v = bytearray(16)        # Registers V0-VF
        self.i = 0                    # Index register
        self.pc = 0x200               # Program counter starts at 0x200
        self.stack = []               # Stack
        self.delay_timer = 0
        self.sound_timer = 0
        self.display = bytearray(64 * 32)
        self.keys = [False] * 16      # Keypad state
        self.draw_flag = False
        self.waiting_for_key = False
        self.key_register = 0
        
        # Load fontset into memory (0x050 - 0x0A0)
        for i in range(len(FONTSET)):
            self.memory[0x50 + i] = FONTSET[i]

    def load_rom(self, rom_data):
        self.reset()
        for i, byte in enumerate(rom_data):
            if 0x200 + i < 4096:
                self.memory[0x200 + i] = byte

    def emulate_cycle(self):
        # Opcode is two bytes; keep PC in range so empty RAM cannot walk past 0xFFF.
        if self.pc >= 4095:
            self.pc = 0x200
        # Fetch Opcode
        opcode = (self.memory[self.pc] << 8) | self.memory[self.pc + 1]
        
        # Decode components
        x = (opcode & 0x0F00) >> 8
        y = (opcode & 0x00F0) >> 4
        n = opcode & 0x000F
        nn = opcode & 0x00FF
        nnn = opcode & 0x0FFF
        
        self.pc += 2

        # Execute Opcode
        op_category = opcode & 0xF000
        
        if op_category == 0x0000:
            if opcode == 0x00E0:    # 00E0 - Clear screen
                self.display = bytearray(64 * 32)
                self.draw_flag = True
            elif opcode == 0x00EE:  # 00EE - Return from subroutine
                self.pc = self.stack.pop()
        
        elif op_category == 0x1000: # 1NNN - Jump to NNN
            self.pc = nnn
            
        elif op_category == 0x2000: # 2NNN - Call subroutine at NNN
            self.stack.append(self.pc)
            self.pc = nnn
            
        elif op_category == 0x3000: # 3XNN - Skip next instruction if VX == NN
            if self.v[x] == nn:
                self.pc += 2
                
        elif op_category == 0x4000: # 4XNN - Skip next instruction if VX != NN
            if self.v[x] != nn:
                self.pc += 2
                
        elif op_category == 0x5000: # 5XY0 - Skip next instruction if VX == VY
            if self.v[x] == self.v[y]:
                self.pc += 2
                
        elif op_category == 0x6000: # 6XNN - VX = NN
            self.v[x] = nn
            
        elif op_category == 0x7000: # 7XNN - VX += NN
            self.v[x] = (self.v[x] + nn) & 0xFF
            
        elif op_category == 0x8000: # 8XY_ - Arithmetic / Logical operations
            if n == 0x0:
                self.v[x] = self.v[y]
            elif n == 0x1:
                self.v[x] |= self.v[y]
            elif n == 0x2:
                self.v[x] &= self.v[y]
            elif n == 0x3:
                self.v[x] ^= self.v[y]
            elif n == 0x4:
                total = self.v[x] + self.v[y]
                self.v[0xF] = 1 if total > 0xFF else 0
                self.v[x] = total & 0xFF
            elif n == 0x5:
                self.v[0xF] = 1 if self.v[x] >= self.v[y] else 0
                self.v[x] = (self.v[x] - self.v[y]) & 0xFF
            elif n == 0x6:
                self.v[0xF] = self.v[x] & 0x1
                self.v[x] = (self.v[x] >> 1)
            elif n == 0x7:
                self.v[0xF] = 1 if self.v[y] >= self.v[x] else 0
                self.v[x] = (self.v[y] - self.v[x]) & 0xFF
            elif n == 0xE:
                self.v[0xF] = (self.v[x] & 0x80) >> 7
                self.v[x] = (self.v[x] << 1) & 0xFF
                
        elif op_category == 0x9000: # 9XY0 - Skip next instruction if VX != VY
            if self.v[x] != self.v[y]:
                self.pc += 2
                
        elif op_category == 0xA000: # ANNN - Set I = NNN
            self.i = nnn
            
        elif op_category == 0xB000: # BNNN - Jump to NNN + V0
            self.pc = nnn + self.v[0]
            
        elif op_category == 0xC000: # CXNN - Set VX = random byte & NN
            self.v[x] = random.randint(0, 255) & nn
            
        elif op_category == 0xD000: # DXYN - Draw sprite
            vx = self.v[x] % 64
            vy = self.v[y] % 32
            self.v[0xF] = 0
            
            for row in range(n):
                if vy + row >= 32: break # Clip bottom
                sprite_byte = self.memory[self.i + row]
                
                for col in range(8):
                    if vx + col >= 64: break # Clip right
                    sprite_pixel = (sprite_byte >> (7 - col)) & 1
                    display_idx = (vy + row) * 64 + (vx + col)
                    
                    if sprite_pixel:
                        if self.display[display_idx]:
                            self.v[0xF] = 1
                        self.display[display_idx] ^= 1
            self.draw_flag = True
            
        elif op_category == 0xE000: # EX__ - Keypad operations
            if nn == 0x9E: # EX9E - Skip if key in VX is pressed
                if self.keys[self.v[x] & 0xF]:
                    self.pc += 2
            elif nn == 0xA1: # EXA1 - Skip if key in VX is NOT pressed
                if not self.keys[self.v[x] & 0xF]:
                    self.pc += 2
                    
        elif op_category == 0xF000: # FX__ - Timers, Memory, I/O
            if nn == 0x07: # FX07 - VX = delay timer
                self.v[x] = self.delay_timer
            elif nn == 0x0A: # FX0A - Wait for keypress, store in VX
                pressed = False
                for k, is_pressed in enumerate(self.keys):
                    if is_pressed:
                        self.v[x] = k
                        pressed = True
                        break
                if not pressed:
                    self.pc -= 2 # Decrement PC to repeat instruction until key pressed
            elif nn == 0x15: # FX15 - Delay timer = VX
                self.delay_timer = self.v[x]
            elif nn == 0x18: # FX18 - Sound timer = VX
                self.sound_timer = self.v[x]
            elif nn == 0x1E: # FX1E - I += VX
                self.i = (self.i + self.v[x]) & 0xFFFF
            elif nn == 0x29: # FX29 - I = location of sprite for digit VX
                self.i = 0x50 + (self.v[x] & 0xF) * 5
            elif nn == 0x33: # FX33 - Store BCD representation of VX in memory locations I, I+1, I+2
                val = self.v[x]
                self.memory[self.i] = val // 100
                self.memory[self.i + 1] = (val // 10) % 10
                self.memory[self.i + 2] = val % 10
            elif nn == 0x55: # FX55 - Store registers V0 through VX in memory starting at location I
                for idx in range(x + 1):
                    self.memory[self.i + idx] = self.v[idx]
            elif nn == 0x65: # FX65 - Read registers V0 through VX from memory starting at location I
                for idx in range(x + 1):
                    self.v[idx] = self.memory[self.i + idx]


class Chip8App:
    def __init__(self, root):
        self.root = root
        # Title as explicitly requested
        self.root.title("ac's chip 8 emu 0.1")
        
        # mgba blue hue background
        self.bg_color = "#1E1E3F"
        self.button_bg = "black"
        self.text_color = "#00AAFF" # Blue text
        self.pixel_on = "#00AAFF"
        self.pixel_off = "#00001A"  # Very dark blue for canvas background

        self.root.configure(bg=self.bg_color)
        
        self.cpu = Chip8CPU()
        
        # Scale for rendering (10x makes a 640x320 window)
        self.scale = 10
        self.width = 64
        self.height = 32
        
        # UI Setup
        self.setup_ui()
        self.setup_bindings()
        # Idle at $200 so PC never scans the whole RAM as 0x0000 (would OOB past 4094).
        self.cpu.load_rom(IDLE_ROM)
        
        # 60 Hz main loop; CHIP-8 delay/sound timers also run at 60 Hz.
        self.target_fps = 60
        self.frame_ms = max(1, round(1000.0 / self.target_fps))
        # ~500–800 Hz on original VIP-class hardware; 12 inst × 60 fps ≈ 720 Hz.
        self.cpu_speed = 12
        
        # Start loop
        self.running = True
        self.update_loop()

    def setup_ui(self):
        # Frame for canvas to give it a nice border
        self.canvas_frame = tk.Frame(self.root, bg=self.pixel_off, bd=2, relief=tk.SUNKEN)
        self.canvas_frame.pack(pady=10, padx=10)
        
        self.canvas = tk.Canvas(
            self.canvas_frame, 
            width=self.width * self.scale, 
            height=self.height * self.scale, 
            bg=self.pixel_off, 
            highlightthickness=0
        )
        self.canvas.pack()
        
        # Pre-create rectangles to optimize drawing speed
        self.rects = []
        for y in range(self.height):
            row = []
            for x in range(self.width):
                x0, y0 = x * self.scale, y * self.scale
                x1, y1 = x0 + self.scale, y0 + self.scale
                # Start all off
                rect = self.canvas.create_rectangle(x0, y0, x1, y1, fill=self.pixel_off, outline="")
                row.append(rect)
            self.rects.append(row)
            
        # Controls Frame (Bottom)
        self.controls = tk.Frame(self.root, bg=self.bg_color)
        self.controls.pack(fill=tk.X, padx=10, pady=5)
        
        # Label with Blue Text as requested
        self.info_lbl = tk.Label(
            self.controls, 
            text="Keypad: 1234/QWER/ASDF/ZXCV  |  No ROM loaded (blank screen)", 
            bg=self.bg_color, 
            fg=self.text_color,
            font=("Consolas", 10, "bold")
        )
        self.info_lbl.pack(side=tk.LEFT)
        
        # Buttons with Black background and Blue Text as requested
        btn_style = {
            "bg": self.button_bg,
            "fg": self.text_color,
            "activebackground": "#222",
            "activeforeground": "#00FFFF",
            "font": ("Consolas", 10, "bold"),
            "bd": 1,
            "relief": tk.RAISED,
            "cursor": "hand2"
        }
        
        self.btn_load = tk.Button(self.controls, text="Load ROM", command=self.open_rom, **btn_style)
        self.btn_load.pack(side=tk.RIGHT, padx=5)
        
        self.btn_reset = tk.Button(self.controls, text="Reset", command=self.reset_emu, **btn_style)
        self.btn_reset.pack(side=tk.RIGHT, padx=5)

    def setup_bindings(self):
        # Standard CHIP-8 hex keypad mapped to modern QWERTY layout
        # 1 2 3 C   ->   1 2 3 4
        # 4 5 6 D   ->   Q W E R
        # 7 8 9 E   ->   A S D F
        # A 0 B F   ->   Z X C V
        self.keymap = {
            '1': 0x1, '2': 0x2, '3': 0x3, '4': 0xC,
            'q': 0x4, 'w': 0x5, 'e': 0x6, 'r': 0xD,
            'a': 0x7, 's': 0x8, 'd': 0x9, 'f': 0xE,
            'z': 0xA, 'x': 0x0, 'c': 0xB, 'v': 0xF
        }
        
        self.root.bind("<KeyPress>", self.key_down)
        self.root.bind("<KeyRelease>", self.key_up)

    def key_down(self, event):
        key = event.keysym.lower()
        if key in self.keymap:
            self.cpu.keys[self.keymap[key]] = True

    def key_up(self, event):
        key = event.keysym.lower()
        if key in self.keymap:
            self.cpu.keys[self.keymap[key]] = False

    def open_rom(self):
        # Open file dialog for a CHIP-8 ROM
        filepath = filedialog.askopenfilename(
            title="Select a CHIP-8 ROM",
            filetypes=(("CHIP-8 ROMs", "*.ch8"), ("All files", "*.*"))
        )
        if filepath:
            try:
                with open(filepath, 'rb') as f:
                    rom_data = f.read()
                self.cpu.load_rom(rom_data)
                filename = filepath.split('/')[-1].split('\\')[-1]
                self.info_lbl.config(text=f"Keypad: 1234/QWER/ASDF/ZXCV  |  Playing: {filename}")
                self.clear_display()
            except Exception as e:
                self.info_lbl.config(text=f"Error loading ROM!")

    def reset_emu(self):
        # Resets the CPU state but keeps the loaded ROM in memory
        rom_backup = self.cpu.memory[0x200:]
        self.cpu.reset()
        for i in range(len(rom_backup)):
            self.cpu.memory[0x200 + i] = rom_backup[i]
        self.clear_display()

    def clear_display(self):
        for y in range(self.height):
            for x in range(self.width):
                self.canvas.itemconfig(self.rects[y][x], fill=self.pixel_off)

    def update_loop(self):
        if not self.running:
            return

        # Execute multiple instructions per frame for performance
        try:
            for _ in range(self.cpu_speed):
                self.cpu.emulate_cycle()
        except Exception as e:
            print(f"Emulator error: {e}")
            pass # Failsafe against bad opcodes halting the GUI thread completely
            
        # Delay and sound timers tick at 60 Hz (one step per frame).
        if self.cpu.delay_timer > 0:
            self.cpu.delay_timer -= 1
        if self.cpu.sound_timer > 0:
            self.cpu.sound_timer -= 1
            # (Optional: Play sound here if desired)

        # Draw to screen if required
        if self.cpu.draw_flag:
            for y in range(self.height):
                for x in range(self.width):
                    idx = y * self.width + x
                    color = self.pixel_on if self.cpu.display[idx] else self.pixel_off
                    # Only update if the canvas color is different
                    current_color = self.canvas.itemcget(self.rects[y][x], "fill")
                    if current_color != color:
                        self.canvas.itemconfig(self.rects[y][x], fill=color)
            self.cpu.draw_flag = False

        # Schedule next frame at target FPS
        self.root.after(self.frame_ms, self.update_loop)

if __name__ == "__main__":
    root = tk.Tk()
    root.resizable(False, False)
    app = Chip8App(root)
    root.mainloop()
