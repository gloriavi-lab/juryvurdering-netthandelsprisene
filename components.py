"""Gjenbrukbare UI-byggeklosser, slik at hver side slipper å style ting selv."""

import re

import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode

from data import er_tall
from theme import FAGFELT_FARGE


def topptekst(sidetittel: str):
    """Toppområde med merke/tittel til venstre, og tilkoblingsstatus + valgt
    jurymedlem til høyre (sidepanelet er fjernet, se app.py)."""
    sh = st.session_state.get("_sh")
    jurynavn = st.session_state.get("_jurynavn")
    fagfelt = st.session_state.get("_fagfelt")

    prikk_klasse = "ok" if sh else "feil"
    prikk_tekst = "Tilkoblet" if sh else "Ikke tilkoblet"
    jury_html = f'<span class="jurymedlem-brikke">👤 {jurynavn}{" · " + fagfelt if fagfelt else ""}</span>' if jurynavn else ""

    st.markdown(
        f'<div class="topptekst">'
        f'<div><div class="merke-label">Netthandelsprisene · Fase 2 – Ekspertvurdering</div>'
        f'<div class="sidetittel">{sidetittel}</div></div>'
        f'<div class="hoyre">{jury_html}'
        f'<span class="status-prikk"><span class="prikk {prikk_klasse}"></span>{prikk_tekst}</span></div>'
        f"</div>",
        unsafe_allow_html=True,
    )


def status_prikk(tilkoblet: bool, tekst_ok="Tilkoblet til Google Sheets", tekst_feil="Ikke tilkoblet"):
    klasse = "ok" if tilkoblet else "feil"
    tekst = tekst_ok if tilkoblet else tekst_feil
    st.markdown(f'<span class="status-prikk"><span class="prikk {klasse}"></span>{tekst}</span>', unsafe_allow_html=True)


def klasse_badge(klasse: str):
    st.markdown(f'<span class="klasse-badge">{klasse or "–"}</span>', unsafe_allow_html=True)


def rutenett(kort_html_liste, tre_per_rad=False):
    """Tegner en liste med ferdig bygget indre-HTML som ETT samlet CSS-grid,
    slik at alle kortene i rutenettet garantert får lik bredde/høyde – også på
    en ufullstendig siste rad (den strekkes ikke ut, kun venstrejusteres)."""
    ekstra_klasse = " tre-per-rad" if tre_per_rad else ""
    indre = "".join(f'<div class="rutenett-kort">{kort}</div>' for kort in kort_html_liste)
    st.markdown(f'<div class="rutenett{ekstra_klasse}">{indre}</div>', unsafe_allow_html=True)


def fremdriftslinje(andel: float, tekst: str):
    prosent = max(0, min(100, round(andel * 100)))
    st.markdown(
        f'<div class="fremdrift-rad"><div style="flex:1;">'
        f'<div class="fremdrift-tekst">{tekst}</div>'
        f'<div class="fremdrift-bakgrunn"><div class="fremdrift-fyll" style="width:{prosent}%;"></div></div>'
        f"</div></div>",
        unsafe_allow_html=True,
    )


def lagringsstatus(tilstand: str, detalj: str = ""):
    """tilstand: "lagrer", "lagret", "feil" eller "" (ingenting vist)."""
    if tilstand == "lagrer":
        st.markdown('<div class="lagringsstatus">⏳ Lagrer …</div>', unsafe_allow_html=True)
    elif tilstand == "lagret":
        st.markdown(f'<div class="lagringsstatus ok">✓ Lagret {detalj}</div>', unsafe_allow_html=True)
    elif tilstand == "feil":
        st.markdown(f'<div class="lagringsstatus feil">⚠ Ikke lagret – prøv igjen{(" (" + detalj + ")") if detalj else ""}</div>', unsafe_allow_html=True)


def onboarding_steg(aktivt_steg: int):
    """aktivt_steg: 1 = sett opp regneark, 2 = vurder butikker, 3 = se finale."""
    navn = ["Sett opp regneark", "Vurder butikker", "Se finale"]
    html = '<div class="steg-rad">'
    for i, t in enumerate(navn, start=1):
        klasse = "aktiv" if i == aktivt_steg else ("ferdig" if i < aktivt_steg else "")
        merke = "✓ " if i < aktivt_steg else f"{i}. "
        html += f'<div class="steg {klasse}">{merke}{t}</div>'
        if i < len(navn):
            html += '<div class="steg-linje"></div>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def tom_tilstand(ikon: str, tittel: str, tekst: str):
    st.markdown(
        f'<div class="tom-tilstand"><div class="ikon">{ikon}</div>'
        f'<div class="tittel">{tittel}</div><div class="tekst">{tekst}</div></div>',
        unsafe_allow_html=True,
    )




def _slug(tekst: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", tekst.lower()).strip("_")


def regneark_tabell(butikker: dict, ratings: dict, kriterier_per_fagfelt: dict, navn_liste=None, hoyde: int = 600, fagfelt_liste=None):
    """Tabell som speiler regnearkets oppsett: grupperte, fargede overskrifter
    per fagfelt (nøyaktig samme farger som Netthandelsprisene_Fase 1.xlsx,
    se theme.py), kriteriene under, URL som lenken «Besøk →», og Butikk/Klasse
    festet ved horisontal scrolling. st.dataframe støtter ikke grupperte,
    fargede overskrifter – derfor streamlit-aggrid (ag-Grid) her, som gjør det
    ferdig (kolonnegrupper, egen styling per gruppe, faste kolonner, filter
    og sortering) i stedet for en hjemmesnekret HTML-tabell med manuell
    JS for de samme tingene. kriterier_per_fagfelt kommer fra jury.py (lest
    fra Kriterier-fanen) – IKKE hardkodet lenger."""
    fagfelt_liste = fagfelt_liste or list(kriterier_per_fagfelt.keys())
    navn_liste = navn_liste if navn_liste is not None else sorted(butikker.keys())

    rader = []
    for navn in navn_liste:
        info = butikker.get(navn, {})
        rad = {"Butikk": navn, "Klasse": info.get("klasse", "–"), "Bransje": info.get("bransje", "–"), "URL": info.get("url", "")}
        scorer = ratings.get(navn, {}).get("scorer", {})
        alle_tall = []
        for fagfelt in fagfelt_liste:
            for krit in kriterier_per_fagfelt.get(fagfelt, []):
                felt = f"{_slug(fagfelt)}__{_slug(krit)}"
                verdi = scorer.get(krit, "")
                rad[felt] = verdi
                if er_tall(verdi):
                    alle_tall.append(float(verdi))
        # ALDRI None her – pandas gjør det om til NaN, som ikke er gyldig JSON
        # og feilte stille i AgGrid-komponenten som "Component Error" i nettleseren.
        rad["Snitt"] = round(sum(alle_tall) / len(alle_tall), 2) if alle_tall else "–"
        rader.append(rad)
    df = pd.DataFrame(rader)

    # Returnerer et EKTE DOM-element (ikke en HTML-streng) – strenger blir i
    # noen ag-Grid-versjoner satt som ren tekst (innerText) i stedet for
    # tolket som HTML, som ga rå "<a href=...>"-tekst i cellen i stedet for
    # en klikkbar lenke. Et DOM-element unngår den tvetydigheten helt.
    lenke_renderer = JsCode(
        "function(params) {"
        "  if (!params.value) { return document.createTextNode(''); }"
        "  var a = document.createElement('a');"
        "  a.href = params.value; a.target = '_blank'; a.rel = 'noopener';"
        "  a.innerText = 'Besøk →'; a.style.color = '#C8102E';"
        "  return a;"
        "}"
    )
    kolonne_defs = [
        {"field": "Butikk", "headerName": "Butikk", "pinned": "left", "width": 170},
        {"field": "Klasse", "headerName": "Klasse", "pinned": "left", "width": 90},
        {"field": "Bransje", "headerName": "Bransje", "width": 160},
        {"field": "URL", "headerName": "Lenke", "width": 100, "cellRenderer": lenke_renderer},
    ]

    custom_css = {
        ".ag-root-wrapper, .ag-header-cell, .ag-cell, .ag-header-group-cell": {
            "font-family": "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important",
            "font-size": "13px !important",
        },
        ".ag-header": {"background-color": "var(--lys-bakgrunn, #FAFAF9) !important", "border-bottom": "1px solid var(--kant, #E5E3DF) !important"},
        ".ag-header-cell-text": {"color": "var(--tekst, #1C1C1C) !important", "font-weight": "600 !important"},
    }
    for fagfelt in fagfelt_liste:
        farge = FAGFELT_FARGE.get(fagfelt, "#888888")
        klasse_css = f"fagfelt-{_slug(fagfelt)}"
        barn = []
        for krit in kriterier_per_fagfelt.get(fagfelt, []):
            felt = f"{_slug(fagfelt)}__{_slug(krit)}"
            if felt not in df.columns:
                continue
            barn.append({
                "field": felt, "headerName": krit[:16] + ("…" if len(krit) > 16 else ""), "headerTooltip": krit, "width": 110,
                "cellStyle": JsCode(f"function(p) {{ return p.value ? {{backgroundColor: '{farge}22'}} : {{}}; }}"),
            })
        if barn:
            kolonne_defs.append({"headerName": fagfelt, "headerClass": klasse_css, "children": barn})
            custom_css[f".ag-header-group-cell.{klasse_css}"] = {
                "background-color": f"{farge} !important", "color": "white !important", "font-weight": "700",
            }
            custom_css[f".ag-header-group-cell.{klasse_css} .ag-header-group-text"] = {"color": "white !important"}

    kolonne_defs.append({"field": "Snitt", "headerName": "Snitt totalt", "pinned": "right", "width": 100})

    grid_options = {
        "columnDefs": kolonne_defs,
        "defaultColDef": {"resizable": True, "sortable": True, "filter": True},
        "tooltipShowDelay": 200,
        "headerHeight": 36,
        "groupHeaderHeight": 36,
    }
    AgGrid(
        df, gridOptions=grid_options, height=hoyde, allow_unsafe_jscode=True,
        fit_columns_on_grid_load=False, custom_css=custom_css, theme="streamlit",
    )


