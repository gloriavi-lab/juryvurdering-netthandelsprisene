"""Side 3 – Butikker: totaloversikt over ALLE nettbutikkene i konkurransen,
ikke bare ett jurymedlems egne. Plassert mellom Vurdering og Finale."""

from collections import defaultdict

import streamlit as st

from components import klasse_badge, rutenett, topptekst
from data import FAGFELT, KRITERIER_PER_FAGFELT, er_tall, status_for_butikk
from sheets import read_assignments, read_jury, read_ratings, read_stores, butikker_for_jurymedlem

topptekst("Butikker")

sh = st.session_state.get("_sh")
if not sh:
    st.warning("Google Sheets-tilkoblingen mangler – gå til **Innstillinger**.", icon=":material/cloud_off:")
    st.stop()

butikker, _ = read_stores(sh)
if not butikker:
    st.info("Regnearket er ikke satt opp ennå – gå til **Innstillinger**.", icon=":material/info:")
    st.page_link("pages/innstillinger.py", label="Gå til Innstillinger", icon=":material/settings:")
    st.stop()

jury = read_jury(sh)
tildeling = read_assignments(sh)
rå_rader = read_ratings(sh)
rader_etter_header = rå_rader[1:] if len(rå_rader) > 1 else []

# ── Aggreger Rådata per butikk ──────────────────────────────────────────
per_butikk = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))  # id -> fagfelt -> jurymedlem -> {kriterium: (score, kommentar)}
for rad in rader_etter_header:
    if len(rad) < 7:
        continue
    butikk_id, _, jurymedlem, fagfelt, kriterium, score, kommentar = rad[:7]
    per_butikk[butikk_id][fagfelt][jurymedlem][kriterium] = (score, kommentar)


def fase2_data(butikk_id):
    data = per_butikk.get(butikk_id, {})
    fagfelt_ferdig = 0
    alle_scorer = []
    for fagfelt in FAGFELT:
        kriterier = KRITERIER_PER_FAGFELT[fagfelt]
        for jurymedlem, svar in data.get(fagfelt, {}).items():
            if all(k in svar for k in kriterier):
                fagfelt_ferdig += 1
                break
        for jurymedlem, svar in data.get(fagfelt, {}).items():
            for score, _ in svar.values():
                if er_tall(score):
                    alle_scorer.append(float(score))
    snitt = (sum(alle_scorer) / len(alle_scorer)) if alle_scorer else None
    if fagfelt_ferdig == 0 and not alle_scorer:
        status = "Ikke startet"
    elif fagfelt_ferdig == len(FAGFELT):
        status = "Ferdig"
    else:
        status = "Påbegynt"
    return fagfelt_ferdig, snitt, status


# ── Oppsummering ──────────────────────────────────────────────────────
klasser_count = defaultdict(int)
status_count = defaultdict(int)
for butikk_id, info in butikker.items():
    klasser_count[info.get("klasse", "Ukjent")] += 1
    _, _, status = fase2_data(butikk_id)
    status_count[status] += 1

total_fremdrift = round((status_count["Ferdig"] / len(butikker)) * 100) if butikker else 0

oppsummering_kort = [
    f'<div class="stor-tall">{len(butikker)}</div><div class="belop">butikker totalt</div>',
    f'<div class="stor-tall">{total_fremdrift}%</div><div class="belop">ferdig vurdert (Fase 2)</div>',
] + [f'<div class="stor-tall">{klasser_count.get(k, 0)}</div><div class="belop">{k}</div>' for k, _ in [("Liten", None), ("Medium", None), ("Stor", None)]]
rutenett(oppsummering_kort)

st.divider()

# ── Tabell over alle butikker ───────────────────────────────────────────
st.subheader("Alle butikker", anchor=False)

sok = st.text_input("🔍 Søk etter butikk", "")
fc1, fc2, fc3 = st.columns(3)
klasse_filter = fc1.multiselect("Størrelsesklasse", sorted({i.get("klasse", "") for i in butikker.values() if i.get("klasse")}))
bransje_filter = fc2.multiselect("Kategori", sorted({i.get("bransje", "") for i in butikker.values() if i.get("bransje")}))
status_filter = fc3.multiselect("Status", ["Ikke startet", "Påbegynt", "Ferdig"])

rader, id_for_rad = [], []
for butikk_id, info in sorted(butikker.items(), key=lambda kv: kv[1]["navn"]):
    if sok and sok.lower() not in info["navn"].lower():
        continue
    if klasse_filter and info.get("klasse") not in klasse_filter:
        continue
    if bransje_filter and info.get("bransje") not in bransje_filter:
        continue
    fagfelt_ferdig, snitt, status = fase2_data(butikk_id)
    if status_filter and status not in status_filter:
        continue
    rader.append({
        "Butikk": info["navn"], "URL": info.get("url", ""), "Kategori": info.get("bransje", "–"),
        "Klasse": info.get("klasse", "–"), "Fase 1-snitt": info.get("fase1_snitt"),
        "Fase 2-fremdrift": fagfelt_ferdig / len(FAGFELT), "Fase 2-snitt": round(snitt, 2) if snitt is not None else None,
        "Status": status,
    })
    id_for_rad.append(butikk_id)

st.caption(f"{len(rader)} av {len(butikker)} butikker")
hendelse = st.dataframe(
    rader, hide_index=True, use_container_width=True, on_select="rerun", selection_mode="single-row",
    column_config={
        "URL": st.column_config.LinkColumn("Lenke", display_text="Besøk ↗"),
        "Fase 2-fremdrift": st.column_config.ProgressColumn("Fase 2-fremdrift", min_value=0, max_value=1, help="Andel av 5 fagfelt som har minst én fullført vurdering."),
        "Fase 1-snitt": st.column_config.NumberColumn("Fase 1-snitt", format="%.2f"),
        "Fase 2-snitt": st.column_config.NumberColumn("Fase 2-snitt", format="%.2f"),
    },
)


@st.dialog("Butikkdetaljer", width="large")
def vis_detaljpanel(butikk_id):
    info = butikker[butikk_id]
    st.markdown(f"## {info['navn']}")
    klasse_badge(info.get("klasse", "–"))
    st.caption(info.get("bransje", "–"))
    if info.get("url"):
        st.link_button("Besøk butikk", info["url"], icon=":material/open_in_new:")

    st.divider()
    st.markdown("**Fase 1**")
    if info.get("fase1_snitt") is not None:
        st.metric("Fase 1-snitt", f"{info['fase1_snitt']:.2f}")
    else:
        st.caption("Ingen Fase 1-score registrert i regnearket.")

    st.divider()
    st.markdown("**Fase 2 – Ekspertvurdering**")
    mitt_navn = st.session_state.get("_jurynavn")
    data = per_butikk.get(butikk_id, {})
    for fagfelt in FAGFELT:
        kriterier = KRITERIER_PER_FAGFELT[fagfelt]
        svar_per_jury = data.get(fagfelt, {})
        if not svar_per_jury:
            continue

        # Blindvurdering: hvis dette ER mitt eget fagfelt og jeg ikke selv har
        # fullført denne butikken ennå, skjul ANDRES poeng/kommentarer for det
        # fagfeltet – for å unngå å bli påvirket før egen vurdering er levert.
        min_status = "Ferdig"
        if fagfelt == st.session_state.get("_fagfelt") and mitt_navn:
            mine_svar = svar_per_jury.get(mitt_navn, {})
            min_status = "Ferdig" if all(k in mine_svar for k in kriterier) else "Ikke ferdig"

        with st.expander(f"{fagfelt} ({len(svar_per_jury)} jurymedlem(mer))"):
            if min_status != "Ferdig":
                st.info("Fullfør din egen vurdering av dette fagfeltet på denne butikken for å se de andre jurymedlemmenes poeng og kommentarer.", icon=":material/visibility_off:")
                if mitt_navn in svar_per_jury:
                    st.caption("Din egen, foreløpige vurdering:")
                    for krit, (score, kommentar) in svar_per_jury[mitt_navn].items():
                        st.markdown(f"**{krit}** — {'⭐' * int(score) if er_tall(score) else 'Kan ikke vurdere'}")
                        if kommentar:
                            st.caption(kommentar)
            else:
                for jurymedlem, svar in svar_per_jury.items():
                    st.markdown(f"_{jurymedlem}_")
                    for krit, (score, kommentar) in svar.items():
                        st.markdown(f"**{krit}** — {'⭐' * int(score) if er_tall(score) else 'Kan ikke vurdere'}")
                        if kommentar:
                            st.caption(kommentar)

    st.divider()
    if st.button("Vurder denne butikken", icon=":material/edit_note:", type="primary"):
        st.session_state["_fokus_id"] = butikk_id
        st.session_state["_visning_vurdering"] = "Fokus"
        st.switch_page("pages/vurdering.py")


if hendelse and hendelse.selection and hendelse.selection.rows:
    valgt = hendelse.selection.rows[0]
    vis_detaljpanel(id_for_rad[valgt])

st.divider()

# ── Jury-oversikt ────────────────────────────────────────────────────
st.subheader("Jury-oversikt", anchor=False)
st.caption("Fremdrift per jurymedlem – «ferdig av tildelt» for deres eget fagfelt.")

alle_ider = list(butikker.keys())
jury_rader = []
for navn, fagfelt in sorted(jury.items()):
    if fagfelt not in FAGFELT:
        continue
    tildelte = butikker_for_jurymedlem(tildeling, navn, alle_ider)
    kriterier = KRITERIER_PER_FAGFELT[fagfelt]
    mine_svar = {(bid, k): True for bid, data in per_butikk.items() for k, (s, _) in data.get(fagfelt, {}).get(navn, {}).items()}
    ferdig = sum(1 for bid in tildelte if all((bid, k) in mine_svar for k in kriterier))
    jury_rader.append({"Jurymedlem": navn, "Fagfelt": fagfelt, "Ferdig": ferdig, "Tildelt": len(tildelte)})

st.dataframe(
    jury_rader, hide_index=True, use_container_width=True,
    column_config={"Ferdig": st.column_config.ProgressColumn("Fremdrift", min_value=0, max_value=max((r["Tildelt"] for r in jury_rader), default=1))},
)
