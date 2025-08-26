import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class A1 {

    // ====== Data Models ======================================================
    static final class Proc {
        final String pid; // e.g., "p1"
        final int idNum; // numeric part (1)
        final int arrival; // ArrTime (>= 0)
        final int service; // SrvTime (> 0)

        Proc(String pid, int arrival, int service) {
            this.pid = Objects.requireNonNull(pid, "pid");
            this.idNum = parsePidNumber(pid);
            this.arrival = arrival;
            this.service = service;
        }

        @Override
        public String toString() {
            return pid + " ArrTime=" + arrival + " SrvTime=" + service;
        }
    }

    static final class Input {
        final int disp;
        final List<Proc> procs;

        Input(int disp, List<Proc> procs) {
            this.disp = disp;
            this.procs = List.copyOf(procs);
        }
    }

    // Output structs
    static final class Slice {
        final int startTime; // CPU start time (after dispatcher)
        final String pid;

        Slice(int startTime, String pid) {
            this.startTime = startTime;
            this.pid = pid;
        }
    }

    static final class Metrics {
        final Map<String, Integer> completion = new HashMap<>();
        final Map<String, Integer> turnaround = new HashMap<>();
        final Map<String, Integer> waiting = new HashMap<>();
    }

    static final class RunResult {
        final List<Slice> timeline = new ArrayList<>();
        final Metrics metrics = new Metrics();
    }

    // ====== Main =============================================================
    public static void main(String[] args) {
        if (args.length != 1) {
            System.err.println("Usage: java A1 <input-file>");
            System.exit(2);
        }
        Path inputPath = Path.of(args[0]);
        try {
            Input in = parse(inputPath);

            // FCFS (real)
            RunResult fcfs = runFCFS(in);
            printAlgorithmWithResult("FCFS", in.procs, fcfs);

            System.out.println();

            // RR (real; q = 3)
            RunResult rr = runRR(in, 3);
            printAlgorithmWithResult("RR", in.procs, rr);

            System.out.println();

            // SRR (real; per-process q grows 3→6)
            RunResult srr = runSRR(in);
            printAlgorithmWithResult("SRR", in.procs, srr);

            System.out.println();

            // FB (real; 4 levels, q=3, demote on expiry, no boosting)
            RunResult fb = runFB(in);
            printAlgorithmWithResult("FB", in.procs, fb);

            System.out.println();

            // Summary (real)
            printSummary(fcfs, rr, srr, fb, in.procs);

        } catch (IOException e) {
            System.err.println("I/O error reading file: " + e.getMessage());
            System.exit(1);
        } catch (ParseException e) {
            System.err.println("Parse error: " + e.getMessage());
            System.exit(1);
        }
    }

    // ====== FCFS Simulation ==================================================
    private static RunResult runFCFS(Input in) {
        final class PState {
            final Proc p;
            int remaining;
            int completion = -1;

            PState(Proc p) {
                this.p = p;
                this.remaining = p.service;
            }
        }

        List<PState> all = new ArrayList<>();
        for (Proc p : in.procs)
            all.add(new PState(p));

        RunResult out = new RunResult();
        Deque<PState> ready = new ArrayDeque<>();

        int time = 0;
        int nextIdx = 0;
        int finished = 0;
        int n = all.size();

        while (finished < n) {
            // bring in arrivals up to current time
            while (nextIdx < n && all.get(nextIdx).p.arrival <= time) {
                ready.addLast(all.get(nextIdx));
                nextIdx++;
            }

            if (ready.isEmpty()) {
                if (nextIdx < n) {
                    time = all.get(nextIdx).p.arrival;
                    while (nextIdx < n && all.get(nextIdx).p.arrival <= time) {
                        ready.addLast(all.get(nextIdx));
                        nextIdx++;
                    }
                    if (ready.isEmpty())
                        continue;
                } else {
                    break;
                }
            }

            int dispatchStart = time;
            PState cur = ready.removeFirst();
            int cpuStart = dispatchStart + in.disp;
            out.timeline.add(new Slice(cpuStart, cur.p.pid));

            time = cpuStart + cur.remaining; // non-preemptive
            cur.remaining = 0;
            cur.completion = time;
            finished++;
        }

        for (PState s : all) {
            int comp = s.completion;
            out.metrics.completion.put(s.p.pid, comp);
            int tat = comp - s.p.arrival;
            int wait = tat - s.p.service;
            out.metrics.turnaround.put(s.p.pid, tat);
            out.metrics.waiting.put(s.p.pid, wait);
        }

        return out;
    }

    // ====== Round Robin Simulation (q fixed) =================================
    // Dispatcher semantics:
    // - Pay DISP at each selection (including when the same process is
    // re-dispatched after quantum expiry).
    // - At dispatch start time t1, only consider arrivals with arrival <= t1.
    // - If a process is preempted at time t1 and others arrive at the same t1,
    // enqueue those arrivals FIRST, then the preempted proc.
    private static RunResult runRR(Input in, int quantum) {
        final class PState {
            final Proc p;
            int remaining;
            int completion = -1;

            PState(Proc p) {
                this.p = p;
                this.remaining = p.service;
            }
        }

        List<PState> all = new ArrayList<>();
        for (Proc p : in.procs)
            all.add(new PState(p));

        RunResult out = new RunResult();
        Deque<PState> ready = new ArrayDeque<>();

        int time = 0;
        int nextIdx = 0;
        int finished = 0;
        int n = all.size();

        while (finished < n) {
            // If ready is empty, jump to next arrival and pull arrivals at that time
            if (ready.isEmpty()) {
                if (nextIdx < n) {
                    time = Math.max(time, all.get(nextIdx).p.arrival);
                    // pull all arrivals with arrival <= time
                    while (nextIdx < n && all.get(nextIdx).p.arrival <= time) {
                        ready.addLast(all.get(nextIdx));
                        nextIdx++;
                    }
                } else {
                    break;
                }
            }
            if (ready.isEmpty())
                continue; // safety

            int dispatchStart = time;

            // Choose next from ready (only arrivals <= dispatchStart are present)
            PState cur = ready.removeFirst();

            int cpuStart = dispatchStart + in.disp;
            out.timeline.add(new Slice(cpuStart, cur.p.pid));

            int runLen = Math.min(cur.remaining, quantum);
            time = cpuStart + runLen;
            cur.remaining -= runLen;

            if (cur.remaining == 0) {
                // Finished: record completion
                cur.completion = time;
                finished++;
                // Pull arrivals that occurred up to and including 'time'
                while (nextIdx < n && all.get(nextIdx).p.arrival <= time) {
                    ready.addLast(all.get(nextIdx));
                    nextIdx++;
                }
            } else {
                // Quantum expired:
                // 1) Pull arrivals up to and including 'time' FIRST...
                while (nextIdx < n && all.get(nextIdx).p.arrival <= time) {
                    ready.addLast(all.get(nextIdx));
                    nextIdx++;
                }
                // 2) ...then re-enqueue the preempted process at the tail
                ready.addLast(cur);
            }
        }

        // Metrics
        for (PState s : all) {
            int comp = s.completion;
            out.metrics.completion.put(s.p.pid, comp);
            int tat = comp - s.p.arrival;
            int wait = tat - s.p.service;
            out.metrics.turnaround.put(s.p.pid, tat);
            out.metrics.waiting.put(s.p.pid, wait);
        }

        return out;
    }

    // ====== SRR Simulation (per-process quantum grows 3→6) ===================
    private static RunResult runSRR(Input in) {
        final class PState {
            final Proc p;
            int remaining;
            int q; // current quantum for this process
            int completion = -1;

            PState(Proc p) {
                this.p = p;
                this.remaining = p.service;
                this.q = 3;
            }
        }

        List<PState> all = new ArrayList<>();
        for (Proc p : in.procs)
            all.add(new PState(p));

        RunResult out = new RunResult();
        Deque<PState> ready = new ArrayDeque<>();

        int time = 0, nextIdx = 0, finished = 0, n = all.size();

        while (finished < n) {
            // If ready is empty, jump to next arrival and pull arrivals at that time
            if (ready.isEmpty()) {
                if (nextIdx < n) {
                    time = Math.max(time, all.get(nextIdx).p.arrival);
                    while (nextIdx < n && all.get(nextIdx).p.arrival <= time) {
                        ready.addLast(all.get(nextIdx));
                        nextIdx++;
                    }
                } else {
                    break;
                }
            }
            if (ready.isEmpty())
                continue; // safety

            int dispatchStart = time;

            // Choose next from ready (only arrivals <= dispatchStart are present)
            PState cur = ready.removeFirst();

            // Dispatcher cost
            int cpuStart = dispatchStart + in.disp;
            out.timeline.add(new Slice(cpuStart, cur.p.pid));

            // Run up to this process's current quantum
            int runLen = Math.min(cur.remaining, cur.q);
            time = cpuStart + runLen;
            cur.remaining -= runLen;

            if (cur.remaining == 0) {
                // Finished
                cur.completion = time;
                finished++;

                // Pull any arrivals that occurred up to and including 'time'
                while (nextIdx < n && all.get(nextIdx).p.arrival <= time) {
                    ready.addLast(all.get(nextIdx));
                    nextIdx++;
                }
            } else {
                // Quantum expired:
                // 1) Pull arrivals first (<= 'time', including exactly at 'time')
                while (nextIdx < n && all.get(nextIdx).p.arrival <= time) {
                    ready.addLast(all.get(nextIdx));
                    nextIdx++;
                }
                // 2) Increase this process's quantum by 1 (cap at 6)
                cur.q = Math.min(cur.q + 1, 6);
                // 3) Re-enqueue the preempted process at the tail (after any new arrivals)
                ready.addLast(cur);
            }
        }

        // Metrics
        for (PState s : all) {
            int comp = s.completion;
            int tat = comp - s.p.arrival;
            int wait = tat - s.p.service;
            out.metrics.completion.put(s.p.pid, comp);
            out.metrics.turnaround.put(s.p.pid, tat);
            out.metrics.waiting.put(s.p.pid, wait);
        }
        return out;
    }

    // ====== FB Simulation (4 levels, q=3, demote on expiry, no boosting) ======
    private static RunResult runFB(Input in) {
        final class PState {
            final Proc p;
            int remaining;
            int level; // 0 (highest) .. 3 (lowest)
            int completion = -1;

            PState(Proc p) {
                this.p = p;
                this.remaining = p.service;
                this.level = 0;
            }
        }

        List<PState> all = new ArrayList<>();
        for (Proc p : in.procs)
            all.add(new PState(p));

        RunResult out = new RunResult();
        @SuppressWarnings("unchecked")
        Deque<PState>[] q = new Deque[4];
        for (int i = 0; i < 4; i++)
            q[i] = new ArrayDeque<>();

        int time = 0, nextIdx = 0, finished = 0, n = all.size();
        final int quantum = 3;

        while (finished < n) {
            // If all queues empty, jump to next arrival and enqueue to level 0
            if (q[0].isEmpty() && q[1].isEmpty() && q[2].isEmpty() && q[3].isEmpty()) {
                if (nextIdx < n) {
                    time = Math.max(time, all.get(nextIdx).p.arrival);
                    while (nextIdx < n && all.get(nextIdx).p.arrival <= time) {
                        q[0].addLast(all.get(nextIdx));
                        nextIdx++;
                    }
                } else {
                    break;
                }
            }
            if (q[0].isEmpty() && q[1].isEmpty() && q[2].isEmpty() && q[3].isEmpty())
                continue;

            // Pick highest non-empty level
            int lvl = 0;
            while (lvl < 4 && q[lvl].isEmpty())
                lvl++;
            PState cur = q[lvl].removeFirst();

            int dispatchStart = time;
            int cpuStart = dispatchStart + in.disp;
            out.timeline.add(new Slice(cpuStart, cur.p.pid));

            // Run for min(remaining, quantum)
            int runLen = Math.min(cur.remaining, quantum);
            time = cpuStart + runLen;
            cur.remaining -= runLen;

            if (cur.remaining == 0) {
                // Finished
                cur.completion = time;
                finished++;
                // Pull arrivals up to and including 'time' into level 0
                while (nextIdx < n && all.get(nextIdx).p.arrival <= time) {
                    q[0].addLast(all.get(nextIdx));
                    nextIdx++;
                }
            } else {
                // Quantum expired: arrivals first (<= time), then demote and enqueue at tail
                while (nextIdx < n && all.get(nextIdx).p.arrival <= time) {
                    q[0].addLast(all.get(nextIdx)); // new arrivals always enter level 0
                    nextIdx++;
                }
                cur.level = Math.min(cur.level + 1, 3); // demote, bottom queue stays RR
                q[cur.level].addLast(cur);
            }
        }

        // Metrics
        for (PState s : all) {
            int comp = s.completion;
            int tat = comp - s.p.arrival;
            int wait = tat - s.p.service;
            out.metrics.completion.put(s.p.pid, comp);
            out.metrics.turnaround.put(s.p.pid, tat);
            out.metrics.waiting.put(s.p.pid, wait);
        }
        return out;
    }

    // ====== Printing =========================================================
    private static void printAlgorithmWithResult(String name, List<Proc> procs, RunResult r) {
        System.out.println(name + ":");
        for (Slice s : r.timeline) {
            System.out.println("T" + s.startTime + ": " + s.pid);
        }
        System.out.println();
        System.out.printf("%-8s%-20s%-14s%n", "Process", "Turnaround Time", "Waiting Time");
        for (Proc p : procs) {
            int tat = r.metrics.turnaround.getOrDefault(p.pid, 0);
            int wt = r.metrics.waiting.getOrDefault(p.pid, 0);
            System.out.printf("%-8s%-20d%-14d%n", p.pid, tat, wt);
        }
    }

    private static void printSummary(RunResult fcfs, RunResult rr, RunResult srr, RunResult fb, List<Proc> procs) {
        System.out.println("Summary");
        System.out.printf("%-10s%-28s%-14s%n", "Algorithm", "Average Turnaround Time", "Waiting Time");
        printSummaryRow("FCFS", avg(fcfs.metrics.turnaround, procs), avg(fcfs.metrics.waiting, procs));
        printSummaryRow("RR", avg(rr.metrics.turnaround, procs), avg(rr.metrics.waiting, procs));
        printSummaryRow("SRR", avg(srr.metrics.turnaround, procs), avg(srr.metrics.waiting, procs));
        printSummaryRow("FB", avg(fb.metrics.turnaround, procs), avg(fb.metrics.waiting, procs));
    }

    private static double avg(Map<String, Integer> map, List<Proc> procs) {
        long sum = 0;
        for (Proc p : procs)
            sum += map.getOrDefault(p.pid, 0);
        return procs.isEmpty() ? 0.0 : (sum * 1.0) / procs.size();
    }

    private static void printSummaryRow(String algo, double avgTAT, double avgWT) {
        System.out.printf("%-10s%-28.2f%-14.2f%n", algo, avgTAT, avgWT);
    }

    // ====== Parser ===========================================================
    // Accepts files with optional markers like BEGIN/END/EOF on their own lines.
    // Expected key/value lines:
    // DISP: <int>
    // PID: pN
    // ArrTime: <int>
    // SrvTime: <int>
    static Input parse(Path file) throws IOException, ParseException {
        List<String> lines = Files.readAllLines(file);

        Integer disp = null;
        final Pattern keyVal = Pattern.compile("^\\s*([A-Za-z]+)\\s*:\\s*(\\S.*)?\\s*$");
        final List<Proc> procs = new ArrayList<>();

        String curPid = null;
        Integer curArr = null;
        Integer curSrv = null;

        int lineNo = 0;
        for (String raw : lines) {
            lineNo++;
            String line = raw.trim();
            if (line.isEmpty())
                continue;

            // ignore block markers without a colon
            if (!line.contains(":")) {
                String upper = line.toUpperCase(Locale.ROOT);
                if (upper.equals("BEGIN") || upper.equals("END") || upper.equals("EOF"))
                    continue;
                throw new ParseException(lineNo, "Malformed line (expected Key: Value): " + raw);
            }

            Matcher m = keyVal.matcher(line);
            if (!m.matches()) {
                throw new ParseException(lineNo, "Malformed line (expected Key: Value): " + raw);
            }

            String key = m.group(1);
            String value = m.group(2) == null ? "" : m.group(2).trim();

            switch (key.toUpperCase(Locale.ROOT)) {
                case "DISP":
                    if (disp != null)
                        throw new ParseException(lineNo, "DISP specified more than once.");
                    disp = parseNonNegativeInt(value, lineNo, "DISP");
                    break;

                case "PID":
                    // finalize previous proc block if any
                    if (curPid != null) {
                        ensureProcCompleteAndAdd(procs, curPid, curArr, curSrv, lineNo);
                        curPid = null;
                        curArr = null;
                        curSrv = null;
                    }
                    if (value.isEmpty())
                        throw new ParseException(lineNo, "PID value missing.");
                    curPid = value;
                    break;

                case "ARRTIME":
                    if (curPid == null)
                        throw new ParseException(lineNo, "ArrTime before any PID block.");
                    curArr = parseNonNegativeInt(value, lineNo, "ArrTime");
                    break;

                case "SRVTIME":
                    if (curPid == null)
                        throw new ParseException(lineNo, "SrvTime before any PID block.");
                    curSrv = parsePositiveInt(value, lineNo, "SrvTime");
                    break;

                default:
                    throw new ParseException(lineNo, "Unknown key: " + key);
            }
        }

        if (curPid != null) {
            ensureProcCompleteAndAdd(procs, curPid, curArr, curSrv, lineNo + 1);
        }
        if (disp == null)
            throw new ParseException(0, "Missing required DISP line.");

        // Enforce non-decreasing arrivals (safety)
        for (int i = 1; i < procs.size(); i++) {
            if (procs.get(i).arrival < procs.get(i - 1).arrival) {
                throw new ParseException(0, String.format(
                        "Arrival times must be non-decreasing: %s at %d before %s at %d",
                        procs.get(i).pid, procs.get(i).arrival,
                        procs.get(i - 1).pid, procs.get(i - 1).arrival));
            }
        }
        return new Input(disp, procs);
    }

    private static void ensureProcCompleteAndAdd(List<Proc> out, String pid, Integer arr, Integer srv, int lineNo)
            throws ParseException {
        if (arr == null)
            throw new ParseException(lineNo, "Missing ArrTime for process " + pid);
        if (srv == null)
            throw new ParseException(lineNo, "Missing SrvTime for process " + pid);
        out.add(new Proc(pid, arr, srv));
    }

    static int parsePidNumber(String pid) {
        Matcher m = Pattern.compile("^p(\\d+)$").matcher(pid);
        if (!m.matches())
            throw new IllegalArgumentException("PID must be of form p<number>, got: " + pid);
        try {
            return Integer.parseInt(m.group(1));
        } catch (NumberFormatException nfe) {
            throw new IllegalArgumentException("PID numeric part too large: " + pid);
        }
    }

    private static int parseNonNegativeInt(String s, int lineNo, String field) throws ParseException {
        int v = parseIntStrict(s, lineNo, field);
        if (v < 0)
            throw new ParseException(lineNo, field + " must be >= 0, got " + v);
        return v;
    }

    private static int parsePositiveInt(String s, int lineNo, String field) throws ParseException {
        int v = parseIntStrict(s, lineNo, field);
        if (v <= 0)
            throw new ParseException(lineNo, field + " must be > 0, got " + v);
        return v;
    }

    private static int parseIntStrict(String s, int lineNo, String field) throws ParseException {
        try {
            return Integer.parseInt(s);
        } catch (NumberFormatException nfe) {
            throw new ParseException(lineNo, "Invalid integer for " + field + ": '" + s + "'");
        }
    }

    // Lightweight checked exception for precise error messages
    static final class ParseException extends Exception {
        ParseException(int line, String msg) {
            super((line > 0 ? ("line " + line + ": ") : "") + msg);
        }
    }
}
