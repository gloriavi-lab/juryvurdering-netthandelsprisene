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

st.session_state["_sh"] = koble_sheets()

sider = [
    st.Page("pages/oversikt.py", title="Oversikt", icon=":material/menu_book:", default=True),
    st.Page("pages/vurdering.py", title="Vurdering", icon=":material/edit_note:"),
    st.Page("pages/butikker.py", title="Butikker", icon=":material/storefront:"),
    st.Page("pages/finale.py", title="Finale", icon=":material/emoji_events:"),
    st.Page("pages/innstillinger.py", title="Innstillinger", icon=":material/settings:"),
]
nav = st.navigation(sider, position="top")
nav.run()
