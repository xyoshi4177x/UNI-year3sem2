import org.junit.Test;
import static org.junit.Assert.*;
import java.nio.file.*;
import java.util.List;

public class TestA1 {
    private double avg(java.util.Map<String, Integer> map, List<A1.Proc> procs) {
        long sum = 0;
        for (A1.Proc p : procs)
            sum += map.get(p.pid);
        return procs.isEmpty() ? 0.0 : (double) sum / procs.size();
    }

    @Test
    public void testParseRejectsDuplicatePid() throws Exception {
        Path tmp = Files.createTempFile("dup", ".txt");
        String content = "DISP: 0\nPID: p1\nArrTime: 0\nSrvTime: 1\nPID: p1\nArrTime: 1\nSrvTime: 1\n";
        Files.writeString(tmp, content);
        try {
            A1.parse(tmp);
            fail("Expected ParseException");
        } catch (A1.ParseException expected) {
            // expected
        }
    }

    @Test
    public void testRRAveragesMatchSample1() throws Exception {
        A1.Input in = A1.parse(Path.of("datafile1.txt"));
        A1.RunResult rr = A1.runRR(in, 3);
        double avgTat = avg(rr.metrics.turnaround, in.procs);
        double avgWait = avg(rr.metrics.waiting, in.procs);
        assertEquals(15.20, avgTat, 0.01);
        assertEquals(11.40, avgWait, 0.01);
    }
}
