"""
ITCH 5.0 parser — reconstructs an OrderBook by replaying real (or synthetic)
NASDAQ exchange messages in sequence.

Key design principle: this is a RECORDER, not a matcher.
NASDAQ already ran the matching engine when the data was recorded.
We apply each message directly to the book's storage layer:
  - add_order()    for Add messages      (order rested — NASDAQ decided)
  - cancel_order() for Delete messages   (order pulled)
  - direct quantity edits for Execute/Cancel (partial fill or partial cancel)
  - NO submit() — that would re-run matching decisions already made
"""

import gzip
import struct
from order_book import OrderBook
from order import Order, Side


class ITCHParser:

    def __init__(self, book: OrderBook, target_stock: str = None) -> None:
        self.book         = book
        # filter to one symbol (e.g. 'AAPL'). None = accept all (mixes every stock — not useful)
        self._target      = target_stock.upper().encode('ascii').ljust(8)[:8] \
                            if target_stock else None
        self.stats = {'add': 0, 'delete': 0, 'cancel': 0,
                      'execute': 0, 'replace': 0, 'skip': 0}

    # ------------------------------------------------------------------ #
    # Public interface                                                     #
    # ------------------------------------------------------------------ #

    def parse_file(self, filepath: str, max_messages: int = None) -> None:
        """
        Read every length-prefixed message from an ITCH binary file.
        Handles both plain binary (.itch) and gzip-compressed (.gz) files
        transparently — no need to decompress to disk first.
        max_messages: stop early after this many messages (useful for testing
        on a large real file without processing all 200M+ messages).
        """
        opener = gzip.open if filepath.endswith('.gz') else open
        count  = 0
        with opener(filepath, 'rb') as f:
            while True:
                if max_messages and count >= max_messages:
                    break

                # read the 2-byte length prefix
                raw_len = f.read(2)
                if len(raw_len) < 2:
                    break                              # end of file
                length = struct.unpack('>H', raw_len)[0]

                # read exactly that many bytes for the message body
                body = f.read(length)
                if len(body) < length:
                    break                              # truncated file

                self._dispatch(body)
                count += 1

        print(f"parsed {count:,} messages")

    def summary(self) -> None:
        """Print a count of each message type processed."""
        print("\n--- ITCH parse summary ---")
        for msg_type, count in self.stats.items():
            print(f"  {msg_type:>8}: {count}")

    # ------------------------------------------------------------------ #
    # Dispatcher                                                          #
    # ------------------------------------------------------------------ #

    def _dispatch(self, body: bytes) -> None:
        # byte 0 is the message type — the prefix that selects which rule to use
        handlers = {
            b'A': self._handle_add,
            b'F': self._handle_add,      # Add Order with MPID — same layout, treat identically
            b'D': self._handle_delete,
            b'X': self._handle_cancel,
            b'E': self._handle_execute,
            b'C': self._handle_execute,  # Execute with price — same layout for our purposes
            b'U': self._handle_replace,
        }
        msg_type = body[0:1]
        handler  = handlers.get(msg_type)
        if handler:
            handler(body)
        else:
            self.stats['skip'] += 1      # system events, stock directory, etc. — safely ignored

    # ------------------------------------------------------------------ #
    # Common header                                                       #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _timestamp(body: bytes) -> int:
        # bytes 5-10 are the 6-byte big-endian nanosecond timestamp
        # pad to 8 bytes on the left so int.from_bytes gives a uint64
        return int.from_bytes(b'\x00\x00' + body[5:11], 'big')

    # ------------------------------------------------------------------ #
    # Message handlers — one per ITCH message type                       #
    # ------------------------------------------------------------------ #

    def _handle_add(self, body: bytes) -> None:
        """
        Add Order ('A' / 'F'): a new order rested in the book.
        Body layout after the common 11-byte header:
          Q  8 bytes  order reference number (NASDAQ's unique order ID)
          c  1 byte   side ('B' or 'S')
          I  4 bytes  shares
          8s 8 bytes  stock symbol (ASCII, space-padded)
          I  4 bytes  price (× 10,000 — divide by 100 to get cents/ticks)
        """
        # unpack_from reads from offset 11 and ignores trailing bytes —
        # safe for both 'A' (36 bytes) and 'F' (40 bytes, has extra MPID field)
        order_ref, side_byte, shares, stock_bytes, price_itch = \
            struct.unpack_from('>QcI8sI', body, 11)

        # filter by stock symbol before doing anything else
        if self._target is not None and stock_bytes != self._target:
            return

        price_ticks = price_itch // 100        # 500100 → 5001 cents
        side        = Side.BUY if side_byte == b'B' else Side.SELL

        # price=0 = free shares — parser error; zero shares = nothing to add
        if price_ticks == 0 or shares == 0:
            return
        # duplicate order_ref: can happen if the file starts mid-session
        if order_ref in self.book.orders:
            return

        # build an Order, then overwrite its auto-increment ID with NASDAQ's ref
        # (the auto-ID was never registered in book.orders, so no cleanup needed)
        order          = Order(side, price_ticks, shares)
        order.order_id = order_ref
        self.book.add_order(order)
        self.stats['add'] += 1

    def _handle_delete(self, body: bytes) -> None:
        """
        Delete Order ('D'): order fully cancelled — remove it from the book.
        Body layout after header:
          Q  8 bytes  order reference number
        """
        order_ref, = struct.unpack('>Q', body[11:])

        if order_ref not in self.book.orders:
            # can happen if the Add arrived before our parsing window started — skip
            return

        self.book.cancel_order(order_ref)
        self.stats['delete'] += 1

    def _handle_cancel(self, body: bytes) -> None:
        """
        Order Cancel ('X'): PARTIAL cancel — reduce quantity, keep order in book.
        Body layout after header:
          Q  8 bytes  order reference number
          I  4 bytes  cancelled shares (how much was removed, not the remainder)
        """
        order_ref, cancelled_shares = struct.unpack('>QI', body[11:])

        order = self.book.orders.get(order_ref)
        if order is None:
            return

        order.quantity -= cancelled_shares

        # if the cancel wiped out all remaining quantity, clean up
        if order.quantity <= 0:
            self.book.cancel_order(order_ref)

        self.stats['cancel'] += 1

    def _handle_execute(self, body: bytes) -> None:
        """
        Execute Order ('E' / 'C'): some or all of a resting order was filled.
        Body layout after header:
          Q  8 bytes  order reference number
          I  4 bytes  executed shares
          Q  8 bytes  match number (exchange's trade ID — useful for Phase 4 analysis)
        """
        # unpack_from: safe for both 'E' (31 bytes) and 'C' (36 bytes, extra price field)
        order_ref, executed_shares, match_number = \
            struct.unpack_from('>QIQ', body, 11)

        order = self.book.orders.get(order_ref)
        if order is None:
            return

        # record the trade at the resting order's price (same rule as our matching engine)
        self.book._record_trade(order.price, executed_shares)

        order.quantity -= executed_shares

        if order.quantity <= 0:               # fully filled — remove from book
            level = self.book._book_for(order.side)[order.price]
            level.remove(order)
            del self.book.orders[order_ref]
            if not level:
                del self.book._book_for(order.side)[order.price]

        self.stats['execute'] += 1

    def _handle_replace(self, body: bytes) -> None:
        """
        Replace Order ('U'): old order is replaced by a new one at a new price/qty.
        Equivalent to: delete old + add new.
        Body layout after header:
          Q  8 bytes  original order reference number
          Q  8 bytes  new order reference number
          I  4 bytes  new shares
          I  4 bytes  new price (× 10,000)
        """
        orig_ref, new_ref, new_shares, new_price_itch = \
            struct.unpack('>QQII', body[11:])

        old_order = self.book.orders.get(orig_ref)
        if old_order is None:
            return

        side        = old_order.side           # side never changes on a replace
        new_price   = new_price_itch // 100

        self.book.cancel_order(orig_ref)       # remove the old order

        new_order          = Order(side, new_price, new_shares)
        new_order.order_id = new_ref
        self.book.add_order(new_order)         # add the replacement

        self.stats['replace'] += 1


# ------------------------------------------------------------------ #
# Self-tests                                                          #
# ------------------------------------------------------------------ #

if __name__ == '__main__':
    import subprocess, sys, os

    # ---- Test 1: synthetic file (known-answer, always runs) ----
    subprocess.run([sys.executable, 'generate_test_itch.py'], check=True)
    print()

    book   = OrderBook()
    parser = ITCHParser(book)
    parser.parse_file('data/test.itch')
    parser.summary()

    print("\n--- final book state ---")
    print("bids:", {p: [o.quantity for o in q] for p, q in book.bids.items()})
    print("asks:", {p: [o.quantity for o in q] for p, q in book.asks.items()})
    print("trades:", book.trades)

    print("\n--- sanity checks ---")
    bid_order = list(book.bids[5001])[0]
    assert bid_order.quantity == 40,      f"expected qty=40, got {bid_order.quantity}"
    assert len(book.asks)     == 0,       f"expected empty asks, got {dict(book.asks)}"
    assert len(book.trades)   == 1,       f"expected 1 trade, got {book.trades}"
    assert book.trades[0]     == (5001, 60), f"expected (5001,60), got {book.trades[0]}"
    print("synthetic test passed ✓")

    # ---- Test 2: real NASDAQ file (runs only if downloaded) ----
    real_file = 'data/12302019.NASDAQ_ITCH50.gz'
    if not os.path.exists(real_file):
        print(f"\nreal file not found at {real_file} — skipping real-data test")
        sys.exit(0)

    print(f"\n{'='*55}")
    print("  REAL DATA TEST — 12 Dec 2019, first 500,000 messages")
    print(f"{'='*55}")

    real_book   = OrderBook()
    real_parser = ITCHParser(real_book, target_stock='AAPL')
    real_parser.parse_file(real_file, max_messages=500_000)
    real_parser.summary()

    print("\n--- book snapshot (top 5 levels each side) ---")
    bids = list(reversed(real_book.bids.items()))[:5]
    asks = list(real_book.asks.items())[:5]
    print("asks (low → high):")
    for price, level in reversed(asks):
        vol = sum(o.quantity for o in level)
        print(f"  ${price/100:>8.2f}  qty={vol:>8,}")
    print("  ----------- spread -----------")
    for price, level in bids:
        vol = sum(o.quantity for o in level)
        print(f"  ${price/100:>8.2f}  qty={vol:>8,}")
    print("\nbest bid / ask:", real_book.best_bid, "/", real_book.best_ask)
    print("spread (ticks):", real_book.spread)
    print("midpoint:      ", real_book.midpoint)
    print("trades so far: ", len(real_book.trades))
    print("last price:    ", real_book.last_price)

    # sanity: prices and spread should be realistic for US equities
    if real_book.spread is not None:
        assert real_book.spread >= 0,   "negative spread — something is wrong"
        assert real_book.best_bid > 0,  "zero/negative best bid"
        print("\nreal-data sanity checks passed ✓")
