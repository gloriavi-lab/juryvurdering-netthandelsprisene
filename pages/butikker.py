"""Side 3 – Butikker: totaloversikt over ALLE nettbutikkene, i en tabell som
speiler regnearkets fargede, grupperte oppsett (se components.regneark_tabell)."""

from collections import defaultdict

import streamlit as st

from components import regneark_tabell, rutenett, topptekst
from data import FAGFELT, JURY_FAGFELT_FORSLAG, KLASSE_DEFINISJON, KRITERIER_PER_FAGFELT, er_tall, status_for_scorer
from sheets import read_ratings, read_stores

topptekst("Butikker")

sh = st.session_state.get("_sh")
if not sh:
    st.warning("Google Sheets-tilkoblingen mangler – gå til **Innstillinger**.", icon=":material/cloud_off:")
    st.stop()

try:
    butikker, _ = read_stores(sh)
    rating_data = read_ratings(sh)
except Exception as e:
    st.error(f"Kunne ikke lese regnearket: {e}", icon=":material/error:")
    st.stop()

if not butikker:
    st.info("Fant ingen butikker – sjekk **Innstillinger**.", icon=":material/info:")
    st.stop()


def fase2_status(navn):
    scorer = rating_data.get(navn, {}).get("scorer", {})
    antall_fagfelt_ferdig = sum(1 for f in FAGFELT if status_for_scorer(scorer, KRITERIER_PER_FAGFELT[f]) == "Ferdig")
    if antall_fagfelt_ferdig == 0 and not scorer:
        return "Ikke startet"
    if antall_fagfelt_ferdig == len(FAGFELT):
        return "Ferdig"
    return "Påbegynt"


# ── Oppsummering ──
klasser_count = defaultdict(int)
status_count = defaultdict(int)
for navn, info in butikker.items():
    klasser_count[info.get("klasse", "Ukjent")] += 1
    status_count[fase2_status(navn)] += 1

total_fremdrift = round((status_count["Ferdig"] / len(butikker)) * 100) if butikker else 0
oppsummering_kort = [
    f'<div class="stor-tall">{len(butikker)}</div><div class="belop">butikker totalt</div>',
    f'<div class="stor-tall">{total_fremdrift}%</div><div class="belop">ferdig vurdert (Fase 2)</div>',
] + [f'<div class="stor-tall">{klasser_count.get(k, 0)}</div><div class="belop">{k}</div>' for k, _ in KLASSE_DEFINISJON]
rutenett(oppsummering_kort)

st.divider()
st.subheader("Alle butikker", anchor=False)
st.caption("Tabellen speiler regnearkets oppsett – grupperte, fargede overskrifter per fagfelt, Butikk/Klasse festet ved sidescrolling.")

sok = st.text_input("🔍 Søk etter butikk", "")
fc1, fc2 = st.columns(2)
klasse_filter = fc1.multiselect("Størrelsesklasse", sorted({i.get("klasse", "") for i in butikker.values() if i.get("klasse")}))
fagfelt_filter = fc2.multiselect("Vis kun fagfelt", FAGFELT)

navn_liste = sorted(butikker.keys())
if sok:
    navn_liste = [n for n in navn_liste if sok.lower() in n.lower()]
if klasse_filter:
    navn_liste = [n for n in navn_liste if butikker[n].get("klasse") in klasse_filter]

st.caption(f"{len(navn_liste)} av {len(butikker)} butikker")
regneark_tabell(butikker, rating_data, navn_liste=navn_liste, fagfelt_liste=fagfelt_filter or None)

st.divider()

# ── Jury-oversikt (fast fagfelt→ekspert-liste, ingen Tildeling-fane) ──
st.subheader("Jury-oversikt", anchor=False)
st.caption("Fremdrift per fagfelt – hvor mange av de 111 butikkene som er ferdig vurdert.")

jury_rader = []
for navn, fagfelt in sorted(JURY_FAGFELT_FORSLAG.items(), key=lambda kv: kv[1]):
    kriterier = KRITERIER_PER_FAGFELT[fagfelt]
    ferdig = sum(1 for n in butikker if status_for_scorer(rating_data.get(n, {}).get("scorer", {}), kriterier) == "Ferdig")
    jury_rader.append({"Jurymedlem": navn, "Fagfelt": fagfelt, "Ferdig": ferdig, "Totalt": len(butikker)})

st.dataframe(
    jury_rader, hide_index=True, use_container_width=True,
    column_config={"Ferdig": st.column_config.ProgressColumn("Fremdrift", min_value=0, max_value=len(butikker))},
)
