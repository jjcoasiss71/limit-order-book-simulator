from random import gauss, randint, choice, seed as set_seed

from order_book import OrderBook
from order import Order, Side
from metrics import FillResult, summarise

# ------------------------------------------------------------------ #
# Default fee model (in ticks per share)                              #
# Maker = passive order that rests and gets hit → receives a rebate   #
# Taker = aggressive order that crosses the spread → pays a fee       #
# ------------------------------------------------------------------ #
FEE_MAKER = -0.2   # negative = exchange pays YOU (rebate)
FEE_TAKER =  0.3   # positive = YOU pay the exchange


# ------------------------------------------------------------------ #
# Synthetic order flow generator                                       #
# ------------------------------------------------------------------ #

def random_order(mid: float, sigma: float = 3) -> Order:
    # side is 50/50 by construction — choice() picks uniformly
    side  = choice([Side.BUY, Side.SELL])
    # prices drawn from a normal distribution centred on the midpoint.
    # most land within a few ticks of mid (realistic); some cross the
    # spread and match immediately (aggressive); the rest rest passively.
    price = max(1, round(gauss(mid, sigma)))   # max(1,...) prevents zero/negative ticks
    qty   = randint(1, 10) * 10               # realistic lot sizes: 10, 20, …, 100
    return Order(side, price, qty)


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

def _mid(book: OrderBook, fallback: float) -> float:
    # use the book's live midpoint when available; fall back to the seed
    # price when one or both sides of the book are empty
    return book.midpoint if book.midpoint is not None else fallback


def _run_background(book: OrderBook, n: int, mid_ref: float, sigma: float) -> None:
    # submit n random orders to simulate background market activity
    for _ in range(n):
        book.submit(random_order(_mid(book, mid_ref), sigma))


# ------------------------------------------------------------------ #
# Strategy: PASSIVE                                                    #
# Post a limit buy at the current best bid (join the queue).          #
# Wait n_wait background steps; check if it got fully filled.         #
# ------------------------------------------------------------------ #

def _passive_test(
    book: OrderBook,
    mid_ref: float,
    sigma: float,
    n_wait: int,
    fee_maker: float,
) -> FillResult:

    mid_before = _mid(book, mid_ref)

    # post one tick below best ask (or at mid-1 if no bids exist yet)
    # this keeps the order passive — it sits in the book rather than crossing
    bid_price = book.best_bid if book.best_bid is not None else round(mid_before) - 1
    order = Order(Side.BUY, bid_price, 10)
    book.submit(order)

    # run the market forward — background orders may hit our resting bid
    _run_background(book, n_wait, mid_ref, sigma)

    # O(1) fill check: if our id was removed from book.orders, it fully filled
    filled = order.order_id not in book.orders

    mid_after = _mid(book, mid_ref)

    if not filled:
        # cancel the leftover so it doesn't pollute future iterations
        book.cancel_order(order.order_id)

    return FillResult(
        strategy   = "passive",
        filled     = filled,
        fill_price = bid_price if filled else None,
        mid_before = mid_before,
        mid_after  = mid_after if filled else None,
        fee        = fee_maker if filled else 0.0,
    )


# ------------------------------------------------------------------ #
# Strategy: AGGRESSIVE                                                 #
# Cross the spread by buying at the best ask — immediate execution.   #
# ------------------------------------------------------------------ #

def _aggressive_test(
    book: OrderBook,
    mid_ref: float,
    sigma: float,
    n_wait: int,
    fee_taker: float,
) -> FillResult | None:

    # ensure asks exist to cross; if the book is empty on the ask side,
    # run a few background steps to seed it before giving up
    if book.best_ask is None:
        _run_background(book, 5, mid_ref, sigma)
    if book.best_ask is None:
        return None   # still no asks — skip this trial

    mid_before  = _mid(book, mid_ref)
    ask_price   = book.best_ask
    trades_before = len(book.trades)

    # buy at the ask: this crosses the spread and matches immediately
    order = Order(Side.BUY, ask_price, 10)
    book.submit(order)

    # any new entry in book.trades means our order matched
    new_trades = book.trades[trades_before:]
    filled     = len(new_trades) > 0
    # fill price = the resting ask's price (the maker's price, not ours)
    fill_price = new_trades[0][0] if filled else None

    # run the market forward so we can measure mid_after (for realised spread)
    _run_background(book, n_wait, mid_ref, sigma)
    mid_after = _mid(book, mid_ref)

    return FillResult(
        strategy   = "aggressive",
        filled     = filled,
        fill_price = fill_price,
        mid_before = mid_before,
        mid_after  = mid_after if filled else None,
        fee        = fee_taker if filled else 0.0,
    )


# ------------------------------------------------------------------ #
# Main simulation runner                                               #
# ------------------------------------------------------------------ #

def run(
    n_background: int   = 200,   # orders to seed the book before any strategy tests
    n_test:       int   = 100,   # strategy trials per run (each trial = 1 passive + 1 aggressive)
    seed_price:   int   = 5000,  # starting midpoint in ticks ($50.00 if tick = 1 cent)
    sigma:        float = 3.0,   # std dev of price distribution in ticks
    n_wait:       int   = 10,    # background steps to run after each test order
    fee_maker:    float = FEE_MAKER,
    fee_taker:    float = FEE_TAKER,
    random_seed:  int   = 42,    # fix for reproducibility; change to get different runs
) -> list[FillResult]:

    set_seed(random_seed)
    book = OrderBook()

    # seed phase: build up realistic bid/ask depth before testing begins.
    # 50/50 BUY/SELL with gauss prices → orders that don't cross rest on
    # their respective sides, creating a real spread to interact with.
    _run_background(book, n_background, seed_price, sigma)

    results = []

    for _ in range(n_test):
        # alternate passive and aggressive tests on the SAME evolving book.
        # this keeps both strategies experiencing the same market conditions,
        # making the comparison fair.
        p = _passive_test(book, seed_price, sigma, n_wait, fee_maker)
        a = _aggressive_test(book, seed_price, sigma, n_wait, fee_taker)
        results.append(p)
        if a is not None:
            results.append(a)

    return results


if __name__ == "__main__":
    results = run()
    summarise(results)
