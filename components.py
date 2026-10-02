"""Gjenbrukbare UI-byggeklosser, slik at hver side slipper å style ting selv."""

import streamlit as st

from data import FAGFELT


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
        f'<div><div class="merke">Netthandelsprisene · Fase 2 – Ekspertvurdering</div>'
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


def jury_velger(jury: dict):
    """Nedtrekksliste med jurymedlemmer fra Jury-fanen (navn + fagfelt), med
    mulighet for å legge til et nytt medlem. Returnerer (jurynavn, fagfelt),
    eller (None, None) mens "legg til nytt"-skjemaet er åpent."""
    from sheets import legg_til_jurymedlem

    navn_liste = sorted(jury.keys())
    NYTT = "+ Legg til nytt jurymedlem …"
    valg = navn_liste + [NYTT]
    standard = st.session_state.get("_jurynavn")
    startindeks = valg.index(standard) if standard in navn_liste else 0

    col1, col2 = st.columns(2)
    with col1:
        valgt = st.selectbox("Ditt navn (jurymedlem)", valg, index=startindeks)

    if valgt == NYTT:
        with col2:
            st.write("")  # juster vertikal linje med selectboxen
            st.caption("Fyll inn under for å legge til et nytt jurymedlem.")
        with st.form("nytt_jurymedlem_form"):
            fc1, fc2, fc3 = st.columns([2, 2, 1])
            nytt_navn = fc1.text_input("Navn")
            nytt_fagfelt = fc2.selectbox("Fagfelt", FAGFELT)
            lagt_til = fc3.form_submit_button("Legg til", icon=":material/person_add:")
        if lagt_til and nytt_navn.strip():
            sh = st.session_state.get("_sh")
            legg_til_jurymedlem(sh, nytt_navn.strip(), nytt_fagfelt)
            st.session_state["_jurynavn"] = nytt_navn.strip()
            st.session_state["_fagfelt"] = nytt_fagfelt
            st.rerun()
        return None, None

    standard_fagfelt = st.session_state.get("_fagfelt") if st.session_state.get("_jurynavn") == valgt else None
    fagfelt_forslag = standard_fagfelt or jury.get(valgt) or FAGFELT[0]
    with col2:
        fagfelt_valgt = st.selectbox(
            "Ditt fagfelt", FAGFELT,
            index=FAGFELT.index(fagfelt_forslag) if fagfelt_forslag in FAGFELT else 0,
            help="Hentet fra Jury-fanen i regnearket – kan overstyres her for denne økten.",
        )
    st.session_state["_jurynavn"] = valgt
    st.session_state["_fagfelt"] = fagfelt_valgt
    return valgt, fagfelt_valgt


@st.dialog("Fjerne butikkliste?")
def bekreft_fjern_liste():
    st.write("Dette fjerner alle butikker fra 'Butikker'-fanen i regnearket. Vurderinger i 'Rådata' slettes **ikke**, men mister koblingen til en synlig butikk til du setter opp lista på nytt.")
    c1, c2 = st.columns(2)
    if c1.button("Avbryt", use_container_width=True):
        st.rerun()
    if c2.button("Ja, fjern", type="primary", use_container_width=True, icon=":material/delete:"):
        from sheets import _skriv_butikker
        _skriv_butikker(st.session_state["_sh"], {})
        st.rerun()
