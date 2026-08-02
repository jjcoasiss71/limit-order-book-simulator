"""
Generates a small synthetic ITCH 5.0 binary file with known content.
Use this to verify the parser before pointing it at real NASDAQ data.

Scenario written into the file:
  1. Add Order #1: BUY  100 AAPL @ $50.01  → rests as bid
  2. Add Order #2: SELL 200 AAPL @ $50.02  → rests as ask
  3. Execute #1: 60 shares filled           → #1 now has qty 40 remaining
  4. Cancel  #2: 50 shares removed          → #2 now has qty 150 remaining
  5. Delete  #2: fully removed              → ask side empty

Expected final book state:
  bids: {5001: [order#1, qty=40]}
  asks: {}
"""

import struct
import os

# repo root = parent of this python/ folder, so data paths work from any CWD
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ------------------------------------------------------------------ #
# Helpers for packing individual field types                          #
# ------------------------------------------------------------------ #

def _pack_uint48(value: int) -> bytes:
    # ITCH timestamps are 6-byte big-endian unsigned ints.
    # Pack as 8-byte uint64, then drop the first 2 bytes (which are zero
    # for any realistic nanosecond timestamp within a trading day).
    return struct.pack('>Q', value)[2:]


def _length_prefix(body: bytes) -> bytes:
    # every ITCH message is prefixed with a 2-byte big-endian length
    return struct.pack('>H', len(body)) + body


# ------------------------------------------------------------------ #
# Message builders — one function per message type                    #
# ------------------------------------------------------------------ #

def add_order(order_ref: int, side: bytes, shares: int,
              stock: str, price_itch: int,
              locate: int = 1, timestamp_ns: int = 0) -> bytes:
    """
    Build an Add Order ('A') message body (36 bytes).
    price_itch = real price × 10,000  e.g. $50.01 → 500100
    """
    header = struct.pack('>cHH', b'A', locate, 0)  # type + locate + tracking
    ts     = _pack_uint48(timestamp_ns)
    data   = struct.pack(
        '>QcI8sI',
        order_ref,
        side,                                    # b'B' or b'S'
        shares,
        stock.encode('ascii').ljust(8)[:8],      # 8-byte space-padded ticker
        price_itch,
    )
    return _length_prefix(header + ts + data)    # 2 + 36 = 38 bytes on disk


def execute_order(order_ref: int, executed_shares: int,
                  match_number: int = 1,
                  locate: int = 1, timestamp_ns: int = 0) -> bytes:
    """Build an Execute Order ('E') message body (31 bytes)."""
    header = struct.pack('>cHH', b'E', locate, 0)
    ts     = _pack_uint48(timestamp_ns)
    data   = struct.pack('>QIQ', order_ref, executed_shares, match_number)
    return _length_prefix(header + ts + data)


def cancel_order(order_ref: int, cancelled_shares: int,
                 locate: int = 1, timestamp_ns: int = 0) -> bytes:
    """Build an Order Cancel ('X') message body (23 bytes) — partial cancel."""
    header = struct.pack('>cHH', b'X', locate, 0)
    ts     = _pack_uint48(timestamp_ns)
    data   = struct.pack('>QI', order_ref, cancelled_shares)
    return _length_prefix(header + ts + data)


def delete_order(order_ref: int,
                 locate: int = 1, timestamp_ns: int = 0) -> bytes:
    """Build a Delete Order ('D') message body (19 bytes) — full removal."""
    header = struct.pack('>cHH', b'D', locate, 0)
    ts     = _pack_uint48(timestamp_ns)
    data   = struct.pack('>Q', order_ref)
    return _length_prefix(header + ts + data)


# ------------------------------------------------------------------ #
# Write the test file                                                 #
# ------------------------------------------------------------------ #

if __name__ == '__main__':
    os.makedirs(os.path.join(ROOT, 'data'), exist_ok=True)
    path = os.path.join(ROOT, 'data', 'test.itch')

    # ITCH price encoding: real price × 10,000
    # $50.01 → 500100    $50.02 → 500200
    # Parser converts back: 500100 // 100 = 5001 ticks (cents)

    messages = [
        add_order(   1, b'B', 100, 'AAPL', 500100, timestamp_ns=1_000_000),  # +1ms
        add_order(   2, b'S', 200, 'AAPL', 500200, timestamp_ns=2_000_000),  # +2ms
        execute_order(1,  60, match_number=1,       timestamp_ns=3_000_000),  # +3ms
        cancel_order( 2,  50,                       timestamp_ns=4_000_000),  # +4ms
        delete_order( 2,                            timestamp_ns=5_000_000),  # +5ms
    ]

    with open(path, 'wb') as f:
        for msg in messages:
            f.write(msg)

    print(f"written: {path}  ({sum(len(m) for m in messages)} bytes, {len(messages)} messages)")
    print()
    print("expected final book state:")
    print("  bids: {5001: [qty=40]}  (order #1: 100 - 60 executed)")
    print("  asks: {}                (order #2 fully removed)")
