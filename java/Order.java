public class Order {

    // class-level counter — same role as Python's itertools.count(1)
    private static long nextId = 1;

    public final long   orderId;    // auto-assigned, immutable after construction
    public final Side   side;
    public final int    price;      // in ticks — same convention as Python
    public       int    quantity;   // mutable: shrinks on partial fill
    public final long   timestamp;  // System.nanoTime() — monotonic nanoseconds

    public Order(Side side, int price, int quantity) {
        this.orderId   = nextId++;
        this.side      = side;
        this.price     = price;
        this.quantity  = quantity;
        this.timestamp = System.nanoTime();
    }

    @Override
    public String toString() {
        return String.format("Order{id=%d, side=%s, price=%d, qty=%d}",
                             orderId, side, price, quantity);
    }
}
