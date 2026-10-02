"""Side 5 – Innstillinger: Google Sheets-tilkobling, oppsett av regnearket fra
Excel, validering, og finale-lås."""

import streamlit as st

from components import status_prikk, topptekst
from data import JURY_FAGFELT_FORSLAG, les_fase1_liste
from sheets import er_finale_last, finale_las_info, fjern_finale_las, read_jury, read_stores, setup_from_excel

topptekst("Innstillinger")

sh = st.session_state.get("_sh")

st.subheader("Google Sheets", anchor=False)
status_prikk(sh is not None)
if sh:
    st.link_button("Åpne regnearket", sh.url, icon=":material/open_in_new:")
    if st.button("Hent siste fra regnearket", icon=":material/refresh:", help="Tømmer mellomlagringen – nyttig rett etter du har redigert noe manuelt i Sheets."):
        read_stores.clear()
        read_jury.clear()
        st.toast("Hentet siste versjon fra regnearket.", icon=":material/check_circle:")
        st.rerun()
else:
    with st.expander("Feilmelding"):
        st.code(st.session_state.get("_gsheets_feil", "Ukjent feil"))
    st.stop()

butikker, advarsler = read_stores(sh)

if advarsler:
    st.warning(
        "Fant noen rader i regnearket appen ikke forstår helt – de andre fungerer som normalt:\n\n"
        + "\n".join(f"- {a}" for a in advarsler),
        icon=":material/warning:",
    )

@st.dialog("Sette opp regnearket på nytt?")
def bekreft_oppsett(antall_totalt, antall_nye):
    st.write(
        f"Dette skriver {antall_totalt} butikker til 'Butikker'-fanen ({antall_nye} nye, "
        f"resten beholder sin eksisterende ID og vurderinger). En sikkerhetskopi av dagens "
        f"'Butikker'-fane tas automatisk først."
    )
    c1, c2 = st.columns(2)
    if c1.button("Avbryt", use_container_width=True):
        st.rerun()
    if c2.button("Ja, sett opp", type="primary", use_container_width=True, icon=":material/database:"):
        forhandsvisning = st.session_state.pop("_excel_forhandsvisning")
        oppsummering = setup_from_excel(sh, forhandsvisning, JURY_FAGFELT_FORSLAG)
        st.session_state["_oppsett_resultat"] = oppsummering
        st.rerun()


if st.session_state.get("_oppsett_resultat"):
    st.success(st.session_state.pop("_oppsett_resultat"), icon=":material/check_circle:")

st.divider()
st.subheader("Butikkliste", anchor=False)

if butikker:
    st.markdown(f'<div class="kort-kompakt">📄 <strong>Butikker-fanen</strong><br>{len(butikker)} butikker satt opp</div>', unsafe_allow_html=True)
else:
    st.info("Ingen butikker satt opp ennå. Last opp Fase 1-Excel-fila under for å komme i gang.", icon=":material/info:")

st.write("")
with st.expander("📤 Sett opp regnearket på nytt fra Excel", expanded=not butikker):
    st.caption(
        "Bygger 'Butikker'-fanen fra en opplastet Fase 1-Excel-fil. Eksisterende butikker beholder sin ID "
        "(matches på navn), så allerede lagrede vurderinger i Rådata mister ikke koblingen. En sikkerhetskopi "
        "av dagens 'Butikker'-fane tas automatisk først. 'Jury'-fanen berøres ikke hvis den allerede har innhold."
    )
    ny_fil = st.file_uploader("Fase 1-Excel (.xlsx)", type=["xlsx"], key="innstillinger_opplaster")
    if ny_fil is not None:
        forhandsvisning = les_fase1_liste(ny_fil)
        if forhandsvisning:
            nye_navn = [n for n in forhandsvisning if n not in {info["navn"] for info in butikker.values()}]
            st.success(f"Fant {len(forhandsvisning)} butikker i fila ({len(nye_navn)} nye, {len(forhandsvisning) - len(nye_navn)} finnes fra før).", icon=":material/check_circle:")
            if st.button("Sett opp regnearket", type="primary", icon=":material/database:"):
                ny_fil.seek(0)
                st.session_state["_excel_forhandsvisning"] = forhandsvisning
                bekreft_oppsett(len(forhandsvisning), len(nye_navn))

st.write("")
with st.expander("🗑️ Fjern alle butikker"):
    st.caption("Fjerner alt innhold i 'Butikker'-fanen. Vurderinger i 'Rådata' slettes ikke, men mister sin synlige butikk til lista settes opp på nytt.")
    from components import bekreft_fjern_liste
    if st.button("Fjern butikkliste", icon=":material/delete:"):
        bekreft_fjern_liste()

st.divider()
st.subheader("Finale", anchor=False)
if er_finale_last(sh):
    av, tid = finale_las_info(sh)
    st.info(f"Finalelista er låst av **{av}** ({tid}). Endringer i Rådata påvirker ikke lenger rangeringen.", icon=":material/lock:")
    if st.button("Lås opp finalelista", icon=":material/lock_open:"):
        fjern_finale_las(sh)
        st.rerun()
else:
    st.caption("Finalelista er ikke låst – rangeringen på Finale-siden oppdateres live etter hvert som vurderinger lagres. Lås den fra Finale-siden når resultatet er klart.")
