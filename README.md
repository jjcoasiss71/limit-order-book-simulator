# Limit Order Book Simulator

A limit order book (LOB) simulator built from scratch, starting in Python with the
goal of porting the core matching engine to Java and then C++.

The aim is to reconstruct real market mechanics — how orders are placed, matched,
cancelled, and how prices move as a result — and to use that as a foundation for
exploring market-microstructure ideas (microprice, order-flow imbalance, queue
dynamics, latency, and maker/taker economics).

## Status

Early stage. See [`LOB_simulator_project_brief.md`](LOB_simulator_project_brief.md)
for the full design and the phased build plan.

## Roadmap

1. **Core engine** — `Order` / `OrderBook`, matching, cancel, snapshot
2. **Market metrics** — best bid/ask, spread, mid, microprice, order imbalance, last traded price
3. **Simulation** — synthetic order flow, passive vs aggressive strategies, maker/taker fees
4. **Real data** — reconstruct the book from Level-2 / ITCH data
5. **Visualisation** — depth ladder, price vs microprice, imbalance signal, PnL
6. **Ports** — Java, then C++, with latency benchmarks

## Design notes

- Each side of the book is a **sorted map of price → FIFO queue of orders**, plus a
  flat `order_id → order` dict for O(1) cancellation.
- Prices are stored as **integer ticks** (e.g. cents) to avoid floating-point
  comparison bugs in the matching path.
- Time priority within a price level falls out of the FIFO queue — new orders go to
  the back, matches come off the front.

## Tech

Python 3 (`sortedcontainers`, `collections.deque`). Visualisation via matplotlib /
plotly. Later ports to Java and C++.
