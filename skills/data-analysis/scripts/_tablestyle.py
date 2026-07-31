"""House visual identity for great_tables — the table counterpart of
`assets/charts/theme.json`. Keep the palette in sync with that file.

`style_house(gt)` applies the shared look (Inter, muted uppercase labels, light
row hlines) to any GT table. `nanoplot_house()` themes in-cell sparklines to the
house indigo. Restyle every table at once by editing this one file.
"""

from __future__ import annotations

from great_tables import loc, nanoplot_options, style

FONT = ["Inter", "-apple-system", "Helvetica Neue", "Arial", "sans-serif"]
INK = "#111827"
MUTED = "#6B7280"
HLINE = "#EEF1F4"
GOOD = "#059669"
BAD = "#DC2626"
ACCENT = "#4F46E5"
ACCENT_FILL = "#E0E7FF"


def style_house(gt):
    """Apply the house look. Always safe to call (styles only column labels)."""
    gt = gt.tab_options(
        table_font_names=FONT,
        table_font_size="14px",
        table_font_color=INK,
        table_background_color="#FFFFFF",
        heading_title_font_size="16px",
        heading_title_font_weight="700",
        heading_subtitle_font_size="12px",
        column_labels_font_weight="600",
        column_labels_text_transform="uppercase",
        column_labels_font_size="11px",
        table_border_top_style="none",
        table_body_hlines_color=HLINE,
        table_body_hlines_width="1px",
        data_row_padding="9px",
        column_labels_padding="8px",
    )
    return gt.tab_style(style=style.text(color=MUTED), locations=loc.column_labels())


def nanoplot_house():
    """House-themed sparkline options (indigo line/area, red negative bars)."""
    return nanoplot_options(
        data_line_stroke_color=ACCENT,
        data_line_stroke_width=2,
        data_area_fill_color=ACCENT_FILL,
        data_point_fill_color=ACCENT,
        data_point_stroke_color="#FFFFFF",
        data_point_radius=3,
        data_bar_fill_color=ACCENT,
        data_bar_negative_fill_color=BAD,
    )
