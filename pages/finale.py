"""Side 4 – Finale: rangering per størrelsesklasse. Rangeres i dag UTELUKKENDE
på snitt av Fase 2-scorer (samme regel som tidligere versjon) – vekting mot
Fase 1 og regler for lik score er IKKE definert ennå, se infoboksen på siden;
poengberegningen endres ikke her uten at det er avtalt."""

import csv
import io
from collections import defaultdict

import streamlit as st

from components import klasse_badge, topptekst
from data import FAGFELT, KLASSER, er_tall
from sheets import er_finale_last, finale_las_info, hent_finale_snapshot, las_finale, read_ratings, read_stores

topptekst("Finale")

sh = st.session_state.get("_sh")
if not sh:
    st.warning("Google Sheets-tilkoblingen mangler – gå til **Innstillinger**.", icon=":material/cloud_off:")
    st.stop()

butikker, _ = read_stores(sh)
if not butikker:
    st.info("Regnearket er ikke satt opp ennå – gå til **Innstillinger**.", icon=":material/info:")
    st.stop()

with st.expander("ℹ️ Hvordan rangeringen beregnes", expanded=False):
    st.markdown(
        "- **Rangeres på:** snitt av alle registrerte Fase 2-scorer (ekspertvurdering) for butikken.\n"
        "- **Fase 1 vektes IKKE inn ennå** – dette er bevisst ikke bestemt, og endres ikke uten avtale.\n"
        "- **«Kan ikke vurdere»** telles ikke med i snittet (verken som 0 eller 1).\n"
        "- **Ved lik score** er det foreløpig ingen definert regel for rekkefølge – vises i den rekkefølgen de kom inn.\n\n"
        "Si ifra om dere ønsker en annen vekting eller en tie-break-regel, så legger vi det inn."
    )

låst = er_finale_last(sh)
if låst:
    av, tid = finale_las_info(sh)
    st.info(f"🔒 Finalelista er låst av **{av}** ({tid}) – viser det låste øyeblikksbildet, ikke live tall.", icon=":material/lock:")

rå_rader = read_ratings(sh)
rader_etter_header = rå_rader[1:] if len(rå_rader) > 1 else []

per_butikk = defaultdict(list)       # id -> [(fagfelt, kriterium, score, kommentar, jurymedlem)]
fagfelt_per_butikk = defaultdict(set)
for rad in rader_etter_header:
    if len(rad) < 7:
        continue
    butikk_id, _, jurymedlem, fagfelt, kriterium, score, kommentar = rad[:7]
    per_butikk[butikk_id].append((fagfelt, kriterium, score, kommentar, jurymedlem))
    if er_tall(score):
        fagfelt_per_butikk[butikk_id].add(fagfelt)


def snitt_og_antall(butikk_id):
    tall = [float(s) for _, _, s, _, _ in per_butikk.get(butikk_id, []) if er_tall(s)]
    return (sum(tall) / len(tall), len(tall)) if tall else (None, 0)


if låst:
    snapshot = hent_finale_snapshot(sh)
    faner = st.tabs(KLASSER)
    for fane, klasse in zip(faner, KLASSER):
        with fane:
            rader_i_klasse = [r for r in snapshot if r["Klasse"] == klasse]
            if not rader_i_klasse:
                st.caption("Ingen låste finalister i denne klassen.")
            for r in rader_i_klasse:
                st.markdown(f'<div class="finale-rad"><strong>#{r["Plass"]} &nbsp; {r["Butikk"]}</strong> &nbsp; ⭐ {r["Snittscore"]} snitt</div>', unsafe_allow_html=True)
    st.stop()

antall_per_klasse = st.number_input("Antall finalister som vises per klasse", min_value=1, max_value=20, value=3)

if not per_butikk:
    st.info("Ingen vurderinger registrert ennå.", icon=":material/info:")
    st.stop()

alle_topp = []  # for lagring ved låsing
faner = st.tabs(KLASSER)
for fane, klasse in zip(faner, KLASSER):
    with fane:
        butikker_i_klasse = []
        for butikk_id, info in butikker.items():
            if info.get("klasse") != klasse:
                continue
            snitt, antall = snitt_og_antall(butikk_id)
            if snitt is not None:
                butikker_i_klasse.append((butikk_id, info["navn"], snitt, antall))
        butikker_i_klasse.sort(key=lambda x: x[2], reverse=True)
        topp = butikker_i_klasse[:antall_per_klasse]

        if not topp:
            st.caption("Ingen vurderte butikker i denne klassen ennå.")
            continue

        for plass, (butikk_id, navn, snitt, antall) in enumerate(topp, start=1):
            alle_topp.append({"klasse": klasse, "plass": plass, "butikk_id": butikk_id, "butikk": navn, "snitt": snitt, "antall": antall})
            mangler = [f for f in FAGFELT if f not in fagfelt_per_butikk.get(butikk_id, set())]
            fyll_prosent = round(snitt / 5 * 100)
            with st.container(border=True):
                rc1, rc2 = st.columns([4, 1])
                with rc1:
                    st.markdown(f"**#{plass} &nbsp; {navn}**")
                    klasse_badge(klasse)
                    st.markdown(f'<div class="scorelinje-bakgrunn"><div class="scorelinje-fyll" style="width:{fyll_prosent}%;"></div></div>', unsafe_allow_html=True)
                    if mangler:
                        st.warning(f"Mangler vurdering i: {', '.join(mangler)} – rangert på et ufullstendig grunnlag.", icon=":material/warning:")
                with rc2:
                    st.metric("Snitt", f"{snitt:.2f}", help=f"{antall} registrerte kriterie-vurderinger")

                with st.expander("Se snitt per fagfelt og alle kommentarer"):
                    per_fagfelt = defaultdict(list)
                    for fagfelt, kriterium, score, kommentar, jurymedlem in per_butikk[butikk_id]:
                        per_fagfelt[fagfelt].append((kriterium, score, kommentar, jurymedlem))
                    for fagfelt, oppforinger in per_fagfelt.items():
                        tall = [float(s) for _, s, _, _ in oppforinger if er_tall(s)]
                        st.markdown(f"**{fagfelt}** — snitt {sum(tall)/len(tall):.2f}" if tall else f"**{fagfelt}**")
                        for krit, score, kommentar, jurymedlem in oppforinger:
                            st.caption(f"{krit} _( {jurymedlem})_ — {'⭐' * int(score) if er_tall(score) else 'Kan ikke vurdere'}" + (f" — {kommentar}" if kommentar else ""))

@st.dialog("Låse finalelisten?")
def bekreft_las(topp_liste):
    st.write("Dette fryser dagens rangering som det offisielle finaleresultatet. Nye vurderinger i regnearket vil ikke lenger endre det som vises her, før noen låser opp igjen fra Innstillinger.")
    c1, c2 = st.columns(2)
    if c1.button("Avbryt", use_container_width=True):
        st.rerun()
    if c2.button("Ja, lås", type="primary", use_container_width=True, icon=":material/lock:"):
        las_finale(sh, topp_liste, st.session_state.get("_jurynavn", "Ukjent"))
        st.rerun()


st.divider()
c1, c2 = st.columns(2)

with c1:
    buffer = io.StringIO()
    skriver = csv.writer(buffer)
    skriver.writerow(["Klasse", "Plass", "Butikk", "Snittscore", "Antall vurderinger"])
    for r in alle_topp:
        skriver.writerow([r["klasse"], r["plass"], r["butikk"], f'{r["snitt"]:.2f}', r["antall"]])
    st.download_button("Last ned som CSV", data=buffer.getvalue().encode("utf-8-sig"), file_name="finale_rangering.csv", mime="text/csv", icon=":material/download:", use_container_width=True)

with c2:
    if st.button("🔒 Lås finalelisten", use_container_width=True, help="Fryser denne rangeringen – senere endringer i Rådata påvirker ikke det låste resultatet."):
        bekreft_las(alle_topp)
