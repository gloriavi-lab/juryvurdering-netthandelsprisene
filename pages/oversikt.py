"""Side 1 – Oversikt: kriterier, klassedefinisjoner og veien til finalen.
Ingen stegindikator her (den hører til Vurdering, jf. brief)."""

import streamlit as st

from components import rutenett, topptekst
from data import FAGFELT, KLASSE_DEFINISJON, KRITERIER_PER_FAGFELT, SKALA_FORKLARING
from sheets import read_stores
from theme import FAGFELT_FARGE


def _bryt_etter_skratrek(tekst: str) -> str:
    """Setter inn <wbr> (valgfritt linjeskift) etter hver «/», slik at lange
    sammensatte ord ("Markedsføring/kundedialog") kan brytes PENT ved
    skråstreken i stedet for midt i et ord når de ikke får plass."""
    return tekst.replace("/", "/<wbr>")

topptekst("Oversikt")

sh = st.session_state.get("_sh")
butikker = {}
if sh:
    butikker, _ = read_stores(sh)

st.caption(
    "Hvert kriterium vurderes fra 1 til 5 stjerner, eller merkes «Kan ikke vurdere» hvis det ikke lar seg bedømme – "
    "med mulighet for å legge inn en kommentar. Samme kriterier som ble brukt i Fase 1.",
    help=SKALA_FORKLARING,
)

st.subheader("Størrelsesklasser", anchor=False)
antall_per_klasse = {klasse: 0 for klasse, _ in KLASSE_DEFINISJON}
for info in butikker.values():
    if info.get("klasse") in antall_per_klasse:
        antall_per_klasse[info["klasse"]] += 1

klasse_kort = [
    f'<h4>{klasse}</h4><div class="belop">{belop}</div>'
    f'<div class="antall">{antall_per_klasse[klasse]} butikker</div>'
    for klasse, belop in KLASSE_DEFINISJON
]
rutenett(klasse_kort, tre_per_rad=True)

st.divider()
st.subheader("Kriterier per fagfelt", anchor=False)

mitt_fagfelt = st.session_state.get("_fagfelt")
if mitt_fagfelt:
    st.caption(f"Ditt fagfelt (**{mitt_fagfelt}**) er uthevet med rød kant under – de andre vises likt, slik at alle kan se hele vurderingsgrunnlaget.")

# rutenett() legger selv til "rutenett-kort"-klassen uten "aktiv" eller
# fagfelt-farge; disse kortene trenger begge deler, så de bygges manuelt her.
MERKE = ' <span class="merke-tekst">· ditt fagfelt</span>'
deler = []
for kat in FAGFELT:
    er_mitt = kat == mitt_fagfelt
    punkter = "".join(f"<li>{_bryt_etter_skratrek(k)}</li>" for k in KRITERIER_PER_FAGFELT[kat])
    klasse = " aktiv" if er_mitt else ""
    merke = MERKE if er_mitt else ""
    # Rødt (aktiv) går foran fagfelt-fargen når det er ditt eget fagfelt –
    # fagfelt-fargen vises likevel som en liten prikk ved tittelen, slik at
    # koblingen til regnearkets fargekoding alltid er synlig.
    toppstripe = "" if er_mitt else f'style="border-top-color:{FAGFELT_FARGE[kat]};"'
    prikk = f'<span class="fagfelt-ikon" style="background:{FAGFELT_FARGE[kat]};"></span>'
    deler.append(f'<div class="rutenett-kort{klasse}" {toppstripe}><h4>{prikk}{_bryt_etter_skratrek(kat)}{merke}</h4><ul>{punkter}</ul></div>')
st.markdown(f'<div class="rutenett">{"".join(deler)}</div>', unsafe_allow_html=True)

st.divider()
st.subheader("Veien til finalen", anchor=False)

veien_kort = [
    '<h4>1. Fase 1</h4><ul><li>Alle nominerte butikker vurderes av juryen.</li><li>Topp ca. 50 (etter snittscore) går videre.</li></ul>',
    '<h4>2. Fase 2 – Ekspertvurdering <span class="merke-tekst">· du er her</span></h4><ul><li>Hvert jurymedlem vurderer butikkene på sitt eget fagfelt.</li></ul>',
    '<h4>3. Finale</h4><ul><li>Butikker gjennom både Fase 1 og Fase 2 rangeres.</li><li>De beste per størrelsesklasse blir finalister.</li></ul>',
]
rutenett(veien_kort, tre_per_rad=True)
