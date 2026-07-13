from dataclasses import dataclass
from typing import Optional


@dataclass
class FillResult:
    """Records the outcome of one test order — one row of data per strategy trial."""

    strategy:   str            # "passive" or "aggressive"
    filled:     bool           # did the order fully execute?
    fill_price: Optional[int]  # execution price in ticks; None if unfilled
    mid_before: Optional[float]  # midpoint when the order was placed
    mid_after:  Optional[float]  # midpoint after N background steps post-placement
    fee:        float          # ticks per share: negative = rebate received, positive = cost paid

    # ------------------------------------------------------------------ #
    # Derived metrics — computed from the six raw fields above            #
    # ------------------------------------------------------------------ #

    @property
    def slippage(self):
        # how far from fair value did we fill?
        # for a buy: positive = we paid ABOVE mid (bad); negative = paid below (good)
        # passive buys will be negative (we post below mid by design)
        # aggressive buys will be positive (we cross to the ask, which is above mid)
        if not self.filled:
            return None
        return self.fill_price - self.mid_before

    @property
    def realised_spread(self):
        # did the price move against us AFTER our fill?
        # for a buy: positive = price fell after we bought (bad — we got picked off)
        #            negative = price rose after we bought (good — we got a fair fill)
        # this is the key measure of adverse selection for passive orders
        if not self.filled:
            return None
        return self.fill_price - self.mid_after

    @property
    def net_pnl(self):
        # net profit/loss per share (in ticks), accounting for fee
        # for a buy: we "own" the asset at mid_after; we paid fill_price + fee to get it
        # positive = profitable (asset worth more than we paid + fees)
        if not self.filled:
            return None
        return self.mid_after - self.fill_price - self.fee


def summarise(results: list) -> None:
    """Print a side-by-side comparison of passive vs aggressive strategy outcomes."""

    print(f"\n{'='*50}")
    print(f"  STRATEGY COMPARISON  (n={len(results)} total trials)")
    print(f"{'='*50}")

    for strategy in ("passive", "aggressive"):
        group  = [r for r in results if r.strategy == strategy]
        filled = [r for r in group if r.filled]
        n      = len(group)

        if n == 0:
            print(f"\n--- {strategy.upper()} ---  (no data)")
            continue

        fill_prob = len(filled) / n

        # averages are only meaningful over filled orders
        def avg(values):
            vals = [v for v in values if v is not None]
            return sum(vals) / len(vals) if vals else None

        avg_slip  = avg(r.slippage        for r in filled)
        avg_real  = avg(r.realised_spread for r in filled)
        avg_pnl   = avg(r.net_pnl         for r in filled)
        avg_fee   = avg(r.fee             for r in filled)

        def fmt(val, decimals=4):
            return f"{val:+.{decimals}f}" if val is not None else "N/A"

        print(f"\n--- {strategy.upper()} ---")
        print(f"  trials:              {n}")
        print(f"  fill probability:    {fill_prob:.1%}  ({len(filled)}/{n})")
        print(f"  avg slippage:        {fmt(avg_slip)} ticks")
        print(f"  avg realised spread: {fmt(avg_real)} ticks")
        print(f"  avg fee/rebate:      {fmt(avg_fee)} ticks per share")
        print(f"  avg net pnl:         {fmt(avg_pnl)} ticks per share")

    print(f"\n{'='*50}\n")
