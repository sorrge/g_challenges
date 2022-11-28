import random
import time
from collections import defaultdict, Counter

from asciimatics.screen import Screen
from asciimatics.event import MouseEvent, KeyboardEvent


levels = {
    "beginner": (10, 9, 9),
    "intermediate": (40, 16, 16),
    "expert": (99, 16, 30)
}


class Board:
    def __init__(self, level) -> None:
        self.level = level
        self.mines_left, self.rows, self.columns = levels[level]
        self.size = self.rows * self.columns
        self.mines = [False] * self.size
        self.revealed = [False] * self.size
        self.flags = [False] * self.size
        self.neighbor_mines = [0] * self.size
        pos = list(range(self.size))
        random.shuffle(pos)
        for mine_pos in pos[:self.mines_left]:
            self.mines[mine_pos] = True

        self.neighbors = []
        for i in range(self.rows):
            for j in range(self.columns):        
                nn = []
                for si in range(-1, 2):
                    for sj in range(-1, 2):
                        if 0 <= i + si < self.rows and 0 <= j + sj < self.columns:
                            nn.append((i + si) * self.columns + j + sj)
                
                self.neighbors.append(nn)

        self.free_pos = pos[self.mines_left:]
        self.first_move_complete = False
        self.time = 0
        self.start_time = None
        self.status = "._."

    def game_on(self):
        return self.status == "._."

    def display(self, screen, discount_flags):
        if self.game_on() and self.first_move_complete:
            self.time = min(999, round(time.time() - self.start_time))

        screen.print_at(f"{self.mines_left:03d}{self.status.center(self.columns - 6)}{self.time:03d}", 0, 0)
        for i in range(self.rows):
            for j in range(self.columns):
                p = i * self.columns + j
                if not self.revealed[p]:
                    if self.flags[p]:
                        screen.print_at("⚑", j, i + 1, Screen.COLOUR_RED, bg=Screen.COLOUR_GREEN)
                    else:
                        screen.print_at("▒", j, i + 1)
                elif self.mines[p]:
                    screen.print_at("¤", j, i + 1, Screen.COLOUR_BLACK, bg=Screen.COLOUR_RED)
                else:
                    nm = self.neighbor_mines[p]
                    if discount_flags:
                        for n in self.neighbors[p]:
                            if n != p and not self.revealed[n] and self.flags[n]:
                                nm -= 1

                    if nm == 0:
                        screen.print_at(" ", j, i + 1)
                    elif nm < 0:
                        screen.print_at("?", j, i + 1)
                    else:
                        screen.print_at(str(nm), j, i + 1)

    def reveal(self, p):
        if not self.game_on():
            return False

        if self.revealed[p]:
            changed = False
            if self.neighbor_mines[p] > 0:
                flags_around = 0
                can_be_revealed = []
                for n in self.neighbors[p]:
                    if n != p and not self.revealed[n]:
                        if self.flags[n]:
                            flags_around += 1
                        else:
                            can_be_revealed.append(n)
                
                if flags_around == self.neighbor_mines[p]:
                    for n in can_be_revealed:
                        changed |= self.reveal(n)
                elif flags_around + len(can_be_revealed) == self.neighbor_mines[p]:
                    for n in can_be_revealed:
                        self.flag(n)
                        changed = True

            return changed

        self.revealed[p] = True
        if self.mines[p]:
            if self.first_move_complete:
                self.status = "x_x"
                self.start_time = None
            else:
                self.mines[p] = False
                new_mine = random.choice(self.free_pos)
                self.mines[new_mine] = True

        if self.flags[p]:
            self.mines_left += 1

        if not self.first_move_complete:
            self.start_time = time.time()
            for p1 in range(self.size):
                if self.mines[p1]:
                    for n in self.neighbors[p1]:
                        self.neighbor_mines[n] += 1
            
            self.first_move_complete = True

        if self.neighbor_mines[p] == 0:
            revealed_empty = [p]
            while revealed_empty:
                p1 = revealed_empty.pop()
                for n in self.neighbors[p1]:
                    if not self.revealed[n]:
                        self.revealed[n] = True
                        if self.neighbor_mines[n] == 0:
                            revealed_empty.append(n)

        self.check_win()
        return True

    def check_win(self):
        if self.game_on():
            all_done = True
            for p in range(self.size):
                if not (self.revealed[p] or (self.flags[p] and self.mines[p])):
                    all_done = False
                    break

                if not all_done:
                    break

            if all_done:
                self.status = "o~o"

    def get_unrevealed_neighbors(self, p):
        unflagged_mines = self.neighbor_mines[p]
        s = set()
        for n in self.neighbors[p]:
            if n != p and not self.revealed[n]:
                if self.flags[n]:
                    unflagged_mines -= 1
                else:
                    s.add(n)

        return s, unflagged_mines

    def check_sets(self):
        if not self.game_on():
            return False

        cell_sets = defaultdict(list)
        for p in range(self.size):
            if self.revealed[p] and self.neighbor_mines[p] > 0:
                s, unflagged_mines = self.get_unrevealed_neighbors(p)
                if unflagged_mines < 0:
                    return False

                if unflagged_mines > 0:
                    if len(s) <= unflagged_mines:
                        return False

                    for p1 in s:
                        cell_sets[p1].append((s, unflagged_mines))

        to_reveal = set()
        to_flag = set()
        for css in cell_sets.values():
            for s1, m1 in css:
                for s2, m2 in css:
                    if s1 is not s2 and len(s1) <= len(s2):
                        if s1 == s2:
                            assert m1 == m2
                            continue
                        
                        s1_only = s1 - s2
                        s2_only = s2 - s1
                        both = s1 & s2
                        assert len(both) > 0
                        assert len(s2_only) > 0
                        if len(s1_only) == 0:
                            assert m2 >= m1
                            s2_only_mines = m2 - m1
                            if s2_only_mines == 0:
                                to_reveal.update(s2_only)
                            elif s2_only_mines == len(s2_only):
                                to_flag.update(s2_only)
                        else:
                            max_mines_in_both = min(m1, m2)
                            min_s1 = m1 - max_mines_in_both
                            assert min_s1 <= len(s1_only)
                            if min_s1 == len(s1_only):
                                to_flag.update(s1_only)

                            min_s2 = m2 - max_mines_in_both
                            assert min_s2 <= len(s2_only)
                            if min_s2 == len(s2_only):
                                to_flag.update(s2_only)

        for p in to_reveal:
            self.reveal(p)
        
        for p in to_flag:
            self.flag(p)

        return len(to_reveal) + len(to_flag) > 0

    def check_total(self):
        if not self.game_on():
            return False

        accounted_mines = 0
        cells_considered = set()
        for p in range(self.size):
            if self.revealed[p] and self.neighbor_mines[p] > 0:
                s, unflagged_mines = self.get_unrevealed_neighbors(p)               
                if unflagged_mines > 0:
                    already_considered = cells_considered & s
                    if len(already_considered) < unflagged_mines:
                        accounted_mines += unflagged_mines - len(already_considered)
                        cells_considered.update(s)

        if accounted_mines > self.mines_left:
            return False

        changed = False
        remaining_cells = set()
        for p in range(self.size):
            if not self.revealed[p] and not self.flags[p] and p not in cells_considered:
                remaining_cells.add(p)

        if accounted_mines == self.mines_left:
            for p in remaining_cells:
                self.reveal(p)
                changed = True
        elif self.mines_left - accounted_mines == len(remaining_cells):
            for p in remaining_cells:
                self.flag(p)
                changed = True

        return changed

    def flag(self, p):
        if not self.revealed[p]:
            self.mines_left += 1 if self.flags[p] else -1
            self.flags[p] = not self.flags[p]

        self.check_win()

    def recheck_all(self):
        changed = False
        for p in range(self.size):
            if self.revealed[p] and self.neighbors[p] != 0:
                changed |= self.reveal(p)

        return changed

    def auto_reveal(self, screen, discount_flags):
        while True:
            while True:
                self.display(screen, discount_flags)
                screen.refresh()
                time.sleep(0.1)

                while self.recheck_all():
                    self.display(screen, discount_flags)
                    screen.refresh()
                    time.sleep(0.1)

                if not self.check_sets():
                    break

            if not self.check_total():
                break

    def find_best_try_reveal(self):
        probs = defaultdict(float)
        for p in range(self.size):
            if self.revealed[p] and self.neighbor_mines[p] > 0:
                s, unflagged_mines = self.get_unrevealed_neighbors(p)
                if unflagged_mines > 0:
                    prob = unflagged_mines / len(s)
                    for n in s:
                        probs[n] = max(probs[n], prob)

        remaining_cells = set()
        for p in range(self.size):
            if not p in probs and not self.revealed[p] and not self.flags[p]:
                remaining_cells.add(p)

        if remaining_cells:
            prob = self.mines_left / len(remaining_cells)
            for p in remaining_cells:
                probs[p] = prob

        best_prob = min(probs.values())
        cells_best_prob = [p for p, prob in probs.items() if prob == best_prob]
        return random.choice(cells_best_prob)
                            

board = Board("beginner")
started = Counter()
lost = Counter()
won = Counter()

def game_loop(screen):
    global board
    discount_flags = False

    while True:
        event = screen.get_event()
        if event is None:
            board.display(screen, discount_flags)
            screen.print_at("Controls:", 0, board.rows + 1)
            screen.print_at("[left click] reveal    [right click] toggle flag", 0, board.rows + 2)
            screen.print_at("[q]uit                 [b]eginner", 0, board.rows + 3)
            screen.print_at("[i]ntermediate         [e]xpert", 0, board.rows + 4)
            screen.print_at("[d]iscount flags       [r]estart", 0, board.rows + 5)
            screen.print_at("[space] reveal random safest cell", 0, board.rows + 6)
            screen.refresh()
            time.sleep(0.01)
        elif isinstance(event, MouseEvent):
            game_was_on = board.game_on()
            first_move_was_complete = board.first_move_complete
            c, r = event.x, event.y - 1
            if 0 <= c < board.columns and 0 <= r < board.rows:
                if event.buttons & event.LEFT_CLICK:
                    board.reveal(r * board.columns + c)
                    board.auto_reveal(screen, discount_flags)
                if event.buttons & event.RIGHT_CLICK:
                    board.flag(r * board.columns + c)
                    board.auto_reveal(screen, discount_flags)

            if not first_move_was_complete and board.first_move_complete:
                started[board.level] += 1

            if game_was_on and not board.game_on():
                if board.status == "o~o":
                    won[board.level] += 1
                else:
                    lost[board.level] += 1
        elif isinstance(event, KeyboardEvent):
            try:
                key = chr(event.key_code).lower()
            except Exception:
                continue

            if key == "b":
                screen.clear()
                board = Board("beginner")
            elif key == "i":
                screen.clear()
                board = Board("intermediate")
            elif key == "e":
                screen.clear()
                board = Board("expert")
            elif key == "r":
                screen.clear()
                board = Board(board.level)                
            elif key == "q":
                return
            elif key == "d":
                discount_flags = not discount_flags
            elif key == " ":
                p = board.find_best_try_reveal()
                game_was_on = board.game_on()
                first_move_was_complete = board.first_move_complete
                board.reveal(p)
                board.auto_reveal(screen, discount_flags)
                if not first_move_was_complete and board.first_move_complete:
                    started[board.level] += 1

                if game_was_on and not board.game_on():
                    if board.status == "o~o":
                        won[board.level] += 1
                    else:
                        lost[board.level] += 1


Screen.wrapper(game_loop)

for level in started:
    print(f"{level}:\t{started[level]} games started, {won[level]} won, {lost[level]} lost, "
        f"{started[level] - won[level] - lost[level]} reset")
