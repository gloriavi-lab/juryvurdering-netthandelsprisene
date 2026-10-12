"""Side – Testkjøp. Guide-først: forklarer hvordan et testkjøp skal
gjennomføres (hele kjøpsløpet, kundeservice, retur/angrerett, compliance,
universell utforming). Bevisst INGEN egen registrering av funn her ennå –
det er ikke spesifisert hva som skal noteres/av hvem/i hvilket format, så en
datamodell for det bygges først når det er avklart (se svar til bruker)."""

import streamlit as st

from components import topptekst, tom_tilstand
from jury import aktiv_fase, read_faser, read_testkjop_veiledning
from sheets import read_stores

topptekst("Testkjøp")

sh = st.session_state.get("_sh")
if not sh:
    st.warning("Google Sheets-tilkoblingen mangler – gå til **Innstillinger**.", icon=":material/cloud_off:")
    st.stop()

try:
    faser = read_faser(sh)
except Exception as e:
    faser = []
    st.error(f"Kunne ikke lese faser: {e}", icon=":material/error:")

gjeldende = aktiv_fase(faser) if faser else None
if gjeldende and gjeldende.get("Navn") != "Testkjøp":
    st.info(
        f"Gjeldende fase er **{gjeldende.get('Navn', '–')}**, ikke Testkjøp ennå – veiledningen under er likevel "
        "tilgjengelig for forberedelse.",
        icon=":material/info:",
    )

st.markdown(
    "Når en butikk går videre til testkjøp-fasen, handler du som en vanlig kunde – fra søk til varen er mottatt "
    "(eller returnert) – for å avdekke ting som er vanskelige å vurdere uten et reelt kjøp."
)

st.divider()
st.subheader("Slik gjennomfører du et testkjøp", anchor=False)
try:
    veiledning = read_testkjop_veiledning(sh)
except Exception as e:
    veiledning = []
    st.error(f"Kunne ikke lese veiledningen: {e}", icon=":material/error:")

if veiledning:
    for rad in veiledning:
        overskrift, tekst = rad.get("Overskrift", ""), rad.get("Tekst", "")
        if overskrift:
            with st.expander(overskrift):
                st.markdown(tekst)
else:
    tom_tilstand("📋", "Fant ingen veiledningstekst", "Sjekk fanen «Testkjøp-veiledning» i regnearket.")

st.divider()
st.caption(
    "Denne siden er bevisst kun en veiledning foreløpig – registrering av funn fra testkjøp (hva som skal "
    "noteres, og i hvilket format) er ikke bygget ennå. Si ifra hvordan dere ønsker å samle inn og dele funnene, "
    "så bygger vi det neste."
)
