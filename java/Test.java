public class Test {

    static int passed = 0;
    static int failed = 0;

    public static void main(String[] args) {
        test1_basicMatch();
        test2_partialFill();
        test3_noMatch();
        test4_cancel();
        test5_fifo();
        test6_multiLevelSweep();

        System.out.printf("%n%d passed, %d failed%n", passed, failed);
        if (failed > 0) System.exit(1);
    }

    // ------------------------------------------------------------------ //

    static void test1_basicMatch() {
        // sell 100 @ 5001 rests, then buy 100 @ 5001 crosses it
        OrderBook book = new OrderBook();
        book.addOrder(new Order(Side.SELL, 5001, 100));
        book.submit(new Order(Side.BUY,  5001, 100));

        assertEqual("test1 trades",     1,    book.tradeCount());
        assertEqual("test1 trade price", 5001, (int) book.trades().get(0)[0]);
        assertEqual("test1 trade qty",  100,  (int) book.trades().get(0)[1]);
        assertEqual("test1 orders left", 0,   book.orderCount());
        assertNull ("test1 bestAsk",         book.bestAsk());
    }

    static void test2_partialFill() {
        // sell 50 @ 5001 rests, buy 100 @ 5001 — partial fill, 50 remainder rests as bid
        OrderBook book = new OrderBook();
        book.addOrder(new Order(Side.SELL, 5001, 50));
        book.submit(new Order(Side.BUY,  5001, 100));

        assertEqual("test2 trades",      1,   book.tradeCount());
        assertEqual("test2 trade qty",   50,  (int) book.trades().get(0)[1]);
        assertEqual("test2 orders left", 1,   book.orderCount());   // 50 bid remaining
        assertEqual("test2 bestBid",  5001,   book.bestBid());
        assertNull ("test2 bestAsk",          book.bestAsk());
    }

    static void test3_noMatch() {
        // bid @ 5000, ask @ 5002 — spread exists, nothing should match
        OrderBook book = new OrderBook();
        book.submit(new Order(Side.BUY,  5000, 100));
        book.submit(new Order(Side.SELL, 5002, 100));

        assertEqual("test3 trades",   0,    book.tradeCount());
        assertEqual("test3 bestBid",  5000, book.bestBid());
        assertEqual("test3 bestAsk",  5002, book.bestAsk());
        assertEqual("test3 orders",   2,    book.orderCount());
    }

    static void test4_cancel() {
        // add an order, cancel it, book should be empty
        OrderBook book = new OrderBook();
        Order o = new Order(Side.BUY, 5000, 100);
        book.addOrder(o);
        assertEqual("test4 before cancel", 1, book.orderCount());

        boolean removed = book.cancelOrder(o.orderId);
        assertEqual("test4 cancel returned true", 1, removed ? 1 : 0);
        assertEqual("test4 after cancel",  0, book.orderCount());
        assertNull ("test4 bestBid",           book.bestBid());

        // cancelling a non-existent id should return false
        boolean removedAgain = book.cancelOrder(o.orderId);
        assertEqual("test4 double cancel", 0, removedAgain ? 1 : 0);
    }

    static void test5_fifo() {
        // two bids at same price — first one in must fill first
        OrderBook book = new OrderBook();
        Order first  = new Order(Side.BUY, 5000, 50);
        Order second = new Order(Side.BUY, 5000, 50);
        book.addOrder(first);
        book.addOrder(second);

        // sell 50 — should hit `first` only
        book.submit(new Order(Side.SELL, 5000, 50));

        assertEqual("test5 first filled",  0,  first.quantity);   // fully consumed
        assertEqual("test5 second intact", 50, second.quantity);   // untouched
        assertEqual("test5 orders left",   1,  book.orderCount());
    }

    static void test6_multiLevelSweep() {
        // aggressive buy sweeps two ask levels in one submit
        OrderBook book = new OrderBook();
        book.addOrder(new Order(Side.SELL, 5001, 30));
        book.addOrder(new Order(Side.SELL, 5002, 30));

        // buy 80 @ 5005 — should sweep both levels (30+30=60) and rest 20 @ 5005
        book.submit(new Order(Side.BUY, 5005, 80));

        assertEqual("test6 trades",      2,    book.tradeCount());
        assertEqual("test6 asks empty",  0,    book.bestAsk() == null ? 0 : 1);
        assertEqual("test6 bid resting", 5005, book.bestBid());
    }

    // ------------------------------------------------------------------ //
    // Assertion helpers                                                    //
    // ------------------------------------------------------------------ //

    static void assertEqual(String label, int expected, int actual) {
        if (expected == actual) {
            System.out.printf("  PASS  %s%n", label);
            passed++;
        } else {
            System.out.printf("  FAIL  %s — expected %d, got %d%n", label, expected, actual);
            failed++;
        }
    }

    static void assertNull(String label, Object actual) {
        if (actual == null) {
            System.out.printf("  PASS  %s%n", label);
            passed++;
        } else {
            System.out.printf("  FAIL  %s — expected null, got %s%n", label, actual);
            failed++;
        }
    }
}
