# Limit Order Book Simulator — Project Brief
> This document is intended as context for Claude Code to help build the LOB simulator step by step.

---

## 1. Project Goal

Build a **Limit Order Book (LOB) Simulator** from scratch, starting in Python, with the eventual goal of porting to Java and then C++. This is a portfolio project targeting quant trading firms (Optiver, IMC, SIG, Jane Street, Citadel Securities).

The simulator should reconstruct real market mechanics — how orders are placed, matched, cancelled, and how prices move as a result.

---

## 2. Core Concepts to Implement

### 2.1 What is a Limit Order Book?

| Term | Definition |
|------|-----------|
| **Limit Order** | An order with a price condition. e.g. "Buy 100 shares at $50 or less" |
| **Order Book** | A live record of all pending buy and sell limit orders at every price level |
| **Matching Engine** | The system that matches buy and sell orders when prices overlap |
| **Snapshot** | The state of the order book at a single moment in time |

The order book has two sides:
- **Bid side** — all pending buy orders, sorted highest to lowest price
- **Ask side** — all pending sell orders, sorted lowest to highest price

---

### 2.2 How Orders Work

**Basic flow:**
1. A buy order arrives: "Buy 100 shares @ $50" → enters the bid side of the book
2. A sell order arrives: "Sell 100 shares @ $50" → matching engine finds a match → trade executes → both orders removed
3. If sell price > best bid → no match → sell order sits in ask side and waits
4. Orders can be **cancelled** at any time before they're filled

**Order types to simulate:**
- **Passive order** — posted into the book, waits for someone to match it (adds liquidity)
- **Aggressive order** — crosses the spread and immediately matches an existing order (takes liquidity)

---

### 2.3 Key Market Concepts

#### Best Bid and Ask
- **Best bid** = highest price any buyer is currently willing to pay
- **Best ask** = lowest price any seller is currently willing to accept
- **Spread** = best ask − best bid (the gap between them)
- **Midpoint** = (best bid + best ask) / 2

#### Last Traded Price
The public share price shown on investing apps is the **last traded price** — the most recent successful match. It is NOT the current ask price, and it is NOT set by the exchange.

#### Market Makers
Professional traders (or algorithms) who:
- Constantly post both buy and sell orders near the midpoint
- Profit from the spread (buy low, sell slightly higher)
- Provide liquidity so other traders don't wait forever for a match
- In real markets (e.g. US stocks), retail orders often go to wholesale market makers like Citadel Securities or Virtu via payment for order flow (PFOF)

---

### 2.4 Why Stock Prices Move

- More buyers than sellers → buyers raise their bids to get filled → price goes up
- More sellers than buyers → sellers lower their asks to get filled → price goes down
- It's pure supply and demand — the exchange doesn't pick sides

**When a company is failing:**
- Everyone wants to sell, no one wants to buy
- Sellers keep lowering their price to find a buyer
- Price collapses — the market is voting that the company has no future

---

### 2.5 How Companies Issue Stock

| Event | Description |
|-------|-------------|
| **IPO (Initial Public Offering)** | First time a company issues shares to the public. Company raises money here. |
| **Secondary Market** | All trading after IPO. Company gets nothing — it's just investors trading with each other. |
| **Secondary Offering** | Company issues MORE shares after IPO to raise more cash. Dilutes existing shareholders. Usually causes stock price to drop. |
| **Share Buyback** | Company buys its own shares back from the market, reducing supply. Usually seen as positive. |

> Key insight: After IPO, when you buy a stock on your app, you're buying from another investor (or a market maker) — not from the company.

---

## 3. Advanced Features to Build (from Instagram Quant Post)

These are the features that will make the project stand out for quant firm applications:

### 3.1 Depth-of-Book from Level-2 Data
- **Level-2 data** = real market data showing every price level and volume at each level (not just last price)
- Reconstruct the full order book from this raw data feed
- Track: best bid/ask, queue position, order cancellations, hidden liquidity, trade-through events

**Hidden liquidity (iceberg orders):** Some large orders only show a small portion of their true size publicly. The rest is hidden and revealed as the visible portion gets filled.

**Trade-through:** When a trade executes at a worse price than what was available elsewhere. Illegal in the US under Reg NMS.

### 3.2 Queue Position Tracking
If 10 people all want to buy at $50, orders are filled in **time priority** (first in, first served). Your simulator needs to track where in the queue each order sits — this directly affects fill probability.

### 3.3 Passive vs Aggressive Order Simulation
Measure for each strategy:
- **Fill probability** — how often does a passive order actually get matched?
- **Slippage** — difference between expected price and actual execution price
- **Realised spread** — how much did the market move against you after your trade?

### 3.4 Microprice Formula
A smarter fair value estimate than the midpoint, weighted by volume:

```
microprice = (ask × Vbid + bid × Vask) / (Vbid + Vask)
```

Where:
- `ask` = best ask price
- `bid` = best bid price
- `Vbid` = volume available at best bid
- `Vask` = volume available at best ask

**Why it's better than midpoint:** If there's way more volume on the buy side, fair value is closer to the ask price. The midpoint ignores this information.

### 3.5 Order Imbalance Signal
```
imbalance = (Vbid - Vask) / (Vbid + Vask)
```
- Ranges from -1 (all sellers) to +1 (all buyers)
- Test whether high imbalance predicts short-horizon price moves (next few seconds)
- This is a real alpha signal used in HFT

### 3.6 Latency Simulation
- Insert artificial delays (microseconds to milliseconds) before order insertion
- Observe how queue priority drops as a result
- Measure the PnL impact — this shows why speed matters at HFT firms

### 3.7 Maker/Taker Fee Model
Real exchanges charge differently based on whether you add or remove liquidity:

| Role | Action | Typical Fee |
|------|--------|------------|
| **Maker** | Post a limit order (passive) | Rebate or low fee |
| **Taker** | Cross the spread (aggressive) | Higher fee |

Simulate this and compare profitability of posting vs crossing across different tick sizes.

---

## 4. Build Plan (Python First)

### Phase 1 — Core Engine
- [ ] `Order` class: id, side (buy/sell), price, quantity, timestamp
- [ ] `OrderBook` class: bid side (max-heap), ask side (min-heap)
- [ ] Matching engine: match orders when bid >= ask
- [ ] Cancel order by ID
- [ ] Snapshot: print current state of the book

### Phase 2 — Market Metrics
- [ ] Best bid, best ask, spread, midpoint at any moment
- [ ] Microprice calculation
- [ ] Order imbalance calculation
- [ ] Last traded price tracking

### Phase 3 — Simulation
- [ ] Generate synthetic order flow (random or based on real patterns)
- [ ] Simulate passive vs aggressive order strategies
- [ ] Measure fill probability, slippage, realised spread per strategy
- [ ] Add maker/taker fee model

### Phase 4 — Real Data
- [ ] Connect to Level-2 historical data (Polygon.io or ITCH feed)
- [ ] Reconstruct order book from real data
- [ ] Backtest strategies on real historical order flow

### Phase 5 — Visualisation
- [ ] Dashboard showing order book depth (bid/ask ladders)
- [ ] Price and microprice over time
- [ ] Imbalance signal vs subsequent price movement
- [ ] PnL curves per strategy

### Phase 6 — Port to Java / C++
- [ ] Rebuild core matching engine in Java first
- [ ] Then C++ for maximum performance
- [ ] Benchmark latency improvements across languages

---

## 5. Tech Stack

| Layer | Tool |
|-------|------|
| Language (start) | Python 3.x |
| Data structures | `heapq` for bid/ask sides, `dict` for order lookup by ID |
| Data source | Polygon.io API or NASDAQ ITCH 5.0 feed |
| Visualisation | matplotlib, plotly, or a simple React dashboard |
| Later languages | Java → C++ |

---

## 6. Why This Project Matters for Quant Applications

At firms like Jane Street and IMC:
- **Execution quality matters more than signal quality** at short horizons
- Execution costs (spread, fees, slippage) eat signals alive if you're not careful
- **Quoting logic** (where and how you post orders) matters more than raw price prediction
- Understanding market microstructure — queue dynamics, latency, hidden liquidity — is core to the job

This project demonstrates exactly that understanding.

---

## 7. Differentiators (to Stand Out vs Other Candidates)

- Use **real Level-2 data**, not just synthetic/mocked data
- Implement **microprice** and test imbalance as a predictive signal
- Simulate **latency effects** on queue priority and PnL
- Show **strategy comparison** with actual performance metrics
- Build a **visual dashboard** of order book depth
- Port to multiple languages to show performance awareness

---

*Project brief compiled from foundational learning session. Start with Phase 1 and iterate.*
