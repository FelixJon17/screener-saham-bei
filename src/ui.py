"""
src/ui.py
Komponen antarmuka yang dipakai bersama oleh seluruh halaman, ditambah
pembungkus cache agar hasil perhitungan hanya dihitung sekali untuk setiap
hasil aktif.
"""
from __future__ import annotations

import html
import re

import numpy as np
import pandas as pd
from pandas.io.formats.style import Styler
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import config
from src import data_loader, dataset_store, pipeline, theme
from src.pipeline import PipelineOutput

CSS_PATH = config.BASE_DIR / "assets" / "style.css"
FONT = "Plus Jakarta Sans, Segoe UI, sans-serif"

# Diisi app.py dengan objek st.Page yang terdaftar untuk peran saat ini,
# supaya halaman lain bisa berpindah halaman lewat goto().
PAGES: dict[str, st.Page] = {}


# --------------------------------------------------------------------------
# Cache pipeline
# --------------------------------------------------------------------------
@st.cache_resource(show_spinner="Menghitung K-Means dan Random Forest…", max_entries=8)
def _pipeline(path: str, version: float, mode: str) -> PipelineOutput:
    """
    Menghitung hasil langsung dari dataset. Kunci cache: berkas dataset, waktu
    modifikasinya, dan konfigurasi data; mengganti salah satunya menghitung ulang.
    """
    return pipeline.from_file(path, mode)


def active_set(pribadi: bool = True) -> dataset_store.ActiveSet:
    """Dataset untuk sesi ini: dataset pribadi pengguna bila ada dan pribadi=True."""
    from src import auth
    u = auth.current_user() if pribadi else None
    return dataset_store.active(u["username"] if u else None)


def get_pipeline(pribadi: bool = True) -> PipelineOutput:
    ds = active_set(pribadi)
    try:
        return _pipeline(str(ds.path), ds.version, dataset_store.data_mode())
    except (FileNotFoundError, data_loader.SchemaError, ValueError, TypeError) as e:
        st.error(f"Dataset tidak dapat diproses: {e}")
        st.stop()


def clear_pipeline_cache() -> None:
    _pipeline.clear()
    _comparison.clear()


@st.cache_resource(show_spinner="Menghitung K-Means dan Random Forest untuk kedua K…",
                   max_entries=4)
def _comparison(path: str, version: float, mode: str, ka: int, kb: int):
    from src import compare
    from src.winsorizer import lower_for
    p = _pipeline(path, version, mode)
    lower = lower_for(p.data_mode)
    return compare.run_k(p.clu.data, ka, lower), compare.run_k(p.clu.data, kb, lower)


def get_comparison(ka: int = 3, kb: int = 4):
    ds = active_set()
    return _comparison(str(ds.path), ds.version, dataset_store.data_mode(), ka, kb)


# --------------------------------------------------------------------------
# Utilitas
# --------------------------------------------------------------------------
def winsor_text(p: PipelineOutput) -> str:
    """Mis. "winsorizing P95" atau "winsorizing P5–P95" sesuai konfigurasi data."""
    from src.winsorizer import lower_for
    lo = lower_for(p.data_mode)
    return (f"winsorizing P{lo}–P{config.WINSOR_PERCENTILE}" if lo
            else f"winsorizing P{config.WINSOR_PERCENTILE}")


def data_badge(p: PipelineOutput) -> str:
    """Teks singkat konfigurasi data aktif, mis. "Data positif · 627 saham"."""
    nama = "Data positif" if p.data_mode == config.DATA_POSITIF else "Seluruh data"
    return f"{nama} · {len(p.table)} saham"


def sector_means(p: PipelineOutput) -> pd.DataFrame:
    """
    Tolok ukur sektor: rata-rata PER dan PBV hasil winsorizing (μ yang dipakai
    Z-score, dari statistik_sektor.csv) beserta simpangan bakunya, ditambah
    rata-rata ROE dan DER hasil winsorizing setiap sektor.
    """
    d = p.clu.data
    g = d.groupby(config.COL_SEKTOR)
    # ROE dan DER: nilai hasil winsorizing (masukan Random Forest) bila tersedia, agar
    # rata-rata tidak terseret nilai ekstrem (mis. ROE -3.698 pada konfigurasi "semua").
    roe = f"{config.COL_ROE}_w" if f"{config.COL_ROE}_w" in d else config.COL_ROE
    der = f"{config.COL_DER}_w" if f"{config.COL_DER}_w" in d else config.COL_DER
    out = pd.DataFrame({"Jumlah": g[config.COL_KODE].count(),
                        "ROE": g[roe].mean(), "DER": g[der].mean()})
    st_ = p.sector_stats
    if st_ is not None and {"mu_PER", "mu_PBV"} <= set(st_.columns):
        out["PER"], out["PBV"] = st_["mu_PER"], st_["mu_PBV"]
        out["Std PER"], out["Std PBV"] = st_["sigma_PER"], st_["sigma_PBV"]
    else:   # cadangan: hitung dari kolom hasil winsorizing di tabel notebook
        cols = {c: (f"{c}_w" if f"{c}_w" in d else c) for c in ("PER", "PBV")}
        for c, src in cols.items():
            out[c], out[f"Std {c}"] = g[src].mean(), g[src].std(ddof=config.ZSCORE_DDOF)
    out["Std ROE"] = g[roe].std(ddof=config.ZSCORE_DDOF)
    out["Std DER"] = g[der].std(ddof=config.ZSCORE_DDOF)
    return out[["Jumlah", "PER", "PBV", "ROE", "DER", "Std PER", "Std PBV", "Std ROE",
                "Std DER"]]


def inject_css() -> None:
    st.html(f"<style>{CSS_PATH.read_text(encoding='utf-8')}{theme.css_overrides()}</style>")


def tc(name: str) -> str:
    """Warna sesuai mode aktif (lihat src/theme.py), mis. tc("strong")."""
    return theme.colors()[name]


def accent(c: str | None) -> str | None:
    """Royal terlalu gelap di mode gelap; ganti dengan periwinkle."""
    return config.PERI if c == config.ROYAL and theme.is_dark() else c


def goto(name: str, **state) -> None:
    for k, v in state.items():
        st.session_state[k] = v
    st.switch_page(PAGES[name])


def esc(x) -> str:
    return html.escape(str(x))


def color_of(kategori: str) -> str:
    return config.COLOR_MAP.get(kategori, config.COLOR_FALLBACK)


def short(kategori: str) -> str:
    """Mis. "Relatif Rendah (Undervalue)"."""
    return config.LABEL_SHORT.get(kategori, kategori)


def tiny(kategori: str) -> str:
    """Mis. "Rendah", untuk sumbu grafik dan matriks."""
    return config.LABEL_TINY.get(kategori, kategori.replace("Valuasi Relatif ", ""))


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


_DESIMAL = re.compile(r"^[\s+\-−]*\d[\d.,]*[.,]\d+([\s±()+\-−\d.,]*)$")
_BULAT = re.compile(r"^[\s+\-−]*\d+$")


def _alignment(s: pd.Series, cfg: dict) -> str | None:
    """Angka desimal rata kanan, angka bulat di tengah, teks dibiarkan rata kiri."""
    fmt = (cfg.get("type_config") or {}).get("format") or ""
    if pd.api.types.is_bool_dtype(s):
        return None
    if pd.api.types.is_integer_dtype(s) or fmt == "%d":
        return "center"
    if pd.api.types.is_float_dtype(s):
        v = s.dropna()
        bulat = not fmt and len(v) and bool((v == v.round()).all())
        return "center" if bulat else "right"
    v = s.dropna().astype(str)
    desimal, bulat = v.str.match(_DESIMAL), v.str.match(_BULAT)
    if not len(v) or not (desimal | bulat).all():
        return None
    return "right" if desimal.any() else "center"


def table(data, column_config: dict | None = None, **kw):
    """
    st.dataframe dengan perataan seragam di seluruh aplikasi: kolom angka
    desimal rata kanan, angka bulat di tengah. Perataan yang sudah diisi pada
    column_config tidak diubah.
    """
    df = data.data if isinstance(data, Styler) else pd.DataFrame(data)
    cfg = dict(column_config or {})
    for col in df.columns:
        if not isinstance(col, str):
            continue
        c = cfg.get(col)
        c = {"label": c} if isinstance(c, str) else dict(c or {})
        if c.get("alignment") is None and (al := _alignment(df[col], c)):
            c["alignment"] = al
            cfg[col] = c
    if not kw.get("hide_index") and pd.api.types.is_integer_dtype(df.index):
        cfg.setdefault("_index", {"alignment": "center"})
    return st.dataframe(data, column_config=cfg, **kw)


def missing_note(p: PipelineOutput) -> str | None:
    """Keterangan saham yang tidak dihitung karena datanya kosong (mis. FREN)."""
    d = p.pre.dropped.get("missing_value") if p.pre is not None else None
    if d is None or d.empty:
        return None
    nama = {config.COL_PER: "PER", config.COL_PBV: "PBV", config.COL_ROE: "ROE",
            config.COL_DER: "DER"}

    def gabung(xs: list[str]) -> str:
        if len(xs) <= 2:
            return " dan ".join(xs)
        return ", ".join(xs[:-1]) + ", dan " + xs[-1]

    item = [(r[config.COL_KODE], [n for c, n in nama.items() if pd.isna(r[c])])
            for _, r in d.iterrows()]
    if len(item) == 1:
        kode, kosong = item[0]
        return (f"Saham {kode} tidak dimasukkan dalam perhitungan karena tidak memiliki "
                f"data {gabung(kosong)}.")
    return ("Saham berikut tidak dimasukkan dalam perhitungan karena datanya tidak lengkap: "
            + "; ".join(f"{k} (tanpa {gabung(m)})" for k, m in item) + ".")


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
        f"<div class='v' style=\"color:{accent(c) or 'var(--title)'}\">{esc(val)}</div></div>"
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
        c = accent(it.get("color") or config.COLOR_PRIMARY)
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


def category_cards(df: pd.DataFrame, colors: dict | None = None) -> None:
    total = max(len(df), 1)
    order = [k for k in config.LABEL_ORDER if k in df["Kategori"].unique()]
    order += [k for k in df["Kategori"].unique() if k not in order]
    cards = []
    for kat in order:
        sub = df[df["Kategori"] == kat]
        pct = len(sub) / total * 100
        c = (colors or {}).get(kat) or color_of(kat)
        cards.append(
            f"<div class='cat-card' style='--c:{c};--bg:{_hex_rgba(c, .1)}'>"
            f"<div class='top'><span class='name'><span class='cdot' style='background:{c}'></span>"
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
    palette = {"info": "#1B2CC1", "warn": "#D97706", "ok": "#16A34A", "bad": "#DC2626",
               "neutral": "#5B6B92"}
    c = palette.get(kind, palette["info"])
    ttl = f"<div class='ttl'>{esc(title)}</div>" if title else ""
    st.html(f"<div class='callout' style='--bg:{_hex_rgba(c, .07)};--bd:{_hex_rgba(c, .25)}'>"
            f"{ttl}{text}</div>")


def disclaimer() -> None:
    st.caption("Label valuasi adalah hasil pengelompokan statistik PER dan PBV relatif "
               "sektor, bukan rekomendasi jual atau beli.")


def sidebar() -> None:
    """Kartu pengguna (atau ajakan masuk bagi tamu), mode tema, dan tombol keluar."""
    from src import auth

    u = auth.current_user()
    with st.sidebar:
        if not u:
            st.html("<div class='user-card guest'><div class='av'>"
                    "</div><div>"
                    "<div class='nm'>Mode tamu</div>"
                    "<span class='rl user'>Akses Screener</span></div></div>")
            a, b = st.columns([4, 1], gap="small")
            if a.button("Masuk", icon=":material/login:", type="primary", width="stretch"):
                goto("masuk")
            with b:
                theme.toggle(key="theme_sb", label=False)
            return
        # Kartu pengguna = tombol menuju halaman Profil (tidak tampil di menu).
        if st.button(f"**{u['full_name']}**  \n{config.ROLE_LABEL[u['role']]}",
                     icon=":material/account_circle:", width="stretch", key="profil_card",
                     help="Profil dan kata sandi"):
            goto("profil")
        ds = active_set()
        if ds.pribadi:
            st.html(f"<div class='sb-ds'>Dataset Anda: <b>{esc(ds.label)}</b></div>")
        a, b = st.columns([4, 1], gap="small")
        if a.button("Keluar", icon=":material/logout:", width="stretch"):
            auth.logout()
            st.rerun()
        with b:
            theme.toggle(key="theme_sb", label=False)


def brand_logo() -> None:
    st.logo(str(config.LOGO_WIDE), size="large", icon_image=str(config.LOGO_ICON))


def logo_img(size: int = 42) -> str:
    """Logo ValuMap sebagai <img> base64 untuk blok HTML (mis. halaman login)."""
    import base64
    data = base64.b64encode(config.LOGO_ICON.read_bytes()).decode()
    return (f"<img class='brand-logo' src='data:image/png;base64,{data}' "
            f"width='{size}' height='{size}' alt='{esc(config.APP_NAME)}'>")


# --------------------------------------------------------------------------
# Grafik
# --------------------------------------------------------------------------
def style_fig(fig: go.Figure, height: int = 460, legend: bool = True) -> go.Figure:
    """
    Gaya seragam seluruh grafik: latar transparen (mengikuti kartu), hanya
    garis bantu horizontal yang tipis, sumbu tanpa garis nol, dan toolbar
    Plotly yang samar (muncul jelas saat kursor di atas grafik, lihat CSS).
    """
    has_title = bool(fig.layout.title.text)
    if has_title:
        # Hanya bila judul ada: objek judul tanpa teks ditampilkan Streamlit
        # sebagai "undefined".
        fig.update_layout(title_font=dict(size=14, color=tc("strong")), title_x=0)
    fig.update_layout(
        height=height,
        font=dict(family=FONT, size=12, color=tc("text")),
        margin=dict(t=(40 if has_title else 10) + (30 if legend else 0), b=30, l=10, r=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(bgcolor=tc("hover_bg"), font_color="#FFFFFF", font_family=FONT,
                        bordercolor=tc("hover_bg")),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                    title_text="", font=dict(size=11), itemsizing="constant"),
        modebar=dict(bgcolor="rgba(0,0,0,0)", color=tc("muted"),
                     activecolor=accent(config.ROYAL)),
    )
    axis = dict(gridcolor=tc("grid"), gridwidth=1, zeroline=False, linecolor=tc("line"),
                tickfont=dict(size=11, color=tc("muted")),
                title_font=dict(size=12, color=tc("muted")))
    fig.update_xaxes(showgrid=False, showline=True, ticks="", **axis)
    fig.update_yaxes(showgrid=True, showline=False, **axis)
    return fig


def horizontal(fig: go.Figure) -> go.Figure:
    """Untuk batang horizontal: garis bantu vertikal, tanpa garis bantu per kategori."""
    fig.update_xaxes(showgrid=True, showline=False)
    fig.update_yaxes(showgrid=False, showline=False)
    return fig


def zero_lines(fig: go.Figure) -> go.Figure:
    """Garis acuan Z = 0 (rata-rata sektor) yang tipis dan tidak putus-putus."""
    garis = dict(line_width=1.2, line_color=tc("line"), layer="below")
    fig.add_hline(y=0, **garis)
    fig.add_vline(x=0, **garis)
    return fig


def mark_k(fig: go.Figure, k: float, text: str, color: str, y: float | None = None,
           band: bool = False, below: bool = False) -> go.Figure:
    """
    Penanda K pada grafik evaluasi: pita lembut (band=True) untuk K yang
    dipakai, atau label kecil berpanah yang menunjuk titik (y) untuk K terbaik.
    """
    if band:
        fig.add_vrect(x0=k - .28, x1=k + .28, fillcolor=_hex_rgba(color, .12), line_width=0,
                      layer="below")
        fig.add_annotation(x=k, y=1, yref="paper", yanchor="bottom", text=f"<b>{text}</b>",
                           showarrow=False, font=dict(size=11, color=color))
    else:
        fig.add_annotation(x=k, y=y, text=text, showarrow=True, arrowhead=0, arrowwidth=1.2,
                           arrowcolor=color, ax=0, ay=34 if below else -34,
                           font=dict(size=11, color="#FFFFFF"),
                           bgcolor=color, borderpad=3)
    return fig


def html_table(df: pd.DataFrame, fmt: dict | None = None, index: bool = True) -> str:
    """
    Tabel HTML dengan header di tengah, termasuk header dua tingkat (kolom
    MultiIndex). Angka desimal rata kanan, angka bulat di tengah, teks rata kiri.
    fmt: format per kolom (nama kolom atau tuple MultiIndex), mis. "{:.2f}".
    """
    fmt = fmt or {}
    cols = list(df.columns)
    multi = isinstance(df.columns, pd.MultiIndex)
    head = "<thead>"
    if multi:
        head += "<tr>" + (f"<th rowspan='2'>{esc(df.index.name or '')}</th>" if index else "")
        top = [c[0] for c in cols]
        i = 0
        while i < len(cols):
            n = 1
            while i + n < len(cols) and top[i + n] == top[i] and top[i]:
                n += 1
            if top[i]:
                head += f"<th colspan='{n}' class='grp'>{esc(top[i])}</th>"
            else:
                head += f"<th rowspan='2'>{esc(cols[i][1])}</th>"
            i += n
        head += "</tr><tr>" + "".join(f"<th>{esc(c[1])}</th>" for c in cols if c[0]) + "</tr>"
    else:
        head += ("<tr>" + (f"<th>{esc(df.index.name or '')}</th>" if index else "")
                 + "".join(f"<th>{esc(c)}</th>" for c in cols) + "</tr>")
    head += "</thead>"

    def cell(c, v) -> str:
        if isinstance(v, (int, np.integer)) or (isinstance(v, float) and float(v).is_integer()
                                                 and c not in fmt):
            return f"<td class='c'>{int(v)}</td>"
        if isinstance(v, (float, np.floating)):
            return f"<td class='r'>{fmt.get(c, '{:.2f}').format(v)}</td>"
        return f"<td>{v if str(v).startswith('<') else esc(v)}</td>"

    body = "".join(
        "<tr>" + (f"<td class='lbl'>{i if str(i).startswith('<') else esc(i)}</td>"
                  if index else "")
        + "".join(cell(c, r[c]) for c in cols) + "</tr>"
        for i, r in df.iterrows())
    return f"<div class='vt-wrap'><table class='vt'>{head}<tbody>{body}</tbody></table></div>"


def color_map_for(df: pd.DataFrame) -> dict:
    return {k: color_of(k) for k in df["Kategori"].unique()}


def scatter_cluster(df: pd.DataFrame, x: str, y: str, title: str = "",
                    highlight: str | None = None, log: bool = False,
                    height: int = 520, colors: dict | None = None) -> go.Figure:
    fig = px.scatter(
        df, x=x, y=y, color="Kategori",
        color_discrete_map=colors or color_map_for(df),
        custom_data=[config.COL_KODE, config.COL_SEKTOR, config.COL_PER,
                     config.COL_PBV, config.COL_ROE, config.COL_DER],
        category_orders={"Kategori": config.LABEL_ORDER},
        title=title or None, log_x=log, log_y=log,
    )
    fig.update_traces(
        marker=dict(size=9, opacity=0.85, line=dict(width=1, color=tc("plot_bg"))),
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
                marker=dict(size=24, symbol="star", color=tc("strong"),
                            line=dict(width=2, color=tc("plot_bg"))),
                text=[f"<b>{highlight}</b>"], textposition="top center",
                textfont=dict(size=14, color=tc("strong")),
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
        marker=dict(colors=[color_of(k) for k in cnt.index], line=dict(color=tc("plot_bg"), width=3)),
        textinfo="percent", sort=False,
        hovertemplate="<b>%{label}</b><br>%{value} saham (%{percent})<extra></extra>",
    ))
    fig.add_annotation(text=f"<b style='font-size:26px'>{len(df)}</b><br>saham",
                       showarrow=False, font=dict(size=13, color=tc("strong")))
    return style_fig(fig, height)


def bar_sector(df: pd.DataFrame, value_col: str, title: str, xlab: str,
               color: str = config.COLOR_PRIMARY, highlight: str | None = None) -> go.Figure:
    d = df.sort_values(value_col, ascending=True).reset_index()
    colors = [(tc("strong") if s == highlight else color) for s in d[config.COL_SEKTOR]]
    fig = go.Figure(go.Bar(
        x=d[value_col], y=d[config.COL_SEKTOR], orientation="h",
        marker=dict(color=colors, cornerradius=6),
        text=[fmt_num(v) for v in d[value_col]], textposition="outside",
        hovertemplate="<b>%{y}</b><br>" + xlab + ": %{x:.2f}<extra></extra>",
    ))
    fig.update_layout(title=title, xaxis_title=xlab, yaxis_title="")
    return horizontal(style_fig(fig, 440, legend=False))


def heatmap_confusion(cm: pd.DataFrame, title: str) -> go.Figure:
    xs = [tiny(c.replace("Prediksi: ", "")) for c in cm.columns]
    ys = [tiny(i.replace("Aktual: ", "")) for i in cm.index]
    fig = px.imshow(cm.values, x=xs, y=ys, text_auto=True,
                    color_continuous_scale=[tc("scale_lo"), tc("scale_hi")], title=title,
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
