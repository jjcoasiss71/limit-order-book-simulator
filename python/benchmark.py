"""Python equivalent of Benchmark.java — run after the Java benchmark to compare."""
import time
from random import Random
from order_book import OrderBook
from order import Order, Side

WARMUP  =   100_000
MEASURE = 1_000_000

def submit_benchmark(n, rng, print_result=True):
    book = OrderBook()
    mid  = 5000

    for _ in range(500):
        price = max(1, round(rng.gauss(mid, 3)))
        side  = rng.choice([Side.BUY, Side.SELL])
        book.submit(Order(side, price, 10))

    start = time.perf_counter_ns()
    for _ in range(n):
        price = max(1, round(rng.gauss(mid, 3)))
        side  = rng.choice([Side.BUY, Side.SELL])
        book.submit(Order(side, price, 10))
    elapsed = time.perf_counter_ns() - start

    if print_result:
        ns_per_op    = elapsed / n
        m_ops_per_sec = n / (elapsed / 1e9) / 1_000_000
        print(f"{'submit (add + match)':<26}  {n:>8,} ops   {ns_per_op:6.1f} ns/op   {m_ops_per_sec:5.2f} M ops/sec")

def cancel_benchmark(n, print_result=True):
    book = OrderBook()
    mid  = 5000

    orders = []
    for i in range(n):
        price = mid - 100 if i % 2 == 0 else mid + 100
        side  = Side.BUY  if i % 2 == 0 else Side.SELL
        o = Order(side, price, 10)
        book.add_order(o)
        orders.append(o.order_id)

    start = time.perf_counter_ns()
    for oid in orders:
        book.cancel_order(oid)
    elapsed = time.perf_counter_ns() - start

    if print_result:
        ns_per_op    = elapsed / n
        m_ops_per_sec = n / (elapsed / 1e9) / 1_000_000
        print(f"{'cancel (O(1) lookup)':<26}  {n:>8,} ops   {ns_per_op:6.1f} ns/op   {m_ops_per_sec:5.2f} M ops/sec")

if __name__ == '__main__':
    print("=== LOB Python Benchmark ===\n")
    rng = Random(42)

    # warmup
    submit_benchmark(WARMUP, rng, print_result=False)
    cancel_benchmark(WARMUP, print_result=False)

    # measure
    submit_benchmark(MEASURE, rng, print_result=True)
    cancel_benchmark(MEASURE, print_result=True)
