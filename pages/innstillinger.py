"""Side 4 – Innstillinger: Google Sheets-tilkobling og butikkliste for fasen.
Flyttet hit fra sidepanelet slik at sidepanelet kun viser en liten statusprikk."""

import streamlit as st

from components import bekreft_fjern_liste, status_prikk, topptekst
from data import prosesser_opplastet_fil

topptekst("Innstillinger")

sh = st.session_state.get("_sh")

st.subheader("Google Sheets")
status_prikk(sh is not None)
if sh:
    st.link_button("Åpne regnearket", sh.url, icon=":material/open_in_new:")
else:
    with st.expander("Feilmelding"):
        st.code(st.session_state.get("_gsheets_feil", "Ukjent feil"))

st.divider()
st.subheader("Butikkliste for denne fasen")
st.caption("Last opp butikkene som gikk videre fra Fase 1 (Excel). Listen deles automatisk med alle jurymedlemmer via Google Sheets.")

butikkliste = st.session_state.get("butikkliste")

if butikkliste:
    filnavn = st.session_state.get("butikkliste_filnavn") or "Opplastet liste"
    st.markdown(
        f'<div class="kort-kompakt">📄 <strong>{filnavn}</strong><br>{len(butikkliste)} butikker lastet inn</div>',
        unsafe_allow_html=True,
    )
    st.write("")
    c1, c2 = st.columns(2)
    if c1.button("Bytt liste", icon=":material/upload_file:", use_container_width=True):
        st.session_state["_vis_ny_opplasting"] = True
    if c2.button("Fjern liste", icon=":material/delete:", use_container_width=True):
        bekreft_fjern_liste()

if not butikkliste or st.session_state.get("_vis_ny_opplasting"):
    ny_fil = st.file_uploader("Fase 1-Excel (.xlsx)", type=["xlsx"], key="innstillinger_opplaster")
    if ny_fil is not None and prosesser_opplastet_fil(ny_fil, sh):
        st.session_state["_vis_ny_opplasting"] = False
        st.success(f"✅ {len(st.session_state.butikkliste)} butikker lastet inn!", icon=":material/check_circle:")
        st.rerun()
