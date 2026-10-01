"""
Juryvurdering Netthandelsprisene – Ekspertvurdering (Fase 2)
==============================================================
Entry point. Setter opp tema, kobler til Google Sheets, laster delt tilstand
(butikkliste) én gang per økt, og definerer navigasjonen. Selve sidene ligger
i pages/, delt logikk i data.py (forretningslogikk) og components.py/styles.py
(UI-byggeklosser).

Arbeidsflyt – se README.md for full forklaring:
1. Fase 1 gjøres i et eget Excel-ark (utenfor denne appen). Topp ~50 derfra
   lastes opp her som butikklisten for fasen (lagres delt i Google Sheets).
2. Hvert jurymedlem vurderer butikkene på sitt eget fagfelt, 1–5 stjerner +
   kommentar per kriterium.
3. "Finale"-siden rangerer butikkene per størrelsesklasse basert på snittet
   av alle registrerte ekspertscorer.
"""

import streamlit as st

from components import status_prikk
from data import koble_sheets, hent_butikkliste, last_lokalt
from styles import injiser_css

st.set_page_config(page_title="Ekspertvurdering – Netthandelsprisene", page_icon="🎓", layout="wide")
injiser_css()

sh = koble_sheets()
st.session_state["_sh"] = sh

# Butikkliste lastes KUN én gang per økt: først fra det delte Google Sheet-et
# (overlever redeploy, lik for alle), så lokal snarvei som siste utvei.
if "butikkliste" not in st.session_state:
    fra_sheet, filnavn_fra_sheet = (None, None)
    if sh:
        try:
            fra_sheet, filnavn_fra_sheet = hent_butikkliste(sh)
        except Exception:
            pass
    if fra_sheet:
        st.session_state.butikkliste = fra_sheet
        st.session_state.butikkliste_filnavn = filnavn_fra_sheet
    else:
        lokal = last_lokalt() or {}
        st.session_state.butikkliste = lokal.get("butikker")
        st.session_state.butikkliste_filnavn = lokal.get("filnavn")

with st.sidebar:
    st.caption("🎓 Netthandelsprisene")
    status_prikk(sh is not None)
    if st.session_state.get("butikkliste"):
        st.caption(f":material/storefront: {len(st.session_state.butikkliste)} butikker lastet inn")

sider = [
    st.Page("pages/oversikt.py", title="Oversikt", icon=":material/menu_book:", default=True),
    st.Page("pages/vurdering.py", title="Vurdering", icon=":material/edit_note:"),
    st.Page("pages/finale.py", title="Finale", icon=":material/emoji_events:"),
    st.Page("pages/innstillinger.py", title="Innstillinger", icon=":material/settings:"),
]
nav = st.navigation(sider, position="top")
nav.run()
