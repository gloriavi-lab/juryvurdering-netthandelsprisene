"""
Juryvurdering Netthandelsprisene – Ekspertvurdering (Fase 2)
==============================================================
Entry point. Setter opp tema, kobler til Google Sheets, og definerer
navigasjonen. Regnearket er fasiten (se sheets.py) – appen holder ingen egen
kopi av butikklisten mellom økter, den leses derfra med kort cache hver gang.

Sidepanelet er bevisst fjernet (se brief): tilkoblingsstatus og valgt
jurymedlem vises i stedet øverst til høyre i topptekst-komponenten på hver
side (components.topptekst).
"""

import os

import streamlit as st

from jury import aktiv_fase, read_faser
from sheets import koble_sheets
from styles import injiser_css

LOGO_STI = "assets/bring-logo.svg"

st.set_page_config(
    page_title="Ekspertvurdering – Netthandelsprisene",
    page_icon=LOGO_STI if os.path.exists(LOGO_STI) else "🎓",
    layout="wide", initial_sidebar_state="collapsed",
)
injiser_css()

if os.path.exists(LOGO_STI):
    st.logo(LOGO_STI)
# NB: assets/bring-logo.svg er ikke lagt inn ennå – appen fungerer fint uten,
# men logoen vises først når fila er på plass (se svar til bruker).

sh = koble_sheets()
st.session_state["_sh"] = sh

# Demper «Finale» i menyen («Kommende») helt til gjeldende fase faktisk ER
# Finale – samme fase-kilde som Innstillinger -> Fasestatus styrer.
finale_tittel = "Finale"
if sh:
    try:
        gjeldende = aktiv_fase(read_faser(sh))
        if not gjeldende or gjeldende.get("Navn") != "Finale":
            finale_tittel = "Finale (kommende)"
    except Exception:
        pass

sider = [
    st.Page("pages/oversikt.py", title="Oversikt", icon=":material/menu_book:", default=True),
    st.Page("pages/vurdering.py", title="Vurdering", icon=":material/edit_note:"),
    st.Page("pages/butikker.py", title="Butikker", icon=":material/storefront:"),
    st.Page("pages/testkjop.py", title="Testkjøp", icon=":material/shopping_cart:"),
    st.Page("pages/finale.py", title=finale_tittel, icon=":material/emoji_events:"),
    st.Page("pages/innstillinger.py", title="Innstillinger", icon=":material/settings:"),
]
nav = st.navigation(sider, position="top")
nav.run()
