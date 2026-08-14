"""Shared visualization theme (light mode), following the project's
data-viz method: sequential single-hue ramps for magnitude, a diverging
blue↔red pair with a neutral-gray midpoint for polarity, categorical slots
in fixed order (validated palette), recessive chrome.
"""

import plotly.graph_objects as go
import plotly.io as pio

# Categorical slots - fixed order, never cycled (validated palette).
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
          "#e87ba4", "#008300", "#4a3aa7", "#e34948"]

# Sequential blue ramp, light -> dark (steps 100..700).
SEQ_BLUE = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7",
            "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281",
            "#0d366b"]

# Diverging: blue <-> red with neutral gray midpoint.
DIVERGING = [[0.0, "#0d366b"], [0.25, "#3987e5"], [0.5, "#f0efec"],
             [0.75, "#e34948"], [1.0, "#7a1f1f"]]

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"

FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'

_template = go.layout.Template(
    layout=dict(
        font=dict(family=FONT, color=INK, size=13),
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        colorway=SERIES,
        margin=dict(l=60, r=30, t=60, b=50),
        title=dict(font=dict(size=16, color=INK), x=0.02, xanchor="left"),
        xaxis=dict(gridcolor=GRID, linecolor=BASELINE, zerolinecolor=BASELINE,
                   tickfont=dict(color=INK_MUTED, size=11),
                   title_font=dict(color=INK_SECONDARY, size=12)),
        yaxis=dict(gridcolor=GRID, linecolor=BASELINE, zerolinecolor=BASELINE,
                   tickfont=dict(color=INK_MUTED, size=11),
                   title_font=dict(color=INK_SECONDARY, size=12)),
        legend=dict(font=dict(color=INK_SECONDARY, size=12),
                    bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(font=dict(family=FONT, size=12)),
    )
)
pio.templates["bucees"] = _template
pio.templates.default = "bucees"


def save_fig(fig, path_html, png_too: bool = True) -> list:
    """Write interactive HTML (+ static PNG when kaleido is available)."""
    written = []
    fig.write_html(path_html, include_plotlyjs="cdn")
    written.append(path_html)
    if png_too:
        try:
            png = path_html.with_suffix(".png")
            fig.write_image(png, width=1000, height=620, scale=2)
            written.append(png)
        except Exception:  # kaleido missing - HTML remains the artifact
            pass
    return written
