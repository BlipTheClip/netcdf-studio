"""
Taylor diagram generation using matplotlib (Module C).

A Taylor diagram summarises model–observation agreement by plotting:
  - Normalised standard deviation on the radial axis
    (std_model / std_reference; reference is at radius = 1)
  - Correlation on the angular axis
    (θ = arccos(correlation); perfect correlation at θ = 0)
  - RMSE contours (dashed, centred on the reference point at (1, 0))

Reference:
  Taylor, K. E. (2001). Summarizing multiple aspects of model performance
  in a single diagram. J. Geophys. Res., 106(D7), 7183–7192.

Entry point: render_taylor(models, output_path, **kwargs) → Path
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

logger = logging.getLogger(__name__)

# Default colour cycle for models (up to 10 models use distinct colours)
_DEFAULT_COLORS = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
]
_DEFAULT_MARKERS = ["o", "s", "^", "D", "v", "P", "X", "*", "h", "p"]


@dataclass
class ModelStat:
    """Statistics for a single model to plot on the Taylor diagram."""
    name: str
    std_ratio: float
    correlation: float
    color: str = ""
    marker: str = ""

    def __post_init__(self) -> None:
        if not (-1.0 <= self.correlation <= 1.0):
            raise ValueError(
                f"Model '{self.name}': correlation must be in [-1, 1], got {self.correlation}"
            )
        if self.std_ratio < 0:
            raise ValueError(
                f"Model '{self.name}': std_ratio must be ≥ 0, got {self.std_ratio}"
            )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _polar_to_xy(r: float, corr: float) -> tuple[float, float]:
    """Convert (std_ratio, correlation) to Cartesian (x, y) on the diagram."""
    theta = np.arccos(corr)
    return r * np.cos(theta), r * np.sin(theta)


def _draw_std_arcs(ax: plt.Axes, radii: list[float], max_std: float) -> None:
    """Draw quarter-circle arcs representing constant normalised standard deviation."""
    theta = np.linspace(0.0, np.pi / 2.0, 200)
    for r in radii:
        if r > max_std:
            continue
        ax.plot(r * np.cos(theta), r * np.sin(theta), color="grey", lw=0.7, alpha=0.5)
        if r > 0:
            ax.text(
                r * np.cos(np.pi / 2.0 + 0.05), r * np.sin(np.pi / 2.0 + 0.05),
                f"{r:.1f}", fontsize=7, color="grey", ha="right", va="bottom",
            )


def _draw_rmse_contours(
    ax: plt.Axes, levels: list[float], max_std: float
) -> None:
    """Draw dashed circles centred on the reference point (1, 0) for constant RMSE."""
    theta = np.linspace(0.0, np.pi, 300)
    for rmse in levels:
        # Full circle centred at (1, 0); clip to the first quadrant
        xs = 1.0 + rmse * np.cos(theta)
        ys = rmse * np.sin(theta)
        # Keep only points in the first quadrant and within max_std radius
        mask = (xs >= 0) & (ys >= 0) & (np.hypot(xs, ys) <= max_std * 1.05)
        if mask.sum() < 2:
            continue
        ax.plot(xs[mask], ys[mask], color="#2ca02c", lw=0.7, ls="--", alpha=0.55)
        # Label near the outer arc
        mid = np.argmax(mask)
        ax.text(
            xs[mask][-1], ys[mask][-1],
            f"RMSE={rmse:.2f}", fontsize=6, color="#2ca02c", alpha=0.8,
        )


def _draw_correlation_radii(ax: plt.Axes, correlations: list[float], max_std: float) -> None:
    """Draw radial lines from origin for target correlation values."""
    for corr in correlations:
        theta = np.arccos(corr)
        ax.plot(
            [0, max_std * np.cos(theta)], [0, max_std * np.sin(theta)],
            color="grey", lw=0.5, ls=":", alpha=0.6,
        )
        ax.text(
            (max_std + 0.06) * np.cos(theta), (max_std + 0.06) * np.sin(theta),
            f"{corr}", fontsize=7, color="grey", ha="center", va="center",
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_taylor(
    models: list[dict | ModelStat],
    output_path: str | Path,
    *,
    title: str = "Taylor Diagram",
    max_std_ratio: float = 1.5,
    std_arc_ticks: list[float] | None = None,
    rmse_levels: list[float] | None = None,
    correlation_ticks: list[float] | None = None,
    dpi: int = 150,
    figsize: tuple[float, float] = (8, 7),
    label_fontsize: int = 8,
) -> Path:
    """
    Render a Taylor diagram comparing multiple models against a reference.

    Args:
        models: List of model statistics. Each item is either a ModelStat or a dict
                with keys: name (str), std_ratio (float), correlation (float),
                color (str, optional), marker (str, optional).
                std_ratio = std_model / std_reference (reference is at 1.0).
                correlation = Pearson correlation with the reference.
        output_path: Destination .png path.
        title: Plot title.
        max_std_ratio: Maximum radius of the diagram (sets axis limits).
        std_arc_ticks: Normalised standard deviation values for arc labels.
                       Default: [0.25, 0.5, 0.75, 1.0, 1.25, 1.5].
        rmse_levels: RMSE values for green dashed contours.
                     Default: [0.25, 0.5, 0.75, 1.0].
        correlation_ticks: Correlation values for radial guide lines.
                           Default: [0, 0.1, 0.2, …, 0.9, 0.95, 0.99].
        dpi: Output resolution.
        figsize: Figure size in inches.
        label_fontsize: Font size for model labels.

    Returns:
        Path to the saved PNG file.

    Raises:
        ValueError: models is empty, or a model has an out-of-range statistic.
    """
    if not models:
        raise ValueError("models must contain at least one entry")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Normalise to ModelStat objects
    stats: list[ModelStat] = []
    for i, m in enumerate(models):
        if isinstance(m, ModelStat):
            ms = m
        else:
            ms = ModelStat(
                name=str(m["name"]),
                std_ratio=float(m["std_ratio"]),
                correlation=float(m["correlation"]),
                color=str(m.get("color", "")),
                marker=str(m.get("marker", "")),
            )
        if not ms.color:
            ms.color = _DEFAULT_COLORS[i % len(_DEFAULT_COLORS)]
        if not ms.marker:
            ms.marker = _DEFAULT_MARKERS[i % len(_DEFAULT_MARKERS)]
        stats.append(ms)

    # Defaults for diagram guides
    if std_arc_ticks is None:
        std_arc_ticks = [0.25, 0.5, 0.75, 1.0, 1.25, max_std_ratio]
    if rmse_levels is None:
        rmse_levels = [0.25, 0.5, 0.75, 1.0, 1.25]
    if correlation_ticks is None:
        correlation_ticks = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5,
                             0.6, 0.7, 0.8, 0.9, 0.95, 0.99]

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    ax.set_aspect("equal")
    ax.set_xlim(-0.05, max_std_ratio + 0.18)
    ax.set_ylim(-0.05, max_std_ratio + 0.18)
    ax.set_xlabel("Normalised Standard Deviation", fontsize=10)
    ax.set_ylabel("Normalised Standard Deviation", fontsize=10)
    ax.set_title(title, fontsize=12, pad=10)
    ax.spines[["top", "right"]].set_visible(False)

    # Draw diagram structure
    _draw_std_arcs(ax, std_arc_ticks, max_std_ratio)
    _draw_rmse_contours(ax, rmse_levels, max_std_ratio)
    _draw_correlation_radii(ax, correlation_ticks, max_std_ratio)

    # Outer arc boundary
    theta = np.linspace(0.0, np.pi / 2.0, 200)
    ax.plot(
        max_std_ratio * np.cos(theta), max_std_ratio * np.sin(theta),
        "k-", lw=1.0,
    )

    # Reference point (observations): std_ratio=1, correlation=1 → (1, 0)
    ax.scatter([1.0], [0.0], s=120, c="k", marker="*", zorder=10, label="Reference")
    ax.text(1.03, 0.04, "REF", fontsize=8, fontweight="bold")

    # Model points
    for ms in stats:
        x, y = _polar_to_xy(ms.std_ratio, ms.correlation)
        # Clip to diagram bounds
        if x < 0 or y < 0 or np.hypot(x, y) > max_std_ratio * 1.05:
            logger.warning(
                "Model '%s' (std_ratio=%.2f, corr=%.2f) falls outside diagram bounds; skipping",
                ms.name, ms.std_ratio, ms.correlation,
            )
            continue
        ax.scatter([x], [y], s=70, c=ms.color, marker=ms.marker, zorder=8, label=ms.name)
        ax.text(x + 0.02, y + 0.02, ms.name, fontsize=label_fontsize, color=ms.color)

    ax.legend(
        loc="upper right",
        fontsize=8,
        framealpha=0.85,
        markerscale=1.2,
        bbox_to_anchor=(1.0, 1.0),
    )

    # Correlation axis label along the outer arc
    ax.text(
        max_std_ratio * 0.5,
        max_std_ratio * 0.88,
        "Correlation",
        fontsize=9, color="grey",
        rotation=-45, ha="center",
    )

    fig.tight_layout()
    fig.savefig(str(output_path), dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    logger.info("Taylor diagram saved: %s  (%d models)", output_path.name, len(stats))
    return output_path
