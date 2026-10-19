"""Chart Generator: Creates authentic TradingView Pro and Binance App competitor-style charts."""
import os
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import itertools
import pandas as pd
import numpy as np
import matplotlib
# Headless server backend
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.patches as patches
import matplotlib.lines as lines
import matplotlib.font_manager as fm
import mplfinance as mpf
from src.technical_analysis import TradeSetup
from src.market_scanner import compute_rsi

logger = logging.getLogger(__name__)

# Register real Windows Segoe UI & Arial fonts
for font_file in ("segoeui.ttf", "segoeuib.ttf", "arial.ttf", "arialbd.ttf"):
    font_path = Path("C:/Windows/Fonts") / font_file
    if font_path.exists():
        try:
            fm.fontManager.addfont(str(font_path))
        except Exception:
            pass


def fmt_price(p: float, use_comma: bool = False) -> str:
    """Formats prices cleanly according to magnitude."""
    if p is None or np.isnan(p):
        return "0.00"
    if p >= 1000:
        res = f"{p:,.1f}"
    elif p >= 10:
        res = f"{p:,.2f}"
    elif p >= 1:
        res = f"{p:,.4f}"
    elif p >= 0.001:
        res = f"{p:,.5f}"
    else:
        res = f"{p:,.7f}"
    
    if use_comma:
        return res.replace(",", "X").replace(".", ",").replace("X", ".")
    return res


def fmt_compact_vol(v: float, use_comma: bool = False) -> str:
    """Format volume as 1.23B, 45.6M, 789K."""
    if v is None or np.isnan(v):
        return "0"
    if v >= 1_000_000_000:
        res = f"{v / 1_000_000_000:.2f}B"
    elif v >= 1_000_000:
        res = f"{v / 1_000_000:.2f}M"
    elif v >= 1_000:
        res = f"{v / 1_000:.1f}K"
    else:
        res = f"{v:.0f}"
    
    if use_comma:
        return res.replace(".", ",")
    return res


def draw_binance_watermark(ax):
    """Draws official subtle Binance diamond logo and text in center of chart."""
    cx, cy = 0.44, 0.50
    # Central diamond
    d_center = patches.RegularPolygon((cx, cy), numVertices=4, radius=0.045, orientation=0, transform=ax.transAxes, facecolor="#ffffff", alpha=0.035)
    # Inner hole
    d_hole = patches.RegularPolygon((cx, cy), numVertices=4, radius=0.022, orientation=0, transform=ax.transAxes, facecolor="#202630", alpha=1.0)
    # Middle diamond inside hole
    d_mid = patches.RegularPolygon((cx, cy), numVertices=4, radius=0.010, orientation=0, transform=ax.transAxes, facecolor="#ffffff", alpha=0.035)
    
    # 4 satellite diamond points (top, bottom, left, right)
    d_top = patches.RegularPolygon((cx, cy + 0.055), numVertices=4, radius=0.012, orientation=0, transform=ax.transAxes, facecolor="#ffffff", alpha=0.035)
    d_bot = patches.RegularPolygon((cx, cy - 0.055), numVertices=4, radius=0.012, orientation=0, transform=ax.transAxes, facecolor="#ffffff", alpha=0.035)
    d_left = patches.RegularPolygon((cx - 0.055, cy), numVertices=4, radius=0.012, orientation=0, transform=ax.transAxes, facecolor="#ffffff", alpha=0.035)
    d_right = patches.RegularPolygon((cx + 0.055, cy), numVertices=4, radius=0.012, orientation=0, transform=ax.transAxes, facecolor="#ffffff", alpha=0.035)

    ax.add_patch(d_center)
    ax.add_patch(d_hole)
    ax.add_patch(d_mid)
    ax.add_patch(d_top)
    ax.add_patch(d_bot)
    ax.add_patch(d_left)
    ax.add_patch(d_right)

    # BINANCE Text
    ax.text(
        cx + 0.12, cy, "BINANCE",
        transform=ax.transAxes,
        fontsize=24, fontweight="bold", color="#ffffff",
        alpha=0.035, ha="left", va="center",
    )


def draw_vector_toolbar(fig):
    """Draws authentic Binance drawing tool icons using vector shapes on far right."""
    tb_x = 0.966
    
    # Tool 1: Crosshair cursor (circle with cross)
    y1 = 0.810
    circle = patches.Circle((tb_x, y1), 0.006, transform=fig.transFigure, fill=False, edgecolor="#848e9c", linewidth=1.0)
    fig.patches.append(circle)
    line_h = lines.Line2D([tb_x - 0.009, tb_x + 0.009], [y1, y1], transform=fig.transFigure, color="#848e9c", linewidth=1.0)
    line_v = lines.Line2D([tb_x, tb_x], [y1 - 0.009, y1 + 0.009], transform=fig.transFigure, color="#848e9c", linewidth=1.0)
    fig.lines.extend([line_h, line_v])

    # Tool 2: Trendline (diagonal line with endpoints)
    y2 = 0.730
    tl = lines.Line2D([tb_x - 0.008, tb_x + 0.008], [y2 - 0.008, y2 + 0.008], transform=fig.transFigure, color="#848e9c", linewidth=1.2)
    p1 = patches.Circle((tb_x - 0.008, y2 - 0.008), 0.002, transform=fig.transFigure, facecolor="#848e9c")
    p2 = patches.Circle((tb_x + 0.008, y2 + 0.008), 0.002, transform=fig.transFigure, facecolor="#848e9c")
    fig.lines.append(tl)
    fig.patches.extend([p1, p2])

    # Tool 3: Pitchfork / Fib (3 horizontal parallel tines)
    y3 = 0.650
    for dy in (-0.006, 0.0, 0.006):
        l = lines.Line2D([tb_x - 0.008, tb_x + 0.008], [y3 + dy, y3 + dy], transform=fig.transFigure, color="#848e9c", linewidth=1.1)
        fig.lines.append(l)
    v_stem = lines.Line2D([tb_x - 0.008, tb_x - 0.008], [y3 - 0.006, y3 + 0.006], transform=fig.transFigure, color="#848e9c", linewidth=1.1)
    fig.lines.append(v_stem)

    # Tool 4: Rectangle / Shapes
    y4 = 0.570
    rect = patches.Rectangle((tb_x - 0.008, y4 - 0.006), 0.016, 0.012, transform=fig.transFigure, fill=False, edgecolor="#848e9c", linewidth=1.2)
    fig.patches.append(rect)

    # Tool 5: Text Tool (T)
    y5 = 0.490
    fig.text(tb_x, y5, "T", fontsize=11, color="#848e9c", fontweight="bold", ha="center", va="center")

    # Tool 6: Ruler / Measure
    y6 = 0.410
    ruler = patches.Rectangle((tb_x - 0.008, y6 - 0.005), 0.016, 0.010, transform=fig.transFigure, fill=False, edgecolor="#848e9c", linewidth=1.1)
    fig.patches.append(ruler)
    for dx in (-0.004, 0.0, 0.004):
        rl = lines.Line2D([tb_x + dx, tb_x + dx], [y6 + 0.001, y6 + 0.005], transform=fig.transFigure, color="#848e9c", linewidth=0.8)
        fig.lines.append(rl)

    # Tool 7: Magnet (Horseshoe U shape)
    y7 = 0.330
    arc = patches.Arc((tb_x, y7), 0.014, 0.014, angle=0, theta1=180, theta2=360, transform=fig.transFigure, color="#848e9c", linewidth=1.2)
    l_arm = lines.Line2D([tb_x - 0.007, tb_x - 0.007], [y7, y7 + 0.006], transform=fig.transFigure, color="#848e9c", linewidth=1.2)
    r_arm = lines.Line2D([tb_x + 0.007, tb_x + 0.007], [y7, y7 + 0.006], transform=fig.transFigure, color="#848e9c", linewidth=1.2)
    fig.patches.append(arc)
    fig.lines.extend([l_arm, r_arm])

    # Tool 8: Eye (Hide/Show)
    y8 = 0.250
    eye_top = patches.Arc((tb_x, y8 - 0.004), 0.018, 0.014, angle=0, theta1=30, theta2=150, transform=fig.transFigure, color="#848e9c", linewidth=1.2)
    eye_bot = patches.Arc((tb_x, y8 + 0.004), 0.018, 0.014, angle=0, theta1=210, theta2=330, transform=fig.transFigure, color="#848e9c", linewidth=1.2)
    pupil = patches.Circle((tb_x, y8), 0.0025, transform=fig.transFigure, facecolor="#848e9c")
    fig.patches.extend([eye_top, eye_bot, pupil])

    # Tool 9: Trash Can
    y9 = 0.170
    bin_body = patches.Polygon([[tb_x - 0.006, y9 + 0.004], [tb_x + 0.006, y9 + 0.004], [tb_x + 0.005, y9 - 0.006], [tb_x - 0.005, y9 - 0.006]], transform=fig.transFigure, fill=False, edgecolor="#848e9c", linewidth=1.1)
    bin_lid = lines.Line2D([tb_x - 0.008, tb_x + 0.008], [y9 + 0.005, y9 + 0.005], transform=fig.transFigure, color="#848e9c", linewidth=1.3)
    fig.patches.append(bin_body)
    fig.lines.append(bin_lid)


class ChartGenerator:
    def __init__(
        self,
        output_dir: Path | str = "charts",
        watermark_text: str = "Talha Sniper",
        default_style: str = "both",
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.watermark_text = watermark_text
        self.default_style = default_style.lower()
        self._style_cycle = itertools.cycle(["binance_app", "tradingview"])

    def generate_chart(
        self,
        setup: TradeSetup,
        bars_count: Optional[int] = None,
        filename_prefix: Optional[str] = None,
        style: Optional[str] = None,
    ) -> Path:
        """
        Generates a chart according to requested or alternating style:
        - 'binance_app' (Competitor real Binance Futures App screenshot style)
        - 'tradingview' (TradingView Pro dark style with RSI sub-panel)
        - 'both' / 'alternate' (Alternates automatically on each post)
        """
        chosen_style = (style or self.default_style).lower()
        if chosen_style in ("both", "alternate", "auto", "mix"):
            chosen_style = next(self._style_cycle)

        if chosen_style in ("binance_app", "binance", "competitor", "app"):
            return self._render_binance_app(setup, bars_count or 52, filename_prefix)
        else:
            return self._render_tradingview_pro(setup, bars_count or 70, filename_prefix)

    def _render_binance_app(
        self,
        setup: TradeSetup,
        bars_count: int = 52,
        filename_prefix: Optional[str] = None,
    ) -> Path:
        """
        Renders the exact Binance App Futures (Perpetual) screenshot style
        matching competitor posts (clean UI, top stats bar, high/low tags,
        hand-drawn trendline/box projection, and bottom-right creator watermark).
        """
        full_df = setup.df_1h.copy()
        full_df.rename(
            columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"},
            inplace=True,
        )

        effective_bars = min(bars_count, len(full_df))
        df = full_df.tail(effective_bars).copy()

        # Volume MAs: MA5 (yellow) and MA10 (purple)
        vol_ma5 = df["Volume"].rolling(5, min_periods=2).mean()
        vol_ma10 = df["Volume"].rolling(10, min_periods=3).mean()

        # Binance Dark Colors (exact RGB 32, 38, 48 from competitor screenshots)
        bg_color = "#202630"
        up_color = "#0ecb81"
        down_color = "#f6465d"
        text_color = "#eaecef"
        text_muted = "#848e9c"
        grid_color = "#28303d"

        mc = mpf.make_marketcolors(
            up=up_color,
            down=down_color,
            edge={"up": up_color, "down": down_color},
            wick={"up": up_color, "down": down_color},
            volume={"up": up_color, "down": down_color},
        )

        custom_style = mpf.make_mpf_style(
            base_mpf_style="nightclouds",
            marketcolors=mc,
            facecolor=bg_color,
            edgecolor=bg_color,
            figcolor=bg_color,
            gridcolor=grid_color,
            gridstyle="-",
            gridaxis="both",
            rc={
                "font.family": "sans-serif",
                "font.sans-serif": ["Segoe UI", "Arial", "sans-serif"],
                "font.size": 8.5,
                "text.color": text_muted,
                "axes.labelcolor": text_muted,
                "axes.edgecolor": grid_color,
                "xtick.color": text_muted,
                "ytick.color": text_muted,
                "grid.alpha": 0.5,
            },
        )

        add_plots = [
            mpf.make_addplot(vol_ma5, color="#f0b90b", width=1.1, panel=1),
            mpf.make_addplot(vol_ma10, color="#9c27b0", width=1.1, panel=1),
        ]

        # Calculate y-limits with padding
        all_prices = [df["Low"].min(), df["High"].max(), setup.current_price]
        if setup.target_price and not np.isnan(setup.target_price):
            all_prices.append(setup.target_price)
        if setup.stop_loss and not np.isnan(setup.stop_loss):
            all_prices.append(setup.stop_loss)
        if setup.support_level > 0:
            all_prices.append(setup.support_level)
        if setup.resistance_level > 0:
            all_prices.append(setup.resistance_level)

        min_p = min(all_prices)
        max_p = max(all_prices)
        p_range = max_p - min_p if max_p > min_p else max_p * 0.1
        y_min = min_p - (p_range * 0.08)
        y_max = max_p + (p_range * 0.08)

        # Plot figure in authentic 2.15:1 mobile landscape ratio (matching real phone screens)
        fig, axlist = mpf.plot(
            df,
            type="candle",
            style=custom_style,
            volume=True,
            addplot=add_plots,
            ylim=(y_min, y_max),
            returnfig=True,
            figsize=(12.8, 6.0),
            panel_ratios=(3.8, 1.0),
            tight_layout=False,
            ylabel="",
            ylabel_lower="",
        )

        main_ax = axlist[0]
        vol_ax = axlist[2]

        # Explicitly position main_ax and vol_ax to eliminate empty black voids on left and bottom!
        chart_left = 0.020
        chart_width = 0.895
        chart_bottom = 0.045
        vol_height = 0.130
        gap = 0.018
        main_bottom = chart_bottom + vol_height + gap
        main_height = 0.835 - main_bottom

        main_ax.set_position([chart_left, main_bottom, chart_width, main_height])
        vol_ax.set_position([chart_left, chart_bottom, chart_width, vol_height])

        for ax in (main_ax, vol_ax):
            ax.spines["top"].set_visible(False)
            ax.spines["left"].set_visible(True)
            ax.spines["left"].set_color(grid_color)
            ax.spines["bottom"].set_color(grid_color)
            ax.spines["right"].set_color(grid_color)
            ax.tick_params(axis="both", which="both", length=0)

        main_ax.yaxis.tick_right()
        main_ax.yaxis.set_label_position("right")
        vol_ax.yaxis.tick_right()
        vol_ax.yaxis.set_label_position("right")

        n_bars = len(df)
        extra_bars = 7
        main_ax.set_xlim(-0.5, n_bars + extra_bars)
        vol_ax.set_xlim(-0.5, n_bars + extra_bars)

        # Format price scale
        main_ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, pos: fmt_price(x, use_comma=True)))
        vol_ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, pos: fmt_compact_vol(x, use_comma=True)))

        # Sleek bottom date timeline bar matching competitor
        plt.setp(vol_ax.get_xticklabels(), visible=False)
        timeline_top = lines.Line2D([chart_left, chart_left + chart_width], [0.045, 0.045], transform=fig.transFigure, color=grid_color, linewidth=1.0)
        timeline_bot = lines.Line2D([chart_left, chart_left + chart_width], [0.012, 0.012], transform=fig.transFigure, color=grid_color, linewidth=0.8)
        fig.lines.extend([timeline_top, timeline_bot])

        first_dt = df.index[0].strftime("%Y-%m-%d %H:%M")
        mid_dt = df.index[len(df) // 2].strftime("%Y-%m-%d %H:%M")
        fig.text(0.24, 0.024, first_dt, color=text_muted, fontsize=8.0, ha="center", va="center")
        fig.text(0.60, 0.024, mid_dt, color=text_muted, fontsize=8.0, ha="center", va="center")

        # Official subtle Binance diamond logo and text in center of chart
        draw_binance_watermark(main_ax)

        # Signature Binance High & Low price ticks
        high_idx = int(df["High"].values.argmax())
        high_val = float(df["High"].iloc[high_idx])
        low_idx = int(df["Low"].values.argmin())
        low_val = float(df["Low"].iloc[low_idx])

        main_ax.text(
            high_idx, high_val, f"- {fmt_price(high_val, use_comma=True)}",
            color=text_color, fontsize=8.5, fontweight="bold", va="bottom", ha="left",
        )
        main_ax.text(
            low_idx, low_val, f"- {fmt_price(low_val, use_comma=True)}",
            color=text_color, fontsize=8.5, fontweight="bold", va="top", ha="left",
        )

        # Current Price Dotted Line & Pill
        curr_p = setup.current_price
        main_ax.axhline(curr_p, color="#848e9c", linestyle="--", linewidth=0.8, alpha=0.8)
        main_ax.text(
            1.002, curr_p, f" {fmt_price(curr_p, use_comma=True)} ",
            transform=main_ax.get_yaxis_transform(),
            color="#ffffff", fontsize=8.5, fontweight="bold", va="center", ha="left",
            bbox=dict(boxstyle="round,pad=0.25", fc="#2b313a", ec="#848e9c", lw=0.8),
            zorder=10,
        )

        # Realistic Trader Drawing Overlay (Natural paths with arrowheads)
        if setup.direction == "SHORT":
            peak_x = high_idx
            peak_y = high_val
            curr_x = n_bars - 1

            # Natural resistance trendline across highs
            main_ax.plot([peak_x, curr_x + 5], [peak_y, curr_p * 0.995], color="#f6465d", linewidth=1.5, alpha=0.9, zorder=5)

            if setup.support_level > 0:
                main_ax.hlines(setup.support_level, peak_x, curr_x + 7, colors="#0ecb81", linestyles="-", linewidths=1.0, alpha=0.6)

            # Smooth trader projection path curving down to target
            arrow_start_x = curr_x
            arrow_start_y = curr_p
            arrow_end_x = curr_x + 6
            arrow_end_y = setup.target_price

            arrow = patches.FancyArrowPatch(
                (arrow_start_x, arrow_start_y),
                (arrow_end_x, arrow_end_y),
                arrowstyle="-|>",
                mutation_scale=13,
                color="#f6465d",
                linewidth=1.8,
                linestyle="-",
                zorder=7,
            )
            main_ax.add_patch(arrow)

            # Target & Invalidation rounded pills on right axis matching real Binance App
            main_ax.axhline(setup.stop_loss, color="#f6465d", linestyle="-", linewidth=0.9, alpha=0.85)
            main_ax.text(
                1.002, setup.stop_loss, f" {fmt_price(setup.stop_loss, use_comma=True)} ",
                transform=main_ax.get_yaxis_transform(),
                color="#ffffff", fontsize=8.5, fontweight="bold", va="center", ha="left",
                bbox=dict(boxstyle="round,pad=0.3", fc="#f6465d", ec="none"),
                zorder=10,
            )
            main_ax.axhline(setup.target_price, color="#0ecb81", linestyle="-", linewidth=0.9, alpha=0.85)
            main_ax.text(
                1.002, setup.target_price, f" {fmt_price(setup.target_price, use_comma=True)} ",
                transform=main_ax.get_yaxis_transform(),
                color="#ffffff", fontsize=8.5, fontweight="bold", va="center", ha="left",
                bbox=dict(boxstyle="round,pad=0.3", fc="#0ecb81", ec="none"),
                zorder=10,
            )
        elif setup.direction == "LONG":
            box_start = max(0, n_bars - 20)
            box_end = n_bars + 2
            box_low = df["Low"].iloc[box_start:].min()
            box_high = curr_p * 1.006

            rect = patches.Rectangle(
                (box_start, box_low), box_end - box_start, box_high - box_low,
                linewidth=1.3, edgecolor="#0ecb81", facecolor="#0ecb8118", zorder=3
            )
            main_ax.add_patch(rect)

            arrow_start_x = n_bars - 1
            arrow_start_y = curr_p
            arrow_end_x = n_bars + 6
            arrow_end_y = setup.target_price

            arrow = patches.FancyArrowPatch(
                (arrow_start_x, arrow_start_y),
                (arrow_end_x, arrow_end_y),
                arrowstyle="-|>",
                mutation_scale=13,
                color="#0ecb81",
                linewidth=1.8,
                linestyle="-",
                zorder=7,
            )
            main_ax.add_patch(arrow)

            main_ax.axhline(setup.stop_loss, color="#f6465d", linestyle="-", linewidth=0.9, alpha=0.85)
            main_ax.text(
                1.002, setup.stop_loss, f" {fmt_price(setup.stop_loss, use_comma=True)} ",
                transform=main_ax.get_yaxis_transform(),
                color="#ffffff", fontsize=8.5, fontweight="bold", va="center", ha="left",
                bbox=dict(boxstyle="round,pad=0.3", fc="#f6465d", ec="none"),
                zorder=10,
            )
            main_ax.axhline(setup.target_price, color="#0ecb81", linestyle="-", linewidth=0.9, alpha=0.85)
            main_ax.text(
                1.002, setup.target_price, f" {fmt_price(setup.target_price, use_comma=True)} ",
                transform=main_ax.get_yaxis_transform(),
                color="#ffffff", fontsize=8.5, fontweight="bold", va="center", ha="left",
            )

        # Volume Panel Header with exact multi-colored MA values like competitor screenshots
        base_sym = setup.coin.replace("USDT", "")
        last_vol = df["Volume"].iloc[-1]
        last_q_vol = last_vol * curr_p
        v_ma5 = vol_ma5.iloc[-1] if not np.isnan(vol_ma5.iloc[-1]) else last_vol
        v_ma10 = vol_ma10.iloc[-1] if not np.isnan(vol_ma10.iloc[-1]) else last_vol

        vol_ax.text(0.010, 1.05, f"VOL({base_sym}): {fmt_compact_vol(last_vol, use_comma=True)}   VOL(USDT): {fmt_compact_vol(last_q_vol, use_comma=True)}   ", transform=vol_ax.transAxes, color=text_muted, fontsize=8, va="bottom")
        vol_ax.text(0.330, 1.05, f"MA(5): {fmt_compact_vol(v_ma5, use_comma=True)}", transform=vol_ax.transAxes, color="#f0b90b", fontsize=8, fontweight="bold", va="bottom")
        vol_ax.text(0.460, 1.05, f"MA(10): {fmt_compact_vol(v_ma10, use_comma=True)}", transform=vol_ax.transAxes, color="#9c27b0", fontsize=8, fontweight="bold", va="bottom")

        # Top Header (Binance App Title Bar)
        last_row = df.iloc[-1]
        prev_close = df.iloc[-2]["Close"] if len(df) > 1 else last_row["Close"]
        chg = ((last_row["Close"] - prev_close) / prev_close) * 100 if prev_close else 0
        price_color = up_color if chg >= 0 else down_color
        chg_sign = "+" if chg >= 0 else ""

        # Menu icon (3 crisp lines) aligned with left
        for dy in (-0.005, 0.0, 0.005):
            m_line = lines.Line2D([0.020, 0.032], [0.948 + dy, 0.948 + dy], transform=fig.transFigure, color=text_color, linewidth=1.8)
            fig.lines.append(m_line)

        fig.text(0.040, 0.944, f"{base_sym}USDT", fontsize=13, color="#ffffff", fontweight="bold")
        fig.text(
            0.130, 0.946, " Perp ", fontsize=7.5, color=text_muted, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.2", fc="#2b313a", ec="none"),
        )

        fig.text(0.180, 0.945, fmt_price(curr_p, use_comma=True), fontsize=14, color=price_color, fontweight="bold")
        fig.text(
            0.180, 0.916, f"${fmt_price(curr_p, use_comma=True)}  {chg_sign}{chg:.2f}%",
            fontsize=8.5, color=price_color, fontweight="bold"
        )

        h_24h = df["High"].max()
        l_24h = df["Low"].min()
        tot_vol = df["Volume"].sum()
        tot_q_vol = tot_vol * curr_p

        # 5 Stats Columns
        fig.text(0.310, 0.944, "Mark Price", fontsize=7.5, color=text_muted)
        fig.text(0.310, 0.918, fmt_price(curr_p, use_comma=True), fontsize=8.0, color=text_color, fontweight="bold")

        fig.text(0.390, 0.944, "24h High", fontsize=7.5, color=text_muted)
        fig.text(0.390, 0.918, fmt_price(h_24h, use_comma=True), fontsize=8.0, color=text_color, fontweight="bold")

        fig.text(0.465, 0.944, "24h Low", fontsize=7.5, color=text_muted)
        fig.text(0.465, 0.918, fmt_price(l_24h, use_comma=True), fontsize=8.0, color=text_color, fontweight="bold")

        fig.text(0.540, 0.944, f"24h Vol({base_sym})", fontsize=7.5, color=text_muted)
        fig.text(0.540, 0.918, fmt_compact_vol(tot_vol, use_comma=True), fontsize=8.0, color=text_color, fontweight="bold")

        fig.text(0.635, 0.944, "24h Vol(USDT)", fontsize=7.5, color=text_muted)
        fig.text(0.635, 0.918, fmt_compact_vol(tot_q_vol, use_comma=True), fontsize=8.0, color=text_color, fontweight="bold")

        # Close icon ✕
        x_c, y_c, d = 0.965, 0.946, 0.005
        l1 = lines.Line2D([x_c - d, x_c + d], [y_c - d, y_c + d], transform=fig.transFigure, color=text_muted, linewidth=1.5)
        l2 = lines.Line2D([x_c - d, x_c + d], [y_c + d, y_c - d], transform=fig.transFigure, color=text_muted, linewidth=1.5)
        fig.lines.extend([l1, l2])

        # Timeframe Selector Tab Bar aligned with chart left (0.020)
        tf_tabs = ["Time", "5m", "15m", "30m", "1h", "4h", "1d", "1w", "More v"]
        x_cursor = 0.020
        for tab in tf_tabs:
            is_active = (tab == "1h")
            t_color = "#ffffff" if is_active else text_muted
            font_wt = "bold" if is_active else "normal"
            fig.text(x_cursor, 0.865, tab, fontsize=8.5, color=t_color, fontweight=font_wt)
            x_cursor += 0.075 if "More" in tab else 0.060

        fig.text(0.875, 0.865, "[ ]", fontsize=8.5, color=text_muted)

        # Draw Vector Toolbar on Far Right (Clean, crisp, no missing glyphs!)
        draw_vector_toolbar(fig)

        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        prefix = filename_prefix or setup.coin
        output_file = self.output_dir / f"{prefix}_binance_{timestamp_str}.png"

        fig.savefig(output_file, dpi=160, facecolor=bg_color, edgecolor="none")
        plt.close(fig)
        logger.info(f"Generated Binance App chart: {output_file}")
        return output_file

    def _render_tradingview_pro(
        self,
        setup: TradeSetup,
        bars_count: int = 70,
        filename_prefix: Optional[str] = None,
    ) -> Path:
        """
        Renders the TradingView Pro dark-theme chart with RSI(14) panel,
        EMA lines, and TradingView Position Tool.
        """
        base_sym = setup.coin.replace("USDT", "")
        full_df = setup.df_1h.copy()
        full_df.rename(
            columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"},
            inplace=True,
        )

        full_ma20 = full_df["Close"].rolling(20, min_periods=5).mean()
        full_ma50 = full_df["Close"].rolling(50, min_periods=10).mean()
        full_rsi = compute_rsi(full_df["Close"], 14)

        effective_bars = min(bars_count, len(full_df))
        df = full_df.tail(effective_bars).copy()
        ma20 = full_ma20.tail(effective_bars)
        ma50 = full_ma50.tail(effective_bars)
        rsi = full_rsi.tail(effective_bars)

        bg_color = "#131722"
        grid_color = "#1e222d"
        up_color = "#089981"
        down_color = "#f23645"
        ma20_color = "#f0b90b"
        ma50_color = "#2962ff"
        rsi_line_color = "#9353d3"

        mc = mpf.make_marketcolors(
            up=up_color,
            down=down_color,
            edge={"up": up_color, "down": down_color},
            wick={"up": up_color, "down": down_color},
            volume={"up": "#08998140", "down": "#f2364540"},
        )

        custom_style = mpf.make_mpf_style(
            base_mpf_style="nightclouds",
            marketcolors=mc,
            facecolor=bg_color,
            edgecolor=bg_color,
            figcolor=bg_color,
            gridcolor=grid_color,
            gridstyle="-",
            gridaxis="both",
            rc={
                "font.family": "sans-serif",
                "font.sans-serif": ["Segoe UI", "Arial", "sans-serif"],
                "font.size": 8.5,
                "text.color": "#d1d4dc",
                "axes.labelcolor": "#787b86",
                "axes.edgecolor": "#2a2e39",
                "xtick.color": "#787b86",
                "ytick.color": "#787b86",
                "grid.alpha": 0.4,
            },
        )

        add_plots = []
        if ma20.dropna().size > 0:
            add_plots.append(mpf.make_addplot(ma20, color=ma20_color, width=1.3, panel=0))
        if ma50.dropna().size > 0:
            add_plots.append(mpf.make_addplot(ma50, color=ma50_color, width=1.3, panel=0))

        add_plots.append(mpf.make_addplot(rsi, color=rsi_line_color, width=1.4, panel=1, ylabel="RSI (14)"))

        all_prices = [df["Low"].min(), df["High"].max()]
        if setup.direction in ("LONG", "SHORT"):
            if setup.stop_loss and not np.isnan(setup.stop_loss):
                all_prices.append(setup.stop_loss)
            if setup.target_price and not np.isnan(setup.target_price):
                all_prices.append(setup.target_price)
        if setup.support_level > 0:
            all_prices.append(setup.support_level)
        if setup.resistance_level > 0:
            all_prices.append(setup.resistance_level)

        min_p = min(all_prices)
        max_p = max(all_prices)
        p_range = max_p - min_p if max_p > min_p else max_p * 0.1
        y_min = min_p - (p_range * 0.04)
        y_max = max_p + (p_range * 0.06)

        fig, axlist = mpf.plot(
            df,
            type="candle",
            style=custom_style,
            addplot=add_plots,
            ylim=(y_min, y_max),
            returnfig=True,
            figsize=(13.0, 7.2),
            panel_ratios=(3.5, 1.1),
            tight_layout=False,
            ylabel="",
            ylabel_lower="",
        )

        main_ax = axlist[0]
        rsi_ax = axlist[2]

        # Hide any secondary/extra twin axes created by mplfinance
        for ax in axlist:
            if ax not in (main_ax, rsi_ax):
                ax.set_visible(False)

        # Explicitly position axes to eliminate empty black voids on left and footer!
        chart_left = 0.020
        chart_width = 0.895
        chart_bottom = 0.050
        rsi_height = 0.150
        gap = 0.035
        main_bottom = chart_bottom + rsi_height + gap
        main_height = 0.880 - main_bottom

        main_ax.set_position([chart_left, main_bottom, chart_width, main_height])
        rsi_ax.set_position([chart_left, chart_bottom, chart_width, rsi_height])

        for ax in (main_ax, rsi_ax):
            ax.spines["top"].set_visible(False)
            ax.spines["left"].set_visible(True)
            ax.spines["left"].set_color("#2a2e39")
            ax.spines["bottom"].set_color("#2a2e39")
            ax.spines["right"].set_color("#2a2e39")
            ax.tick_params(axis="both", which="both", length=3, color="#2a2e39")

        main_ax.yaxis.tick_right()
        main_ax.yaxis.set_label_position("right")
        rsi_ax.yaxis.tick_right()
        rsi_ax.yaxis.set_label_position("right")
        rsi_ax.set_ylim(15, 85)
        rsi_ax.set_yticks([30, 50, 70])

        if max_p >= 1000:
            main_ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.1f"))
        elif max_p >= 10:
            main_ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.2f"))
        elif max_p >= 1:
            main_ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.4f"))
        else:
            main_ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.6f"))

        n_bars = len(df)
        extra_bars = 9
        main_ax.set_xlim(-0.5, n_bars + extra_bars)
        rsi_ax.set_xlim(-0.5, n_bars + extra_bars)

        plt.setp(rsi_ax.get_xticklabels(), rotation=0, horizontalalignment="center")
        rsi_ax.axhline(70, color="#f23645", linestyle="--", linewidth=0.9, alpha=0.55)
        rsi_ax.axhline(50, color="#787b86", linestyle=":", linewidth=0.8, alpha=0.35)
        rsi_ax.axhline(30, color="#089981", linestyle="--", linewidth=0.9, alpha=0.55)
        rsi_ax.axhspan(30, 70, color="#9353d3", alpha=0.08, zorder=0)

        if setup.support_level > 0:
            main_ax.axhline(setup.support_level, color="#089981", linestyle="--", linewidth=1.0, alpha=0.55)
            main_ax.text(
                0.01, setup.support_level, f"Support {fmt_price(setup.support_level)}",
                transform=main_ax.get_yaxis_transform(),
                color="#089981", fontsize=8, va="bottom",
            )

        if setup.resistance_level > 0:
            main_ax.axhline(setup.resistance_level, color="#f23645", linestyle="--", linewidth=1.0, alpha=0.55)
            main_ax.text(
                0.01, setup.resistance_level, f"Resistance {fmt_price(setup.resistance_level)}",
                transform=main_ax.get_yaxis_transform(),
                color="#f23645", fontsize=8, va="bottom",
            )

        # Signature TradingView Large Background Watermark
        main_ax.text(
            0.50, 0.53, f"{base_sym}USDT · 1H",
            transform=main_ax.transAxes,
            fontsize=42, fontweight="heavy",
            color="#ffffff", alpha=0.038,
            ha="center", va="center", zorder=0,
        )
        main_ax.text(
            0.50, 0.39, f"{self.watermark_text.upper()}",
            transform=main_ax.transAxes,
            fontsize=24, fontweight="bold",
            color="#ffffff", alpha=0.048,
            ha="center", va="center", zorder=0,
        )

        if setup.direction in ("LONG", "SHORT"):
            box_start = max(0, n_bars - 6)
            box_end = n_bars + 6
            x_coords = np.arange(box_start, box_end + 1)

            curr_p = setup.current_price
            tp_p = setup.target_price
            sl_p = setup.stop_loss

            if setup.direction == "LONG":
                tp_pct = ((tp_p - curr_p) / curr_p) * 100 if curr_p else 0
                sl_pct = ((curr_p - sl_p) / curr_p) * 100 if curr_p else 0
                main_ax.fill_between(x_coords, curr_p, tp_p, color="#089981", alpha=0.22, zorder=2)
                main_ax.fill_between(x_coords, curr_p, sl_p, color="#f23645", alpha=0.22, zorder=2)
            else:
                tp_pct = ((curr_p - tp_p) / curr_p) * 100 if curr_p else 0
                sl_pct = ((sl_p - curr_p) / curr_p) * 100 if curr_p else 0
                main_ax.fill_between(x_coords, curr_p, tp_p, color="#089981", alpha=0.22, zorder=2)
                main_ax.fill_between(x_coords, curr_p, sl_p, color="#f23645", alpha=0.22, zorder=2)

            # Solid boundary lines for official TradingView Position Tool
            main_ax.hlines(tp_p, box_start, box_end, colors="#089981", linestyles="-", linewidths=1.6, zorder=4)
            main_ax.hlines(curr_p, box_start, box_end, colors="#ffffff", linestyles="--", linewidths=1.2, zorder=4)
            main_ax.hlines(sl_p, box_start, box_end, colors="#f23645", linestyles="-", linewidths=1.6, zorder=4)

            # Circular anchor point on position tool (like real TradingView)
            main_ax.scatter([box_start], [curr_p], color="#ffffff", s=35, zorder=8, edgecolors="#131722", linewidths=1.0)

            mid_x = (box_start + box_end) / 2
            main_ax.text(
                mid_x, curr_p, f"  Risk/Reward: {setup.risk_reward:.1f}  ",
                color="#ffffff", fontsize=8.0, fontweight="bold", ha="center", va="center",
                bbox=dict(boxstyle="round,pad=0.25", fc="#1e222d", ec="#2a2e39", lw=1),
                zorder=7,
            )

            tp_sign = "+" if setup.direction == "LONG" else "-"
            sl_sign = "-" if setup.direction == "LONG" else "+"

            # In-box target & stop labels
            main_ax.text(
                box_start + 0.3, tp_p, f" Target: {fmt_price(tp_p)} ({tp_sign}{tp_pct:.1f}%)",
                color="#089981", fontsize=7.5, fontweight="bold", va="bottom" if setup.direction == "LONG" else "top",
                zorder=7,
            )
            main_ax.text(
                box_start + 0.3, sl_p, f" Stop: {fmt_price(sl_p)} ({sl_sign}{sl_pct:.1f}%)",
                color="#f23645", fontsize=7.5, fontweight="bold", va="top" if setup.direction == "LONG" else "bottom",
                zorder=7,
            )

            # Right axis rounded pills matching TradingView
            main_ax.text(
                1.002, tp_p, f" {fmt_price(tp_p)} ",
                transform=main_ax.get_yaxis_transform(),
                color="#ffffff", fontsize=8.5, fontweight="bold", va="center", ha="left",
                bbox=dict(boxstyle="round,pad=0.25", fc="#089981", ec="none"),
                zorder=9,
            )
            main_ax.text(
                1.002, curr_p, f" {fmt_price(curr_p)} ",
                transform=main_ax.get_yaxis_transform(),
                color="#131722", fontsize=8.5, fontweight="bold", va="center", ha="left",
                bbox=dict(boxstyle="round,pad=0.25", fc="#eaecef", ec="none"),
                zorder=9,
            )
            main_ax.text(
                1.002, sl_p, f" {fmt_price(sl_p)} ",
                transform=main_ax.get_yaxis_transform(),
                color="#ffffff", fontsize=8.5, fontweight="bold", va="center", ha="left",
                bbox=dict(boxstyle="round,pad=0.25", fc="#f23645", ec="none"),
                zorder=9,
            )

        base_sym = setup.coin.replace("USDT", "")
        last_row = df.iloc[-1]
        prev_close = df.iloc[-2]["Close"] if len(df) > 1 else last_row["Close"]
        chg = ((last_row["Close"] - prev_close) / prev_close) * 100 if prev_close else 0
        chg_color = up_color if chg >= 0 else down_color

        fig.text(chart_left, 0.958, f"{base_sym}/USDT · 1H · BINANCE", fontsize=13, fontweight="bold", color="#ffffff")
        
        if setup.direction in ("LONG", "SHORT"):
            dir_color = up_color if setup.direction == "LONG" else down_color
            fig.text(
                0.235, 0.958, f"● {setup.direction} SETUP",
                fontsize=10, fontweight="bold", color=dir_color,
                bbox=dict(boxstyle="round,pad=0.25", fc=f"{dir_color}25", ec=dir_color, lw=0.8),
            )
        else:
            fig.text(
                0.235, 0.958, "● CONSOLIDATION / NEUTRAL",
                fontsize=10, fontweight="bold", color="#f0b90b",
                bbox=dict(boxstyle="round,pad=0.25", fc="#f0b90b25", ec="#f0b90b", lw=0.8),
            )

        fig.text(
            0.915, 0.958, f"{self.watermark_text.upper()}",
            fontsize=10, fontweight="bold", color="#f0b90b", ha="right",
            bbox=dict(boxstyle="round,pad=0.3", fc="#1e222d", ec="#f0b90b50", lw=1),
        )

        ohlc_str = f"O {fmt_price(last_row['Open'])}   H {fmt_price(last_row['High'])}   L {fmt_price(last_row['Low'])}   C {fmt_price(last_row['Close'])}   {chg:+.2f}%"
        fig.text(chart_left, 0.925, ohlc_str, fontsize=8.5, color=chg_color, fontweight="bold")

        ind_str = f"EMA(20): {fmt_price(setup.ma20_1h)}   EMA(50): {fmt_price(setup.ma50_1h)}   RSI(14): {setup.rsi_1h:.1f}"
        fig.text(0.380, 0.925, ind_str, fontsize=8.5, color="#787b86", fontweight="bold")

        fig.text(chart_left, main_bottom - 0.022, f"Relative Strength Index (14) · {setup.rsi_1h:.1f}", fontsize=8, color="#9353d3", fontweight="bold")

        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        prefix = filename_prefix or setup.coin
        output_file = self.output_dir / f"{prefix}_tv_{timestamp_str}.png"

        fig.savefig(
            output_file,
            dpi=160,
            facecolor=bg_color,
            edgecolor="none",
        )
        plt.close(fig)
        logger.info(f"Generated TradingView Pro chart: {output_file}")
        return output_file
