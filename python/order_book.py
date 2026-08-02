from sortedcontainers import SortedDict
from collections import deque
from order import Order, Side

class OrderBook:
    def __init__(self):
        self.bids  = SortedDict()   # price -> deque of Orders (buy side); keys kept sorted
        self.asks = SortedDict()    # price -> deque of Orders (sell side); keys kept sorted
        self.orders = {}            # order_id -> Order (direct lookup for O(1) cancel)
        self.trades = []            # (price, quantity) executions, in time order
        self.last_price = None      # last traded price (Phase 2 metric)

    def _book_for(self, side):
        # 'is' (not '=='): enum members are singletons, so identity compare is idiomatic
        return self.bids if side is Side.BUY else self.asks

    def add_order(self, order):
        # rests an order in the book (no matching here — that's match_buy/match_sell's job)
        book = self._book_for(order.side)          # pick bid or ask side
        if order.price not in book:                # first order at this price?
            book[order.price] = deque()            # create the empty FIFO queue
        book[order.price].append(order)            # add to the BACK (time priority)
        self.orders[order.order_id] = order        # register for O(1) cancel/lookup

    def cancel_order(self, order_id):
        # pop from self.orders; remove from its level; delete level if empty
        if order_id in self.orders:
            order = self.orders.pop(order_id)       # O(1) lookup and remove from dict
            book = self._book_for(order.side)       # pick bid or ask side
            level = book[order.price]               # O(log n) lookup of price level
            level.remove(order)                     # O(n) remove from deque (could be optimized)
            if not level:                           # if the deque is now empty
                del book[order.price]               # remove the price level from the book

    def _record_trade(self, price, quantity):
        # a trade prints at the RESTING (passive) order's price, not the aggressor's
        self.trades.append((price, quantity))
        self.last_price = price

    def match_buy(self, order):
        # aggressive buy: eat the lowest asks while we still cross AND still have quantity
        while order.quantity > 0 and self.asks:
            best_ask_price, level = self.asks.peekitem(0)     # lowest ask (best for a buyer)
            if best_ask_price > order.price:                  # can't cross → stop matching
                break
            resting = level[0]                                # oldest order at that price (FIFO)
            trade_qty = min(order.quantity, resting.quantity) # can't trade more than smaller side
            order.quantity   -= trade_qty
            resting.quantity -= trade_qty
            self._record_trade(best_ask_price, trade_qty)     # trade at the resting ask's price
            if resting.quantity == 0:                         # resting fully filled → remove it
                level.popleft()
                del self.orders[resting.order_id]
                if not level:                                 # level now empty → drop the price
                    del self.asks[best_ask_price]
        if order.quantity > 0:                                # leftover rests passively as a bid
            self.add_order(order)

    def match_sell(self, order):
        # mirror of match_buy: eat the highest bids while we cross AND have quantity
        while order.quantity > 0 and self.bids:
            best_bid_price, level = self.bids.peekitem(-1)    # highest bid (best for a seller)
            if best_bid_price < order.price:                  # buyer won't pay enough → stop
                break
            resting = level[0]
            trade_qty = min(order.quantity, resting.quantity)
            order.quantity   -= trade_qty
            resting.quantity -= trade_qty
            self._record_trade(best_bid_price, trade_qty)     # trade at the resting bid's price
            if resting.quantity == 0:
                level.popleft()
                del self.orders[resting.order_id]
                if not level:
                    del self.bids[best_bid_price]
        if order.quantity > 0:                                # leftover rests passively as an ask
            self.add_order(order)

    def submit(self, order):
        # single front door: match-then-rest handles both aggressive and passive orders
        if order.side is Side.BUY:
            self.match_buy(order)
        else:
            self.match_sell(order)

    # ------------------------------------------------------------------ #
    # Phase 2 — market metrics (read-only views computed from the book)   #
    # ------------------------------------------------------------------ #

    @property
    def best_bid(self):
        # highest price any buyer is offering; None if the bid side is empty
        if not self.bids:
            return None
        return self.bids.peekitem(-1)[0]   # last key = largest price

    @property
    def best_ask(self):
        # lowest price any seller will accept; None if the ask side is empty
        if not self.asks:
            return None
        return self.asks.peekitem(0)[0]    # first key = smallest price

    @property
    def spread(self):
        # gap between best ask and best bid; None unless BOTH sides exist
        if self.best_bid is None or self.best_ask is None:
            return None
        return self.best_ask - self.best_bid

    @property
    def midpoint(self):
        # naive fair value: halfway between best bid and best ask
        if self.best_bid is None or self.best_ask is None:
            return None
        return (self.best_bid + self.best_ask) / 2

    def _volume_at(self, book, price):
        # total resting quantity sitting at one price level
        return sum(o.quantity for o in book[price])

    @property
    def best_bid_volume(self):
        if not self.bids:
            return None
        return self._volume_at(self.bids, self.best_bid)

    @property
    def best_ask_volume(self):
        if not self.asks:
            return None
        return self._volume_at(self.asks, self.best_ask)

    @property
    def microprice(self):
        # volume-weighted fair value: leans toward the side with LESS volume.
        # microprice = (ask*Vbid + bid*Vask) / (Vbid + Vask)
        if self.best_bid is None or self.best_ask is None:
            return None
        v_bid = self.best_bid_volume
        v_ask = self.best_ask_volume
        total = v_bid + v_ask
        if total == 0:                     # guard: no volume → undefined
            return None
        return (self.best_ask * v_bid + self.best_bid * v_ask) / total

    @property
    def imbalance(self):
        # buy vs sell pressure at the top of book, in [-1, +1].
        # +1 = all bid volume (buying pressure), -1 = all ask volume.
        if self.best_bid is None or self.best_ask is None:
            return None
        v_bid = self.best_bid_volume
        v_ask = self.best_ask_volume
        total = v_bid + v_ask
        if total == 0:
            return None
        return (v_bid - v_ask) / total


if __name__ == "__main__":

    # ------------------------------------------------------------------ #
    # Scenario 1 — baseline: partial fill, leftover rests                 #
    # ------------------------------------------------------------------ #
    # sell 100 @ 5001 rests. sell 200 @ 5002 rests.
    # buy 250 @ 5001 → matches 100 @ 5001 (fully consumes that level),
    # can't reach 5002 (price too high), so 150 leftover rests as a bid.
    print("=== scenario 1: partial fill, leftover rests ===")
    book = OrderBook()
    book.submit(Order(Side.SELL, 5001, 100))
    book.submit(Order(Side.SELL, 5002, 200))
    book.submit(Order(Side.BUY,  5001, 250))
    print("asks:  ", {p: [o.quantity for o in q] for p, q in book.asks.items()})
    print("bids:  ", {p: [o.quantity for o in q] for p, q in book.bids.items()})
    print("trades:", book.trades)
    print("last:  ", book.last_price)
    print("best bid / ask:", book.best_bid, "/", book.best_ask)
    print("spread:", book.spread, "  midpoint:", book.midpoint)
    print("microprice:", book.microprice, "  imbalance:", round(book.imbalance, 4))

    # ------------------------------------------------------------------ #
    # Scenario 2 — cancel: pulled order must vanish from book + id dict   #
    # ------------------------------------------------------------------ #
    # place two bids; cancel the first one by its id.
    # only the second should remain; its level should still exist cleanly.
    # also tests that cancelling an unknown id is a safe no-op.
    print("\n=== scenario 2: cancel ===")
    book2 = OrderBook()
    o1 = Order(Side.BUY, 5000, 100)
    o2 = Order(Side.BUY, 5000, 200)   # same price level, different queue position
    book2.submit(o1)
    book2.submit(o2)
    book2.cancel_order(o1.order_id)
    print("bids after cancel:", {p: [o.quantity for o in q] for p, q in book2.bids.items()})
    print("o1 in orders dict:", o1.order_id in book2.orders)   # expect False
    print("o2 in orders dict:", o2.order_id in book2.orders)   # expect True
    book2.cancel_order(9999)                                    # unknown id — should not crash
    print("cancel unknown id: ok")

    # ------------------------------------------------------------------ #
    # Scenario 3 — sweep: aggressor eats through multiple price levels    #
    # ------------------------------------------------------------------ #
    # three ask levels: 100 @ 5001, 150 @ 5002, 200 @ 5003.
    # buy 400 @ 5003 is priced high enough to cross all three levels.
    # expected trades: 100 @ 5001, 150 @ 5002, 150 @ 5003 (quantity runs out mid-level).
    # the 5001 and 5002 levels are fully consumed; 5003 has 50 remaining.
    print("\n=== scenario 3: sweep across multiple levels ===")
    book3 = OrderBook()
    book3.submit(Order(Side.SELL, 5001, 100))
    book3.submit(Order(Side.SELL, 5002, 150))
    book3.submit(Order(Side.SELL, 5003, 200))
    book3.submit(Order(Side.BUY,  5003, 400))
    print("asks after sweep:", {p: [o.quantity for o in q] for p, q in book3.asks.items()})
    print("bids after sweep:", {p: [o.quantity for o in q] for p, q in book3.bids.items()})
    print("trades:", book3.trades)           # expect [(5001,100),(5002,150),(5003,150)]
    print("last:  ", book3.last_price)       # expect 5003

    # ------------------------------------------------------------------ #
    # Scenario 4 — empty book: all metrics must return None safely        #
    # ------------------------------------------------------------------ #
    print("\n=== scenario 4: empty book metrics ===")
    book4 = OrderBook()
    print("best_bid:", book4.best_bid)       # None
    print("best_ask:", book4.best_ask)       # None
    print("spread:  ", book4.spread)         # None
    print("midpoint:", book4.midpoint)       # None
    print("microprice:", book4.microprice)   # None
    print("imbalance: ", book4.imbalance)    # None
