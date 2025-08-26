# COMP2240 Assignment 1 – CPU Scheduling Simulator (Java 21)

## Build & Run
javac A1.java
java A1 datafile1.txt
java A1 datafile2.txt

## Input format
DISP:<int>
PID:pN
ArrTime:<int>
SrvTime:<int>
(repeats; BEGIN/END/EOF markers are ignored if present)

## Algorithms
- FCFS (non-preemptive)
- RR (q=3)
- SRR (per-process q: starts at 3; +1 on each quantum expiry up to 6)
- FB (4 levels 0..3; q=3; new arrivals to level 0; demote on quantum expiry; RR within levels; no boosting)

## Dispatcher rules (implemented exactly as spec)
- Context switch cost = `DISP` at every dispatch (even when the same process is re-dispatched after quantum expiry).
- At dispatch start t1, only consider arrivals with `arrival ≤ t1`.
- If a process is preempted at time t and another arrives at **exactly** t, the new arrival is enqueued **before** the preempted process.
- Tie-breaks naturally follow PID order since input PIDs are non-decreasing with arrivals.

## Output
Matches the given samples exactly:
- Sections in order: FCFS, RR, SRR, FB, Summary
- Timeline lines: `T<start>: <pid>`
- Tables with exact headers, spacing, and 2-dp averages.
