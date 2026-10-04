"""Side 1 – Oversikt: banner, kriterier og klassedefinisjoner. Ingen
stegindikator her (den hører til Vurdering)."""

import os

import streamlit as st

from components import rutenett
from data import FAGFELT, KLASSE_DEFINISJON, KRITERIER_PER_FAGFELT, SKALA_FORKLARING
from sheets import read_stores
from theme import FAGFELT_FARGE


def _bryt_etter_skratrek(tekst: str) -> str:
    """Setter inn <wbr> (valgfritt linjeskift) etter hver «/», slik at lange
    sammensatte ord ("Markedsføring/kundedialog") kan brytes PENT ved
    skråstreken i stedet for midt i et ord når de ikke får plass."""
    return tekst.replace("/", "/<wbr>")


sh = st.session_state.get("_sh")
butikker = {}
if sh:
    try:
        butikker, _ = read_stores(sh)
    except Exception:
        pass

BANNER_HTML = (
    '<div class="banner">'
    '<div class="fase">Netthandelsprisene · Fase 2</div>'
    "<h1>Ekspertvurdering</h1>"
    "<p>Vurder butikkene på ditt fagfelt – gi score fra 1 til 5 og legg gjerne igjen en kommentar. "
    "Vurderingene lagres fortløpende i regnearket.</p>"
    "</div>"
)
# ── Toppbanner (erstatter grå stikktittel + tom flate) ──
if os.path.exists("assets/bring-logo.svg"):
    logo_kol, banner_kol = st.columns([1, 6])
    with logo_kol:
        st.image("assets/bring-logo.svg", width=64)
    with banner_kol:
        st.markdown(BANNER_HTML, unsafe_allow_html=True)
else:
    st.markdown(BANNER_HTML, unsafe_allow_html=True)
if st.button("Start vurdering →", type="primary", icon=":material/edit_note:"):
    st.switch_page("pages/vurdering.py")

st.caption(
    "Hvert kriterium vurderes fra 1 til 5 stjerner, eller merkes «Kan ikke vurdere» hvis det ikke lar seg bedømme – "
    "med mulighet for å legge inn en kommentar. Samme kriterier som ble brukt i Fase 1. ⓘ",
    help=SKALA_FORKLARING,
)

st.subheader("Størrelsesklasser", anchor=False)
antall_per_klasse = {klasse: 0 for klasse, _ in KLASSE_DEFINISJON}
for info in butikker.values():
    if info.get("klasse") in antall_per_klasse:
        antall_per_klasse[info["klasse"]] += 1

KLASSE_IKON = {"Liten": "🌱", "Medium": "🌿", "Stor": "🌳"}
KLASSE_TONE = {"Liten": "#E7F3EC", "Medium": "#E6F0F5", "Stor": "#FBF1E0"}
deler = []
for klasse, belop in KLASSE_DEFINISJON:
    deler.append(
        f'<div class="rutenett-kort" style="background:{KLASSE_TONE.get(klasse, "")};border-top-color:transparent;">'
        f'<div class="kort-ikon">{KLASSE_IKON.get(klasse, "")}</div>'
        f'<div class="stor-tall">{antall_per_klasse[klasse]}</div>'
        f'<div style="font-weight:700;">{klasse}</div>'
        f'<div class="belop">{belop}</div></div>'
    )
st.markdown(f'<div class="rutenett tre-per-rad">{"".join(deler)}</div>', unsafe_allow_html=True)

st.divider()
st.subheader("Kriterier per fagfelt", anchor=False)

mitt_fagfelt = st.session_state.get("_fagfelt")
if mitt_fagfelt:
    st.caption(f"Ditt fagfelt (**{mitt_fagfelt}**) er uthevet under.")

MERKE = ' <span class="merke-tekst">· ditt fagfelt</span>'
kort_deler = []
for kat in FAGFELT:
    er_mitt = kat == mitt_fagfelt
    punkter = "".join(f"<li>{_bryt_etter_skratrek(k)}</li>" for k in KRITERIER_PER_FAGFELT[kat])
    klasse = " aktiv" if er_mitt else ""
    merke = MERKE if er_mitt else ""
    toppstripe = "" if er_mitt else f'style="border-top-color:{FAGFELT_FARGE[kat]};"'
    prikk = f'<span class="fagfelt-ikon" style="background:{FAGFELT_FARGE[kat]};"></span>'
    kort_deler.append(f'<div class="rutenett-kort{klasse}" {toppstripe}><h4>{prikk}{_bryt_etter_skratrek(kat)}{merke}</h4><ul>{punkter}</ul></div>')
st.markdown(f'<div class="rutenett">{"".join(kort_deler)}</div>', unsafe_allow_html=True)

st.divider()
st.subheader("Veien til finalen", anchor=False)

veien_kort = [
    '<h4>1. Fase 1</h4><ul><li>Alle nominerte butikker vurderes av juryen.</li><li>Topp ca. 50 (etter snittscore) går videre.</li></ul>',
    '<h4>2. Fase 2 – Ekspertvurdering <span class="merke-tekst">· du er her</span></h4><ul><li>Hvert jurymedlem vurderer butikkene på sitt eget fagfelt.</li></ul>',
    '<h4>3. Finale</h4><ul><li>Butikker gjennom både Fase 1 og Fase 2 rangeres.</li><li>De beste per størrelsesklasse blir finalister.</li></ul>',
]
rutenett(veien_kort, tre_per_rad=True)
