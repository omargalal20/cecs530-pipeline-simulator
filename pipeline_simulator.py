"""Five-stage pipeline simulator (IF, ID, EX, MEM, WB).

Q1: ideal pipeline, Q2: RAW dependency detection,
Q3: pipeline stalls without forwarding, Q4: instruction scheduling.
Standard library only. Run with: python pipeline_simulator.py
"""

import re
from dataclasses import dataclass
from itertools import permutations

# ---------------------------------------------------------------------------
# Instruction sequences
# ---------------------------------------------------------------------------

# Q1: no dependencies
Q1_PROGRAM = [
    "ADD R1, R2, R3",
    "SUB R4, R5, R6",
    "AND R7, R8, R9",
    "OR  R10, R11, R12",
    "ADD R13, R14, R15",
]

# Q2 and Q3: with RAW dependencies
Q2_PROGRAM = [
    "ADD R1, R2, R3",
    "SUB R4, R1, R5",
    "AND R6, R4, R7",
    "OR  R8, R9, R10",
    "ADD R11, R6, R8",
]

# Q4: original sequence and the manual reordering (by instruction name)
Q4_PROGRAM = [
    "LD  R1, 0(R2)",
    "ADD R3, R1, R4",
    "SUB R5, R6, R7",
    "AND R8, R9, R10",
    "OR  R11, R3, R12",
]
Q4_REORDERED = ["I1", "I3", "I4", "I2", "I5"]


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Instruction:
    name: str  # I1, I2, ...
    text: str  # original assembly text
    dest: str  # register written
    srcs: tuple  # registers read


@dataclass(frozen=True)
class Timing:
    """Cycle numbers of one instruction. Stalls are the gaps between stages."""

    if_start: int  # first IF cycle
    id_start: int  # first ID cycle
    id_end: int  # last ID cycle (stays in ID while waiting)

    @property
    def ex(self):
        return self.id_end + 1

    @property
    def mem(self):
        return self.id_end + 2

    @property
    def wb(self):
        return self.id_end + 3


@dataclass(frozen=True)
class Dependency:
    producer: int  # index of the instruction that writes the register
    consumer: int  # index of the instruction that reads it
    register: str


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def parse_instruction(name, text):
    """Parse 'ADD R1, R2, R3' or 'LD R1, 0(R2)' into dest and source registers."""
    _, operands = text.split(None, 1)
    parts = [p.strip() for p in operands.split(",")]
    srcs = tuple(re.sub(r".*\((\w+)\)", r"\1", p) for p in parts[1:])
    return Instruction(name, " ".join(text.split()), parts[0], srcs)


def parse_program(lines):
    """Name the instructions I1, I2, ... and parse each line."""
    return [parse_instruction(f"I{i}", line) for i, line in enumerate(lines, 1)]


# ---------------------------------------------------------------------------
# Scheduling
# ---------------------------------------------------------------------------


def schedule_ideal(instrs):
    """Ideal pipeline: instruction i is fetched in cycle i+1, no stalls."""
    return [Timing(i + 1, i + 2, i + 2) for i in range(len(instrs))]


def schedule_with_stalls(instrs):
    """In-order pipeline without forwarding.

    An instruction can enter ID once the previous one has left it, and it
    cannot finish ID before the WB cycle of the instructions that write its
    source registers (a WB value can be read in that same cycle).
    """
    timings = []
    wb_of = {}  # register -> WB cycle of its latest writer
    for instr in instrs:
        if not timings:
            if_start, id_start = 1, 2
        else:
            prev = timings[-1]
            if_start = prev.id_start  # fetch starts when the previous instruction leaves IF
            id_start = prev.id_end + 1  # decode starts when the previous one leaves ID
        ready = max((wb_of.get(reg, 0) for reg in instr.srcs), default=0)
        t = Timing(if_start, id_start, max(id_start, ready))
        timings.append(t)
        wb_of[instr.dest] = t.wb
    return timings


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------


def total_cycles(timings):
    """The program ends when the last instruction writes back."""
    return timings[-1].wb


def cpi(timings):
    return total_cycles(timings) / len(timings)


def id_stalls(timings):
    """Cycles each instruction spends waiting in ID."""
    return [t.id_end - t.id_start for t in timings]


def improvement_percent(before, after):
    """Percentage reduction in execution time (same clock, so cycles compare directly)."""
    return (before - after) / before * 100


# ---------------------------------------------------------------------------
# RAW dependencies
# ---------------------------------------------------------------------------


def detect_raw(instrs):
    """Find RAW dependencies: each source register is linked to its nearest earlier writer."""
    deps = []
    for j, instr in enumerate(instrs):
        for reg in dict.fromkeys(instr.srcs):
            for i in range(j - 1, -1, -1):
                if instrs[i].dest == reg:
                    deps.append(Dependency(i, j, reg))
                    break
    return sorted(deps, key=lambda d: (d.producer, d.consumer))


def min_stalls(distance):
    """Stalls for a RAW pair `distance` instructions apart (no forwarding).

    The producer's WB is 3 cycles after its ID. Without stalls, the consumer's
    ID is `distance` cycles after the producer's ID.
    """
    return max(0, 3 - distance)


# ---------------------------------------------------------------------------
# Reordering
# ---------------------------------------------------------------------------


def reorder(instrs, names):
    """Return the instructions in the given order of names, e.g. ['I1', 'I3', ...]."""
    by_name = {instr.name: instr for instr in instrs}
    return [by_name[name] for name in names]


def order_is_safe(original, reordered):
    """True if every pair of conflicting instructions (RAW, WAR, WAW) keeps its original order."""
    position = {instr.name: i for i, instr in enumerate(reordered)}
    for i, a in enumerate(original):
        for b in original[i + 1:]:
            conflict = a.dest in b.srcs or b.dest in a.srcs or a.dest == b.dest
            if conflict and position[a.name] > position[b.name]:
                return False
    return True


def best_cycles(instrs):
    """Fewest total cycles over all safe orderings (brute force). Returns (cycles, safe orderings)."""
    best, safe = None, 0
    for order in permutations(instrs):
        if order_is_safe(instrs, order):
            safe += 1
            cycles = total_cycles(schedule_with_stalls(order))
            best = cycles if best is None else min(best, cycles)
    return best, safe


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def stage_labels(t):
    """Map cycle -> label. The first cycle in a stage shows its name, extra cycles show 'stall'."""
    spans = {
        "IF": (t.if_start, t.id_start - 1),
        "ID": (t.id_start, t.id_end),
        "EX": (t.ex, t.ex),
        "MEM": (t.mem, t.mem),
        "WB": (t.wb, t.wb),
    }
    labels = {}
    for stage, (start, end) in spans.items():
        for cycle in range(start, end + 1):
            labels[cycle] = stage if cycle == start else "stall"
    return labels


def format_pipeline_table(instrs, timings):
    """Cycle-by-cycle table, one row per instruction."""
    rows = [stage_labels(t) for t in timings]
    last = total_cycles(timings)
    width = max(len(label) for row in rows for label in row.values()) + 1
    indent = len("Cycle:") + 1

    header = ("Cycle:".ljust(indent) + "".join(str(c).ljust(width) for c in range(1, last + 1))).rstrip()
    lines = [header, ""]
    for instr, row in zip(instrs, rows):
        cells = "".join(row.get(c, "").ljust(width) for c in range(1, last + 1))
        lines.append(f"{instr.name}:".ljust(indent) + cells.rstrip())
    return "\n".join(lines)


def format_instructions(instrs):
    return "\n".join(f"{i.name}: {i.text}" for i in instrs)


def format_performance(timings):
    n = len(timings)
    total = total_cycles(timings)
    return f"Total cycles = {total}\nCPI = {total} / {n} = {total / n:.2f}"


def format_registers(instrs):
    lines = [f"{'Instr':<7}{'Dest':<6}Sources"]
    for i in instrs:
        lines.append(f"{i.name:<7}{i.dest:<6}{', '.join(i.srcs)}")
    return "\n".join(lines)


def format_raw_dependencies(instrs, deps):
    lines = ["RAW Dependencies Detected:", ""]
    for d in deps:
        lines.append(f"{instrs[d.producer].name} -> {instrs[d.consumer].name} : Register {d.register}")
    return "\n".join(lines)


def format_stall_explanation(instrs, deps):
    lines = ["Instructions that may need stalls (no forwarding):", ""]
    for j, instr in enumerate(instrs):
        mine = [d for d in deps if d.consumer == j]
        if not mine:
            lines.append(f"{instr.name}: no stall, it reads no register written by an earlier instruction")
            continue
        parts = []
        for d in mine:
            dist = j - d.producer
            parts.append(f"{d.register} from {instrs[d.producer].name} (distance {dist}, {min_stalls(dist)} stall(s))")
        worst = max(min_stalls(j - d.producer) for d in mine)
        lines.append(f"{instr.name}: waits for " + "; ".join(parts) + f" -> up to {worst} stall cycle(s)")
    lines.append("")
    lines.append("These counts assume no earlier stalls. Question 3 simulates the exact cycles.")
    return "\n".join(lines)


def format_stall_summary(instrs, timings):
    waits = id_stalls(timings)
    lines = ["Stall cycles (waiting in ID):", ""]
    for instr, wait in zip(instrs, waits):
        if wait:
            lines.append(f"{instr.name}: {wait}")
    lines.append(f"Total stall cycles = {sum(waits)}")
    return "\n".join(lines)


def format_comparison(name_a, timings_a, name_b, timings_b):
    """Side-by-side cycles and CPI of two schedules."""
    width = max(len(name_a), len(name_b)) + 3
    rows = [
        ("Instructions", str(len(timings_a)), str(len(timings_b))),
        ("Total cycles", str(total_cycles(timings_a)), str(total_cycles(timings_b))),
        ("CPI", f"{cpi(timings_a):.2f}", f"{cpi(timings_b):.2f}"),
    ]
    lines = [f"{'':<14}{name_a:<{width}}{name_b}"]
    for label, a, b in rows:
        lines.append(f"{label:<14}{a:<{width}}{b}")
    return "\n".join(lines)


def format_improvement(original_timings, new_timings):
    before, after = total_cycles(original_timings), total_cycles(new_timings)
    pct = improvement_percent(before, after)
    return f"Improvement = ({before} - {after}) / {before} x 100 = {pct:.2f}%"


# ---------------------------------------------------------------------------
# Questions (compute only, no printing)
# ---------------------------------------------------------------------------


def question_1():
    """Ideal five-stage pipeline with no stalls."""
    instrs = parse_program(Q1_PROGRAM)
    return instrs, schedule_ideal(instrs)


def question_2():
    """Detect RAW dependencies between instructions."""
    instrs = parse_program(Q2_PROGRAM)
    return instrs, detect_raw(instrs)


def question_3():
    """Simulate the Q2 sequence with RAW stalls."""
    instrs = parse_program(Q2_PROGRAM)
    return instrs, schedule_with_stalls(instrs)


def question_4():
    """Compare an original and a manually reordered sequence on the Q3 simulator."""
    original = parse_program(Q4_PROGRAM)
    reordered = reorder(original, Q4_REORDERED)
    best, safe_orders = best_cycles(original)
    return {
        "original": original,
        "deps": detect_raw(original),
        "original_timings": schedule_with_stalls(original),
        "reordered": reordered,
        "reordered_timings": schedule_with_stalls(reordered),
        "safe": order_is_safe(original, reordered),
        "best_cycles": best,
        "safe_orders": safe_orders,
    }


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def print_question_1(instrs, timings):
    print("=== Question 1: Ideal Five-Stage Pipeline ===\n")
    print(format_instructions(instrs))
    print()
    print(format_pipeline_table(instrs, timings))
    print()
    print(format_performance(timings))


def print_question_2(instrs, deps):
    print("\n\n=== Question 2: RAW Data Hazard Detection ===\n")
    print(format_instructions(instrs))
    print()
    print(format_registers(instrs))
    print()
    print(format_raw_dependencies(instrs, deps))
    print()
    print(format_stall_explanation(instrs, deps))


def print_question_3(instrs, timings, ideal_timings):
    extra = total_cycles(timings) - total_cycles(ideal_timings)
    print("\n\n=== Question 3: Pipeline Stalls and Performance ===\n")
    print(format_instructions(instrs))
    print()
    print(format_pipeline_table(instrs, timings))
    print()
    print(format_stall_summary(instrs, timings))
    print()
    print(format_performance(timings))
    print()
    print(format_comparison("Ideal (Q1)", ideal_timings, "With stalls (Q3)", timings))
    print(f"\nExtra cycles caused by stalls = {total_cycles(timings)} - {total_cycles(ideal_timings)} = {extra}")


def print_question_4(q4):
    original, reordered = q4["original"], q4["reordered"]
    t_orig, t_new = q4["original_timings"], q4["reordered_timings"]

    print("\n\n=== Question 4: Instruction Scheduling ===\n")
    print("Original sequence:")
    print(format_instructions(original))
    print()
    print(format_raw_dependencies(original, q4["deps"]))
    print()
    print(format_pipeline_table(original, t_orig))
    print()
    print(format_stall_summary(original, t_orig))
    print()
    print(format_performance(t_orig))

    print("\n\nReordered sequence:")
    print(format_instructions(reordered))
    print(f"\nAll dependencies kept in order: {'yes' if q4['safe'] else 'NO'}")
    print()
    print(format_pipeline_table(reordered, t_new))
    print()
    print(format_stall_summary(reordered, t_new))
    print()
    print(format_performance(t_new))

    print("\n")
    print(format_comparison("Original", t_orig, "Reordered", t_new))
    print()
    print(format_improvement(t_orig, t_new))
    print(f"\nChecked all {q4['safe_orders']} orderings that keep the dependencies; "
          f"the fewest cycles possible is {q4['best_cycles']}.")


def main():
    q1_instrs, ideal_timings = question_1()
    q2_instrs, deps = question_2()
    q3_instrs, stalled_timings = question_3()
    q4 = question_4()

    print_question_1(q1_instrs, ideal_timings)
    print_question_2(q2_instrs, deps)
    print_question_3(q3_instrs, stalled_timings, ideal_timings)
    print_question_4(q4)


if __name__ == "__main__":
    main()