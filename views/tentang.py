"""
views/tentang.py -- Tentang

Identitas aplikasi dan skripsi: judul, penulis, dosen pembimbing, metode
singkat, dan catatan penggunaan. Halaman ini terbuka untuk tamu.
Data identitas diatur di config.py (bagian "Tentang").
"""
from __future__ import annotations

import streamlit as st

import config
from src import ui


def _orang(peran: str, nama: str, detail: str, inisial: str, warna: str) -> str:
    return (f"<div class='ab-person' style='--c:{warna}'><div class='av'>{ui.esc(inisial)}</div>"
            f"<div><div class='role'>{ui.esc(peran)}</div><div class='nm'>{ui.esc(nama)}</div>"
            f"<div class='dt'>{detail}</div></div></div>")


def _inisial(nama: str) -> str:
    kata = [w for w in nama.replace(",", " ").split() if w[:1].isalpha() and "." not in w]
    return "".join(w[0] for w in kata[:2]).upper() or "?"


def render() -> None:
    st.html(
        "<div class='scr-hero'><div class='txt'>"
        "<div class='eyebrow'>Tentang</div>"
        f"<div class='ttl'>{ui.esc(config.APP_NAME)}</div>"
        f"<div class='sub'>{ui.esc(config.THESIS_TITLE)}</div>"
        "</div></div></div>")
    st.write("")

    pemb = [("Dosen Pembimbing 1", config.PEMBIMBING_1, config.PEMBIMBING_1_INST),
            ("Dosen Pembimbing 2", config.PEMBIMBING_2, config.PEMBIMBING_2_INST)]
    kartu = [_orang("Penulis", config.ABOUT_AUTHOR,
                    f"NIM {ui.esc(config.ABOUT_NIM)}<br>{ui.esc(config.ABOUT_PRODI)}<br>"
                    f"{ui.esc(config.ABOUT_FAKULTAS)}, {ui.esc(config.ABOUT_UNIV)}",
                    _inisial(config.ABOUT_AUTHOR), config.ROYAL)]
    kartu += [_orang(peran, nama, ui.esc(inst), _inisial(nama), warna)
              for (peran, nama, inst), warna in zip(pemb, (config.PERI, "#12A150"))]
    st.html(f"<div class='ab-grid'>{''.join(kartu)}</div>")
    st.write("")

    ui.disclaimer()
