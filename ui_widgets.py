"""Shared soccer and basketball interface components."""
import flet as ft

def card(content, padding=16, radius=16, border_color=None):
    bc = border_color or "#1e293b"
    return ft.Container(content=content, bgcolor="#0f172a",
                        border=ft.Border.all(1, bc),
                        border_radius=radius, padding=padding)


def dual_stat_bar(label_str, home_val, away_val, home_ratio, away_ratio, home_color, away_color):
    total = home_ratio + away_ratio
    home_pct = max(2, min(98, round(home_ratio / total * 100))) if total > 0 else 50
    away_pct = 100 - home_pct
    return ft.Column([
        ft.Row([
            ft.Text(str(home_val), size=12, color="#f1f5f9", weight=ft.FontWeight.W_600, font_family="monospace"),
            ft.Text(label_str, size=10, color="#94a3b8", expand=True, text_align=ft.TextAlign.CENTER),
            ft.Text(str(away_val), size=12, color="#f1f5f9", weight=ft.FontWeight.W_600, font_family="monospace"),
        ]),
        ft.Container(
            content=ft.Row([
                ft.Container(height=10, bgcolor=home_color,
                             border_radius=ft.BorderRadius.only(top_left=5, bottom_left=5), expand=home_pct),
                ft.Container(height=10, bgcolor=away_color,
                             border_radius=ft.BorderRadius.only(top_right=5, bottom_right=5), expand=away_pct),
            ], spacing=0),
            bgcolor="#0f172a", border=ft.Border.all(1, "#1e293b"), border_radius=5,
            padding=ft.Padding.all(2)),
    ], spacing=4)


def kit_dot(color):
    return ft.Container(width=10, height=10, bgcolor=color, border_radius=5,
                        border=ft.Border.all(1, "#334155"))


def action_btn(label, emoji, color, on_click, disabled=False, width=None):
    opacity = 0.35 if disabled else 1.0
    btn_color = color if not disabled else "#64748b"
    # A raw text emoji (e.g. "❌") depends on the OS/font providing a
    # color-emoji glyph, which packaged Flutter release builds don't
    # always have — it silently falls back to a "missing glyph"
    # placeholder there, which is what showed up as a bare "!" on the
    # Mark Incomplete buttons. ft.Icons are bundled directly inside every
    # Flet app's own icon font, so they always render identically
    # regardless of platform/OS font availability. Pass an ft.Icons value
    # instead of a string to use one.
    # A raw text emoji (e.g. "❌") depends on the OS/font providing a
    # color-emoji glyph, which packaged Flutter release builds don't
    # always have — it silently falls back to a "missing glyph"
    # placeholder there, which is what showed up as a bare "!" on the
    # Mark Incomplete buttons. ft.Icons are bundled directly inside every
    # Flet app's own icon font, so they always render identically
    # regardless of platform/OS font availability. Pass an ft.Icons value
    # instead of a string to use one. (Checked via "not a string" rather
    # than isinstance(emoji, ft.Icons) — ft.Icons is a proxy wrapper, not
    # the actual enum class, so isinstance() against it raises a TypeError.)
    icon_widget = (ft.Text(emoji, size=16) if isinstance(emoji, str)
                   else ft.Icon(emoji, size=16, color=btn_color))
    return ft.Container(
        content=ft.Row([
            icon_widget,
            ft.Text(label, size=11, color=btn_color, weight=ft.FontWeight.BOLD),
        ], spacing=6),
        bgcolor=(ft.Colors.with_opacity(0.12, color) if not disabled else "#0a0f1e"),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.35, color) if not disabled else "#1e293b"),
        border_radius=10,
        padding=ft.Padding.symmetric(horizontal=10, vertical=8),
        on_click=(None if disabled else on_click),
        ink=not disabled, opacity=opacity, width=width,
    )
