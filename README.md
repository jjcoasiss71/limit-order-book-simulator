# Limit Order Book Simulator

A price-time priority matching engine built from scratch in Python, then ported to Java and C++ with latency benchmarks. Replays real NASDAQ ITCH 5.0 data, reconstructs live order books, and measures market microstructure signals.

---

## Benchmark

Same matching logic, three languages — measured at 1M operations each after JVM/cache warmup:

| Operation | Python | Java | C++ | Speedup (vs Python) |
|---|---|---|---|---|
| `submit` (add + match) | 1,048 ns — 0.95M ops/s | 90 ns — 11.1M ops/s | 99 ns — 10.1M ops/s | **~11×** |
| `cancel` (O(1) lookup) | 142 ns — 7.1M ops/s | 14 ns — 72.4M ops/s | 30 ns — 33.1M ops/s | **~10×** |

---

## What it does

- **Matching engine** — price-time priority (FIFO within each price level), partial fills, O(log n) best price, O(1) cancel
- **Market metrics** — best bid/ask, spread, midpoint, microprice, order imbalance
- **Strategy simulation** — passive (make) vs aggressive (take), maker/taker fee model, slippage, realised spread, PnL
- **Real data replay** — parses NASDAQ ITCH 5.0 binary protocol, reconstructs a live order book from 5M+ messages
- **Visualisation** — interactive 4-panel plotly dashboard: depth ladder, price/microprice over time, imbalance signal, cumulative PnL

---

## Project structure

```
├── order.py               # Order dataclass + Side enum
├── order_book.py          # Matching engine: add, submit, cancel, match
├── metrics.py             # FillResult dataclass + strategy comparison
├── simulation.py          # Synthetic market, passive/aggressive strategy tests
├── itch_parser.py         # NASDAQ ITCH 5.0 binary parser
├── generate_test_itch.py  # Synthetic ITCH file for parser verification
├── visualise.py           # Interactive plotly dashboard (4 charts)
├── benchmark.py           # Python throughput benchmark
├── java/
│   ├── Order.java
│   ├── Side.java
│   ├── OrderBook.java
│   ├── Benchmark.java     # Java throughput benchmark
│   └── Test.java          # 25 correctness tests
├── cpp/
│   ├── Order.hpp
│   ├── OrderBook.hpp
│   ├── OrderBook.cpp
│   ├── Benchmark.cpp      # C++ throughput benchmark
│   ├── Test.cpp           # 25 correctness tests
│   └── Makefile
└── data/                  # ITCH data file goes here (gitignored, ~3.3 GB)
```

---

## How to run

### Python

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python order_book.py          # matching engine self-tests
python simulation.py          # passive vs aggressive strategy comparison
python itch_parser.py         # replay NASDAQ data (requires data file)
python visualise.py           # interactive dashboard → lob_dashboard.html
python benchmark.py           # throughput benchmark
```

### Java

```bash
cd java
javac Side.java Order.java OrderBook.java Test.java Benchmark.java
java Test        # 25 correctness tests
java Benchmark   # throughput benchmark
```

### C++

```bash
cd cpp
make
./test           # 25 correctness tests
./benchmark      # throughput benchmark
```

---

## Key design decisions

**Prices as integer ticks** — `$50.01` is stored as `5001`. Avoids floating-point comparison bugs in the matching path (e.g. `50.01 != 50.009999...`).

**Two-structure book** — each side is a `SortedDict / TreeMap / std::map` (price → FIFO queue) for O(log n) best price, plus a flat hash map (order ID → order) for O(1) cancel. A heap alone can't support O(1) cancel.

**FIFO within price levels** — a `deque / ArrayDeque / std::deque` per price level gives time priority at no extra cost: new orders go to the back, fills come off the front.

**Recorder vs matcher** — the ITCH parser applies NASDAQ's pre-decided messages directly to the book (`add_order`, `cancel_order`). It never calls `submit`, which would re-run matching decisions NASDAQ already made.

**Microprice** — `(ask × V_bid + bid × V_ask) / (V_bid + V_ask)` — volume-weighted fair value that leans toward the thinner side. More predictive than midpoint for short-horizon price moves.

**Order imbalance** — `(V_bid − V_ask) / (V_bid + V_ask)` — ranges from −1 to +1. A positive OLS slope on the imbalance vs next-price-move scatter confirms it has directional predictive value (a real HFT alpha signal).

---

## NASDAQ data

The visualiser and ITCH parser are tested on `12302019.NASDAQ_ITCH50.gz` (Dec 30 2019, ~3.3 GB). Download from the [NASDAQ FTP](https://emi.nasdaq.com/ITCH/Nasdaq%20ITCH/).

Verification across 5M messages (AAPL): prices in realistic range, 0 crossed-book violations, FIFO preserved, 0 zombie orders.

---

## Tech stack

| Layer | Python | Java | C++ |
|---|---|---|---|
| Sorted map | `sortedcontainers.SortedDict` | `TreeMap` | `std::map` |
| FIFO queue | `collections.deque` | `ArrayDeque` | `std::deque` |
| Hash map | `dict` | `HashMap` | `std::unordered_map` |
| Visualisation | plotly | — | — |
| Timing | `time.perf_counter_ns()` | `System.nanoTime()` | `std::chrono` |
