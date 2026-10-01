"""Gjenbrukbare UI-byggeklosser, slik at hver side slipper å style ting selv."""

import streamlit as st


def topptekst(sidetittel: str):
    st.markdown(
        f'<div class="topptekst">'
        f'<div><div class="merke">Netthandelsprisene</div>'
        f'<div class="sidetittel">{sidetittel}</div></div>'
        f"</div>",
        unsafe_allow_html=True,
    )
    st.badge("Fase 2 – Ekspertvurdering", icon=":material/workspace_premium:", color="red")
    st.write("")


def status_prikk(tilkoblet: bool, tekst_ok="Tilkoblet til Google Sheets", tekst_feil="Ikke tilkoblet"):
    klasse = "ok" if tilkoblet else "feil"
    tekst = tekst_ok if tilkoblet else tekst_feil
    st.markdown(
        f'<span class="status-prikk"><span class="prikk {klasse}"></span>{tekst}</span>',
        unsafe_allow_html=True,
    )


def klasse_badge(klasse: str):
    st.markdown(f'<span class="klasse-badge">{klasse or "–"}</span>', unsafe_allow_html=True)


def onboarding_steg(aktivt_steg: int):
    """aktivt_steg: 1 = last opp liste, 2 = vurder butikker, 3 = se finale."""
    navn = ["Last opp liste", "Vurder butikker", "Se finale"]
    html = '<div class="steg-rad">'
    for i, tekst in enumerate(navn, start=1):
        klasse = "aktiv" if i == aktivt_steg else ("ferdig" if i < aktivt_steg else "")
        merke = "✓ " if i < aktivt_steg else f"{i}. "
        html += f'<div class="steg {klasse}">{merke}{tekst}</div>'
        if i < len(navn):
            html += '<div class="steg-linje"></div>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def tom_tilstand(ikon: str, tittel: str, tekst: str):
    st.markdown(
        f'<div class="tom-tilstand"><div class="ikon">{ikon}</div>'
        f'<div class="tittel">{tittel}</div>'
        f'<div class="tekst">{tekst}</div></div>',
        unsafe_allow_html=True,
    )


@st.dialog("Fjerne butikkliste?")
def bekreft_fjern_liste():
    from data import lagre_lokalt

    st.write(
        "Dette fjerner butikklisten fra appen. Vurderinger som allerede er lagret "
        "i Google Sheets blir **ikke** slettet – kun selve listen over hvilke "
        "butikker som er aktive i denne fasen."
    )
    c1, c2 = st.columns(2)
    if c1.button("Avbryt", use_container_width=True):
        st.rerun()
    if c2.button("Ja, fjern", type="primary", use_container_width=True, icon=":material/delete:"):
        st.session_state.butikkliste = None
        st.session_state.butikkliste_filnavn = None
        st.session_state["_sist_prosesserte_fil"] = None
        lagre_lokalt(None)
        st.rerun()
