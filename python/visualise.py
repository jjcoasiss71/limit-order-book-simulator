#!/usr/bin/env python3
"""
Phase 5 — LOB visualiser (interactive, plotly).

Usage:
    python visualise.py
    python visualise.py --stock AAPL --sample-every 10000 --max-messages 5000000

Writes lob_dashboard.html and opens it in the browser.
"""

import argparse
import gzip
import struct
import webbrowser
from collections import namedtuple
from pathlib import Path

from order_book import OrderBook
from itch_parser import ITCHParser
from simulation import run as run_simulation

# repo root = parent of this python/ folder, so the default data path works from any CWD
ROOT = Path(__file__).resolve().parent.parent


Snapshot = namedtuple('Snapshot', ['msg_count', 'mid', 'microprice', 'imbalance'])


# ------------------------------------------------------------------ #
# Data collection                                                     #
# ------------------------------------------------------------------ #

def collect_snapshots(filepath, target_stock, sample_every, max_messages):
    """Replay the ITCH file and record a snapshot every sample_every messages."""
    book      = OrderBook()
    parser    = ITCHParser(book, target_stock=target_stock)
    snapshots = []

    opener = gzip.open if filepath.endswith('.gz') else open
    count  = 0

    print(f"Replaying {filepath}  stock={target_stock}  sample_every={sample_every:,}")
    with opener(filepath, 'rb') as f:
        while True:
            if max_messages and count >= max_messages:
                break
            raw_len = f.read(2)
            if len(raw_len) < 2:
                break
            length = struct.unpack('>H', raw_len)[0]
            body   = f.read(length)
            if len(body) < length:
                break
            parser._dispatch(body)
            count += 1

            if count % sample_every == 0 and book.midpoint is not None:
                snapshots.append(Snapshot(
                    msg_count  = count,
                    mid        = book.midpoint / 100,
                    microprice = book.microprice / 100 if book.microprice is not None else None,
                    imbalance  = book.imbalance,
                ))

    print(f"  {count:,} messages → {len(snapshots)} snapshots  {len(book.trades):,} trades")
    return book, snapshots


# ------------------------------------------------------------------ #
# Chart data builders                                                 #
# ------------------------------------------------------------------ #

def build_depth_ladder(book, n_levels=12):
    """
    Top n_levels bid/ask prices with their resting volume.
    Bids are stored as negative x values so they render to the left of the
    spread — forming the classic butterfly depth chart.
    """
    bid_prices = list(reversed(book.bids.keys()))[:n_levels]
    ask_prices = list(book.asks.keys())[:n_levels]

    bid_vols   = [-sum(o.quantity for o in book.bids[p]) for p in bid_prices]
    ask_vols   = [ sum(o.quantity for o in book.asks[p]) for p in ask_prices]
    bid_labels = [f'${p/100:.2f}' for p in bid_prices]
    ask_labels = [f'${p/100:.2f}' for p in ask_prices]

    return dict(
        bid_prices=bid_labels, bid_vols=bid_vols,
        ask_prices=ask_labels, ask_vols=ask_vols,
    )


def build_price_series(snapshots):
    """Mid and microprice time series, indexed by message count."""
    xs       = [s.msg_count for s in snapshots]
    mids     = [s.mid       for s in snapshots]
    micro_xs = [s.msg_count  for s in snapshots if s.microprice is not None]
    micros   = [s.microprice for s in snapshots if s.microprice is not None]
    return xs, mids, micro_xs, micros


def build_imbalance_signal(snapshots, lookahead=5):
    """
    Pair each snapshot's imbalance with the price change lookahead snapshots
    ahead. A positive OLS slope means imbalance predicts direction — a real
    alpha signal used by HFT firms.
    """
    pairs = [
        (snapshots[i].imbalance, snapshots[i + lookahead].mid - snapshots[i].mid)
        for i in range(len(snapshots) - lookahead)
        if snapshots[i].imbalance is not None
    ]
    return [p[0] for p in pairs], [p[1] for p in pairs]


def build_pnl_curves(results):
    """Cumulative net PnL over filled trades, per strategy."""
    curves = {}
    for strategy in ('passive', 'aggressive'):
        filled = [r for r in results if r.strategy == strategy and r.filled]
        cum, xs, ys = 0.0, [], []
        for i, r in enumerate(filled, 1):
            cum += r.net_pnl
            xs.append(i)
            ys.append(cum)
        curves[strategy] = (xs, ys)
    return curves


def _linreg(xs, ys):
    """OLS slope and intercept — no scipy dependency."""
    n = len(xs)
    if n < 2:
        return 0.0, 0.0
    sx  = sum(xs)
    sy  = sum(ys)
    sxy = sum(x * y for x, y in zip(xs, ys))
    sxx = sum(x * x for x in xs)
    d   = n * sxx - sx * sx
    slope     = (n * sxy - sx * sy) / d if d else 0.0
    intercept = (sy - slope * sx) / n
    return slope, intercept


# ------------------------------------------------------------------ #
# Interactive mode (plotly)                                           #
# ------------------------------------------------------------------ #

def plot_interactive(depth, xs, mids, micro_xs, micros,
                     imbalances, price_changes, pnl_curves,
                     stock, output_path):
    from plotly.subplots import make_subplots
    import plotly.graph_objects as go

    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            f'Order Book Depth — {stock}',
            f'{stock} Price & Microprice',
            'Imbalance Signal vs Next Price Move',
            'Cumulative PnL: Passive vs Aggressive',
        ),
        horizontal_spacing=0.13,
        vertical_spacing=0.18,
    )

    # --- Chart 1: Depth ladder ---
    # Asks on top (positive x = right), bids below (negative x = left)
    fig.add_trace(go.Bar(
        name='Asks',
        y=depth['ask_prices'], x=depth['ask_vols'],
        orientation='h', marker_color='rgba(239,83,80,0.80)',
    ), row=1, col=1)
    fig.add_trace(go.Bar(
        name='Bids',
        y=depth['bid_prices'], x=depth['bid_vols'],
        orientation='h', marker_color='rgba(38,166,154,0.80)',
    ), row=1, col=1)

    # --- Chart 2: Price over time ---
    fig.add_trace(go.Scatter(
        name='Midpoint', x=xs, y=mids,
        mode='lines', line=dict(color='#4FC3F7', width=2),
    ), row=1, col=2)
    if micros:
        fig.add_trace(go.Scatter(
            name='Microprice', x=micro_xs, y=micros,
            mode='lines', line=dict(color='#FFB300', width=1.5, dash='dot'),
        ), row=1, col=2)

    # --- Chart 3: Imbalance signal ---
    if imbalances:
        slope, intercept = _linreg(imbalances, price_changes)
        x0, x1 = min(imbalances), max(imbalances)
        fig.add_trace(go.Scatter(
            name='Observations', x=imbalances, y=price_changes,
            mode='markers', marker=dict(color='#CE93D8', opacity=0.30, size=4),
            showlegend=False,
        ), row=2, col=1)
        fig.add_trace(go.Scatter(
            name=f'OLS trend  slope={slope:+.5f}',
            x=[x0, x1], y=[slope * x0 + intercept, slope * x1 + intercept],
            mode='lines', line=dict(color='#FF7043', width=2.5),
        ), row=2, col=1)

    # --- Chart 4: PnL curves ---
    pnl_colors = {'passive': '#66BB6A', 'aggressive': '#EF5350'}
    for strategy, (pxs, pys) in pnl_curves.items():
        fig.add_trace(go.Scatter(
            name=strategy.title(),
            x=pxs, y=pys,
            mode='lines', line=dict(color=pnl_colors[strategy], width=2.5),
        ), row=2, col=2)

    fig.update_layout(
        title=dict(
            text=f'LOB Simulator — {stock}  (Dec 30 2019 · NASDAQ ITCH 5.0)',
            font=dict(size=17),
        ),
        template='plotly_dark',
        height=780,
        legend=dict(
            orientation='h', yanchor='bottom', y=-0.14,
            xanchor='center', x=0.5,
        ),
        barmode='overlay',
    )

    fig.update_xaxes(title_text='Volume (shares)',              row=1, col=1)
    fig.update_yaxes(title_text='Price',                        row=1, col=1)
    fig.update_xaxes(title_text='Messages processed',
                     tickformat=',d',                           row=1, col=2)
    fig.update_yaxes(title_text='Price ($)',                    row=1, col=2)
    fig.update_xaxes(title_text='Order imbalance', zeroline=True, row=2, col=1)
    fig.update_yaxes(title_text='ΔPrice (next 5 snapshots, $)',
                     zeroline=True,                             row=2, col=1)
    fig.update_xaxes(title_text='Filled trades',                row=2, col=2)
    fig.update_yaxes(title_text='Cumulative PnL (ticks)',
                     zeroline=True,                             row=2, col=2)

    fig.write_html(output_path)
    print(f"Dashboard written → {output_path}")
    webbrowser.open(f'file://{Path(output_path).resolve()}')


# ------------------------------------------------------------------ #
# Entry point                                                         #
# ------------------------------------------------------------------ #

def main():
    ap = argparse.ArgumentParser(description='LOB Simulator — Phase 5 Visualisation')
    ap.add_argument('--stock',        default='AAPL')
    ap.add_argument('--file',         default=str(ROOT / 'data' / '12302019.NASDAQ_ITCH50.gz'))
    ap.add_argument('--sample-every', type=int, default=10_000, dest='sample_every')
    ap.add_argument('--max-messages', type=int, default=5_000_000, dest='max_messages')
    ap.add_argument('--output',       default='lob_dashboard.html')
    args = ap.parse_args()

    if not Path(args.file).exists():
        print(f"ITCH file not found: {args.file}")
        print("Download it first — see README for the NASDAQ FTP link.")
        return

    book, snapshots = collect_snapshots(
        args.file, args.stock, args.sample_every, args.max_messages,
    )
    depth                      = build_depth_ladder(book)
    xs, mids, micro_xs, micros = build_price_series(snapshots)
    imbalances, price_changes  = build_imbalance_signal(snapshots)

    print("Running strategy simulation...")
    pnl_curves = build_pnl_curves(run_simulation())

    plot_interactive(
        depth, xs, mids, micro_xs, micros,
        imbalances, price_changes, pnl_curves,
        args.stock, args.output,
    )


if __name__ == '__main__':
    main()
