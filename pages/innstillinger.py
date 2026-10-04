"""Side 5 – Innstillinger: Google Sheets-tilkobling, validering, og finale-lås.
Butikklisten kommer direkte fra "Rangering fase 1"-fanen – ingen Excel-
opplasting her lenger (se brief del 3: regnearket ER fasiten, appen bygger
ingen egen struktur)."""

import streamlit as st

from components import status_prikk, topptekst
from sheets import (
    FASE1_FANE, FASE2_FANE, er_finale_last, finale_las_info, fjern_finale_las,
    legg_til_na_i_datavalidering, read_fase1_scores, read_ratings, read_stores,
)

topptekst("Innstillinger")

sh = st.session_state.get("_sh")

st.subheader("Google Sheets", anchor=False)
status_prikk(sh is not None)
if sh:
    st.link_button("Åpne regnearket", sh.url, icon=":material/open_in_new:")
    if st.button("Hent siste fra regnearket", icon=":material/refresh:", help="Tømmer mellomlagringen – nyttig rett etter du har redigert noe manuelt i Sheets."):
        read_stores.clear()
        read_ratings.clear()
        read_fase1_scores.clear()
        st.toast("Hentet siste versjon fra regnearket.", icon=":material/check_circle:")
        st.rerun()
else:
    with st.expander("Feilmelding"):
        st.code(st.session_state.get("_gsheets_feil", "Ukjent feil"))
    st.stop()

try:
    butikker, advarsler = read_stores(sh)
except Exception as e:
    st.error(f"Fant ikke fanen «{FASE1_FANE}» i regnearket (eller noe annet gikk galt): {e}", icon=":material/error:")
    st.stop()

st.caption(f"Leser butikklisten direkte fra fanen «{FASE1_FANE}» – {len(butikker)} butikker funnet.")

if advarsler:
    st.warning(
        "Fant noen rader appen ikke forstår helt – resten fungerer som normalt:\n\n" + "\n".join(f"- {a}" for a in advarsler),
        icon=":material/warning:",
    )

st.divider()
st.subheader("Fase 2 – vurderingsark", anchor=False)
st.caption(
    f"«{FASE2_FANE}» opprettes automatisk (som en nøyaktig kopi av «{FASE1_FANE}» – samme farger, "
    "sammenslåinger, nedtrekkslister og filter) første gang noen lagrer en vurdering, eller når du trykker knappen under."
)
try:
    sh.worksheet(FASE2_FANE)
    st.success(f"«{FASE2_FANE}» finnes allerede.", icon=":material/check_circle:")
except Exception:
    if st.button("Opprett «Rangering fase 2» nå", icon=":material/content_copy:"):
        read_ratings(sh)  # trigger _sikre_fase2_fane
        st.rerun()

with st.expander("🔓 Tillat «Kan ikke vurdere» i nedtrekkslisten"):
    st.caption(
        "Legger «Kan ikke vurdere» til som en ekstra gyldig verdi i kriteriecellenes nedtrekksliste på "
        f"«{FASE2_FANE}» (i tillegg til 1–5). Endrer kun datavalideringen, ingen annen formatering."
    )
    if st.button("Legg til nå", icon=":material/playlist_add_check:"):
        legg_til_na_i_datavalidering(sh)
        st.success("Lagt til.", icon=":material/check_circle:")

st.divider()
st.subheader("Finale", anchor=False)
if er_finale_last(sh):
    av, tid = finale_las_info(sh)
    st.info(f"Finalelista er låst av **{av}** ({tid}). Endringer i Sheets påvirker ikke lenger rangeringen.", icon=":material/lock:")
    if st.button("Lås opp finalelista", icon=":material/lock_open:"):
        fjern_finale_las(sh)
        st.rerun()
else:
    st.caption("Finalelista er ikke låst – rangeringen på Finale-siden oppdateres live. Lås den fra Finale-siden når resultatet er klart.")
