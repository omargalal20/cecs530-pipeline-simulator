# Five-Stage Pipeline Simulator

**CECS 530 — Advanced Computer Architecture | CSULB Fall 2026 | Sec 01 | Assignment 3**

A small Python simulator for an in-order, five-stage pipeline (IF, ID, EX, MEM, WB). It prints cycle-by-cycle pipeline tables, finds RAW data dependencies, adds the stalls they cause when there is no forwarding, and compares an instruction sequence before and after reordering.

---

## What It Does

| Question | Task | Result |
|---|---|---|
| 1 | Ideal pipeline, no stalls | 9 cycles, CPI 1.80 |
| 2 | Detect RAW dependencies automatically | 4 dependencies found |
| 3 | Add stalls for RAW hazards, no forwarding | 15 cycles, CPI 3.00 (6 stall cycles) |
| 4 | Reorder instructions to reduce stalls | 11 cycles before and after, 0% improvement |

## Background

| Term | Meaning |
|---|---|
| **Pipeline stages** | IF (fetch), ID (decode and read registers), EX (execute), MEM (memory access), WB (write registers). Each takes one cycle |
| **CPI** | Cycles per instruction: total cycles ÷ number of instructions |
| **RAW hazard** | Read After Write. An instruction reads a register that an earlier instruction has not written yet |
| **Stall** | A cycle where an instruction waits instead of moving to the next stage |
| **Forwarding** | Passing a result straight from EX or MEM to a later instruction. Not available in this assignment |
| **Instruction scheduling** | Reordering independent instructions to fill the gaps that would otherwise be stalls |

For an ideal pipeline, total cycles = stages + instructions − 1 = 5 + 5 − 1 = 9.

## Timing Model

The simulator follows the assumptions given in the assignment:

- Instructions run in program order, one per stage per cycle.
- Registers are read in ID and written in WB. A value written in WB can be read by ID in the same cycle.
- There is no forwarding. A dependent instruction stays in ID until its producer reaches WB.
- While an instruction waits in ID, the instruction behind it waits in IF.
- Only RAW hazards are modeled (WAR and WAW cannot occur in an in-order pipeline). There are no control or structural hazards.
- `LD` is treated like any other instruction: it writes its destination in WB.

For each instruction the scheduler keeps three numbers: the first IF cycle, the first ID cycle and the last ID cycle. EX, MEM and WB follow one cycle after the other.

```
first ID  = after the previous instruction leaves ID
last ID   = max(first ID, WB cycle of each source register's latest writer)
EX, MEM, WB = last ID + 1, + 2, + 3
```

In the tables, a stage name marks the first cycle in that stage and `stall` marks each extra cycle the instruction stays there.

## Repository Structure

```
.
├── README.md
├── .gitignore
├── pipeline_simulator.py    simulator, all four questions
└── output/
    └── program_output.txt   saved output of one run
```

## Getting Started

The code uses only the Python standard library (Python 3.8 or newer). Nothing needs to be installed.

```bash
git clone https://github.com/omargalal20/cecs530-pipeline-simulator.git
cd cecs530-pipeline-simulator
python pipeline_simulator.py
```

On Windows, use `py pipeline_simulator.py` if `python` is not on your PATH.

To save the output:

```bash
python pipeline_simulator.py > output/program_output.txt
```

## Code Overview

| Part | Functions |
|---|---|
| Parsing | `parse_instruction`, `parse_program` |
| Scheduling | `schedule_ideal` (Q1), `schedule_with_stalls` (Q3, Q4) |
| Performance | `total_cycles`, `cpi`, `id_stalls`, `improvement_percent` |
| RAW dependencies | `detect_raw`, `min_stalls` (Q2) |
| Reordering | `reorder`, `order_is_safe`, `best_cycles` (Q4) |
| Output | `format_*` functions build the text; `print_question_*` print each question |
| Questions | `question_1` to `question_4` compute results; `main` runs them in order |

`question_*` functions only compute and return results. Printing is done afterwards by `print_question_*`.

## Results

| Sequence | Cycles | CPI | Stall cycles |
|---|---|---|---|
| Q1: ideal pipeline | 9 | 1.80 | 0 |
| Q3: with RAW stalls, no forwarding | 15 | 3.00 | 6 |
| Q4: original order | 11 | 2.20 | 2 |
| Q4: reordered (I1, I3, I4, I2, I5) | 11 | 2.20 | 2 |

Q4 improvement = (11 − 11) / 11 × 100 = 0%. Moving I3 and I4 between I1 and I2 removes I2's stall but puts I2 directly before I5, so I5 stalls instead. Two independent instructions cannot fill the four gap slots that the two dependencies need. The program also tries every ordering that keeps the dependencies (20 in total) and the best is 11 cycles.

## Limitations

- Only the RAW hazards of the given sequences are handled, with the timing assumptions above.
- The reordering in Q4 is chosen by hand. The brute-force search is a check on it, not a general scheduler.
- Register and instruction names are parsed from simple assembly text (`OP Rd, Rs, Rt` or `LD Rd, offset(Rs)`), not a full instruction set.

## Author

Omar Elhanafy — CECS 530, California State University, Long Beach.