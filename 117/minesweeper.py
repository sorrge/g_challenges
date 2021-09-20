import random
import time

from asciimatics.screen import Screen
from asciimatics.event import MouseEvent, KeyboardEvent


levels = {
    "beginner": (10, 9, 9),
    "intermediate": (40, 16, 16),
    "expert": (99, 16, 30)
}


class Board:
    def __init__(self, level) -> None:
        self.mines_left, rs, cs = levels[level]
        self.mines = [[False] * cs for _ in range(rs)]
        self.revealed = [[False] * cs for _ in range(rs)]
        self.flags = [[False] * cs for _ in range(rs)]
        self.neighbors = [[0] * cs for _ in range(rs)]
        pos = list(range(rs * cs))
        random.shuffle(pos)
        for mine_pos in pos[:self.mines_left]:
            self.mines[mine_pos % rs][mine_pos // rs] = True

        self.free_pos = pos[self.mines_left:]
        self.first_move_complete = False
        self.time = 0
        self.start_time = None
        self.status = "._."

    def display(self, screen):
        if self.status == "._." and self.first_move_complete:
            self.time = min(999, round(time.time() - self.start_time))

        screen.print_at(f"{self.mines_left:03d}{self.status.center(len(self.mines[0]) - 6)}{self.time:03d}", 0, 0)
        for i in range(len(self.mines)):
            for j in range(len(self.mines[0])):
                if not self.revealed[i][j]:
                    if self.flags[i][j]:
                        screen.print_at("⚑", j, i + 1, Screen.COLOUR_RED, bg=Screen.COLOUR_GREEN)
                    else:
                        screen.print_at("▒", j, i + 1)
                elif self.mines[i][j]:
                    screen.print_at("¤", j, i + 1, Screen.COLOUR_BLACK, bg=Screen.COLOUR_RED)
                elif self.neighbors[i][j] == 0:
                    screen.print_at(" ", j, i + 1)
                else:
                    screen.print_at(str(self.neighbors[i][j]), j, i + 1)

    def reveal(self, r, c):
        if self.status != "._.":
            return

        if self.revealed[r][c]:
            if self.neighbors[r][c] > 0:
                flags_around = 0
                can_be_revealed = []
                for si in range(-1, 2):
                    for sj in range(-1, 2):
                        if (si != 0 or sj != 0) and \
                            0 <= r + si < len(self.mines) and 0 <= c + sj < len(self.mines[0]) and \
                            not self.revealed[r + si][c + sj]:
                            if self.flags[r + si][c + sj]:
                                flags_around += 1
                            else:
                                can_be_revealed.append((r + si, c + sj))
                
                if flags_around == self.neighbors[r][c]:
                    for r, c in can_be_revealed:
                        self.reveal(r, c)
                elif flags_around + len(can_be_revealed) == self.neighbors[r][c]:
                    for r, c in can_be_revealed:
                        self.flag(r, c)

            return

        self.revealed[r][c] = True
        if self.mines[r][c]:
            if self.first_move_complete:
                self.status = "x_x"
                self.start_time = None
            else:
                self.mines[r][c] = False
                new_mine = random.choice(self.free_pos)
                self.mines[new_mine % len(self.mines)][new_mine // len(self.mines)] = True

        if self.flags[r][c]:
            self.mines_left += 1

        if not self.first_move_complete:
            self.start_time = time.time()
            for i in range(len(self.mines)):
                for j in range(len(self.mines[0])):
                    if self.mines[i][j]:
                        for si in range(-1, 2):
                            for sj in range(-1, 2):
                                if 0 <= i + si < len(self.mines) and 0 <= j + sj < len(self.mines[0]):
                                    self.neighbors[i + si][j + sj] += 1
            
            self.first_move_complete = True

        if self.neighbors[r][c] == 0:
            revealed_empty = [(r, c)]
            while revealed_empty:
                rr, cc = revealed_empty.pop()
                for si in range(-1, 2):
                    for sj in range(-1, 2):
                        if 0 <= rr + si < len(self.mines) and 0 <= cc + sj < len(self.mines[0]) and \
                            not self.revealed[rr + si][cc + sj]:
                            self.revealed[rr + si][cc + sj] = True
                            if self.neighbors[rr + si][cc + sj] == 0:
                                revealed_empty.append((rr + si, cc + sj))

        if self.status == "._.":
            all_done = True
            for i in range(len(self.mines)):
                for j in range(len(self.mines[0])):
                    if not (self.revealed[i][j] or (self.flags[i][j] and self.mines[i][j])):
                        all_done = False
                        break

                if not all_done:
                    break

            if all_done:
                self.status = "o~o"


    def flag(self, r, c):
        if not self.revealed[r][c]:
            self.mines_left += 1 if self.flags[r][c] else -1
            self.flags[r][c] = not self.flags[r][c]

                            

board = Board("beginner")

def game_loop(screen):
    global board

    while True:
        event = screen.get_event()
        if event is None:
            board.display(screen)
            screen.print_at("Controls:", 0, len(board.mines) + 1)
            screen.print_at("[left click] reveal    [right click] toggle flag", 0, len(board.mines) + 2)
            screen.print_at("[q]uit                 [b]eginner", 0, len(board.mines) + 3)
            screen.print_at("[i]intermediate        [e]xpert", 0, len(board.mines) + 4)
            screen.refresh()
            time.sleep(0.01)
        elif isinstance(event, MouseEvent):
            c, r = event.x, event.y - 1
            if 0 <= c < len(board.mines[0]) and 0 <= r < len(board.mines):
                if event.buttons & event.LEFT_CLICK:
                    board.reveal(r, c)
                if event.buttons & event.RIGHT_CLICK:
                    board.flag(r, c)
        elif isinstance(event, KeyboardEvent):
            if chr(event.key_code).lower() == "b":
                screen.clear()
                board = Board("beginner")
            elif chr(event.key_code).lower() == "i":
                screen.clear()
                board = Board("intermediate")
            elif chr(event.key_code).lower() == "e":
                screen.clear()
                board = Board("expert")
            elif chr(event.key_code).lower() == "q":
                return


Screen.wrapper(game_loop)
