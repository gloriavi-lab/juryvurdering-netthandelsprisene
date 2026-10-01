"""Side 3 – Finale: rangering per størrelsesklasse, alle kommentarer synlige,
nedlastbar som CSV."""

import csv
import io

import streamlit as st

from components import klasse_badge, topptekst
from data import KLASSER, beregn_finale_data, hent_vurderinger

topptekst("Finale")
st.session_state["_besokt_finale"] = True

sh = st.session_state.get("_sh")
butikkliste = st.session_state.get("butikkliste")

if not sh:
    st.warning("Google Sheets-tilkoblingen mangler – gå til **Innstillinger** for å sjekke tilkoblingen.", icon=":material/cloud_off:")
    st.stop()
if not butikkliste:
    st.info("💡 Last opp Fase 1-Excel-fila under **Innstillinger** for å se Finale-rangeringen (størrelsesklasse hentes derfra).", icon=":material/info:")
    st.stop()

st.caption("Rangering basert på snitt av alle registrerte ekspertvurderinger (Fase 2), gruppert per størrelsesklasse.")
antall_per_klasse = st.number_input("Antall finalister som vises per klasse", min_value=1, max_value=20, value=3)

alle_rader = hent_vurderinger(sh)
snitt, detaljer = beregn_finale_data(alle_rader, butikkliste)

if not snitt:
    st.info("Ingen vurderinger registrert ennå.", icon=":material/info:")
    st.stop()

csv_rader = [["Klasse", "Plass", "Butikk", "Snittscore", "Antall vurderinger"]]
faner = st.tabs(KLASSER)

for fane, klasse in zip(faner, KLASSER):
    with fane:
        butikker_i_klasse = [
            (navn, snitt[navn][0], snitt[navn][1])
            for navn in butikkliste
            if butikkliste[navn].get("klasse") == klasse and navn in snitt
        ]
        butikker_i_klasse.sort(key=lambda x: x[1], reverse=True)
        topp = butikker_i_klasse[:antall_per_klasse]

        if not topp:
            st.caption("Ingen vurderte butikker i denne klassen ennå.")
            continue

        for plass, (navn, snittscore, antall) in enumerate(topp, start=1):
            csv_rader.append([klasse, plass, navn, f"{snittscore:.2f}", antall])
            fyll_prosent = round(snittscore / 5 * 100)
            with st.container(border=True):
                rc1, rc2 = st.columns([4, 1])
                with rc1:
                    st.markdown(f"**#{plass} &nbsp; {navn}**")
                    klasse_badge(klasse)
                    st.markdown(
                        f'<div class="scorelinje-bakgrunn"><div class="scorelinje-fyll" style="width:{fyll_prosent}%;"></div></div>',
                        unsafe_allow_html=True,
                    )
                with rc2:
                    st.metric("Snitt", f"{snittscore:.2f}", help=f"{antall} registrerte vurderinger")

                info = butikkliste.get(navn, {})
                with st.expander("Se alle vurderinger og kommentarer"):
                    if info.get("url"):
                        st.link_button("Besøk butikk", info["url"], icon=":material/open_in_new:")
                    for fagfelt, kriterium, score, kommentar, jurymedlem in sorted(detaljer[navn]):
                        st.markdown(f"**{kriterium}** _({fagfelt} · {jurymedlem})_ — {'⭐' * int(score)}")
                        if kommentar:
                            st.caption(kommentar)

st.divider()
buffer = io.StringIO()
csv.writer(buffer).writerows(csv_rader)
st.download_button(
    "Last ned finale-rangering som CSV", data=buffer.getvalue().encode("utf-8-sig"),
    file_name="finale_rangering.csv", mime="text/csv", icon=":material/download:",
)
