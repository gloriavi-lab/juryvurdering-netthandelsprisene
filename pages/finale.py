"""Side 4 – Finale: rangering per størrelsesklasse. Rangeres i dag UTELUKKENDE
på snitt av Fase 2-scorer – vekting mot Fase 1 og regler for lik score er
IKKE avtalt ennå (se infoboks), og endres ikke her uten avtale."""

import csv
import io

import streamlit as st

from components import klasse_badge, topptekst
from data import KLASSER, er_tall, snitt_av_scorer, status_for_scorer
from jury import aktive_kriterier, fagfelt_liste, kriterier_per_fagfelt, read_criteria
from sheets import er_finale_last, finale_las_info, hent_finale_snapshot, las_finale, read_ratings, read_stores

topptekst("Finale")

sh = st.session_state.get("_sh")
if not sh:
    st.warning("Google Sheets-tilkoblingen mangler – gå til **Innstillinger**.", icon=":material/cloud_off:")
    st.stop()

kriterier_fase3 = aktive_kriterier(read_criteria(sh), fase="Fase 3")
FAGFELT = fagfelt_liste(kriterier_fase3)
KRITERIER_PER_FAGFELT = kriterier_per_fagfelt(kriterier_fase3)

try:
    butikker, _ = read_stores(sh)
    rating_data = read_ratings(sh)
except Exception as e:
    st.error(f"Kunne ikke lese regnearket: {e}", icon=":material/error:")
    st.stop()

if not butikker:
    st.info("Fant ingen butikker – sjekk **Innstillinger**.", icon=":material/info:")
    st.stop()

with st.expander("ℹ️ Hvordan rangeringen beregnes"):
    st.markdown(
        "- **Rangeres på:** snitt av alle registrerte Fase 2-scorer (ekspertvurdering) for butikken.\n"
        "- **Fase 1 vektes IKKE inn ennå** – bevisst ikke bestemt, endres ikke uten avtale.\n"
        "- **«Kan ikke vurdere»** telles ikke med i snittet.\n"
        "- **Ved lik score:** ingen definert regel ennå – vises i den rekkefølgen de kom inn.\n\n"
        "Si ifra om dere ønsker en annen vekting eller en tie-break-regel."
    )

låst = er_finale_last(sh)
if låst:
    av, tid = finale_las_info(sh)
    st.info(f"🔒 Finalelista er låst av **{av}** ({tid}) – viser det låste øyeblikksbildet, ikke live tall.", icon=":material/lock:")
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


def snitt_og_antall(navn):
    scorer = rating_data.get(navn, {}).get("scorer", {})
    tall = [float(s) for s in scorer.values() if er_tall(s)]
    return (sum(tall) / len(tall), len(tall)) if tall else (None, 0)


def manglende_fagfelt(navn):
    scorer = rating_data.get(navn, {}).get("scorer", {})
    return [f for f in FAGFELT if status_for_scorer(scorer, KRITERIER_PER_FAGFELT[f]) != "Ferdig"]


antall_per_klasse = st.number_input("Antall finalister som vises per klasse", min_value=1, max_value=20, value=3)

alle_topp = []
faner = st.tabs(KLASSER)
for fane, klasse in zip(faner, KLASSER):
    with fane:
        butikker_i_klasse = []
        for navn, info in butikker.items():
            if info.get("klasse") != klasse:
                continue
            snitt, antall = snitt_og_antall(navn)
            if snitt is not None:
                butikker_i_klasse.append((navn, snitt, antall))
        butikker_i_klasse.sort(key=lambda x: x[1], reverse=True)
        topp = butikker_i_klasse[:antall_per_klasse]

        if not topp:
            st.caption("Ingen vurderte butikker i denne klassen ennå.")
            continue

        for plass, (navn, snitt, antall) in enumerate(topp, start=1):
            alle_topp.append({"klasse": klasse, "plass": plass, "butikk": navn, "snitt": snitt, "antall": antall})
            mangler = manglende_fagfelt(navn)
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

                with st.expander("Se snitt per fagfelt og kommentarer"):
                    scorer = rating_data.get(navn, {}).get("scorer", {})
                    kommentarer = rating_data.get(navn, {}).get("kommentarer", {})
                    for fagfelt in FAGFELT:
                        fagfelt_snitt = snitt_av_scorer(scorer, KRITERIER_PER_FAGFELT[fagfelt])
                        st.markdown(f"**{fagfelt}** — snitt {fagfelt_snitt:.2f}" if fagfelt_snitt is not None else f"**{fagfelt}** — ingen vurdering")
                        if kommentarer.get(fagfelt):
                            st.caption(kommentarer[fagfelt])

st.divider()


@st.dialog("Låse finalelisten?")
def bekreft_las(topp_liste):
    st.write("Dette fryser dagens rangering som det offisielle finaleresultatet. Nye vurderinger vil ikke lenger endre det som vises her, før noen låser opp igjen fra Innstillinger.")
    c1, c2 = st.columns(2)
    if c1.button("Avbryt", use_container_width=True):
        st.rerun()
    if c2.button("Ja, lås", type="primary", use_container_width=True, icon=":material/lock:"):
        las_finale(sh, topp_liste, st.session_state.get("_jurynavn", "Ukjent"))
        st.rerun()


c1, c2 = st.columns(2)
with c1:
    buffer = io.StringIO()
    skriver = csv.writer(buffer)
    skriver.writerow(["Klasse", "Plass", "Butikk", "Snittscore", "Antall vurderinger"])
    for r in alle_topp:
        skriver.writerow([r["klasse"], r["plass"], r["butikk"], f'{r["snitt"]:.2f}', r["antall"]])
    st.download_button("Last ned som CSV", data=buffer.getvalue().encode("utf-8-sig"), file_name="finale_rangering.csv", mime="text/csv", icon=":material/download:", use_container_width=True)
with c2:
    if st.button("🔒 Lås finalelisten", use_container_width=True, help="Fryser denne rangeringen."):
        bekreft_las(alle_topp)
