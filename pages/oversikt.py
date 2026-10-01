"""Side 1 – Oversikt: kriterier, klassedefinisjoner og veien til finalen."""

import streamlit as st

from components import onboarding_steg, topptekst
from data import FAGFELT, KLASSE_DEFINISJON, KRITERIER_PER_FAGFELT

topptekst("Oversikt")

butikkliste = st.session_state.get("butikkliste")
steg = 1 if not butikkliste else (3 if st.session_state.get("_besokt_finale") else 2)
onboarding_steg(steg)

st.caption(
    "Hvert kriterium vurderes fra 1 til 5 stjerner (1 = svak, 5 = utmerket), med mulighet "
    "for å legge inn en kommentar. Samme kriterier som ble brukt i Fase 1.",
    help="Dette er samme poengskala og samme kriterietekst som i Fase 1 – kun fagfeltet avgrenser hvilke du vurderer i Fase 2.",
)

st.subheader("Størrelsesklasser")
kolonner = st.columns(3)
for kol, (klasse, belop) in zip(kolonner, KLASSE_DEFINISJON):
    with kol:
        st.metric(klasse, belop)

st.divider()
st.subheader("Kriterier per fagfelt")

mitt_fagfelt = st.session_state.get("_fagfelt")
if mitt_fagfelt:
    st.caption(f"Ditt fagfelt (**{mitt_fagfelt}**) er uthevet under.")

rekker = [FAGFELT[:3], FAGFELT[3:]]
for rekke in rekker:
    kolonner = st.columns(len(rekke))
    for kol, kategori in zip(kolonner, rekke):
        with kol:
            er_mitt = kategori == mitt_fagfelt
            css_klasse = "kat-kort aktiv" if er_mitt else "kat-kort"
            tittel = f'{kategori} <span class="merke-tekst">· ditt fagfelt</span>' if er_mitt else kategori
            punkter = "".join(f"<li>{krit}</li>" for krit in KRITERIER_PER_FAGFELT[kategori])
            st.markdown(f'<div class="{css_klasse}"><h4>{tittel}</h4><ul>{punkter}</ul></div>', unsafe_allow_html=True)
    st.write("")

st.divider()
st.subheader("Veien til finalen")

steg_tekster = [
    ("1. Fase 1", "Alle nominerte butikker vurderes av juryen. Topp ca. 50 (etter snittscore) går videre."),
    ("2. Fase 2 – Ekspertvurdering", "Hvert jurymedlem vurderer butikkene på sitt eget fagfelt. _(Du er her)_"),
    ("3. Finale", "Butikker som har vært gjennom både Fase 1 og Fase 2 rangeres, og de beste per størrelsesklasse blir finalister."),
]
kol = st.columns(3)
for c, (tittel, tekst) in zip(kol, steg_tekster):
    with c.container(border=True):
        st.markdown(f"**{tittel}**")
        st.caption(tekst)
