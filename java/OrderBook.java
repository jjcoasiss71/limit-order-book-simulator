import java.util.*;

public class OrderBook {

    // bids: highest price first — Comparator.reverseOrder() flips TreeMap's default
    private final TreeMap<Integer, ArrayDeque<Order>> bids =
            new TreeMap<>(Comparator.reverseOrder());
    // asks: lowest price first — default TreeMap ordering
    private final TreeMap<Integer, ArrayDeque<Order>> asks =
            new TreeMap<>();
    // O(1) lookup by order ID — needed for cancel and fill-status check
    private final HashMap<Long, Order> orders = new HashMap<>();
    // trade log: each entry is {price, quantity}
    private final List<long[]> trades = new ArrayList<>();


    // ------------------------------------------------------------------ //
    // Public interface                                                     //
    // ------------------------------------------------------------------ //

    // Place an order directly into the book without matching.
    // Used by the ITCH replayer (same role as Python's add_order).
    public void addOrder(Order order) {
        orders.put(order.orderId, order);
        bookFor(order.side)
            .computeIfAbsent(order.price, k -> new ArrayDeque<>())
            .add(order);
    }

    // Match first, then rest any unfilled remainder.
    // Used by the synthetic simulation (same role as Python's submit).
    public void submit(Order order) {
        if (order.side == Side.BUY) matchBuy(order);
        else                        matchSell(order);
        if (order.quantity > 0) addOrder(order);
    }

    // Remove an order by ID. Returns true if found and removed.
    public boolean cancelOrder(long orderId) {
        Order order = orders.remove(orderId);
        if (order == null) return false;

        TreeMap<Integer, ArrayDeque<Order>> book = bookFor(order.side);
        ArrayDeque<Order> level = book.get(order.price);
        if (level != null) {
            level.remove(order);          // O(k) scan within the level — same as Python
            if (level.isEmpty()) book.remove(order.price);
        }
        return true;
    }


    // ------------------------------------------------------------------ //
    // Matching engine                                                      //
    // ------------------------------------------------------------------ //

    private void matchBuy(Order order) {
        while (order.quantity > 0 && !asks.isEmpty()) {
            int bestAsk = asks.firstKey();          // lowest ask — equivalent to asks.peekitem(0)
            if (order.price < bestAsk) break;       // can't afford — stop

            ArrayDeque<Order> level = asks.get(bestAsk);
            Order resting = level.peek();           // front of FIFO queue

            int fill = Math.min(order.quantity, resting.quantity);
            order.quantity   -= fill;
            resting.quantity -= fill;
            recordTrade(bestAsk, fill);

            if (resting.quantity == 0) {
                level.poll();                       // remove fully filled order from queue
                orders.remove(resting.orderId);
                if (level.isEmpty()) asks.remove(bestAsk);
            }
        }
    }

    private void matchSell(Order order) {
        while (order.quantity > 0 && !bids.isEmpty()) {
            int bestBid = bids.firstKey();          // highest bid — firstKey() because reverseOrder
            if (order.price > bestBid) break;       // price too high — stop

            ArrayDeque<Order> level = bids.get(bestBid);
            Order resting = level.peek();

            int fill = Math.min(order.quantity, resting.quantity);
            order.quantity   -= fill;
            resting.quantity -= fill;
            recordTrade(bestBid, fill);

            if (resting.quantity == 0) {
                level.poll();
                orders.remove(resting.orderId);
                if (level.isEmpty()) bids.remove(bestBid);
            }
        }
    }

    private void recordTrade(int price, int quantity) {
        trades.add(new long[]{price, quantity});
    }


    // ------------------------------------------------------------------ //
    // Helpers and getters                                                  //
    // ------------------------------------------------------------------ //

    private TreeMap<Integer, ArrayDeque<Order>> bookFor(Side side) {
        return side == Side.BUY ? bids : asks;
    }

    public Integer bestBid()  { return bids.isEmpty() ? null : bids.firstKey(); }
    public Integer bestAsk()  { return asks.isEmpty() ? null : asks.firstKey(); }
    public int     orderCount() { return orders.size(); }
    public int     tradeCount() { return trades.size(); }
    public List<long[]> trades()  { return trades; }
}
