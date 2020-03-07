import random
import math
import sys
import time

import svgwrite

from cspuz import Solver, graph
from cspuz.constraints import count_true, fold_or
from cspuz.puzzle import util


def solve_compass(height, width, problem):
    solver = Solver()
    roots = map(lambda x: (x[0], x[1]), problem)
    division = solver.int_array((height, width), 0, len(problem) - 1)
    graph.division_connected(solver, division, len(problem), roots=roots)
    solver.add_answer_key(division)
    for i, (y, x, u, l, d, r) in enumerate(problem):
        solver.ensure(division[y, x] == i)
        if u >= 0:
            solver.ensure(count_true(division[:y, :] == i) == u)
        if d >= 0:
            solver.ensure(count_true(division[(y + 1):, :] == i) == d)
        if l >= 0:
            solver.ensure(count_true(division[:, :x] == i) == l)
        if r >= 0:
            solver.ensure(count_true(division[:, (x + 1):] == i) == r)
    is_sat = solver.solve()

    return is_sat, division


def check_problem_constraints(height, width, problem, flg, circ=-1):
    if flg is None and circ == -1:
        return True
    for clue in problem:
        a = 0
        for i in range(2, 6):
            if clue[i] >= 0:
                a += 1
    solver = Solver()
    roots = map(lambda x: (x[0], x[1]), problem)
    division = solver.int_array((height, width), 0, len(problem) - 1)
    graph.division_connected(solver, division, len(problem), roots=roots)
    solver.add_answer_key(division)
    for i, (y, x, u, l, d, r) in enumerate(problem):
        solver.ensure(division[y, x] == i)
        if flg is not None and flg[i]:
            solver.ensure(count_true(division == i) >= 4)
        if u >= 0:
            solver.ensure(count_true(division[:y, :] == i) == u)
        if d >= 0:
            solver.ensure(count_true(division[(y + 1):, :] == i) == d)
        if l >= 0:
            solver.ensure(count_true(division[:, :x] == i) == l)
        if r >= 0:
            solver.ensure(count_true(division[:, (x + 1):] == i) == r)

    # encircling constraint
    if circ != -1:
        col = solver.bool_array((height, width))
        solver.ensure(col[0, :])
        solver.ensure(col[-1, :])
        solver.ensure(col[:, 0])
        solver.ensure(col[:, -1])
        solver.ensure(((division[1:, :] != circ) & (division[:-1, :] != circ)).then(col[1:, :] == col[:-1, :]))
        solver.ensure(((division[:, 1:] != circ) & (division[:, :-1] != circ)).then(col[:, 1:] == col[:, :-1]))
        solver.ensure(((division[1:, 1:] != circ) & (division[:-1, :-1] != circ)).then(col[1:, 1:] == col[:-1, :-1]))
        solver.ensure(((division[:-1, 1:] != circ) & (division[1:, :-1] != circ)).then(col[:-1, 1:] == col[1:, :-1]))
        solver.ensure(fold_or(col & (division != circ)))
        solver.ensure(fold_or((~col) & (division != circ)))

    sat = solver.find_answer()
    return sat


def compute_score(division):
    score = 0
    for v in division[:, :]:
        if v.sol is not None:
            score += 1
    return score


def generate_compass(height, width, pos, prefer_large_blocks=False, encircling=False, timeout=7200.0, verbose=False):
    problem = [[y, x, -1, -1, -1, -1] for y, x in pos]
    score = 0
    temperature = 5.0
    fully_solved_score = height * width
    start = time.time()

    if prefer_large_blocks:
        flg = [random.random() < 0.9 for _ in range(len(pos))]
    else:
        flg = None
    if encircling:
        circ = random.randint(0, len(pos) - 1)
    else:
        circ = -1

    for step in range(height * width * 10):
        cand = []
        for i in range(len(pos)):
            for j in range(4):
                for n in range(-1, 8):
                    if n == 0:
                        continue
                    if problem[i][j + 2] != n:
                        cand.append((i, j, n))
        random.shuffle(cand)

        for i, j, n in cand:
            if timeout is not None and time.time() - start >= timeout:
                if verbose:
                    print('timeout', file=sys.stderr)
                return None
            n_prev = problem[i][j + 2]
            problem[i][j + 2] = n

            if not check_problem_constraints(height, width, problem, flg, circ):
                problem[i][j + 2] = n_prev
                continue

            sat, division = solve_compass(height, width, problem)
            if not sat:
                score_next = -1
                update = False
            else:
                raw_score = compute_score(division)
                if raw_score == fully_solved_score:
                    return problem
                clue_score = 0
                for i2 in range(len(pos)):
                    for j2 in range(2, 6):
                        if problem[i2][j2] >= 0:
                            clue_score += 3
                score_next = raw_score - clue_score
                update = (score < score_next or random.random() < math.exp((score_next - score) / temperature))

            if update:
                if verbose:
                    print('update: {} -> {}'.format(score, score_next), file=sys.stderr)
                score = score_next
                break
            else:
                problem[i][j + 2] = n_prev
        temperature *= 0.995
    if verbose:
        print('failed', file=sys.stderr)
    return None


def emit_puzz_link_url(height, width, pos):
    problem = [[None for _ in range(width)] for _ in range(height)]
    for (y, x, u, l, d, r) in pos:
        problem[y][x] = (u, l, d, r)
    def convert_clue_value(v):
        if v == -1:
            return '.'
        elif 0 <= v <= 15:
            return format(v, 'x')
        else:
            return '-' + format(v, 'x')
    ret = ''
    contiguous_empty_cells = 0
    for y in range(height):
        for x in range(width):
            if problem[y][x] is None:
                if contiguous_empty_cells == 20:
                    ret += 'z'
                    contiguous_empty_cells = 1
                else:
                    contiguous_empty_cells += 1
            else:
                if contiguous_empty_cells > 0:
                    ret += chr(ord('f') + contiguous_empty_cells)
                    contiguous_empty_cells = 0
                ret += convert_clue_value(problem[y][x][0]) + convert_clue_value(problem[y][x][2]) + \
                       convert_clue_value(problem[y][x][1]) + convert_clue_value(problem[y][x][3])
    if contiguous_empty_cells > 0:
        ret += chr(ord('f') + contiguous_empty_cells)
    return 'https://puzz.link/p?compass/{}/{}/{}'.format(width, height, ret)


def parse_puzz_link_url(url):
    height, width, body = url.split('/')[-3:]
    height = int(height)
    width = int(width)

    pos = 0
    i = 0
    res = []
    while i < len(body):
        if ord(body[i]) >= ord('g'):
            pos += ord(body[i]) - ord('f')
            i += 1
        else:
            num = [-1, -1, -1, -1]
            for j in range(4):
                if body[i] == '-':
                    num[j] = int(body[i+1:i+3], 16)
                    i += 3
                else:
                    if body[i] != '.':
                        num[j] = int(body[i], 16)
                    i += 1
            res.append((pos // width, pos % width, num[0], num[2], num[1], num[3]))
            pos += 1
    return height, width, res


def generate_placement(height, width, nlo, nhi):
    while True:
        has_clue = [[False for _ in range(width)] for _ in range(height)]
        n = random.randint(nlo, nhi) // 2 * 2
        pos = []
        while n > 0:
            y = random.randint(0, height - 1)
            x = random.randint(0, width - 1)
            if has_clue[y][x]:
                continue
            if y == 0 or x == 0 or y == height - 1 or x == width - 1:
                continue
            score = 0
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    y2 = y + dy
                    x2 = x + dx
                    if 0 <= y2 < height and 0 <= x2 < width and has_clue[y2][x2]:
                        if abs(dy) + abs(dx) <= 2:
                            score += 1
                        else:
                            score += 0.5
            if random.random() > math.exp(-score / 1.5):
                continue
            has_clue[y][x] = True
            has_clue[height - 1 - y][width - 1 - x] = True
            pos.append((y, x))
            pos.append((height - 1 - y, width - 1 - x))
            n -= 2
        flg = False
        window = 4
        for y in range(height - window + 1):
            for x in range(width - window + 1):
                cnt = 0
                for dy in range(window):
                    for dx in range(window):
                        if has_clue[y + dy][x + dx]:
                            cnt += 1
                if cnt == 0:
                    flg = True
        if flg:
            continue
        return pos


def emit_svg(height, width, problem):
    boundary = 5
    cell_size = 50

    dwg = svgwrite.Drawing(size=(boundary * 2 + cell_size * width, boundary * 2 + cell_size * height))

    grid_style = {
        'stroke': 'gray',
        'stroke_width': 1,
        'stroke_dasharray': cell_size / 12
    }
    border_style = {
        'stroke': 'black',
        'stroke_width': 4
    }
    compass_style = {
        'stroke': 'black',
        'stroke_width': 1
    }
    text_style_one = {
        'fill': 'black',
        'font_size': cell_size * 0.4,
        'text_anchor': 'middle',
        'dominant_baseline': 'mathematical',
        'font_family': 'Helvetica'
    }
    text_style_two = {
        'fill': 'black',
        'font_size': cell_size * 0.4,
        'text_anchor': 'middle',
        'dominant_baseline': 'mathematical',
        'textLength': cell_size * 0.3,
        'lengthAdjust': 'spacingAndGlyphs',
        'font_family': 'Helvetica'
    }
    # grid
    for y in range(1, height):
        dwg.add(dwg.line((boundary, boundary + y * cell_size),
                         (boundary + width * cell_size, boundary + y * cell_size),
                         **grid_style))
    for x in range(1, width):
        dwg.add(dwg.line((boundary + x * cell_size, boundary),
                         (boundary + x * cell_size, boundary + height * cell_size),
                         **grid_style))

    # border
    dwg.add(dwg.line((boundary - 2, boundary),
                     (boundary + width * cell_size + 2, boundary),
                     **border_style))
    dwg.add(dwg.line((boundary - 2, boundary + height * cell_size),
                     (boundary + width * cell_size + 2, boundary + height * cell_size),
                     **border_style))
    dwg.add(dwg.line((boundary, boundary - 2),
                     (boundary, boundary + height * cell_size + 2),
                     **border_style))
    dwg.add(dwg.line((boundary + width * cell_size, boundary - 2),
                     (boundary + width * cell_size, boundary + height * cell_size + 2),
                     **border_style))

    # clues
    for (y, x, u, l, d, r) in problem:
        dwg.add(dwg.line((boundary + x * cell_size, boundary + y * cell_size),
                         (boundary + (x + 1) * cell_size, boundary + (y + 1) * cell_size),
                         **compass_style))
        dwg.add(dwg.line((boundary + (x + 1) * cell_size, boundary + y * cell_size),
                         (boundary + x * cell_size, boundary + (y + 1) * cell_size),
                         **compass_style))
        center_y = boundary + (y + 0.5) * cell_size
        center_x = boundary + (x + 0.5) * cell_size
        if u >= 0:
            dwg.add(dwg.text(str(u), x=[center_x], y=[center_y - cell_size * 0.27],
                             **(text_style_two if u >= 10 else text_style_one)))
        if l >= 0:
            dwg.add(dwg.text(str(l), x=[center_x - cell_size * 0.3], y=[center_y],
                             **(text_style_two if l >= 10 else text_style_one)))
        if d >= 0:
            dwg.add(dwg.text(str(d), x=[center_x], y=[center_y + cell_size * 0.3],
                             **(text_style_two if d >= 10 else text_style_one)))
        if r >= 0:
            dwg.add(dwg.text(str(r), x=[center_x + cell_size * 0.3], y=[center_y],
                             **(text_style_two if r >= 10 else text_style_one)))
    return dwg


def _main():
    if len(sys.argv) == 1:
        # generated example: https://puzz.link/p?compass/5/5/m..1.i25.1g53..i1..1m
        height = 5
        width = 5
        problem = [
            (1, 2, -1, 1, -1, -1),
            (2, 1, 2, -1, 5, 1),
            (2, 3, 5, -1, 3, -1),
            (3, 2, 1, -1, -1, 1)
        ]
        is_sat, ans = solve_compass(height, width, problem)
        print('has answer:', is_sat)
        if is_sat:
            print(util.stringify_array(ans, str))
    else:
        height, width, nlo, nhi = map(int, sys.argv[1:])
        while True:
            pos = generate_placement(height, width, nlo, nhi)
            problem = generate_compass(height, width, pos, verbose=True)
            if problem is not None:
                print(emit_puzz_link_url(height, width, problem), flush=True)


if __name__ == '__main__':
    _main()
