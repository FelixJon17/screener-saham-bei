"""
src/ui.py
Komponen antarmuka yang dipakai bersama oleh seluruh halaman, ditambah
pembungkus cache agar hasil notebook hanya dimuat sekali untuk setiap set
hasil aktif.
"""
from __future__ import annotations

import html

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import config
from src import data_loader, dataset_store, pipeline
from src.pipeline import PipelineOutput

CSS_PATH = config.BASE_DIR / "assets" / "style.css"
FONT = "Plus Jakarta Sans, Segoe UI, sans-serif"

# Diisi app.py dengan objek st.Page yang terdaftar untuk peran saat ini,
# supaya halaman lain bisa berpindah halaman lewat goto().
PAGES: dict[str, st.Page] = {}


# --------------------------------------------------------------------------
# Cache pipeline
# --------------------------------------------------------------------------
@st.cache_resource(show_spinner="Memuat hasil notebook (K-Means & Random Forest)…",
                   max_entries=4)
def _pipeline(path: str, version: float) -> PipelineOutput:
    """
    Kunci cache: folder set hasil dan waktu modifikasi berkasnya. Mengganti set
    aktif atau menimpa berkasnya memicu pemuatan ulang.
    """
    return pipeline.load(path)


def get_pipeline() -> PipelineOutput:
    ds = dataset_store.active()
    try:
        return _pipeline(str(ds.path), ds.version)
    except (FileNotFoundError, data_loader.SchemaError, ValueError, TypeError) as e:
        st.error(f"Set hasil aktif tidak dapat dimuat: {e}")
        st.stop()


def clear_pipeline_cache() -> None:
    _pipeline.clear()
    _comparison.clear()


@st.cache_resource(show_spinner="Menghitung K-Means dan Random Forest untuk kedua K "
                                "(± 30 detik, sekali saja)…", max_entries=4)
def _comparison(path: str, version: float, ka: int, kb: int):
    from src import compare
    data = _pipeline(path, version).clu.data
    return compare.run_k(data, ka), compare.run_k(data, kb)


def get_comparison(ka: int = 3, kb: int = 4):
    ds = dataset_store.active()
    return _comparison(str(ds.path), ds.version, ka, kb)


# --------------------------------------------------------------------------
# Utilitas
# --------------------------------------------------------------------------
def inject_css() -> None:
    st.html(f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>")


def goto(name: str, **state) -> None:
    for k, v in state.items():
        st.session_state[k] = v
    st.switch_page(PAGES[name])


def esc(x) -> str:
    return html.escape(str(x))


def color_of(kategori: str) -> str:
    return config.COLOR_MAP.get(kategori, config.COLOR_FALLBACK)


def short(kategori: str) -> str:
    return config.LABEL_SHORT.get(kategori, kategori)


def with_label(df: pd.DataFrame) -> pd.DataFrame:
    """Menambahkan kolom 'Valuasi' berlabel pendek untuk tabel."""
    out = df.copy()
    out.insert(2, "Valuasi", out["Kategori"].map(short))
    return out


def dot_html(kategori: str) -> str:
    """Titik warna kategori (pengganti emoji)."""
    return f"<span class='cdot' style='background:{color_of(kategori)}'></span>"


def fmt_num(x: float, nd: int = 2) -> str:
    return f"{x:,.{nd}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _hex_rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


# --------------------------------------------------------------------------
# Blok HTML
# --------------------------------------------------------------------------
def hero(title: str, desc: str, eyebrow: str = "", chips: list[str] | None = None) -> None:
    chips_html = "".join(f"<span class='chip'>{c}</span>" for c in (chips or []))
    st.html(
        f"<div class='hero'><div class='eyebrow'>{esc(eyebrow)}</div>"
        f"<div class='title'>{esc(title)}</div><div class='desc'>{desc}</div>"
        f"<div class='chips'>{chips_html}</div></div>"
    )


def market_header(title: str, meta: str, kpis: list[tuple[str, str, str | None]]) -> None:
    """
    Kepala halaman bergaya terminal: judul, satu baris keterangan, dan strip
    KPI. kpis: (label, nilai, warna aksen atau None).
    """
    cells = "".join(
        f"<div class='kpi'><div class='k'>{esc(lbl)}</div>"
        f"<div class='v' style=\"color:{c or '#0F172A'}\">{esc(val)}</div></div>"
        for lbl, val, c in kpis
    )
    st.html(f"<div class='mkt-head'><div><div class='t'>{esc(title)}</div>"
            f"<div class='m'>{meta}</div></div><div class='kpis'>{cells}</div></div>")


def page_header(title: str, desc: str = "", icon: str = "") -> None:
    """Judul halaman dengan garis aksen. Parameter icon diabaikan (tanpa emoji)."""
    st.html(
        f"<div class='page-head'><div class='bar'></div><div>"
        f"<div class='title'>{esc(title)}</div><div class='desc'>{esc(desc)}</div>"
        f"</div></div>"
    )


def stat_cards(items: list[dict]) -> None:
    """items: dict(label, value, sub, color). Kunci icon diabaikan (tanpa emoji)."""
    cards = []
    for it in items:
        c = it.get("color", config.COLOR_PRIMARY)
        cards.append(
            f"<div class='stat-card' style='--c:{c}'><div>"
            f"<div class='lbl'>{esc(it['label'])}</div>"
            f"<div class='val{' sm' if len(str(it['value'])) > 9 else ''}'>"
            f"{esc(it['value'])}</div>"
            f"<div class='sub'>{it.get('sub', '')}</div></div></div>"
        )
    st.html(f"<div class='stat-grid'>{''.join(cards)}</div>")


def badge_html(kategori: str) -> str:
    c = color_of(kategori)
    return (f"<span class='badge' style='--c:{c};--bg:{_hex_rgba(c, .1)};"
            f"--bd:{_hex_rgba(c, .3)}'><span class='dot'></span>{esc(short(kategori))}</span>")


def category_cards(df: pd.DataFrame) -> None:
    total = max(len(df), 1)
    order = [k for k in config.LABEL_ORDER if k in df["Kategori"].unique()]
    order += [k for k in df["Kategori"].unique() if k not in order]
    cards = []
    for kat in order:
        sub = df[df["Kategori"] == kat]
        pct = len(sub) / total * 100
        c = color_of(kat)
        cards.append(
            f"<div class='cat-card' style='--c:{c};--bg:{_hex_rgba(c, .1)}'>"
            f"<div class='top'><span class='name'>{dot_html(kat)}"
            f"{esc(short(kat))}</span><span class='pct'>{fmt_num(pct, 1)}%</span></div>"
            f"<div class='count'>{len(sub)} <small>saham</small></div>"
            f"<div class='bar'><span style='width:{pct:.1f}%'></span></div>"
            f"<div class='desc'>{esc(config.LABEL_DESC.get(kat, ''))}</div>"
            f"<div class='meta'><span>PER <b>{fmt_num(sub[config.COL_PER].median())}</b></span>"
            f"<span>PBV <b>{fmt_num(sub[config.COL_PBV].median())}</b></span>"
            f"<span>ROE <b>{fmt_num(sub[config.COL_ROE].median())}%</b></span>"
            f"<span class='lbl'>median</span></div>"
            f"</div>"
        )
    st.html(f"<div class='cat-grid'>{''.join(cards)}</div>")


def callout(text: str, title: str = "", kind: str = "info", icon: str = "") -> None:
    palette = {"info": "#2563EB", "warn": "#D97706", "ok": "#16A34A", "bad": "#DC2626",
               "neutral": "#64748B"}
    c = palette.get(kind, palette["info"])
    ttl = f"<div class='ttl'>{esc(title)}</div>" if title else ""
    st.html(f"<div class='callout' style='--bg:{_hex_rgba(c, .07)};--bd:{_hex_rgba(c, .25)}'>"
            f"{ttl}{text}</div>")


def disclaimer() -> None:
    st.caption("Label valuasi adalah hasil pengelompokan statistik PER dan PBV relatif "
               "sektor, bukan rekomendasi jual atau beli.")


def sidebar() -> None:
    """Identitas aplikasi, kartu pengguna, dan tombol keluar."""
    from src import auth

    u = auth.current_user()
    if not u:
        return
    with st.sidebar:
        initials = "".join(w[0] for w in u["full_name"].split()[:2]).upper() or "?"
        st.html(
            f"<div class='user-card'><div class='av'>{esc(initials)}</div><div>"
            f"<div class='nm'>{esc(u['full_name'])}</div>"
            f"<span class='rl {u['role']}'>{esc(config.ROLE_LABEL[u['role']])}</span>"
            f"</div></div>"
        )
        if st.button("Keluar", icon=":material/logout:", width="stretch"):
            auth.logout()
            st.rerun()


def brand_logo() -> None:
    assets = config.BASE_DIR / "assets"
    st.logo(str(assets / "logo.svg"), size="large", icon_image=str(assets / "logo_icon.svg"))


# --------------------------------------------------------------------------
# Grafik
# --------------------------------------------------------------------------
def style_fig(fig: go.Figure, height: int = 460, legend: bool = True) -> go.Figure:
    has_title = bool(fig.layout.title.text)
    if has_title:
        # Hanya bila judul ada: objek judul tanpa teks ditampilkan Streamlit
        # sebagai "undefined".
        fig.update_layout(title_font=dict(size=15, color="#0F172A"))
    fig.update_layout(
        height=height,
        font=dict(family=FONT, size=12, color="#334155"),
        margin=dict(t=(40 if has_title else 10) + (30 if legend else 0), b=30, l=10, r=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#FFFFFF",
        hoverlabel=dict(bgcolor="#0F172A", font_color="#FFFFFF", font_family=FONT,
                        bordercolor="#0F172A"),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    fig.update_xaxes(gridcolor="#EEF2F7", zerolinecolor="#CBD5E1")
    fig.update_yaxes(gridcolor="#EEF2F7", zerolinecolor="#CBD5E1")
    return fig


def color_map_for(df: pd.DataFrame) -> dict:
    return {k: color_of(k) for k in df["Kategori"].unique()}


def scatter_cluster(df: pd.DataFrame, x: str, y: str, title: str = "",
                    highlight: str | None = None, log: bool = False,
                    height: int = 520) -> go.Figure:
    fig = px.scatter(
        df, x=x, y=y, color="Kategori",
        color_discrete_map=color_map_for(df),
        custom_data=[config.COL_KODE, config.COL_SEKTOR, config.COL_PER,
                     config.COL_PBV, config.COL_ROE, config.COL_DER],
        category_orders={"Kategori": config.LABEL_ORDER},
        title=title or None, log_x=log, log_y=log,
    )
    fig.update_traces(
        marker=dict(size=9, opacity=0.78, line=dict(width=1, color="white")),
        hovertemplate=(
            "<b>%{customdata[0]}</b> · %{customdata[1]}<br>"
            "PER %{customdata[2]:.2f} · PBV %{customdata[3]:.2f}<br>"
            "ROE %{customdata[4]:.2f}% · DER %{customdata[5]:.2f}<extra></extra>"
        ),
    )
    fig.for_each_trace(lambda t: t.update(name=short(t.name)))
    if highlight:
        row = df[df[config.COL_KODE] == highlight]
        if len(row):
            fig.add_trace(go.Scatter(
                x=row[x], y=row[y], mode="markers+text",
                marker=dict(size=24, symbol="star", color="#0F172A",
                            line=dict(width=2, color="white")),
                text=[f"<b>{highlight}</b>"], textposition="top center",
                textfont=dict(size=14, color="#0F172A"),
                name=highlight, hoverinfo="skip",
            ))
    return style_fig(fig, height)


def donut_categories(df: pd.DataFrame, height: int = 320) -> go.Figure:
    cnt = df["Kategori"].value_counts()
    order = [k for k in config.LABEL_ORDER if k in cnt.index] + \
            [k for k in cnt.index if k not in config.LABEL_ORDER]
    cnt = cnt.reindex(order)
    fig = go.Figure(go.Pie(
        labels=[short(k) for k in cnt.index], values=cnt.values, hole=0.62,
        marker=dict(colors=[color_of(k) for k in cnt.index], line=dict(color="white", width=3)),
        textinfo="percent", sort=False,
        hovertemplate="<b>%{label}</b><br>%{value} saham (%{percent})<extra></extra>",
    ))
    fig.add_annotation(text=f"<b style='font-size:26px'>{len(df)}</b><br>saham",
                       showarrow=False, font=dict(size=13, color="#0F172A"))
    return style_fig(fig, height)


def bar_sector(df: pd.DataFrame, value_col: str, title: str, xlab: str,
               color: str = config.COLOR_PRIMARY, highlight: str | None = None) -> go.Figure:
    d = df.sort_values(value_col, ascending=True).reset_index()
    colors = [("#0F172A" if s == highlight else color) for s in d[config.COL_SEKTOR]]
    fig = go.Figure(go.Bar(
        x=d[value_col], y=d[config.COL_SEKTOR], orientation="h",
        marker=dict(color=colors, cornerradius=6),
        text=[fmt_num(v) for v in d[value_col]], textposition="outside",
        hovertemplate="<b>%{y}</b><br>" + xlab + ": %{x:.2f}<extra></extra>",
    ))
    fig.update_layout(title=title, xaxis_title=xlab, yaxis_title="")
    return style_fig(fig, 440, legend=False)


def heatmap_confusion(cm: pd.DataFrame, title: str) -> go.Figure:
    xs = [short(c.replace("Prediksi: ", "")) for c in cm.columns]
    ys = [short(i.replace("Aktual: ", "")) for i in cm.index]
    fig = px.imshow(cm.values, x=xs, y=ys, text_auto=True,
                    color_continuous_scale=["#EFF6FF", "#1D4ED8"], title=title,
                    labels=dict(x="Prediksi", y="Aktual", color="Jumlah"))
    fig.update_traces(textfont=dict(size=16))
    fig.update_layout(coloraxis_showscale=False)
    return style_fig(fig, 420, legend=False)


def selected_code(event) -> str | None:
    """Mengambil kode saham dari titik yang diklik pada st.plotly_chart."""
    try:
        pts = event.selection.points
    except AttributeError:
        return None
    for pt in pts or []:
        cd = pt.get("customdata")
        if cd:
            return cd[0] if isinstance(cd, (list, tuple)) else cd
    return None
