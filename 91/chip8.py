import subprocess
import time
import sys
import random

from blessed import Terminal
from pynput.keyboard import Listener


class Colorcodes(object):
    """
    Provides ANSI terminal color codes which are gathered via the ``tput``
    utility. That way, they are portable. If there occurs any error with
    ``tput``, all codes are initialized as an empty string.
    The provides fields are listed below.
    Control:
    - bold
    - reset
    Colors:
    - blue
    - green
    - orange
    - red
    :license: MIT
    """
    def __init__(self):
        def tput_code(command):
            try:
                return subprocess.check_output(f"tput {command}".split(), encoding="utf8")
            except subprocess.CalledProcessError as e:
                return ""

        self.bold = tput_code("bold")
        self.reset = tput_code("sgr0")

        self.blue = tput_code("setaf 4")
        self.green = tput_code("setaf 2")
        self.orange = tput_code("setaf 3")
        self.red = tput_code("setaf 1")            
        self.cursor_home = tput_code("home")
        self.cursor_invisible = tput_code("civis")
        self.cursor_normal = tput_code("cnorm")
        self.save_cursor_pos = tput_code("sc")
        self.restore_cursor_pos = tput_code("rc")
        self.save_screen = tput_code("smcup")
        self.restore_screen = tput_code("rmcup")
        self.clear_screen_and_home_cursor = tput_code("clear")


class KeyPoll:
    def __init__(self) -> None:
        self.pressed = set()
        self.listener = Listener(on_press=lambda key: self.on_press(key), on_release=lambda key: self.on_release(key))
        self.listener.start()        

    def on_press(self, key):
        if hasattr(key, "char"):
            self.pressed.add(key.char)

    def on_release(self, key):
        if hasattr(key, "char") and key.char in self.pressed:
            self.pressed.remove(key.char)


colorcodes = Colorcodes()

term = Terminal()
keys = KeyPoll()    
keyboard_map = list("x123qweasdzc4rfv")
key_layout = [[1, 2, 3, 12], [4, 5, 6, 13], [7, 8, 9, 14], [10, 0, 11, 15]]


class Chip8:
    screen_height = 32
    screen_width = 64
    sprite_data_loc = 0
    memory_size = 4096
    program_start = 0x200
    tick_seconds = 1 / 60.0

    def __init__(self) -> None:
        self.screen = [[0] * Chip8.screen_height for _ in range(Chip8.screen_width)]
        self.memory = [0] * Chip8.memory_size
        self.data_registers = [0] * 16
        self.address_reg = 0
        self.sound_timer = 0
        self.delay_timer = 0
        self.stack = []
        self.exec_addr = Chip8.program_start
        self.last_tick = time.time()

        sprite_data = "F0 90 90 90 F0 20 60 20 20 70 F0 10 F0 80 F0 F0 10 F0 10 F0 90 90 F0 10 10 F0 80 F0 10 F0 F0 80 F0 90 F0 F0 10 20 40 40 "\
                      "F0 90 F0 90 F0 F0 90 F0 10 F0 F0 90 F0 90 90 E0 90 E0 90 E0 F0 80 80 80 F0 E0 90 90 90 E0 F0 80 F0 80 F0 F0 80 F0 80 80"

        for p, b in enumerate(sprite_data.split(" ")):
            self.memory[Chip8.sprite_data_loc + p] = int(b, 16)


    def display(self):
        str = ""
        for y in range(0, Chip8.screen_height, 2):
            for x in range(Chip8.screen_width):
                if self.screen[x][y] == 1:
                    str += "█" if self.screen[x][y + 1] == 1 else "▀"
                else:
                    str += "▄" if self.screen[x][y + 1] == 1 else " "

            str += "\n"

        return str

    def load_file(self, file_name):
        with open(file_name, "rb") as f:
            max_program_len = Chip8.memory_size - Chip8.program_start
            data = f.read(max_program_len)
            if len(data) == 0:
                raise RuntimeError("Empty program")
            
            if len(f.read(1)) != 0:
                raise RuntimeError("Program too large")

            for i, b in enumerate(data):
                self.memory[Chip8.program_start + i] = int(b)

    def step(self):
        b1, nn = self.memory[self.exec_addr:self.exec_addr + 2]
        w = (b1 << 8) | nn
        self.exec_addr += 2
        n1 = b1 >> 4
        x = b1 & 0xf
        y = nn >> 4
        n = nn & 0xf
        nnn = (x << 8) | nn
        need_redraw = False


        if w == 0x00e0:
            self.clear_screen()
            need_redraw = True
        elif w == 0x00ee:
            self.exec_addr = self.stack.pop()
        elif n1 == 1:
            self.exec_addr = nnn
        elif n1 == 2:
            self.stack.append(self.exec_addr)
            self.exec_addr = nnn
        elif n1 == 3:
            if self.data_registers[x] == nn:
                self.exec_addr += 2
        elif n1 == 4:
            if self.data_registers[x] != nn:
                self.exec_addr += 2
        elif n1 == 5 and n == 0:
            if self.data_registers[x] == self.data_registers[y]:
                self.exec_addr += 2                
        elif n1 == 6:
            self.data_registers[x] = nn
        elif n1 == 7:
            self.data_registers[x] = (self.data_registers[x] + nn) & 0xff
        elif n1 == 8:
            if n == 0:
                self.data_registers[x] = self.data_registers[y]
            elif n == 1:
                self.data_registers[x] |= self.data_registers[y]
            elif n == 2:
                self.data_registers[x] &= self.data_registers[y]
            elif n == 3:
                self.data_registers[x] ^= self.data_registers[y]
            elif n == 4:
                carry = int(self.data_registers[x] + self.data_registers[y] > 255)
                self.data_registers[x] = (self.data_registers[x] + self.data_registers[y]) & 0xff
                self.data_registers[0xf] = carry                  
            elif n == 5:
                carry = int(self.data_registers[x] > self.data_registers[y])
                self.data_registers[x] = (self.data_registers[x] - self.data_registers[y]) & 0xff
                self.data_registers[0xf] = carry            
            elif n == 6:
                self.data_registers[x] = self.data_registers[y]
                bit = self.data_registers[x] & 1
                self.data_registers[x] >>= 1
                self.data_registers[0xf] = bit
            elif n == 7:
                carry = int(self.data_registers[y] > self.data_registers[x])
                self.data_registers[x] = (self.data_registers[y] - self.data_registers[x]) & 0xff
                self.data_registers[0xf] = carry
            elif n == 0xe:
                self.data_registers[x] = self.data_registers[y]
                bit = (self.data_registers[x] >> 7) & 1
                self.data_registers[x] <<= 1
                self.data_registers[0xf] = bit                
            else:
                raise RuntimeError(f"Unknown instruction {w:04x} at address {self.exec_addr - 2:04x}")                
        elif n1 == 9 and n == 0:
            if self.data_registers[x] != self.data_registers[y]:
                self.exec_addr += 2                
        elif n1 == 0xa:
            self.address_reg = nnn
        elif n1 == 0xb:
            self.exec_addr = (nnn + self.data_registers[0]) % Chip8.memory_size
        elif n1 == 0xc:
            self.data_registers[x] = random.randint(0, 255) & nn
        elif n1 == 0xd:
            self.draw(self.data_registers[x], self.data_registers[y], self.address_reg, n)
            need_redraw = True
        elif n1 == 0xe:
            if nn == 0x9e:
                if keyboard_map[self.data_registers[x]] in keys.pressed:
                    self.exec_addr += 2
            elif nn == 0xa1:
                if keyboard_map[self.data_registers[x]] not in keys.pressed:
                    self.exec_addr += 2
            else:
                raise RuntimeError(f"Unknown instruction {w:04x} at address {self.exec_addr - 2:04x}")
        elif n1 == 0xf:
            if nn == 0x07:
                self.data_registers[x] = self.delay_timer
            elif nn == 0x0a:
                pressed = keys.pressed & set(keyboard_map)
                if pressed:
                    self.data_registers[x] = keyboard_map.index(pressed.pop())
                else:
                    self.exec_addr -= 2
            elif nn == 0x15:
                self.delay_timer = self.data_registers[x]
            elif nn == 0x18:
                self.sound_timer = self.data_registers[x]
            elif nn == 0x1e:
                self.address_reg += self.data_registers[x]
                if self.address_reg >= Chip8.memory_size:
                    self.address_reg = self.address_reg % Chip8.memory_size
                    self.data_registers[0xf] = 1
            elif nn == 0x29:
                self.address_reg = (self.data_registers[x] & 0xf) * 5
            elif nn == 0x33:
                num = self.data_registers[x]
                self.memory[self.address_reg] = num // 100
                self.memory[self.address_reg + 1] = (num // 10) % 10
                self.memory[self.address_reg + 2] = num % 10
            elif nn == 0x55:
                for i in range(x + 1):
                    self.memory[self.address_reg + i] = self.data_registers[i]
            elif nn == 0x65:
                for i in range(x + 1):
                    self.data_registers[i] = self.memory[self.address_reg + i]
            else:
                raise RuntimeError(f"Unknown instruction {w:04x} at address {self.exec_addr - 2:04x}")                
        else:
            raise RuntimeError(f"Unknown instruction {w:04x} at address {self.exec_addr - 2:04x}")

        now = time.time()
        while now >= self.last_tick + Chip8.tick_seconds:
            if self.delay_timer > 0:
                self.delay_timer -= 1

            self.last_tick += Chip8.tick_seconds

        return need_redraw

    def draw(self, x, y, p, n):
        x = x % Chip8.screen_width
        y = y % Chip8.screen_height
        self.data_registers[0xf] = 0
        for sy in range(n):
            if y + sy >= Chip8.screen_height:
                break

            row = self.memory[p + sy]
            for sx in range(8):
                if x + sx >= Chip8.screen_width:
                    break

                bit = (row >> (7 - sx)) & 1
                if bit and self.screen[x + sx][y + sy]:
                    self.data_registers[0xf] = 1

                self.screen[x + sx][y + sy] ^= bit

    def clear_screen(self):
        for y in range(Chip8.screen_height):
            for x in range(Chip8.screen_width):
                self.screen[x][y] = 0


if len(sys.argv) != 2:
    print("Specify a CHIP-8 ROM file")
    exit(1)

try:
    emulator = Chip8()
    emulator.load_file(sys.argv[1])
except Exception as e:
    print(f"Error: {e}")
    exit(1)


print(colorcodes.save_screen + colorcodes.save_cursor_pos + colorcodes.cursor_invisible)
bye_string = "Bye!"

try:
    with term.cbreak():
        last_time = time.time_ns()
        frame_times = []
        while True:
            need_redraw = emulator.step()
            now = time.time_ns()
            frame_times.append(now - last_time)
            if len(frame_times) > 100:
                frame_times.pop(0)

            last_time = now
            if need_redraw:
                screen = colorcodes.clear_screen_and_home_cursor
                screen += "                   ~~~  CHIP-8 emulator  ~~~\n"
                screen += emulator.display()
                screen += sys.argv[1][-15:].ljust(15, " ")
                screen += f"         Ctrl-C to exit                {sum(frame_times) / len(frame_times) / 1000:0.0f}us/Frame\n"
                screen += "Controls: "
                for i, r in enumerate(key_layout):
                    for ki in r:
                        screen += keyboard_map[ki].upper() + " "

                    if i < 3:
                        screen += "\n          "
                        
                print(screen, flush=True)
                time.sleep(0.001)
except Exception as e:
    bye_string = f"Error: {e}"
except KeyboardInterrupt:
    pass
finally:
    print(colorcodes.restore_screen + colorcodes.restore_cursor_pos + colorcodes.cursor_normal + bye_string)
