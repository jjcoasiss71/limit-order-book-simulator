# Glossary — Limit Order Book Simulator

Terminology reference for this project, grouped by topic.

---

## Market Structure

**Exchange**
The venue where buyers and sellers trade. It runs the order book, enforces rules, and executes matches. Examples: NYSE, NASDAQ, CME. Your `OrderBook` class is the core of what an exchange runs.

**Order Book**
A live record of all pending buy and sell limit orders at every price level. Has two sides: the bid side (buyers) and the ask side (sellers).

**Limit Order**
An order with a price condition. e.g. "Buy 100 shares at $50.01 or less." It only executes at that price or better — never worse.

**Matching Engine**
The system that pairs buy and sell orders when their prices overlap. Your `match_buy` and `match_sell` methods are the matching engine.

**Bid**
A buy order. A bid is a buyer advertising "I will buy at this price." The bid side holds all resting buy orders, sorted highest to lowest. Best bid = the highest price any buyer is currently offering.

**Ask (Offer)**
A sell order. A seller advertising "I will sell at this price." The ask side holds all resting sell orders, sorted lowest to highest. Best ask = the lowest price any seller will accept.

**Spread**
The gap between the best ask and best bid: `spread = best ask − best bid`. Measures how wide (expensive) the market is. A tight spread = liquid market. A wide spread = expensive to trade.

**Midpoint**
The halfway point between best bid and best ask: `mid = (bid + ask) / 2`. A naive estimate of fair value.

**Last Traded Price**
The price of the most recent completed trade. This is the number shown on investing apps as the "stock price." It is NOT the current ask price, and NOT set by the exchange.

**Market Maker**
A firm or algorithm that constantly posts both bids and asks near the midpoint, profiting from the spread. They provide liquidity so other traders don't have to wait. Examples: Citadel Securities, Virtu.

---

## Order Types

**Passive Order**
An order posted into the book that waits for someone to match it. It does NOT cross the spread. Adds liquidity to the book. In the fee model, the passive side is the "maker" and receives a rebate.

**Aggressive Order**
An order that immediately crosses the spread and matches a resting order. Removes liquidity from the book. The aggressive side is the "taker" and pays a fee.

**Being Hit**
When an incoming aggressive order matches your resting passive order. e.g. "My bid got hit" = a seller came in and traded against my resting buy order.

**Partial Fill**
When an order matches for less than its full quantity. The remaining quantity stays in the book. e.g. You want to buy 250 but only 100 are available at that price — you get 250 partially filled for 100; the remaining 150 rests.

---

## Price & Time Priority

**Time Priority (FIFO)**
Within a price level, orders are filled in the order they arrived: first in, first served. This is enforced by the `deque` — new orders go to the back, fills come from the front.

**Queue Position**
Where your order sits within its price level's FIFO queue. Earlier = better. If 5 people are all buying at $50.00, the first one to post fills first.

**Tick**
The smallest price increment an exchange allows. For US stocks, typically 1 cent ($0.01). Prices in this project are stored as integers in ticks to avoid floating-point comparison errors. e.g. $50.01 = `5001` ticks.

**Price Level**
All orders resting at the same price. Stored as a FIFO queue (deque) in the book. When the queue empties, the level is deleted.

---

## Market Metrics

**Microprice**
A volume-weighted fair value estimate, smarter than the midpoint:
```
microprice = (ask × V_bid + bid × V_ask) / (V_bid + V_ask)
```
Leans toward the side with less volume — where the price is more likely to move. When imbalance = 0, microprice = midpoint exactly.

**Order Imbalance**
Measures buy vs sell pressure at the top of the book, ranging from −1 to +1:
```
imbalance = (V_bid − V_ask) / (V_bid + V_ask)
```
+1 = all bid volume (buying pressure). −1 = all ask volume (selling pressure). A real alpha signal in HFT — high imbalance tends to predict short-horizon price moves.

**V_bid / V_ask**
Total quantity (volume) resting at the best bid and best ask price levels respectively.

**Slippage**
The difference between the expected price (midpoint at order time) and the actual execution price. For aggressive buys: positive (you paid above mid). For passive buys: negative (you posted below mid).

**Realised Spread**
How much the price moved against you after your fill. For a buy: `fill_price − mid_after`. Positive = price fell after you bought (bad — you were picked off). The key measure of adverse selection cost for passive strategies.

**Fill Probability**
The fraction of passive orders that eventually get matched: `fills / total orders placed`. Aggressive orders have ~100% fill probability by definition; passive orders are lower.

---

## Adverse Selection

**Adverse Selection**
The risk that the person trading against your passive order knows something you don't. If the price is about to fall, informed traders are happy to sell to you at the current price. You get "picked off" — filled right before the price moves against you. Captured by realised spread.

**Being Picked Off**
When your resting passive order fills at an unfavourable moment — typically because an informed trader took the other side. Your fill was "correct" mechanically, but the timing was bad.

---

## Fee Model (Maker/Taker)

**Maker**
The passive side of a trade — the order that was already resting in the book. Makers *add* liquidity and receive a rebate from the exchange.

**Taker**
The aggressive side of a trade — the order that crossed the spread and triggered the match. Takers *remove* liquidity and pay a fee.

**Rebate**
A small payment from the exchange to the maker after their order fills. e.g. $0.002 per share. Negative fee in our model. The exchange collects a higher fee from the taker and pays part of it to the maker.

---

## Data Structures

**SortedDict**
From the `sortedcontainers` library. Like a Python dict but keeps keys sorted automatically. Used for the bid and ask sides of the book so the best price is always instantly accessible (`peekitem(-1)` for best bid, `peekitem(0)` for best ask).

**Deque (Double-Ended Queue)**
From `collections.deque`. A sequence optimised for O(1) appends and pops at *both* ends. Used as the FIFO queue within each price level: new orders append to the back, fills pop from the front. Removal from the middle is O(k) — a known tradeoff.

**Hash Map (dict)**
Python's built-in `dict`. Used as `self.orders` (order_id → Order) for O(1) cancel and fill-status lookup. Direct key lookup by hash — no scanning.

---

## Complexity Notation

**O(1)** — Constant time. Does not depend on the size of the data. e.g. dict lookup by key, deque append/popleft.

**O(log n)** — Logarithmic time. Grows slowly with data size. e.g. SortedDict insert/lookup (n = number of price levels).

**O(k)** — Linear in k. e.g. `deque.remove(order)` scans up to k orders at a price level to find the one to remove.

---

## Python Concepts Used

**`@dataclass`**
A Python decorator that auto-generates `__init__`, `__repr__`, and `__eq__` from the class's field annotations. Used for `Order` and `FillResult`.

**`field(default_factory=..., init=False)`**
Used inside a dataclass to attach extra instructions to a field. `default_factory` calls a function to generate a fresh default per instance (used for `order_id` and `timestamp`). `init=False` hides the field from the constructor so callers can't set it manually.

**`Enum`**
A class for named constants. Used for `Side` (`BUY = 1`, `SELL = -1`). More robust than bare strings — typos become errors at creation, not silent bugs.

**`@property`**
A decorator that lets a method be accessed like an attribute (no parentheses). Used for all Phase 2 metrics (`book.best_bid`, `book.spread`, etc.) — they read as values the book *has*, and are recomputed fresh each access.

**`itertools.count(n)`**
Produces an endless incrementing sequence starting at n. Used to generate unique order IDs: each call to `next(_id_generator)` returns the next integer.

**`time.perf_counter_ns()`**
A monotonic (never-decreasing) high-resolution clock returning nanoseconds. Used for order timestamps. Monotonic = guaranteed never to go backward even if the system clock adjusts. Better than `datetime.now()` for measuring elapsed time.

**venv (Virtual Environment)**
A project-local, isolated copy of Python and its packages. Created with `python3 -m venv .venv`. Keeps this project's dependencies (`sortedcontainers`) separate from your system Python and other projects. Never committed to git — `requirements.txt` is the portable record of what to install.

**`__name__ == "__main__"`**
A guard that runs a block only when the file is executed directly (`python file.py`), not when it's imported by another module. Used to keep self-tests from running on import.
