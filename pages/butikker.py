"""Side 3 – Butikker: totaloversikt over ALLE nettbutikkene, i en tabell som
speiler regnearkets fargede, grupperte oppsett (se components.regneark_tabell).
Kriteriene er datastyrt (Kriterier-fanen), ikke lenger hardkodet."""

from collections import defaultdict

import streamlit as st

from components import regneark_tabell, rutenett, topptekst
from data import KLASSE_DEFINISJON, er_tall, status_for_scorer
from jury import aktive_kriterier, beskriv_tildeling, fagfelt_liste, kriterier_per_fagfelt, mine_kriterier, read_criteria, read_jury
from sheets import read_ratings, read_stores

topptekst("Butikker")

sh = st.session_state.get("_sh")
if not sh:
    st.warning("Google Sheets-tilkoblingen mangler – gå til **Innstillinger**.", icon=":material/cloud_off:")
    st.stop()

try:
    butikker, _ = read_stores(sh)
    rating_data = read_ratings(sh)
    jury = read_jury(sh)
    kriterier_fase3 = aktive_kriterier(read_criteria(sh), fase="Fase 3")
except Exception as e:
    st.error(f"Kunne ikke lese regnearket: {e}", icon=":material/error:")
    st.stop()

FAGFELT = fagfelt_liste(kriterier_fase3)
KRITERIER_PER_FAGFELT = kriterier_per_fagfelt(kriterier_fase3)
ALLE_KRITERIER_FLAT = [k for liste in KRITERIER_PER_FAGFELT.values() for k in liste]

if not butikker:
    st.info("Fant ingen butikker – sjekk **Innstillinger**.", icon=":material/info:")
    st.stop()


def fase_status(navn):
    scorer = rating_data.get(navn, {}).get("scorer", {})
    return status_for_scorer(scorer, ALLE_KRITERIER_FLAT)


# ── Oppsummering ──
klasser_count = defaultdict(int)
status_count = defaultdict(int)
for navn, info in butikker.items():
    klasser_count[info.get("klasse", "Ukjent")] += 1
    status_count[fase_status(navn)] += 1

total_fremdrift = round((status_count["Ferdig"] / len(butikker)) * 100) if butikker else 0
oppsummering_kort = [
    f'<div class="stor-tall">{len(butikker)}</div><div class="belop">butikker totalt</div>',
    f'<div class="stor-tall">{total_fremdrift}%</div><div class="belop">ferdig vurdert</div>',
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
regneark_tabell(butikker, rating_data, KRITERIER_PER_FAGFELT, navn_liste=navn_liste, fagfelt_liste=fagfelt_filter or None)

st.divider()

# ── Jury-oversikt (per-kriterium-tildeling, ikke hele fagfelt) ──
st.subheader("Jury-oversikt", anchor=False)
st.caption("Fremdrift per jurymedlem, basert på kriteriene de faktisk er tildelt i Jury-fanen.")

jury_rader = []
for navn in sorted(jury.keys()):
    mine = mine_kriterier(jury, navn)
    if not mine:
        jury_rader.append({"Jurymedlem": navn, "Tildeling": "Ingen kriterier tildelt", "Ferdig": 0, "Totalt": 0})
        continue
    ferdig = sum(1 for n in butikker if status_for_scorer(rating_data.get(n, {}).get("scorer", {}), list(mine)) == "Ferdig")
    jury_rader.append({"Jurymedlem": navn, "Tildeling": beskriv_tildeling(navn, jury, KRITERIER_PER_FAGFELT), "Ferdig": ferdig, "Totalt": len(butikker)})

st.dataframe(
    jury_rader, hide_index=True, use_container_width=True,
    column_config={"Ferdig": st.column_config.ProgressColumn("Fremdrift", min_value=0, max_value=len(butikker))},
)
