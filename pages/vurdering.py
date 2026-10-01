"""Side 2 – Vurdering: kjerneopplevelsen. To visninger: Fokus (én butikk om
gangen) og Liste (søkbar oversikt med status). Tilstanden styres utelukkende
av st.session_state (butikkliste, jurynavn, fagfelt) – ALDRI av om
file_uploader-widgeten har en fil i seg akkurat nå, slik at denne siden alltid
viser riktig innhold uansett hvor brukeren kom fra."""

import streamlit as st

from components import klasse_badge, onboarding_steg, tom_tilstand, topptekst
from data import (
    FAGFELT,
    JURY_FAGFELT_FORSLAG,
    KRITERIER_PER_FAGFELT,
    hent_vurderinger,
    lagre_vurderinger_batch,
    prosesser_opplastet_fil,
)

topptekst("Vurdering")

sh = st.session_state.get("_sh")
butikkliste = st.session_state.get("butikkliste")

if not sh:
    st.warning(
        "Google Sheets-tilkoblingen mangler – gå til **Innstillinger** for å sjekke tilkoblingen før vurderinger kan lagres.",
        icon=":material/cloud_off:",
    )
    st.stop()

if not butikkliste:
    onboarding_steg(1)
    tom_tilstand(
        "📋", "Ingen butikkliste lastet inn ennå",
        "Last opp butikkene som gikk videre fra Fase 1, så kan du begynne å vurdere dem her.",
    )
    _, midt, _ = st.columns([1, 2, 1])
    with midt:
        fil = st.file_uploader("Fase 1-Excel (.xlsx)", type=["xlsx"], key="vurdering_opplaster")
        if fil is not None and prosesser_opplastet_fil(fil, sh):
            st.rerun()
    st.stop()

# ── Jurymedlem + fagfelt ──
col1, col2 = st.columns(2)
with col1:
    jurynavn = st.text_input("Ditt navn (jurymedlem)", value=st.session_state.get("_jurynavn", ""))
    st.session_state["_jurynavn"] = jurynavn
with col2:
    forslag = next((v for k, v in JURY_FAGFELT_FORSLAG.items() if k in jurynavn.lower()), FAGFELT[0])
    standard = st.session_state.get("_fagfelt") or forslag
    fagfelt_valgt = st.selectbox(
        "Ditt fagfelt", FAGFELT, index=FAGFELT.index(standard),
        help="Du vurderer kun butikkene på ditt eget fagfelt – de andre kriteriene vurderes av andre jurymedlemmer.",
    )
    st.session_state["_fagfelt"] = fagfelt_valgt

if not jurynavn:
    onboarding_steg(1)
    st.info("Skriv inn navnet ditt over for å begynne å vurdere.", icon=":material/badge:")
    st.stop()

onboarding_steg(2)
kriterier_denne = KRITERIER_PER_FAGFELT[fagfelt_valgt]

alle_rader = hent_vurderinger(sh)
mine_vurderinger = {}
for rad in (alle_rader[1:] if len(alle_rader) > 1 else []):
    if len(rad) >= 6 and rad[1] == jurynavn:
        mine_vurderinger[(rad[0], rad[3])] = {"score": rad[4], "kommentar": rad[5]}

navn_liste_full = sorted(butikkliste.keys())


def er_ferdig(navn):
    return all((navn, k) in mine_vurderinger for k in kriterier_denne)


antall_fullfort = sum(1 for n in navn_liste_full if er_ferdig(n))

topprad1, topprad2 = st.columns([3, 1])
with topprad1:
    st.progress(
        antall_fullfort / len(navn_liste_full) if navn_liste_full else 0,
        text=f"{antall_fullfort} av {len(navn_liste_full)} vurdert · {fagfelt_valgt}",
    )
with topprad2:
    visning = st.segmented_control("Visning", ["Fokus", "Liste"], default="Fokus", label_visibility="collapsed")

st.divider()


def lagre_denne(navn):
    vurderinger = []
    for krit in kriterier_denne:
        key = f"score_{navn}_{krit}"
        feedback_verdi = st.session_state.get(key)
        score = (feedback_verdi if feedback_verdi is not None else 2) + 1  # 0-4 -> 1-5
        kommentar = st.session_state.get(f"kom_{navn}_{krit}", "")
        vurderinger.append((krit, score, kommentar))
    try:
        lagre_vurderinger_batch(sh, navn, jurynavn, fagfelt_valgt, vurderinger)
        st.toast(f"Lagret vurdering for {navn}", icon=":material/check_circle:")
        return True
    except Exception as e:
        st.error(f"Kunne ikke lagre akkurat nå – prøv igjen. ({e})", icon=":material/error:")
        return False


@st.fragment
def vis_vurderingsskjema(navn):
    """Selve vurderingsskjemaet for én butikk – egen fragment slik at det å
    justere en stjerne eller skrive en kommentar ikke trigger en full rerun av
    resten av siden (sidepanel, topptekst, fremdriftslinje osv.)."""
    for krit in kriterier_denne:
        eksisterende = mine_vurderinger.get((navn, krit), {})
        score_key = f"score_{navn}_{krit}"
        if score_key not in st.session_state:
            st.session_state[score_key] = int(eksisterende.get("score") or 3) - 1  # 1-5 -> 0-4

        st.markdown(f"**{krit}**")
        kc1, kc2 = st.columns([1, 2])
        with kc1:
            st.feedback("stars", key=score_key)
        with kc2:
            st.text_area(
                "Kommentar", value=eksisterende.get("kommentar", ""),
                key=f"kom_{navn}_{krit}", label_visibility="collapsed",
                placeholder="Skriv en kommentar (valgfritt)…", height=68,
            )


if visning == "Liste":
    sok = st.text_input("🔍 Søk etter butikk", "", key="liste_sok")
    kun_uvurderte = st.checkbox("Vis kun ikke-vurderte", value=False)
    rader = []
    for navn in navn_liste_full:
        if sok and sok.lower() not in navn.lower():
            continue
        ferdig = er_ferdig(navn)
        if kun_uvurderte and ferdig:
            continue
        info = butikkliste[navn]
        rader.append({
            "Butikk": navn,
            "Klasse": info.get("klasse", "–"),
            "Bransje": info.get("bransje", "–"),
            "Status": "✅ Vurdert" if ferdig else "⏳ Ikke vurdert",
        })
    st.caption(f"{len(rader)} butikker")
    st.dataframe(rader, use_container_width=True, hide_index=True)

    st.write("")
    valgt_navn = st.selectbox("Hopp til butikk for å vurdere", [r["Butikk"] for r in rader] or navn_liste_full)
    if valgt_navn and st.button("Åpne i Fokus-modus", icon=":material/arrow_forward:"):
        st.session_state["_fokus_indeks"] = navn_liste_full.index(valgt_navn)
        st.session_state["_vurdering_visning"] = "Fokus"
        st.rerun()

else:  # Fokusmodus
    i = st.session_state.get("_fokus_indeks", 0)
    i = max(0, min(i, len(navn_liste_full) - 1))
    navn = navn_liste_full[i]
    info = butikkliste[navn]

    with st.container(border=True):
        hc1, hc2 = st.columns([3, 1])
        with hc1:
            st.markdown(f"### {navn}")
            klasse_badge(info.get("klasse", "–"))
            st.caption(info.get("bransje", "–"))
        with hc2:
            if info.get("url"):
                st.link_button("Besøk butikk", info["url"], icon=":material/open_in_new:", use_container_width=True)
            st.caption(f"Butikk {i + 1} av {len(navn_liste_full)}" + (" · ✅ vurdert" if er_ferdig(navn) else ""))

        st.write("")
        vis_vurderingsskjema(navn)

        st.write("")
        nav1, nav2, nav3 = st.columns([1, 1, 2])
        if nav1.button("← Forrige", disabled=(i == 0), use_container_width=True):
            lagre_denne(navn)
            st.session_state["_fokus_indeks"] = max(0, i - 1)
            st.rerun()
        if nav2.button("Neste →", disabled=(i >= len(navn_liste_full) - 1), use_container_width=True):
            lagre_denne(navn)
            st.session_state["_fokus_indeks"] = min(len(navn_liste_full) - 1, i + 1)
            st.rerun()
        if nav3.button("💾 Lagre vurdering", type="primary", use_container_width=True):
            lagre_denne(navn)
            st.rerun()
