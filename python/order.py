from dataclasses import dataclass, field
from enum import Enum
import itertools
import time

# 1. Side enum with explicit values
class Side(Enum):
    BUY = 1
    SELL = -1

# Auto-incrementing counter for order IDs
_id_generator = itertools.count(1)

# 2. Order dataclass
@dataclass
class Order:
    # Economic fields first for positional argument support
    side: Side
    price: int  # in ticks -> $50.01 = 5001 ticks, due to float sum error
    quantity: int  # mutable: shrinks on partial fill


    # Automated fields placed last (so positional arguments above work seamlessly)
    order_id: int = field(default_factory=lambda: next(_id_generator), init=False)
    #                        └ fresh incrementing value per order         └ caller can't pass it
    timestamp: int = field(default_factory=time.perf_counter_ns, init=False)  # monotonic ns
    #                        └ fresh clock reading per order         └ caller can't pass it