"""Side 3 – Butikker: totaloversikt over ALLE nettbutikkene, lest fra den nye
"Vurderinger"-fanen. Filter på jurymedlem viser hva akkurat den personen har
igjen. To visninger: «Oversikt» (kompakt) og «Detaljert» (hvert kriterium for
seg, AgGrid, grupperte fargede overskrifter)."""

from collections import defaultdict

import streamlit as st

from components import regneark_tabell, topptekst, vis_feil
from data import er_tall, grupper_vurderinger, normalize_score, status_for_scorer
from jury import aktive_kriterier, fagfelt_liste, kriterier_per_fagfelt, mine_kriterier, read_criteria, read_jury
from sheets import mal_handling, read_ratings, read_stores, read_vurderinger
from theme import FAGFELT_FARGE, KLASSE_IKON, KLASSE_TONE

topptekst("Butikker")

sh = st.session_state.get("_sh")
if not sh:
    st.warning("Google Sheets-tilkoblingen mangler – gå til **Innstillinger**.", icon=":material/cloud_off:")
    st.stop()

with mal_handling("Bytt side: Butikker"):
    try:
        butikker, _ = read_stores(sh)
        alle_vurderinger = read_vurderinger(sh)
        fargede_fane_data = read_ratings(sh)
        jury = read_jury(sh)
        kriterier_fase3 = aktive_kriterier(read_criteria(sh), fase="Fase 3")
    except Exception as e:
        vis_feil("Kunne ikke lese regnearket", e)
        st.stop()

FAGFELT = fagfelt_liste(kriterier_fase3)
KRITERIER_PER_FAGFELT = kriterier_per_fagfelt(kriterier_fase3)
ALLE_KRITERIER_FLAT = [k for liste in KRITERIER_PER_FAGFELT.values() for k in liste]
gruppert = grupper_vurderinger(alle_vurderinger)

if not butikker:
    st.info("Fant ingen butikker – sjekk **Innstillinger**.", icon=":material/info:")
    st.stop()


def delt_scorer_for(navn):
    """{kriterium: verdi} fra DEN FARGEDE FANEN – det offisielle, delte
    snittet (se DATAMODELL-forklaringen i sheets.py), brukt til status/snitt
    når ingen person er valgt i filteret. Per-jurymedlem-visningen
    (person_scorer_for) bruker fortsatt loggen («Vurderinger»), siden den
    fargede fanen ikke vet HVEM som satte en verdi – bare hva den endte på."""
    alle = fargede_fane_data.get(navn, {}).get("scorer", {})
    resultat = {}
    for k in ALLE_KRITERIER_FLAT:
        if k in alle:
            verdi = normalize_score(alle[k])
            if verdi is not None:
                resultat[k] = verdi
    return resultat


def person_scorer_for(navn, jurymedlem):
    return {
        r["kriterium"]: r["score"] for r in alle_vurderinger
        if r["butikk"] == navn and r["jurymedlem"] == jurymedlem and r["kriterium"] in ALLE_KRITERIER_FLAT
    }


# ── Filter på jurymedlem ──
st.subheader("Fremdrift per jurymedlem", anchor=False)
navn_jury = sorted(jury.keys())
besvart_per_jurymedlem = defaultdict(set)
for r in alle_vurderinger:
    besvart_per_jurymedlem[r["jurymedlem"]].add((r["butikk"], r["kriterium"]))

jury_rader = []
for navn in navn_jury:
    mine = mine_kriterier(jury, navn)
    if not mine:
        continue
    besvart = besvart_per_jurymedlem.get(navn, set())
    ferdig = sum(1 for b in butikker if all((b, k) in besvart for k in mine))
    jury_rader.append({"Jurymedlem": navn, "Ferdig": ferdig, "Totalt": len(butikker)})
st.dataframe(
    jury_rader, hide_index=True, use_container_width=True,
    column_config={"Ferdig": st.column_config.ProgressColumn("Fremdrift", min_value=0, max_value=len(butikker) or 1)},
)

valgt_person = st.selectbox("Filtrer på jurymedlem – se hva akkurat denne personen har igjen", ["Alle (delt snitt)"] + navn_jury)
aktiv_person = None if valgt_person == "Alle (delt snitt)" else valgt_person
aktive_kriterier_person = mine_kriterier(jury, aktiv_person) if aktiv_person else set(ALLE_KRITERIER_FLAT)


def status_for(navn):
    scorer = person_scorer_for(navn, aktiv_person) if aktiv_person else delt_scorer_for(navn)
    relevante = [k for k in ALLE_KRITERIER_FLAT if k in aktive_kriterier_person] if aktiv_person else ALLE_KRITERIER_FLAT
    if not relevante:
        return "Ikke startet"
    return status_for_scorer(scorer, relevante)


# ── Oppsummering ──
st.divider()
klasser_count = defaultdict(int)
status_count = defaultdict(int)
for navn, info in butikker.items():
    klasser_count[info.get("klasse", "Ukjent")] += 1
    status_count[status_for(navn)] += 1
total_fremdrift = round((status_count["Ferdig"] / len(butikker)) * 100) if butikker else 0

deler = [
    f'<div class="rutenett-kort"><h4 style="margin:0 0 8px 0;">Butikker</h4><div class="stor-tall">{len(butikker)}</div><div class="belop">totalt i konkurransen</div></div>',
    f'<div class="rutenett-kort"><h4 style="margin:0 0 8px 0;">Ferdig vurdert</h4><div class="stor-tall">{total_fremdrift}%</div>'
    f'<div class="fremdrift-bakgrunn" style="margin-top:8px;height:6px;"><div class="fremdrift-fyll" style="width:{total_fremdrift}%;"></div></div></div>',
] + [
    f'<div class="rutenett-kort" style="background:{KLASSE_TONE.get(k, "")};border-top-color:transparent;">'
    f'<div class="kort-ikon">{KLASSE_IKON.get(k, "")}</div><div class="stor-tall">{klasser_count.get(k, 0)}</div><div style="font-weight:700;">{k}</div></div>'
    for k in ["Liten", "Medium", "Stor"]
]
st.markdown(f'<div class="rutenett">{"".join(deler)}</div>', unsafe_allow_html=True)

st.divider()
st.subheader("Alle butikker", anchor=False)

sc1, sc2 = st.columns(2)
sok = sc1.text_input("Søk", placeholder="Søk etter butikk …", icon=":material/search:", label_visibility="collapsed")
klasse_filter = sc2.multiselect("Størrelsesklasse", sorted({i.get("klasse", "") for i in butikker.values() if i.get("klasse")}), placeholder="Alle størrelser", label_visibility="collapsed")

navn_liste = sorted(butikker.keys())
if sok:
    navn_liste = [n for n in navn_liste if sok.lower() in n.lower()]
if klasse_filter:
    navn_liste = [n for n in navn_liste if butikker[n].get("klasse") in klasse_filter]

visning = st.segmented_control("Visning", ["Oversikt", "Detaljert"], default="Oversikt", label_visibility="collapsed")
st.write("")


def _fagfelt_status(besvart, totalt):
    if totalt == 0:
        return None, None
    if besvart == totalt:
        return "✅ Ferdig", "#1E8E5A"
    if besvart == 0:
        return "○ Mangler", "#8A8780"
    return "◐ Påbegynt", "#C8A200"


@st.dialog("Butikkdetaljer", width="large")
def vis_detaljpanel(navn):
    info = butikker[navn]
    st.markdown(f"## {navn}")
    st.caption(f"{info.get('klasse', '–')} · {info.get('bransje', '–')}")
    if info.get("url"):
        st.link_button("Besøk butikk", info["url"], icon=":material/open_in_new:")
    if aktiv_person:
        st.caption(f"Viser kun **{aktiv_person}** sine egne kriterier – velg «Alle (delt snitt)» i filteret over for alle jurymedlemmers svar.")
    st.divider()

    for fagfelt in FAGFELT:
        alle_i_felt = KRITERIER_PER_FAGFELT[fagfelt]
        kriterier_i_felt = [k for k in alle_i_felt if k in aktive_kriterier_person] if aktiv_person else alle_i_felt
        if not kriterier_i_felt:
            continue
        farge = FAGFELT_FARGE.get(fagfelt, "#888")

        if aktiv_person:
            besvart = sum(1 for k in kriterier_i_felt if any(jm == aktiv_person for jm, *_ in gruppert.get((navn, k), [])))
        else:
            besvart = sum(1 for k in kriterier_i_felt if gruppert.get((navn, k)))
        status_tekst, status_farge = _fagfelt_status(besvart, len(kriterier_i_felt))

        st.markdown(
            f'<div style="display:flex;justify-content:space-between;align-items:center;border-left:4px solid {farge};padding-left:10px;margin:12px 0 6px 0;">'
            f'<span style="font-weight:700;">{fagfelt}</span>'
            f'<span style="color:{status_farge};font-weight:600;font-size:13px;">{status_tekst} ({besvart}/{len(kriterier_i_felt)})</span>'
            f"</div>",
            unsafe_allow_html=True,
        )
        for k in kriterier_i_felt:
            oppforinger = gruppert.get((navn, k), [])
            if aktiv_person:
                oppforinger = [o for o in oppforinger if o[0] == aktiv_person]
            if not oppforinger:
                st.caption(f"{k}: ikke vurdert")
                continue
            for jurymedlem, score, kommentar, _ in oppforinger:
                normalisert = normalize_score(score)
                verdi_tekst = str(normalisert) if isinstance(normalisert, (int, float)) else score
                kom_ikon = " 💬" if kommentar else ""
                st.caption(f"{k} — **{verdi_tekst}** _({jurymedlem})_{kom_ikon}")
                if kommentar:
                    st.caption(f"　↳ {kommentar}")


if visning == "Detaljert":
    ratings_for_tabell = {
        navn: {"scorer": {k: delt_scorer_for(navn).get(k, "") for k in ALLE_KRITERIER_FLAT}}
        for navn in navn_liste
    }
    try:
        regneark_tabell(butikker, ratings_for_tabell, KRITERIER_PER_FAGFELT, navn_liste=navn_liste)
    except Exception as e:
        st.error(
            "Kunne ikke vise den detaljerte tabellen akkurat nå. Bruk «Oversikt»-visningen i mellomtiden, "
            "eller trykk «Hent siste fra regnearket» i Innstillinger og prøv igjen.",
            icon=":material/error:",
        )
        with st.expander("Detaljer (for feilsøking)"):
            st.code(str(e))
else:
    rader, id_for_rad = [], []
    for navn in navn_liste:
        info = butikker[navn]
        scorer = person_scorer_for(navn, aktiv_person) if aktiv_person else delt_scorer_for(navn)
        relevante = [k for k in ALLE_KRITERIER_FLAT if k in aktive_kriterier_person] if aktiv_person else ALLE_KRITERIER_FLAT
        besvart = sum(1 for k in relevante if k in scorer and scorer[k])
        tall = [normalize_score(scorer[k]) for k in relevante if k in scorer and er_tall(scorer[k])]
        snitt = round(sum(tall) / len(tall), 2) if tall else None
        har_kom = any(gruppert.get((navn, k)) and any(kom for _, _, kom, _ in gruppert[(navn, k)]) for k in ALLE_KRITERIER_FLAT)
        rader.append({
            "Butikk": navn, "Klasse": info.get("klasse", "–"), "Bransje": info.get("bransje", "–"),
            "Besøk": info.get("url", ""), "Fremdrift": (besvart / len(relevante)) if relevante else 0,
            "Snitt": snitt if snitt is not None else "–", "Status": status_for(navn),
            "💬": "💬" if har_kom else "",
        })
        id_for_rad.append(navn)

    st.caption(f"{len(rader)} av {len(butikker)} butikker")
    hendelse = st.dataframe(
        rader, hide_index=True, use_container_width=True, on_select="rerun", selection_mode="single-row",
        column_config={
            "Besøk": st.column_config.LinkColumn("Besøk", display_text="Besøk →"),
            "Fremdrift": st.column_config.ProgressColumn("Fremdrift", min_value=0, max_value=1),
        },
    )
    if hendelse and hendelse.selection and hendelse.selection.rows:
        vis_detaljpanel(id_for_rad[hendelse.selection.rows[0]])
