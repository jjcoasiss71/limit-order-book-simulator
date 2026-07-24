import java.util.Random;

public class Benchmark {

    static final int WARMUP  =   100_000;   // discarded — lets JIT compile hot paths
    static final int MEASURE = 1_000_000;   // actual measurement

    public static void main(String[] args) {
        System.out.println("=== LOB Java Benchmark ===\n");

        // warm up — run once and discard the time
        submitBenchmark(WARMUP, false);
        cancelBenchmark(WARMUP, false);

        // measure
        submitBenchmark(MEASURE, true);
        cancelBenchmark(MEASURE, true);
    }


    // ------------------------------------------------------------------ //
    // Benchmark 1: submit() throughput                                     //
    // Measures how fast the matching engine can process incoming orders.   //
    // ------------------------------------------------------------------ //

    static void submitBenchmark(int n, boolean print) {
        OrderBook book = new OrderBook();
        Random rng = new Random(42);
        int mid = 5000;

        // seed some depth so matches actually happen during measurement
        for (int i = 0; i < 500; i++) {
            int price = Math.max(1, mid + (int)(rng.nextGaussian() * 3));
            Side side = rng.nextBoolean() ? Side.BUY : Side.SELL;
            book.submit(new Order(side, price, 10));
        }

        long start = System.nanoTime();
        for (int i = 0; i < n; i++) {
            int price = Math.max(1, mid + (int)(rng.nextGaussian() * 3));
            Side side = rng.nextBoolean() ? Side.BUY : Side.SELL;
            book.submit(new Order(side, price, 10));
        }
        long elapsed = System.nanoTime() - start;

        if (print) printResult("submit (add + match)", n, elapsed);
    }


    // ------------------------------------------------------------------ //
    // Benchmark 2: cancelOrder() throughput                               //
    // Adds N orders then cancels them all — tests the HashMap O(1) path.  //
    // ------------------------------------------------------------------ //

    static void cancelBenchmark(int n, boolean print) {
        OrderBook book = new OrderBook();
        int mid = 5000;

        // add orders at prices unlikely to match each other
        long[] ids = new long[n];
        for (int i = 0; i < n; i++) {
            // alternate BUY far below mid and SELL far above mid — no matches
            int price  = (i % 2 == 0) ? mid - 100 : mid + 100;
            Side side  = (i % 2 == 0) ? Side.BUY : Side.SELL;
            Order order = new Order(side, price, 10);
            book.addOrder(order);
            ids[i] = order.orderId;
        }

        long start = System.nanoTime();
        for (int i = 0; i < n; i++) {
            book.cancelOrder(ids[i]);
        }
        long elapsed = System.nanoTime() - start;

        if (print) printResult("cancel (O(1) lookup)", n, elapsed);
    }


    // ------------------------------------------------------------------ //
    // Formatting                                                           //
    // ------------------------------------------------------------------ //

    static void printResult(String label, int n, long elapsedNs) {
        double nsPerOp     = (double) elapsedNs / n;
        double mOpsPerSec  = n / (elapsedNs / 1e9) / 1_000_000;
        System.out.printf("%-26s  %,8d ops   %6.1f ns/op   %5.2f M ops/sec%n",
                          label, n, nsPerOp, mOpsPerSec);
    }
}
