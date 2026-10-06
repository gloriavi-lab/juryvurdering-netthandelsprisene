"""Side 5 – Innstillinger: Google Sheets-tilkobling, validering, og finale-lås.
Butikklisten kommer direkte fra "Rangering fase 1"-fanen – ingen Excel-
opplasting her lenger (se brief del 3: regnearket ER fasiten, appen bygger
ingen egen struktur)."""

import streamlit as st

from components import status_prikk, topptekst
from jury import (
    add_criterion, aktive_kriterier, aktiv_fase, deaktiver_kriterium, fagfelt_liste, kriterier_per_fagfelt,
    oppdater_kriterium, read_criteria, read_faser, read_jury, sett_gjeldende_fase, slett_jurymedlem, write_jury,
)
from sheets import (
    FASE1_FANE, FASE2_FANE, er_finale_last, finale_las_info, fjern_finale_las,
    legg_til_kriterium_kolonne, legg_til_na_i_datavalidering, read_fase1_scores, read_ratings, read_stores,
    test_tilkobling,
)
from theme import FAGFELT_FARGE

topptekst("Innstillinger")

sh = st.session_state.get("_sh")

st.subheader("Google Sheets", anchor=False)
status_prikk(sh is not None)
if sh:
    bc1, bc2, bc3 = st.columns(3)
    bc1.link_button("Åpne regnearket", sh.url, icon=":material/open_in_new:", use_container_width=True)
    if bc2.button("Hent siste fra regnearket", icon=":material/refresh:", use_container_width=True, help="Tømmer mellomlagringen – nyttig rett etter du har redigert noe manuelt i Sheets."):
        read_stores.clear()
        read_ratings.clear()
        read_fase1_scores.clear()
        st.toast("Hentet siste versjon fra regnearket.", icon=":material/check_circle:")
        st.rerun()
    if bc3.button("Test tilkobling", icon=":material/network_check:", use_container_width=True):
        st.session_state["_vis_tilkoblingstest"] = True

    if st.session_state.get("_vis_tilkoblingstest"):
        with st.spinner("Tester tilkoblingen …"):
            try:
                resultater = test_tilkobling(sh)
            except Exception as e:
                resultater = [(False, f"Testen selv feilet uventet: {e}")]
        for ok, tekst in resultater:
            if ok:
                st.success(tekst, icon=":material/check_circle:")
            else:
                st.error(tekst, icon=":material/cancel:")
else:
    with st.expander("Feilmelding"):
        st.code(st.session_state.get("_gsheets_feil", "Ukjent feil"))
    st.stop()

try:
    butikker, advarsler = read_stores(sh)
except Exception as e:
    st.error(f"Fant ikke fanen «{FASE1_FANE}» i regnearket (eller noe annet gikk galt): {e}", icon=":material/error:")
    st.stop()

st.caption(f"Leser butikklisten direkte fra fanen «{FASE1_FANE}» – {len(butikker)} butikker funnet.")

if advarsler:
    st.warning(
        "Fant noen rader appen ikke forstår helt – resten fungerer som normalt:\n\n" + "\n".join(f"- {a}" for a in advarsler),
        icon=":material/warning:",
    )

st.divider()
st.subheader("Ekspertvurdering – vurderingsark", anchor=False)
st.caption(
    f"«{FASE2_FANE}» opprettes automatisk (som en nøyaktig kopi av «{FASE1_FANE}» – samme farger, "
    "sammenslåinger, nedtrekkslister og filter) første gang noen lagrer en vurdering, eller når du trykker knappen under."
)
try:
    sh.worksheet(FASE2_FANE)
    st.success(f"«{FASE2_FANE}» finnes allerede.", icon=":material/check_circle:")
except Exception:
    if st.button("Opprett «Rangering fase 2» nå", icon=":material/content_copy:"):
        read_ratings(sh)  # trigger _sikre_fase2_fane
        st.rerun()

with st.expander("Tillat «Kan ikke vurdere» i nedtrekkslisten", icon=":material/lock_open:"):
    st.caption(
        "Legger «Kan ikke vurdere» til som en ekstra gyldig verdi i kriteriecellenes nedtrekksliste på "
        f"«{FASE2_FANE}» (i tillegg til 1–5). Endrer kun datavalideringen, ingen annen formatering."
    )
    if st.button("Legg til nå", icon=":material/playlist_add_check:"):
        legg_til_na_i_datavalidering(sh)
        st.success("Lagt til.", icon=":material/check_circle:")

st.divider()
st.subheader("Jury og kriterier", anchor=False)

alle_kriterier = read_criteria(sh)
kriterier_fase3 = aktive_kriterier(alle_kriterier, fase="Fase 3")
felt_dict = kriterier_per_fagfelt(kriterier_fase3)
jury = read_jury(sh)
navn_liste_jury = sorted(jury.keys())
antall_jury_per_kriterium = {k: sum(1 for p in jury.values() if any(kr == k for kr in p["kriterier"])) for liste in felt_dict.values() for k in liste}


def _sheets_feilboks(e, handling="lagre"):
    st.error(f"Kunne ikke {handling} til regnearket – prøv igjen.", icon=":material/error:")
    with st.expander("Detaljer (for feilsøking)"):
        st.code(str(e))


def _reset_dialog_avkrysninger(dialog_id):
    """Nullstiller avkrysningene i dialogen hver gang den åpnes for en NY
    person (eller for "ny person") – ellers vil et forrige, kanskje
    avbrutt, redigeringsforsøk henge igjen i session_state."""
    if st.session_state.get("_jury_dialog_for") != dialog_id:
        for fagfelt, kriterier in felt_dict.items():
            st.session_state.pop(f"dchk_{dialog_id}_alle_{fagfelt}", None)
            for k in kriterier:
                st.session_state.pop(f"dchk_{dialog_id}_{k}", None)
        st.session_state["_jury_dialog_for"] = dialog_id
        st.session_state["_bekreft_slett_jury"] = False


@st.dialog("Jurymedlem")
def jury_dialog(redigerer_navn=None):
    dialog_id = redigerer_navn or "_ny_"
    _reset_dialog_avkrysninger(dialog_id)
    eksisterende = jury.get(redigerer_navn, {}) if redigerer_navn else {}
    mine_na = eksisterende.get("kriterier", set())

    feil_plassholder = st.empty()

    navn_input = st.text_input("Navn", value=redigerer_navn or "", disabled=bool(redigerer_navn))

    def _sett_alle(kriterier, nokkel_prefiks, alle_nokkel):
        verdi = st.session_state[alle_nokkel]
        for k in kriterier:
            st.session_state[f"{nokkel_prefiks}{k}"] = verdi

    nye_valgt = set()
    for fagfelt, kriterier in felt_dict.items():
        fc1, fc2 = st.columns([4, 1], vertical_alignment="center")
        fc1.markdown(f"<span style='color:{FAGFELT_FARGE.get(fagfelt, '#888')};font-weight:700;'>{fagfelt}</span>", unsafe_allow_html=True)
        alle_nokkel = f"dchk_{dialog_id}_alle_{fagfelt}"
        with fc2:
            _, kol_hoyre = st.columns([1, 2])  # dytter avkrysningen mot høyre i den smale kolonnen
            with kol_hoyre:
                st.checkbox(
                    "Alle", value=all(k in mine_na for k in kriterier), key=alle_nokkel,
                    on_change=_sett_alle, args=(kriterier, f"dchk_{dialog_id}_", alle_nokkel),
                )
        for k in kriterier:
            chk_nokkel = f"dchk_{dialog_id}_{k}"
            if chk_nokkel not in st.session_state:
                st.session_state[chk_nokkel] = k in mine_na
            if st.checkbox(k, key=chk_nokkel):
                nye_valgt.add(k)

    c1, c2 = st.columns(2)
    if c1.button("Avbryt", use_container_width=True):
        st.rerun()
    if c2.button("Lagre", type="primary", use_container_width=True, icon=":material/save:"):
        navn_rengjort = (redigerer_navn or navn_input).strip()
        if not navn_rengjort:
            feil_plassholder.error("Navn kan ikke være tomt.", icon=":material/error:")
        elif not redigerer_navn and navn_rengjort.lower() in {n.lower() for n in jury}:
            feil_plassholder.error(f"«{navn_rengjort}» finnes allerede i lista.", icon=":material/error:")
        else:
            try:
                write_jury(sh, navn_rengjort, nye_valgt, eksisterende.get("epost", ""), eksisterende.get("farge", ""))
                st.toast("Lagret", icon=":material/check_circle:")
                st.session_state["_jury_dialog_for"] = None
                st.rerun()
            except Exception as e:
                with feil_plassholder:
                    _sheets_feilboks(e)

    if redigerer_navn:
        st.divider()
        if not st.session_state.get("_bekreft_slett_jury"):
            if st.button("Fjern jurymedlem", icon=":material/delete:", use_container_width=True):
                st.session_state["_bekreft_slett_jury"] = True
                st.rerun()
        else:
            st.warning(f"Fjerne **{redigerer_navn}**? Vurderinger personen allerede har gjort i regnearket beholdes.", icon=":material/warning:")
            w1, w2 = st.columns(2)
            if w1.button("Avbryt", key="avbryt_slett_jury", use_container_width=True):
                st.session_state["_bekreft_slett_jury"] = False
                st.rerun()
            if w2.button("Ja, fjern", type="primary", key="bekreft_slett_jury", use_container_width=True):
                try:
                    slett_jurymedlem(sh, redigerer_navn)
                    st.toast("Fjernet", icon=":material/check_circle:")
                    st.session_state["_jury_dialog_for"] = None
                    st.rerun()
                except Exception as e:
                    _sheets_feilboks(e, "fjerne")


@st.dialog("Kriterium")
def kriterium_dialog(redigerer_kriterium=None):
    feil_plassholder_krit = st.empty()
    eksisterende = next((k for k in alle_kriterier if k["kriterium"] == redigerer_kriterium), {}) if redigerer_kriterium else {}
    fagfelt_valg = list(felt_dict.keys()) or fagfelt_liste(alle_kriterier)
    fagfelt_sel = st.selectbox("Fagfelt", fagfelt_valg, index=fagfelt_valg.index(eksisterende["fagfelt"]) if eksisterende.get("fagfelt") in fagfelt_valg else 0)
    navn_sel = st.text_input("Kriterium (navn)", value=eksisterende.get("kriterium", ""), disabled=bool(redigerer_kriterium))
    kort_sel = st.text_input("Kort beskrivelse", value=eksisterende.get("kort", ""))
    utfyllende_sel = st.text_area("Utfyllende forklaring", value=eksisterende.get("utfyllende", ""), height=80)
    s1, s3, s5 = st.columns(3)
    skala1_sel = s1.text_input("Hva gir 1", value=eksisterende.get("skala1", ""))
    skala3_sel = s3.text_input("Hva gir 3", value=eksisterende.get("skala3", ""))
    skala5_sel = s5.text_input("Hva gir 5", value=eksisterende.get("skala5", ""))
    eksempler_sel = st.text_input("Eksempler", value=eksisterende.get("eksempler", ""))
    faser_sel = st.multiselect("Brukes i fase(r)", ["Fase 2", "Fase 3", "Testhandel"], default=eksisterende.get("faser", ["Fase 3"]))
    aktiv_sel = st.checkbox("Aktiv", value=eksisterende.get("aktiv", True)) if redigerer_kriterium else True
    sett_inn_kolonne = st.checkbox("Sett også inn ny kolonne i Rangering-fanene nå", value=False, disabled=bool(redigerer_kriterium), help="Kun aktuelt for nye kriterier.")

    c1, c2 = st.columns(2)
    if c1.button("Avbryt", use_container_width=True):
        st.rerun()
    if c2.button("Lagre", type="primary", use_container_width=True, icon=":material/save:"):
        if not navn_sel.strip():
            feil_plassholder_krit.error("Kriterium-navn kan ikke være tomt.", icon=":material/error:")
        else:
            try:
                if redigerer_kriterium:
                    oppdater_kriterium(sh, redigerer_kriterium, kort=kort_sel, utfyllende=utfyllende_sel, skala1=skala1_sel, skala3=skala3_sel, skala5=skala5_sel, eksempler=eksempler_sel)
                    if not aktiv_sel:
                        deaktiver_kriterium(sh, redigerer_kriterium)
                else:
                    add_criterion(sh, fagfelt_sel, navn_sel.strip(), kort_sel, utfyllende_sel, skala1_sel, skala3_sel, skala5_sel, eksempler_sel, faser_sel)
                    if sett_inn_kolonne:
                        if "Fase 2" in faser_sel:
                            legg_til_kriterium_kolonne(sh, FASE1_FANE, fagfelt_sel, navn_sel.strip())
                        if "Fase 3" in faser_sel:
                            legg_til_kriterium_kolonne(sh, FASE2_FANE, fagfelt_sel, navn_sel.strip())
                st.toast("Lagret", icon=":material/check_circle:")
                st.rerun()
            except Exception as e:
                with feil_plassholder_krit:
                    _sheets_feilboks(e)


fane_jury, fane_kriterier = st.tabs(["Jury", "Kriterier"])

with fane_jury:
    manglende = [k for k, antall in antall_jury_per_kriterium.items() if antall == 0]
    if manglende:
        st.warning(f"{len(manglende)} kriterier mangler jurymedlem.", icon=":material/warning:")
        with st.expander("Vis hvilke"):
            for fagfelt, kriterier in felt_dict.items():
                manglende_i_felt = [k for k in kriterier if k in manglende]
                if manglende_i_felt:
                    farge_mangel = FAGFELT_FARGE.get(fagfelt, "#888")
                    st.markdown(f"<span style='color:{farge_mangel};font-weight:700;'>{fagfelt}</span>", unsafe_allow_html=True)
                    for k in manglende_i_felt:
                        st.caption(f"• {k}")

    if st.button("Legg til jurymedlem", type="primary", icon=":material/person_add:"):
        jury_dialog()

    st.write("")
    if not navn_liste_jury:
        st.caption("Ingen jurymedlemmer lagt til ennå.")
    for navn in navn_liste_jury:
        mine = jury[navn]["kriterier"]
        with st.container(border=True):
            rc1, rc2 = st.columns([4, 1])
            with rc1:
                st.markdown(f"**{navn}**")
                if mine:
                    merkelapper = "".join(
                        f'<span class="klasse-badge" style="margin:2px 4px 2px 0;border-color:{FAGFELT_FARGE.get(fagfelt, "#888")};">{k}</span>'
                        for fagfelt, kriterier in felt_dict.items() for k in kriterier if k in mine
                    )
                    st.markdown(merkelapper, unsafe_allow_html=True)
                    st.caption(f"{len(mine)} kriterier")
                else:
                    st.caption("Ingen kriterier tildelt")
            with rc2:
                if st.button("Rediger", key=f"rediger_jury_{navn}", use_container_width=True):
                    jury_dialog(navn)

with fane_kriterier:
    if st.button("Legg til kriterium", type="primary", icon=":material/add_circle:"):
        kriterium_dialog()
    st.write("")
    for fagfelt in fagfelt_liste(alle_kriterier) or list(felt_dict.keys()):
        farge_fagfelt = FAGFELT_FARGE.get(fagfelt, "#888")
        st.markdown(f"<span style='color:{farge_fagfelt};font-weight:700;'>{fagfelt}</span>", unsafe_allow_html=True)
        for k in [kk for kk in alle_kriterier if kk["fagfelt"] == fagfelt]:
            kc1, kc2 = st.columns([5, 1])
            status_tekst = "✅ Aktiv" if k["aktiv"] else "⏸️ Inaktiv"
            antall_jm = antall_jury_per_kriterium.get(k["kriterium"], 0)
            kc1.markdown(f"**{k['kriterium']}** — {k.get('kort', '')}  \n_{status_tekst} · {antall_jm} jurymedlem(mer)_")
            if kc2.button("Rediger", key=f"rediger_krit_{k['kriterium']}", use_container_width=True):
                kriterium_dialog(k["kriterium"])
        st.write("")

st.divider()
st.subheader("Fasestatus", anchor=False)
faser = read_faser(sh)
if faser:
    faser_sortert = sorted(faser, key=lambda f: int(f.get("Fase", 0)))
    gjeldende = aktiv_fase(faser)
    navn_liste_faser = [f"{f.get('Fase')}. {f.get('Navn')}" for f in faser_sortert]
    standard_indeks = faser_sortert.index(gjeldende) if gjeldende in faser_sortert else 0
    fc1, fc2 = st.columns([3, 1])
    valgt_fase_tekst = fc1.selectbox("Gjeldende fase", navn_liste_faser, index=standard_indeks)
    if fc2.button("Sett som gjeldende", use_container_width=True):
        valgt_nummer = int(valgt_fase_tekst.split(".")[0])
        sett_gjeldende_fase(sh, valgt_nummer)
        st.toast("Fasestatus oppdatert.", icon=":material/check_circle:")
        st.rerun()
    st.caption("Tidligere faser settes automatisk til «Fullført», senere til «Kommende». Kan overstyres manuelt i fanen «Faser» i regnearket etterpå.")
else:
    st.caption("Fanen «Faser» finnes ikke ennå – opprettes automatisk neste gang Oversikt-siden åpnes.")

st.divider()
st.subheader("Finale", anchor=False)
if er_finale_last(sh):
    av, tid = finale_las_info(sh)
    st.info(f"Finalelista er låst av **{av}** ({tid}). Endringer i Sheets påvirker ikke lenger rangeringen.", icon=":material/lock:")
    if st.button("Lås opp finalelista", icon=":material/lock_open:"):
        fjern_finale_las(sh)
        st.rerun()
else:
    st.caption("Finalelista er ikke låst – rangeringen på Finale-siden oppdateres live. Lås den fra Finale-siden når resultatet er klart.")
