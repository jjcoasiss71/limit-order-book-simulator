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


if __name__ == "__main__":
    book = OrderBook()
    book.submit(Order(Side.SELL, 5001, 100))   # rests on ask
    book.submit(Order(Side.SELL, 5002, 200))   # rests on ask
    book.submit(Order(Side.BUY,  5001, 250))   # buys 100 @ 5001, then 150 rests as a bid
    print("asks:  ", {p: [o.quantity for o in q] for p, q in book.asks.items()})
    print("bids:  ", {p: [o.quantity for o in q] for p, q in book.bids.items()})
    print("trades:", book.trades)
    print("last:  ", book.last_price)
