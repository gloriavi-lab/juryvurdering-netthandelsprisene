"""Side 3 – Butikker: totaloversikt over ALLE nettbutikkene. To visninger
(st.segmented_control): «Oversikt» (kompakt, standard – én rad per butikk,
snitt per fagfelt) og «Detaljert» (regnearkets fulle kriterieoppsett, AgGrid,
grupperte fargede overskrifter). Klikk på en butikk åpner detaljpanelet."""

from collections import defaultdict

import streamlit as st

from components import regneark_tabell, topptekst
from data import er_tall, snitt_av_scorer, status_for_scorer
from jury import aktive_kriterier, fagfelt_liste, kriterier_per_fagfelt, read_criteria
from sheets import read_kommentarer, read_ratings, read_stores
from theme import FAGFELT_FARGE, KLASSE_IKON, KLASSE_TONE

topptekst("Butikker")

sh = st.session_state.get("_sh")
if not sh:
    st.warning("Google Sheets-tilkoblingen mangler – gå til **Innstillinger**.", icon=":material/cloud_off:")
    st.stop()

try:
    butikker, _ = read_stores(sh)
    rating_data = read_ratings(sh)
    kommentar_rader = read_kommentarer(sh)
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


def scorer_for(navn):
    return rating_data.get(navn, {}).get("scorer", {})


def fase_status(navn):
    return status_for_scorer(scorer_for(navn), ALLE_KRITERIER_FLAT)


def snitt_totalt(navn):
    return snitt_av_scorer(scorer_for(navn), ALLE_KRITERIER_FLAT)


def fremdrift_brok(navn):
    s = scorer_for(navn)
    besvart = sum(1 for k in ALLE_KRITERIER_FLAT if k in s and s[k])
    return besvart, len(ALLE_KRITERIER_FLAT)


# ── Oppsummeringskort (samme fargetoner som størrelseskortene på Oversikt) ──
klasser_count = defaultdict(int)
status_count = defaultdict(int)
for navn, info in butikker.items():
    klasser_count[info.get("klasse", "Ukjent")] += 1
    status_count[fase_status(navn)] += 1

total_fremdrift = round((status_count["Ferdig"] / len(butikker)) * 100) if butikker else 0
deler = [
    f'<div class="rutenett-kort"><h4 style="margin:0 0 8px 0;">Butikker</h4><div class="stor-tall">{len(butikker)}</div><div class="belop">totalt i konkurransen</div></div>',
    (
        '<div class="rutenett-kort"><h4 style="margin:0 0 8px 0;">Ferdig vurdert</h4>'
        f'<div class="stor-tall">{total_fremdrift}%</div>'
        f'<div class="fremdrift-bakgrunn" style="margin-top:8px;"><div class="fremdrift-fyll" style="width:{total_fremdrift}%;"></div></div></div>'
    ),
] + [
    f'<div class="rutenett-kort" style="background:{KLASSE_TONE.get(k, "")};border-top-color:transparent;">'
    f'<div class="kort-ikon">{KLASSE_IKON.get(k, "")}</div><div class="stor-tall">{klasser_count.get(k, 0)}</div><div style="font-weight:700;">{k}</div></div>'
    for k in ["Liten", "Medium", "Stor"]
]
st.markdown(f'<div class="rutenett">{"".join(deler)}</div>', unsafe_allow_html=True)

st.divider()
st.subheader("Alle butikker", anchor=False)

sc1, sc2, sc3 = st.columns([2, 1, 1])
sok = sc1.text_input("Søk", placeholder="Søk etter butikk …", icon=":material/search:", label_visibility="collapsed")
klasse_filter = sc2.multiselect("Størrelsesklasse", sorted({i.get("klasse", "") for i in butikker.values() if i.get("klasse")}), placeholder="Alle størrelser", label_visibility="collapsed")
fagfelt_filter = sc3.multiselect("Fagfelt", FAGFELT, placeholder="Alle fagfelt", label_visibility="collapsed")

navn_liste = sorted(butikker.keys())
if sok:
    navn_liste = [n for n in navn_liste if sok.lower() in n.lower()]
if klasse_filter:
    navn_liste = [n for n in navn_liste if butikker[n].get("klasse") in klasse_filter]

visning = st.segmented_control("Visning", ["Oversikt", "Detaljert"], default="Oversikt", label_visibility="collapsed")
st.write("")


@st.dialog("Butikkdetaljer", width="large")
def vis_detaljpanel(navn):
    info = butikker[navn]
    st.markdown(f"## {navn}")
    st.caption(f"{info.get('klasse', '–')} · {info.get('bransje', '–')}")
    if info.get("url"):
        st.link_button("Besøk butikk", info["url"], icon=":material/open_in_new:")
    st.divider()

    kommentarer_per_kriterium = defaultdict(list)
    for r in kommentar_rader:
        if r["butikk"] == navn and r["kommentar"]:
            kommentarer_per_kriterium[r["kriterium"]].append((r["jurymedlem"], r["kommentar"]))

    scorer = scorer_for(navn)
    for fagfelt in FAGFELT:
        kriterier = KRITERIER_PER_FAGFELT[fagfelt]
        fagfelt_snitt = snitt_av_scorer(scorer, kriterier)
        farge = FAGFELT_FARGE.get(fagfelt, "#888")
        st.markdown(
            f'<div style="border-left:4px solid {farge};padding-left:10px;margin:12px 0 6px 0;font-weight:700;">'
            f'{fagfelt}{f" — snitt {fagfelt_snitt:.2f}" if fagfelt_snitt is not None else " — ingen vurdering"}</div>',
            unsafe_allow_html=True,
        )
        for k in kriterier:
            verdi = scorer.get(k)
            kom_ikon = " 💬" if kommentarer_per_kriterium.get(k) else ""
            if verdi is None:
                st.caption(f"{k}: ikke vurdert{kom_ikon}")
            elif er_tall(verdi):
                st.caption(f"{k}: {'⭐' * int(verdi)}{kom_ikon}")
            else:
                st.caption(f"{k}: {verdi}{kom_ikon}")
            for jurymedlem, kommentar in kommentarer_per_kriterium.get(k, []):
                st.caption(f"　↳ _{jurymedlem}:_ {kommentar}")

    kommentarer = rating_data.get(navn, {}).get("kommentarer", {})
    if any(kommentarer.values()):
        st.divider()
        st.markdown("**Generell kommentar per fagfelt**")
        for fagfelt, kommentar in kommentarer.items():
            if kommentar:
                st.caption(f"_{fagfelt}:_ {kommentar}")


if visning == "Detaljert":
    regneark_tabell(butikker, rating_data, KRITERIER_PER_FAGFELT, navn_liste=navn_liste, fagfelt_liste=fagfelt_filter or None)
else:
    rader = []
    for navn in navn_liste:
        info = butikker[navn]
        rad = {"Butikk": navn, "Klasse": info.get("klasse", "–"), "Bransje": info.get("bransje", "–"), "Besøk": info.get("url", "")}
        for fagfelt in (fagfelt_filter or FAGFELT):
            sn = snitt_av_scorer(scorer_for(navn), KRITERIER_PER_FAGFELT[fagfelt])
            rad[fagfelt] = round(sn, 2) if sn is not None else None
        besvart, totalt_krit = fremdrift_brok(navn)
        rad["Fremdrift"] = (besvart / totalt_krit) if totalt_krit else 0
        rad["Status"] = fase_status(navn)
        st_total = snitt_totalt(navn)
        rad["Snitt totalt"] = round(st_total, 2) if st_total is not None else None
        rader.append(rad)

    column_config = {
        "Besøk": st.column_config.LinkColumn("Besøk", display_text="Besøk →"),
        "Fremdrift": st.column_config.ProgressColumn("Fremdrift", min_value=0, max_value=1, help=f"Antall av {len(ALLE_KRITERIER_FLAT)} kriterier vurdert"),
        "Snitt totalt": st.column_config.NumberColumn("Snitt totalt", format="%.2f"),
    }
    for fagfelt in (fagfelt_filter or FAGFELT):
        column_config[fagfelt] = st.column_config.NumberColumn(fagfelt, format="%.2f", help=f"Snitt for {fagfelt}")

    st.caption(f"{len(rader)} av {len(butikker)} butikker")
    hendelse = st.dataframe(rader, hide_index=True, use_container_width=True, column_config=column_config, on_select="rerun", selection_mode="single-row")
    if hendelse and hendelse.selection and hendelse.selection.rows:
        valgt_navn = rader[hendelse.selection.rows[0]]["Butikk"]
        vis_detaljpanel(valgt_navn)
