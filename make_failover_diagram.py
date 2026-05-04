"""
Generate a before/after failover diagram showing traffic flow changes.
NetBox Labs dark theme.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import matplotlib.patheffects as pe
import numpy as np

# ── Theme ─────────────────────────────────────────────────────────────────────
BG        = "#0D1B2A"
CARD      = "#142A3E"
TEAL      = "#00C2A8"
WHITE     = "#FFFFFF"
GREY      = "#B0BCCC"
RED       = "#E05252"
AMBER     = "#F0A500"
GREEN     = "#00C2A8"
DIM       = "#4A6278"

def make_panel(ax, title, show_primary_active, show_backup_active):
    ax.set_facecolor(BG)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 7)
    ax.axis("off")

    # ── Panel title ───────────────────────────────────────────────────────────
    title_color = RED if "After" in title else TEAL
    ax.text(5, 6.6, title, ha="center", va="center",
            fontsize=13, fontweight="bold", color=title_color, fontfamily="monospace")

    # ── Site boxes ────────────────────────────────────────────────────────────
    def site_box(x, y, label, sublabel):
        box = FancyBboxPatch((x - 1.1, y - 0.55), 2.2, 1.1,
                             boxstyle="round,pad=0.05",
                             facecolor=CARD, edgecolor=TEAL, linewidth=1.5)
        ax.add_patch(box)
        ax.text(x, y + 0.18, label, ha="center", va="center",
                fontsize=10, fontweight="bold", color=WHITE)
        ax.text(x, y - 0.18, sublabel, ha="center", va="center",
                fontsize=7.5, color=GREY)

    site_box(1.5, 3.5, "gb-brs-rtr-01", "GB-Bristol")
    site_box(8.5, 3.5, "US-Atlanta", "us-atl-rtr-01")

    # ── Routing table box ─────────────────────────────────────────────────────
    rt_box = FancyBboxPatch((0.2, 0.3), 3.6, 1.6,
                            boxstyle="round,pad=0.05",
                            facecolor=CARD, edgecolor=DIM, linewidth=1)
    ax.add_patch(rt_box)
    ax.text(2.0, 1.75, "routing table", ha="center", va="center",
            fontsize=7.5, color=GREY, style="italic")

    pri_color = WHITE if show_primary_active else DIM
    bak_color = WHITE if show_backup_active else DIM
    pri_strike = "" if show_primary_active else "  ✗"
    bak_new    = "  ← new" if show_backup_active and not show_primary_active else ""

    ax.text(0.45, 1.38, "default via 172.16.0.1" + pri_strike,
            ha="left", va="center", fontsize=7.5,
            color=pri_color, fontfamily="monospace")
    ax.text(0.45, 0.95, "default via 172.16.1.1" + bak_new,
            ha="left", va="center", fontsize=7.5,
            color=bak_color, fontfamily="monospace")
    if not show_primary_active:
        # strikethrough line over primary route
        ax.plot([0.45, 3.65], [1.38, 1.38], color=RED, linewidth=1, alpha=0.7)

    # ── Circuit paths ─────────────────────────────────────────────────────────
    # Primary circuit  (y=4.3) — Gi0/0/7
    pri_style = "solid" if show_primary_active else "dashed"
    pri_color = TEAL if show_primary_active else RED
    pri_lw    = 2.5 if show_primary_active else 1.2
    pri_alpha = 1.0 if show_primary_active else 0.35
    ax.annotate("", xy=(7.4, 4.3), xytext=(2.6, 4.3),
                arrowprops=dict(arrowstyle="->" if show_primary_active else "-",
                                color=pri_color, lw=pri_lw,
                                linestyle=pri_style, alpha=pri_alpha))
    ax.text(5.0, 4.58, "IPLC-GB-AT-PRI  ·  gw 172.16.0.1  ·  Gi0/0/7",
            ha="center", va="center", fontsize=7.5,
            color=pri_color, alpha=pri_alpha, fontfamily="monospace")
    status_label = "ACTIVE" if show_primary_active else "OFFLINE"
    status_col   = GREEN if show_primary_active else RED
    ax.text(5.0, 4.15, f"[{status_label}]",
            ha="center", va="center", fontsize=7,
            color=status_col, alpha=pri_alpha, fontfamily="monospace")

    # Backup circuit  (y=2.7) — Gi0/0/0
    bak_style = "solid" if show_backup_active else "dashed"
    bak_color = TEAL if show_backup_active else DIM
    bak_lw    = 2.5 if show_backup_active else 1.2
    bak_alpha = 1.0 if show_backup_active else 0.35
    ax.annotate("", xy=(7.4, 2.7), xytext=(2.6, 2.7),
                arrowprops=dict(arrowstyle="->" if show_backup_active else "-",
                                color=bak_color, lw=bak_lw,
                                linestyle=bak_style, alpha=bak_alpha))
    ax.text(5.0, 2.98, "IPLC-GB-AT-SEC  ·  gw 172.16.1.1  ·  Gi0/0/0",
            ha="center", va="center", fontsize=7.5,
            color=bak_color, alpha=bak_alpha, fontfamily="monospace")
    bak_status = "ACTIVE" if show_backup_active else "OFFLINE"
    bak_col    = GREEN if show_backup_active else DIM
    ax.text(5.0, 2.55, f"[{bak_status}]",
            ha="center", va="center", fontsize=7,
            color=bak_col, alpha=bak_alpha, fontfamily="monospace")

    # ── Traffic label on active circuit ───────────────────────────────────────
    if show_primary_active:
        ax.text(5.0, 4.3, "traffic ▶", ha="center", va="center",
                fontsize=6.5, color=WHITE, alpha=0.5, fontfamily="monospace",
                bbox=dict(facecolor=BG, edgecolor="none", pad=1))
    if show_backup_active:
        ax.text(5.0, 2.7, "traffic ▶", ha="center", va="center",
                fontsize=6.5, color=WHITE, alpha=0.5, fontfamily="monospace",
                bbox=dict(facecolor=BG, edgecolor="none", pad=1))


# ── Figure ────────────────────────────────────────────────────────────────────
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))
fig.patch.set_facecolor(BG)

# Divider
fig.add_artist(plt.Line2D([0.5, 0.5], [0.04, 0.96],
                          transform=fig.transFigure,
                          color=DIM, linewidth=1, linestyle="--"))

make_panel(ax1, "Before failover", show_primary_active=True,  show_backup_active=False)
make_panel(ax2, "After failover",  show_primary_active=False, show_backup_active=True)

# ── Centre annotation ─────────────────────────────────────────────────────────
fig.text(0.5, 0.5, "⟶", ha="center", va="center",
         fontsize=22, color=AMBER, transform=fig.transFigure)

# ── Trigger callout (bottom) ─────────────────────────────────────────────────
fig.text(0.5, 0.045,
         'Trigger: NetBox Copilot → "IPLC-GB-AT-PRI has failed"  →  EDA rulebook  →  AAP workflow  →  Ansible pushes IOS config',
         ha="center", va="center", fontsize=8, color=GREY,
         fontfamily="monospace")

# ── Title ─────────────────────────────────────────────────────────────────────
fig.text(0.5, 0.97, "Circuit Failover — Traffic Flow",
         ha="center", va="top", fontsize=15, fontweight="bold",
         color=WHITE)

plt.tight_layout(rect=[0, 0.06, 1, 0.96])

out = "failover_diagram.png"
plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=BG)
print(f"Saved: {out}")
