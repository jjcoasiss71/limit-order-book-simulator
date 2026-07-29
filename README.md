# Limit Order Book Simulator

A price-time priority matching engine built from scratch in Python, then ported to Java and C++ with latency benchmarks. Replays real NASDAQ ITCH 5.0 data, reconstructs live order books, and measures market microstructure signals.

---

## Benchmark

**Identical logic and data structures in all three languages** — measured at 1M operations each after JVM/cache warmup:

| Operation | Python | Java | C++ | Java vs Python | C++ vs Python |
|---|---|---|---|---|---|
| `submit` (add + match) | 1,048 ns — 0.95M ops/s | 90 ns — 11.1M ops/s | 100 ns — 10.0M ops/s | **~12×** | **~11×** |
| `cancel` (hash lookup) | 142 ns — 7.1M ops/s | 14 ns — 72.4M ops/s | 28 ns — 36.0M ops/s | **~10×** | **~5×** |

Note that **Java beats C++ on the cancel path**. That is not a language limit — it is a standard-library data-structure choice. Java's `HashMap` stores entries in a flat array (open addressing), while C++'s `std::unordered_map` is required by the standard to use chained buckets — a separate heap-allocated node per entry, so every lookup chases a pointer into a random cache line. Swapping that one component closes the gap entirely — see the case study below.

---

## Optimization case study: the cancel bottleneck

To confirm the map is the culprit, [`cpp/MapBenchmark.cpp`](cpp/MapBenchmark.cpp) isolates it — same keys, same operations, only the map type differs. Replacing `std::unordered_map` with a flat open-addressing map ([`cpp/OrderMap.hpp`](cpp/OrderMap.hpp), the same idea as Java's `HashMap`), measured on 1M sequential keys:

| Map | insert | find + erase |
|---|---|---|
| `std::unordered_map` | 40 M ops/s | 57 M ops/s |
| flat `OrderMap` | 1,355 M ops/s | 1,532 M ops/s |
| **speed-up** | **~34×** | **~27×** |

Two deliberate caveats, because the isolated number is easy to over-read:

- **End-to-end, the engine's cancel throughput improves ~3×, not 27×.** The map is only one component of a cancel — the price-level `std::deque` removal and deallocation remain (Amdahl's law). Removing an order from a level is still an O(k) linear scan in all three languages; the textbook fix is an **intrusive doubly-linked list** (each order stores its own node pointer) for true O(1) removal.
- **This is a memory-layout win, not a language win.** The same technique speeds up Java identically via a primitive-keyed map (e.g. Agrona's `Long2ObjectHashMap`). The real lesson of this whole benchmark: at this level, **allocation strategy and cache layout dominate — not the language.**

Run it: `cd cpp && make mapbench && ./mapbench`

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
│   ├── OrderMap.hpp       # flat open-addressing map (cancel case study)
│   ├── Benchmark.cpp      # C++ throughput benchmark
│   ├── MapBenchmark.cpp   # std::unordered_map vs flat OrderMap, isolated
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
./mapbench       # cancel-bottleneck case study (std::unordered_map vs flat map)
```

---

## Key design decisions

**Prices as integer ticks** — `$50.01` is stored as `5001`. Avoids floating-point comparison bugs in the matching path (e.g. `50.01 != 50.009999...`).

**Two-structure book** — each side is a `SortedDict / TreeMap / std::map` (price → FIFO queue) for O(log n) best price, plus a hash map (order ID → order) for O(1) cancel *lookup*. A heap alone can't support fast cancel. (Removing the located order from its price-level queue is still an O(k) scan; a production engine would use an intrusive doubly-linked list per level for true O(1) — see the cancel case study above.)

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
| Hash map | `dict` | `HashMap` | `std::unordered_map` (+ flat `OrderMap` case study) |
| Visualisation | plotly | — | — |
| Timing | `time.perf_counter_ns()` | `System.nanoTime()` | `std::chrono` |
