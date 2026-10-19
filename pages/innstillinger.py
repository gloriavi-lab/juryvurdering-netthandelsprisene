"""Side 5 – Innstillinger: Google Sheets-tilkobling, validering, og finale-lås.
Butikklisten kommer direkte fra "Rangering fase 1"-fanen – ingen Excel-
opplasting her lenger (se brief del 3: regnearket ER fasiten, appen bygger
ingen egen struktur)."""

from collections import defaultdict

import streamlit as st

from components import hent_versjonsinfo, status_prikk, topptekst, vis_feil
from jury import (
    add_criterion, aktive_kriterier, aktiv_fase, deaktiver_kriterium, fagfelt_liste, finn_duplisert_kriterium,
    hent_midlertidig_debug_siste_skriving,
    JURY_FANE, kriterier_per_fagfelt, manglende_foreslatte_kriterier, manglende_kriterium_kolonner,
    manglende_kriterium_omdopinger,
    manglende_veiledning_oppdateringer, mine_kriterier, omdop_kriterium, oppdater_kriterium, oppdater_veiledning_rad,
    read_criteria, read_faser, read_jury, sett_gjeldende_fase, slett_jurymedlem, write_jury,
)
from sheets import (
    FASE1_FANE, FASE2_FANE, GENERELLE_KOMMENTARER_FANE, ensrett_butikkrader, ensrett_url_lenker, er_finale_last,
    fane_oversikt, feilsok_farget_fane, feilsok_vurdering, finale_las_info, finn_tomme_butikkrader,
    engangsfiks_epost_omdoping_feilplassering, fjern_finale_las, fjern_formatering_fra_rad, flytt_fane_til_forst,
    konverter_scorer_til_tall, KOMMENTARER_FANE,
    legg_til_kriterium_kolonne, legg_til_na_i_datavalidering, merk_som_arkiv, migrer_orphan_fane,
    hent_api_kall_logg, hent_handling_logg, migrer_til_vurderinger_fane, migrer_vurderinger_til_farget_fane,
    nullstill_vurderinger,
    read_fase1_scores, read_generelle_kommentarer, read_ratings, read_stores, read_vurderinger,
    sett_opp_kommentarer_som_formelvisning, sikkerhetskopier_alle_faner, sjekk_gammel_fane_for_orphan_data,
    test_tilkobling, VURDERINGER_FANE,
)
from theme import FAGFELT_FARGE

topptekst("Innstillinger")
st.info("**Kun for administrator** – jurymedlemmer trenger ikke bruke denne siden.", icon=":material/admin_panel_settings:")

sh = st.session_state.get("_sh")

# Brukeren har eksplisitt bekreftet at DETTE er regnearket appen skal snakke
# med (Netthandelsprisene_Fase 1) – kun brukt til sammenligning/varsel her,
# ALDRI til selve tilkoblingen (den styres fortsatt utelukkende av
# secrets["google_sheets"]["sheet_id"], se sheets.koble_sheets()).
FORVENTET_SHEET_ID = "18fvqNKEh7dFfA9S63uxkBOpigR8vzD31wrAq49yqOIQ"

st.subheader("Google Sheets", anchor=False)
status_prikk(sh is not None)
if sh:
    if sh.id == FORVENTET_SHEET_ID:
        st.success(f"Tilkoblet regneark: **{sh.title}** (ID `{sh.id}`) – stemmer med forventet ark.", icon=":material/check_circle:")
    else:
        st.error(
            f"Tilkoblet regneark: **{sh.title}** (ID `{sh.id}`) – **stemmer IKKE** med arket du har bekreftet "
            f"(«Netthandelsprisene_Fase 1», ID `{FORVENTET_SHEET_ID}`). Alt appen leser og skriver går til "
            "ARKET OVER, ikke til det du har åpent i nettleseren. Rett opp `sheet_id` under "
            "`[google_sheets]` i appens Secrets på Streamlit Cloud (Manage app → Settings → Secrets), "
            "og sørg for at tjenestekontoen (e-posten i `gcp_service_account`) har redigeringstilgang til "
            f"ID `{FORVENTET_SHEET_ID}` før du lagrer secrets på nytt.",
            icon=":material/dangerous:",
        )
    bc1, bc2, bc3 = st.columns(3)
    bc1.link_button("Åpne regnearket", sh.url, icon=":material/open_in_new:", use_container_width=True)
    if bc2.button(
        "Hent siste fra regnearket", icon=":material/refresh:", use_container_width=True,
        help=(
            "Tømmer ALL mellomlagring – nyttig rett etter du har redigert noe manuelt i Sheets. Flere av "
            "cachene (kriterier/jury/faser/veiledning/butikkliste) varer nå 10 minutter i stedet for 30–120 "
            "sekunder, siden de sjelden endres – denne knappen er «tving fram nå» i mellomtiden."
        ),
    ):
        read_stores.clear()
        read_ratings.clear()
        read_fase1_scores.clear()
        read_criteria.clear()
        read_jury.clear()
        read_faser.clear()
        read_vurderinger.clear()
        read_generelle_kommentarer.clear()
        fane_oversikt.clear()
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

st.divider()
st.subheader("Ytelse", anchor=False)
st.caption(
    "Måler faktisk tidsbruk for hvert Sheets-API-kall appen gjør (de siste 500). NB: tilkoblingen er delt av "
    "ALLE som bruker appen samtidig, så loggen viser samlet trafikk for hele appen, ikke bare din egen økt – "
    "fortsatt nyttig for å se hvilke sider/handlinger som faktisk er tregest, i stedet for å gjette."
)

st.markdown("**Siste 10 handlinger**")
_handling_logg = hent_handling_logg()
if not _handling_logg:
    st.caption("Ingen handlinger målt ennå i denne kjøringen – lagre noe eller bytt side, så dukker de opp her.")
else:
    st.dataframe(
        [
            {
                "Tid": h["tid"], "Handling": h["handling"], "Total tid (ms)": h["varighet_ms"],
                "Antall Sheets-kall": h["antall_kall"], "ms per kall": h["ms_per_kall"],
            }
            for h in reversed(_handling_logg)
        ],
        hide_index=True, use_container_width=True,
    )
_api_logg = hent_api_kall_logg()
if not _api_logg:
    st.caption("Ingen kall målt ennå i denne kjøringen (nullstilles når appen restarter).")
else:
    _total_tid = sum(k["varighet_ms"] for k in _api_logg)
    st.markdown(f"**{len(_api_logg)} kall målt · {_total_tid / 1000:.1f} sekunder totalt · {_total_tid / len(_api_logg):.0f} ms i snitt**")

    _per_side = defaultdict(lambda: {"antall": 0, "tid_ms": 0.0})
    for _k in _api_logg:
        _per_side[_k["side"]]["antall"] += 1
        _per_side[_k["side"]]["tid_ms"] += _k["varighet_ms"]
    with st.expander("Per side", expanded=True):
        st.dataframe(
            sorted(
                [
                    {"Side": side, "Antall kall": v["antall"], "Total tid (ms)": round(v["tid_ms"]), "Snitt (ms)": round(v["tid_ms"] / v["antall"])}
                    for side, v in _per_side.items()
                ],
                key=lambda r: -r["Total tid (ms)"],
            ),
            hide_index=True, use_container_width=True,
        )
    with st.expander("10 treigeste enkeltkall"):
        _treigeste = sorted(_api_logg, key=lambda k: -k["varighet_ms"])[:10]
        st.dataframe(
            [{"Tid": k["tid"], "Side": k["side"], "Metode": k["metode"], "Endepunkt": k["endepunkt"], "Varighet (ms)": k["varighet_ms"]} for k in _treigeste],
            hide_index=True, use_container_width=True,
        )

try:
    butikker, advarsler = read_stores(sh)
except Exception as e:
    vis_feil(f"Fant ikke fanen «{FASE2_FANE}» i regnearket (eller noe annet gikk galt)", e)
    st.stop()

st.caption(f"Leser butikklisten direkte fra fanen «{FASE2_FANE}» – {len(butikker)} butikker funnet.")
with st.expander("Fase-styrt butikkliste (valgfritt)", icon=":material/filter_alt:"):
    st.caption(
        f"Legg til en kolonne kalt nøyaktig «Fase» i «{FASE2_FANE}» og skriv «Fase 2», «Fase 3» eller «Testkjøp» "
        "i den for en butikk, så vises den KUN for jury når akkurat den fasen er «Pågår» under Fasestatus lenger "
        "ned. Tom celle (standard) betyr at butikken vises uansett fase – ingenting filtreres bort før dere "
        "faktisk fyller ut kolonnen for noen butikker."
    )

if advarsler:
    with st.expander(f"Avvik i regnearket ({len(advarsler)})", expanded=False, icon=":material/warning:"):
        for a in advarsler:
            st.markdown(f"- {a}")
# Ingenting vises her i det hele tatt når regnearket er i orden – ingen tom boks, ingen varsel.

st.divider()
st.subheader("Datamodell", anchor=False)
st.success(
    f"**Aktiv fane: «{FASE2_FANE}»** – appen leser og skriver score (som tall) og kommentar (som celle-notat) "
    "DIREKTE hit, i samme rad/kolonne-oppsett som resten av regnearket. Manuelle rettelser dere gjør her "
    "vises i appen ved neste lasting.",
    icon=":material/check_circle:",
)
try:
    antall_vurderinger = len(read_vurderinger(sh))
except Exception:
    antall_vurderinger = 0
st.caption(
    f"«{VURDERINGER_FANE}» er en LOGG (ikke det som vises) – {antall_vurderinger} rader der nå. Brukes til å "
    "regne ut riktig snitt når flere jurymedlemmer deler ett kriterium, og som sikkerhet hvis noe må "
    "spores tilbake."
)

bkc1, bkc2 = st.columns(2)
if bkc1.button("Ta sikkerhetskopi av alle faner nå", icon=":material/backup:", use_container_width=True):
    try:
        with st.spinner("Sikkerhetskopierer …"):
            nye_navn = sikkerhetskopier_alle_faner(sh)
    except Exception as e:
        vis_feil("Kunne ikke ta sikkerhetskopi", e)
    else:
        st.success(f"{len(nye_navn)} faner sikkerhetskopiert: {', '.join(nye_navn)}", icon=":material/check_circle:")

if bkc2.button(f"Flytt «{VURDERINGER_FANE}»-logg inn i «{FASE2_FANE}»", icon=":material/database:", use_container_width=True, type="primary"):
    st.session_state["_vis_migrer_til_farget_dialog"] = True


@st.dialog(f"Flytte «{VURDERINGER_FANE}»-logg inn i «{FASE2_FANE}»?")
def migrer_til_farget_dialog():
    st.write(
        f"Dette tar FØRST sikkerhetskopi av absolutt alle faner, deretter regner ut riktig verdi for hvert "
        f"(butikk, kriterium) i «{VURDERINGER_FANE}» (snitt hvis flere jurymedlemmer deler kriteriet) og "
        f"skriver det inn i riktig celle i «{FASE2_FANE}», med kommentaren(e) som celle-notat. "
        f"Ingenting slettes fra «{VURDERINGER_FANE}» – den fortsetter som logg."
    )
    c1, c2 = st.columns(2)
    if c1.button("Avbryt", use_container_width=True, key="avbryt_migrer_farget"):
        st.rerun()
    if c2.button("Ja, flytt nå", type="primary", use_container_width=True, icon=":material/database:", key="bekreft_migrer_farget"):
        try:
            with st.spinner("Sikkerhetskopierer og flytter data …"):
                resultat = migrer_vurderinger_til_farget_fane(sh)
        except Exception as e:
            vis_feil("Kunne ikke flytte data", e)
        else:
            st.session_state["_migrering_til_farget_resultat"] = resultat
            st.rerun()


if st.session_state.get("_vis_migrer_til_farget_dialog"):
    st.session_state["_vis_migrer_til_farget_dialog"] = False
    migrer_til_farget_dialog()

if st.session_state.get("_migrering_til_farget_resultat"):
    r = st.session_state.pop("_migrering_til_farget_resultat")
    st.success(f"Ferdig! {r['detaljer']}", icon=":material/check_circle:")
    st.caption(f"Sikkerhetskopier: {', '.join(r['backup'])}")
    if r["feilet"]:
        with st.expander(f"{len(r['feilet'])} kunne ikke skrives"):
            for feil in r["feilet"]:
                st.markdown(f"- {feil}")

with st.expander(f"Eldre verktøy: flytt «{FASE2_FANE}» → «{VURDERINGER_FANE}» (motsatt retning)", icon=":material/history:"):
    st.caption(
        f"Fra en tidligere runde, da «{VURDERINGER_FANE}» var det appen viste. Nyttig kun hvis noen har "
        f"rettet tall direkte i «{FASE2_FANE}» og dere også vil ha det i loggen."
    )
    if st.button(f"Flytt data fra «{FASE2_FANE}» til «{VURDERINGER_FANE}»", icon=":material/database:", use_container_width=True):
        st.session_state["_vis_migrer_dialog"] = True


@st.dialog("Flytte data til Vurderinger-fanen?")
def migrer_dialog():
    st.write(
        "Dette tar FØRST sikkerhetskopi av absolutt alle faner i regnearket, deretter leser alle "
        f"eksisterende scorer/kommentarer fra «{FASE2_FANE}»-rutenettet og den gamle «Kommentarer»-fanen, "
        "og skriver dem inn i «Vurderinger»-fanen. Ingen rader slettes eller går tapt – "
        "originalen ligger urørt i sikkerhetskopien."
    )
    st.caption(
        "Merk: det gamle rutenettet sporet ikke hvem som satte HVER enkelt score (kun hvem som sist "
        "rørte hele raden) – historiske scorer attribueres derfor til den som kommenterte (hvis kjent), "
        "ellers til den som sist endret raden, ellers «Ukjent»."
    )
    c1, c2 = st.columns(2)
    if c1.button("Avbryt", use_container_width=True):
        st.rerun()
    if c2.button("Ja, flytt data nå", type="primary", use_container_width=True, icon=":material/database:"):
        try:
            with st.spinner("Sikkerhetskopierer og flytter data …"):
                resultat = migrer_til_vurderinger_fane(sh)
        except Exception as e:
            vis_feil("Kunne ikke flytte data", e)
        else:
            st.session_state["_migrering_resultat"] = resultat
            st.rerun()


if st.session_state.get("_vis_migrer_dialog"):
    st.session_state["_vis_migrer_dialog"] = False
    migrer_dialog()

if st.session_state.get("_migrering_resultat"):
    r = st.session_state.pop("_migrering_resultat")
    st.success(f"Ferdig! {r['detaljer']}", icon=":material/check_circle:")
    st.caption(f"Sikkerhetskopier: {', '.join(r['backup'])}")

with st.expander("Konverter tekst-scorer til tall", icon=":material/pin:"):
    st.caption(
        f"Tidligere runder lagret enkelte scorer som TEKST («5») i stedet for ekte tall – dette skriver dem "
        f"om til tall, i både «{FASE2_FANE}» og «{VURDERINGER_FANE}». Trygt å kjøre flere ganger (en celle "
        "som allerede er et tall røres ikke i praksis). «Kan ikke vurdere» røres aldri."
    )
    if st.button("Konverter nå", icon=":material/pin:"):
        st.session_state["_vis_konverter_dialog"] = True


@st.dialog("Konvertere tekst-scorer til tall?")
def konverter_dialog():
    st.write(f"Tar sikkerhetskopi av alt først, leser deretter gjennom alle kriterie-celler i «{FASE2_FANE}» og Score-kolonnen i «{VURDERINGER_FANE}», og skriver tallverdier tilbake der det finnes en gyldig score.")
    c1, c2 = st.columns(2)
    if c1.button("Avbryt", use_container_width=True, key="avbryt_konverter"):
        st.rerun()
    if c2.button("Ja, konverter nå", type="primary", use_container_width=True, icon=":material/pin:", key="bekreft_konverter"):
        try:
            with st.spinner("Sikkerhetskopierer og konverterer …"):
                resultat = konverter_scorer_til_tall(sh)
        except Exception as e:
            vis_feil("Kunne ikke konvertere scorer", e)
        else:
            st.session_state["_konverter_resultat"] = resultat
            st.rerun()


if st.session_state.get("_vis_konverter_dialog"):
    st.session_state["_vis_konverter_dialog"] = False
    konverter_dialog()

if st.session_state.get("_konverter_resultat"):
    r = st.session_state.pop("_konverter_resultat")
    st.success(f"Ferdig! {r['antall_farget_fane']} celler i «{FASE2_FANE}», {r['antall_vurderinger']} i «{VURDERINGER_FANE}».", icon=":material/check_circle:")
    st.caption(f"Sikkerhetskopier: {', '.join(r['backup'])}")
    st.caption("Sjekk at eventuelle snitt-/formelkolonner i regnearket regner riktig etter konverteringen.")

st.divider()
with st.expander("⚠ Nullstill alle vurderinger (start ekspertvurderingen helt tom)", icon=":material/delete_sweep:"):
    st.warning(
        f"Dette tømmer ALLE kriteriecellene og celle-notatene i «{FASE2_FANE}», og fjerner ALLE datarader i "
        f"«{VURDERINGER_FANE}» og «{GENERELLE_KOMMENTARER_FANE}». «Kommentarer» trenger ingen egen handling – "
        "den viser seg selv tom automatisk (den er en live formelvisning av «Vurderinger»).",
        icon=":material/warning:",
    )
    st.caption("Rører ALDRI jury, kriterier, fordeling, veiledning eller faser. Tar sikkerhetskopi av alt FØRST.")
    if st.button("Nullstill nå", icon=":material/delete_sweep:"):
        st.session_state["_vis_nullstill_dialog"] = True


@st.dialog("Nullstille alle vurderinger?")
def nullstill_dialog():
    st.warning(
        f"Dette kan IKKE angres i selve fanene (men alt sikkerhetskopieres først). "
        f"Alle scorer, kommentarer og celle-notater i «{FASE2_FANE}» forsvinner, og alle rader i "
        f"«{VURDERINGER_FANE}» og «{GENERELLE_KOMMENTARER_FANE}» slettes.",
        icon=":material/warning:",
    )
    c1, c2 = st.columns(2)
    if c1.button("Avbryt", use_container_width=True, key="avbryt_nullstill"):
        st.rerun()
    if c2.button("Ja, nullstill alt nå", type="primary", use_container_width=True, icon=":material/delete_sweep:", key="bekreft_nullstill"):
        try:
            with st.spinner("Sikkerhetskopierer og nullstiller …"):
                resultat = nullstill_vurderinger(sh)
        except Exception as e:
            vis_feil("Kunne ikke nullstille vurderinger", e)
        else:
            st.session_state["_nullstill_resultat"] = resultat
            st.rerun()


if st.session_state.get("_vis_nullstill_dialog"):
    st.session_state["_vis_nullstill_dialog"] = False
    nullstill_dialog()

if st.session_state.get("_nullstill_resultat"):
    r = st.session_state.pop("_nullstill_resultat")
    st.success(
        f"Ferdig! {r['fase2_celler']} celler og {r['fase2_notater']} notater tømt i «{FASE2_FANE}», "
        f"{r['vurderinger_rader']} rader fjernet i «{VURDERINGER_FANE}», {r['generelle_rader']} rader fjernet i «{GENERELLE_KOMMENTARER_FANE}».",
        icon=":material/check_circle:",
    )
    st.caption(f"Sikkerhetskopier: {', '.join(r['backup'])}")

st.divider()
st.subheader("Kommentar-oversikt", anchor=False)
st.caption(
    f"«{KOMMENTARER_FANE}» slutter å bli skrevet til av appen når kommentarer flyttet inn i «{VURDERINGER_FANE}» "
    f"– den sto igjen med gamle testrader. Knappen under tar sikkerhetskopi, tømmer «{KOMMENTARER_FANE}» og setter "
    f"den opp som en LIVE formelvisning av «{VURDERINGER_FANE}» (QUERY i celle A2) – Google Sheets holder den "
    "oppdatert av seg selv, appen skriver aldri hit igjen."
)
if st.button(f"Sett opp «{KOMMENTARER_FANE}» som automatisk formelvisning", icon=":material/table_view:"):
    st.session_state["_vis_kommentar_formel_dialog"] = True


@st.dialog(f"Sette opp «{KOMMENTARER_FANE}» som formelvisning?")
def kommentar_formel_dialog():
    st.write(
        f"Dette tar FØRST sikkerhetskopi av alle faner, tømmer deretter «{KOMMENTARER_FANE}» helt (de gamle "
        f"testradene forsvinner fra selve fanen, men ligger urørt i sikkerhetskopien), og setter inn header + "
        f"én QUERY-formel i A2 som henter Butikk, Jurymedlem, Fagfelt, Kriterium, Score, Kommentar og Sist "
        f"endret fra «{VURDERINGER_FANE}» for alle rader med kommentar, sortert på butikk."
    )
    st.caption("Formelen bruker semikolon (;) som skilletegn – vanlig for norsk regnearkspråk. Gir den #ERROR!/#NAME?, si ifra så retter jeg den til komma.")
    c1, c2 = st.columns(2)
    if c1.button("Avbryt", use_container_width=True, key="avbryt_kommentar_formel"):
        st.rerun()
    if c2.button("Ja, sett opp nå", type="primary", use_container_width=True, icon=":material/table_view:", key="bekreft_kommentar_formel"):
        try:
            with st.spinner("Sikkerhetskopierer og setter opp formelvisning …"):
                backup_navn = sett_opp_kommentarer_som_formelvisning(sh)
        except Exception as e:
            vis_feil("Kunne ikke sette opp formelvisning", e)
        else:
            st.session_state["_kommentar_formel_resultat"] = backup_navn
            st.rerun()


if st.session_state.get("_vis_kommentar_formel_dialog"):
    st.session_state["_vis_kommentar_formel_dialog"] = False
    kommentar_formel_dialog()

if st.session_state.get("_kommentar_formel_resultat"):
    backup_navn = st.session_state.pop("_kommentar_formel_resultat")
    st.success(f"Ferdig! «{KOMMENTARER_FANE}» er nå en formelvisning.", icon=":material/check_circle:")
    st.caption(f"Sikkerhetskopier: {', '.join(backup_navn)}")

st.divider()
st.subheader("Faner i regnearket", anchor=False)
st.caption("Alle faner, og hva appen bruker hver av dem til – slik at det alltid er synlig hva som er aktivt kontra gamle levninger. Ingenting slettes noensinne herfra.")
try:
    faner = fane_oversikt(sh)
except Exception as e:
    faner = []
    vis_feil("Kunne ikke liste faner", e)

if faner:
    st.dataframe(
        [{"Fane": f["navn"], "Status": f["status"], "Forklaring": f["forklaring"]} for f in faner],
        hide_index=True, use_container_width=True,
    )
    if st.button(f"Flytt «{FASE2_FANE}» (aktiv) først", icon=":material/arrow_upward:"):
        try:
            flytt_fane_til_forst(sh, FASE2_FANE)
            fane_oversikt.clear()
            st.toast("Flyttet.", icon=":material/check_circle:")
            st.rerun()
        except Exception as e:
            vis_feil("Kunne ikke flytte fanen", e)

    kandidater = [f["navn"] for f in faner if f["kan_arkiveres"]]
    if kandidater:
        valgte = st.multiselect(f"Merk valgte som «ARKIV – »", kandidater, key="_arkiver_valgte")
        if valgte and st.button(f"Merk {len(valgte)} fane(r) som ARKIV", icon=":material/archive:"):
            merket = []
            for navn in valgte:
                try:
                    merket.append(merk_som_arkiv(sh, navn))
                except Exception as e:
                    vis_feil(f"Kunne ikke merke «{navn}»", e)
            if merket:
                fane_oversikt.clear()
                st.success(f"Merket: {', '.join(merket)}", icon=":material/check_circle:")
                st.rerun()

    # «Rangering fase 2» er det GAMLE navnet på «Rangering ekspertvurdering»
    # (se sheets._GAMLE_NAVN) – men siden den aktive fanen allerede finnes
    # under sitt nye navn, blir en eventuell SEPARAT, gjenglemt fane med det
    # gamle navnet ALDRI oppdaget/slått sammen automatisk. Sjekk eksplisitt.
    _gammel_fane_navn = "Rangering fase 2"
    if any(f["navn"] == _gammel_fane_navn for f in faner):
        try:
            _orphan_sjekk = sjekk_gammel_fane_for_orphan_data(sh, _gammel_fane_navn)
        except Exception as e:
            _orphan_sjekk = None
            vis_feil(f"Kunne ikke sjekke «{_gammel_fane_navn}»", e)
        if _orphan_sjekk:
            if _orphan_sjekk["orphans"]:
                st.warning(
                    f"«{_gammel_fane_navn}» finnes som en EGEN fane (ikke samme som «{FASE2_FANE}») og inneholder "
                    f"{len(_orphan_sjekk['orphans'])} verdier som IKKE finnes i «{VURDERINGER_FANE}» ennå – disse "
                    "ville forsvunnet fra det jury ser hvis fanen bare ble arkivert.",
                    icon=":material/warning:",
                )
                if st.button(f"Flytt disse {len(_orphan_sjekk['orphans'])} verdiene inn i «{FASE2_FANE}» og «{VURDERINGER_FANE}»", icon=":material/move_up:"):
                    try:
                        with st.spinner("Sikkerhetskopierer og flytter …"):
                            res = migrer_orphan_fane(sh, _gammel_fane_navn)
                    except Exception as e:
                        vis_feil("Kunne ikke flytte verdiene", e)
                    else:
                        st.success(f"Flyttet {res['antall_migrert']} verdier for {res['antall_butikker']} butikker.", icon=":material/check_circle:")
                        st.caption(f"Sikkerhetskopier: {', '.join(res['backup'])}")
                        if res["feilet"]:
                            with st.expander(f"{len(res['feilet'])} butikk(er) kunne ikke skrives til den fargede fanen"):
                                for feil in res["feilet"]:
                                    st.markdown(f"- {feil}")
            else:
                st.success(f"«{_gammel_fane_navn}» finnes, men inneholder ingen verdier som mangler i «{VURDERINGER_FANE}» – trygt å arkivere over (se listen over).", icon=":material/check_circle:")

st.divider()
with st.expander(f"Ensrett butikkradene (rad 3–48) i «{FASE2_FANE}»", icon=":material/format_paint:"):
    st.caption(
        "Gjør butikkradene like resten av arket: skrift/størrelse/radhøyde/bakgrunnsfarger/kantlinjer kopieres "
        "fra én mal-rad du velger – celleVERDIENE røres aldri. «Besøk →»-lenken skrives om separat. Nedtrekks-"
        "listene (1–5 + «Kan ikke vurdere») settes for HELE arket av «Legg til nå»-knappen lenger ned under "
        "«Opprett «{FASE2_FANE}» manuelt», og gjeldende fase settes under «Fasestatus» – begge er allerede "
        "bygget, så de gjentas ikke her.".format(FASE2_FANE=FASE2_FANE)
    )

    if st.button("Sjekk om noen av rad 3–48 er tomme", icon=":material/search:"):
        try:
            _tomme = finn_tomme_butikkrader(sh, FASE2_FANE, 3, 48)
        except Exception as e:
            vis_feil("Kunne ikke sjekke rad 3–48", e)
        else:
            if _tomme:
                st.warning(f"{len(_tomme)} tom(me) rad(er) blant butikkradene: {', '.join(str(r) for r in _tomme)}.", icon=":material/warning:")
            else:
                st.success("Ingen tomme rader blant rad 3–48.", icon=":material/check_circle:")

    st.write("")
    _mal_rad = st.number_input("Mal-rad (en butikkrad du vet ser riktig ut)", min_value=3, max_value=48, value=3, step=1, key="_mal_rad_ensrett")
    if st.button(f"Kopier formatering + radhøyde fra rad {_mal_rad} til rad 3–48", icon=":material/format_paint:"):
        st.session_state["_vis_ensrett_dialog"] = True

    st.write("")
    if st.button(f"Sett «Besøk →»-lenker i URL-kolonnen for rad 3–48", icon=":material/link:"):
        st.session_state["_vis_url_lenker_dialog"] = True


@st.dialog("Ensrette butikkradene?")
def ensrett_dialog(mal_rad):
    st.write(f"Kopierer formatering og radhøyde fra rad {mal_rad} til alle rader fra 3 til 48 i «{FASE2_FANE}». Celleverdier røres ikke. Sikkerhetskopi tas først.")
    c1, c2 = st.columns(2)
    if c1.button("Avbryt", use_container_width=True, key="avbryt_ensrett"):
        st.rerun()
    if c2.button("Ja, ensrett nå", type="primary", use_container_width=True, icon=":material/format_paint:", key="bekreft_ensrett"):
        try:
            with st.spinner("Sikkerhetskopierer og kopierer formatering …"):
                resultat = ensrett_butikkrader(sh, FASE2_FANE, mal_rad, 3, 48)
        except Exception as e:
            vis_feil("Kunne ikke ensrette butikkradene", e)
        else:
            st.session_state["_ensrett_resultat"] = resultat
            st.rerun()


if st.session_state.get("_vis_ensrett_dialog"):
    st.session_state["_vis_ensrett_dialog"] = False
    ensrett_dialog(_mal_rad)

if st.session_state.get("_ensrett_resultat"):
    r = st.session_state.pop("_ensrett_resultat")
    st.success(f"Ferdig! Formatering kopiert fra rad {r['mal_rad']} til rad {r['fra_rad']}–{r['til_rad']}.", icon=":material/check_circle:")
    st.caption(f"Radhøyde {'ble også satt likt' if r['radhoyde_satt'] else 'ble IKKE endret (mal-raden bruker standardhøyde, så ingenting å kopiere)'}.")
    st.caption(f"Sikkerhetskopier: {', '.join(r['backup'])}")


@st.dialog("Sette «Besøk →»-lenker?")
def url_lenker_dialog():
    st.write(f"Skriver om URL-kolonnen til =HYPERLINK(\"url\";\"Besøk →\") for alle rader fra 3 til 48 i «{FASE2_FANE}» som faktisk har en URL. Selve nettadressen endres ikke, kun visningen. Sikkerhetskopi tas først.")
    c1, c2 = st.columns(2)
    if c1.button("Avbryt", use_container_width=True, key="avbryt_url_lenker"):
        st.rerun()
    if c2.button("Ja, sett lenker nå", type="primary", use_container_width=True, icon=":material/link:", key="bekreft_url_lenker"):
        try:
            with st.spinner("Sikkerhetskopierer og setter lenker …"):
                resultat = ensrett_url_lenker(sh, FASE2_FANE, 3, 48)
        except Exception as e:
            vis_feil("Kunne ikke sette lenker", e)
        else:
            st.session_state["_url_lenker_resultat"] = resultat
            st.rerun()


if st.session_state.get("_vis_url_lenker_dialog"):
    st.session_state["_vis_url_lenker_dialog"] = False
    url_lenker_dialog()

if st.session_state.get("_url_lenker_resultat"):
    r = st.session_state.pop("_url_lenker_resultat")
    if r.get("feil"):
        st.error(r["feil"], icon=":material/error:")
    else:
        st.success(f"Ferdig! {r['antall']} lenke(r) satt til «Besøk →».", icon=":material/check_circle:")
    st.caption(f"Sikkerhetskopier: {', '.join(r['backup'])}")

st.divider()
with st.expander(f"Forhåndsvisning: rad 49 og nedover i «{FASE2_FANE}» (kun lesing)", icon=":material/preview:"):
    st.caption(
        "Viser nøyaktig det som faktisk står i radene – rører ingenting. Brukes til å avgjøre hva som skal "
        "gjøres med disse radene før noe eventuelt flyttes eller slettes."
    )
    if st.button("Vis rad 49+", icon=":material/preview:"):
        try:
            _rader_49 = sh.worksheet(FASE2_FANE).get_all_values()[48:]
        except Exception as e:
            vis_feil(f"Kunne ikke lese «{FASE2_FANE}»", e)
        else:
            _ikke_tomme = [(i + 49, rad) for i, rad in enumerate(_rader_49) if any(c.strip() for c in rad)]
            st.markdown(f"**{len(_rader_49)} rad(er) totalt fra rad 49, {len(_ikke_tomme)} av dem har noe innhold.**")
            if _ikke_tomme:
                st.dataframe(
                    [{"Rad": radnr, **{f"Kolonne {j + 1}": v for j, v in enumerate(rad) if v.strip()}} for radnr, rad in _ikke_tomme[:50]],
                    hide_index=True, use_container_width=True,
                )
                if len(_ikke_tomme) > 50:
                    st.caption(f"… og {len(_ikke_tomme) - 50} rad(er) til (vis færre kolonner/rader om du vil se resten).")
            else:
                st.success("Alle radene fra 49 og nedover er helt tomme.", icon=":material/check_circle:")

    st.divider()
    st.caption(
        "Fjerner bakgrunnsfarger, skrift og kantlinjer fra rad 49 og utover (til fanens siste rad/kolonne) – "
        "rører ALDRI celleverdier eller notater. Nyttig for gamle, uryddede levninger lenger ned i fanen."
    )
    if st.button(f"Fjern formatering og farger fra rad 49+ i «{FASE2_FANE}»", icon=":material/format_color_reset:"):
        st.session_state["_vis_fjern_formatering_dialog"] = True


@st.dialog("Fjerne formatering fra rad 49 og utover?")
def fjern_formatering_dialog():
    st.write(
        f"Dette fjerner bakgrunnsfarger, skrift og kantlinjer fra rad 49 og utover i «{FASE2_FANE}» – "
        "celleverdier og notater røres ikke. Sikkerhetskopi tas først."
    )
    c1, c2 = st.columns(2)
    if c1.button("Avbryt", use_container_width=True, key="avbryt_fjern_format"):
        st.rerun()
    if c2.button("Ja, fjern formatering", type="primary", use_container_width=True, icon=":material/format_color_reset:", key="bekreft_fjern_format"):
        try:
            with st.spinner("Sikkerhetskopierer og fjerner formatering …"):
                resultat = fjern_formatering_fra_rad(sh, FASE2_FANE, 49)
        except Exception as e:
            vis_feil("Kunne ikke fjerne formatering", e)
        else:
            st.session_state["_fjern_formatering_resultat"] = resultat
            st.rerun()


if st.session_state.get("_vis_fjern_formatering_dialog"):
    st.session_state["_vis_fjern_formatering_dialog"] = False
    fjern_formatering_dialog()

if st.session_state.get("_fjern_formatering_resultat"):
    r = st.session_state.pop("_fjern_formatering_resultat")
    st.success(f"Ferdig! Formatering fjernet fra rad {r['fra_rad']} og utover i «{r['fane']}».", icon=":material/check_circle:")
    st.caption(f"Sikkerhetskopier: {', '.join(r['backup'])}")

st.divider()
with st.expander(f"Opprett «{FASE2_FANE}» manuelt", icon=":material/content_copy:"):
    st.caption(
        f"«{FASE2_FANE}» opprettes automatisk (som en nøyaktig kopi av «{FASE1_FANE}» – samme farger, "
        "sammenslåinger, nedtrekkslister og filter) første gang noen lagrer en vurdering, eller når du trykker knappen under."
    )
    try:
        sh.worksheet(FASE2_FANE)
        st.success(f"«{FASE2_FANE}» finnes allerede.", icon=":material/check_circle:")
    except Exception:
        if st.button("Opprett «Rangering fase 2» nå", icon=":material/content_copy:"):
            try:
                read_ratings(sh)  # trigger _sikre_fase2_fane
            except Exception as e:
                vis_feil(f"Kunne ikke opprette «{FASE2_FANE}»", e)
            else:
                fane_oversikt.clear()
                st.rerun()

    st.caption(
        "Legger «Kan ikke vurdere» til som en ekstra gyldig verdi i kriteriecellenes nedtrekksliste på "
        f"«{FASE2_FANE}» (i tillegg til 1–5). Endrer kun datavalideringen, ingen annen formatering."
    )
    if st.button("Legg til nå", icon=":material/playlist_add_check:"):
        try:
            legg_til_na_i_datavalidering(sh)
        except Exception as e:
            vis_feil("Kunne ikke legge til", e)
        else:
            st.success("Lagt til.", icon=":material/check_circle:")

st.divider()
st.subheader("Veiledningstekst («Hvordan bedømme»)", anchor=False)
try:
    manglende_veiledning = manglende_veiledning_oppdateringer(sh)
except Exception as e:
    manglende_veiledning = {}
    vis_feil("Kunne ikke lese veiledningen", e)

if not manglende_veiledning:
    st.success("Veiledningsteksten er oppdatert.", icon=":material/check_circle:")
else:
    st.warning(f"{len(manglende_veiledning)} tekst(er) avviker fra siste godkjente ordlyd.", icon=":material/warning:")
    for overskrift, (gammel, ny) in manglende_veiledning.items():
        with st.expander(f"«{overskrift}»"):
            st.caption("Nåværende:")
            st.caption(gammel or "_(tom)_")
            st.caption("Foreslått:")
            st.markdown(ny)
            if st.button(f"Oppdater «{overskrift}»", key=f"oppdater_veiledning_{overskrift}"):
                try:
                    oppdater_veiledning_rad(sh, overskrift, ny)
                except Exception as e:
                    vis_feil(f"Kunne ikke oppdatere «{overskrift}»", e)
                else:
                    st.toast("Oppdatert", icon=":material/check_circle:")
                    st.rerun()

st.divider()
st.subheader("Jury og kriterier", anchor=False)

_debug_skriving = hent_midlertidig_debug_siste_skriving()
if _debug_skriving:
    with st.expander("MIDLERTIDIG DEBUG: siste skriving til Jury-fanen (fjernes etter feilsøking)", icon=":material/bug_report:"):
        st.json(_debug_skriving, expanded=True)

try:
    alle_kriterier = read_criteria(sh)
    jury = read_jury(sh)
except Exception as e:
    alle_kriterier, jury = [], {}
    vis_feil("Kunne ikke lese jury/kriterier", e)
kriterier_fase3 = aktive_kriterier(alle_kriterier, fase="Fase 3")
felt_dict = kriterier_per_fagfelt(kriterier_fase3)
navn_liste_jury = sorted(jury.keys())
antall_jury_per_kriterium = {k: sum(1 for p in jury.values() if any(kr == k for kr in p["kriterier"])) for liste in felt_dict.values() for k in liste}

st.divider()
with st.expander("⚠ Engangsfiks: E-post-omdøping havnet i feil kolonne", icon=":material/build:"):
    st.warning(
        "En reell bug (cache-kollisjon, nå rettet i koden) gjorde at forrige E-post-omdøping skrev «Kundeklubb, "
        "nyhetsbrev, e-post og SMS» inn i Innovasjon-gruppens FØRSTE kolonne i «Rangering ekspertvurdering» "
        "(der «Innovative løsninger» sto), i stedet for i selve E-post-kolonnen. Denne knappen retter begge "
        "cellene tilbake til riktig innhold – trygt å trykke selv om det alt er rettet (sjekker først).",
        icon=":material/warning:",
    )
    if st.button("Rett opp feilplasseringen nå", icon=":material/build:"):
        st.session_state["_vis_engangsfiks_dialog"] = True


@st.dialog("Rette opp feilplassert kolonneoverskrift?")
def engangsfiks_dialog():
    st.write(f"Retter kolonneoverskriftene i «{FASE2_FANE}» tilbake til riktig innhold. Sikkerhetskopi tas først.")
    c1, c2 = st.columns(2)
    if c1.button("Avbryt", use_container_width=True, key="avbryt_engangsfiks"):
        st.rerun()
    if c2.button("Ja, rett opp nå", type="primary", use_container_width=True, icon=":material/build:", key="bekreft_engangsfiks"):
        try:
            with st.spinner("Sikkerhetskopierer og retter …"):
                resultat = engangsfiks_epost_omdoping_feilplassering(sh)
        except Exception as e:
            vis_feil("Kunne ikke rette opp", e)
        else:
            st.session_state["_engangsfiks_resultat"] = resultat
            st.rerun()


if st.session_state.get("_vis_engangsfiks_dialog"):
    st.session_state["_vis_engangsfiks_dialog"] = False
    engangsfiks_dialog()

if st.session_state.get("_engangsfiks_resultat"):
    r = st.session_state.pop("_engangsfiks_resultat")
    if r["endringer"]:
        st.success("Ferdig! Rettet:", icon=":material/check_circle:")
        for e in r["endringer"]:
            st.markdown(f"- {e}")
    else:
        st.info("Ingen feilplassering funnet – var allerede riktig.", icon=":material/info:")
    st.caption(f"Sikkerhetskopier: {', '.join(r['backup'])}")

st.divider()
st.subheader("Kriterienavn til godkjenning", anchor=False)
try:
    manglende_omdopinger = manglende_kriterium_omdopinger(alle_kriterier)
except Exception as e:
    manglende_omdopinger = {}
    vis_feil("Kunne ikke sjekke kriterienavn", e)

if not manglende_omdopinger:
    st.success("Ingen kriterienavn venter på oppdatering.", icon=":material/check_circle:")
else:
    for gammelt, (fagfelt, nytt, ny_kort, gammel_kort) in manglende_omdopinger.items():
        with st.container(border=True):
            st.markdown(f"**«{gammelt}»** ({fagfelt}) → **«{nytt}»**")
            st.caption("Nåværende kort beskrivelse:")
            st.caption(gammel_kort or "_(tom)_")
            st.caption("Foreslått kort beskrivelse:")
            st.markdown(ny_kort)
            st.caption(
                f"Oppdaterer Kriterier-fanen (navn + kort beskrivelse), kolonneoverskriften i «{FASE2_FANE}» og i "
                "«Jury» – jurymedlemmer som hadde dette kriteriet beholder det (samme kolonne, nytt navn)."
            )
            if st.button(f"Oppdater til «{nytt}»", key=f"omdop_krit_{gammelt}"):
                try:
                    res = omdop_kriterium(sh, fagfelt, gammelt, nytt, ny_kort=ny_kort)
                except Exception as e:
                    vis_feil(f"Kunne ikke omdøpe «{gammelt}»", e)
                else:
                    mangler = [sted for sted, ok in res["endret"].items() if not ok]
                    if mangler:
                        st.warning(f"Oppdatert delvis – fant ikke kolonnen i: {', '.join(mangler)}.", icon=":material/warning:")
                    st.toast("Omdøpt", icon=":material/check_circle:")
                    st.rerun()

# «Universell utforming» ble tidligere foreslått under Kundeservice &
# Tilgjengelighet – foreslås nå i stedet under Førsteinntrykk (se
# FORESLATTE_TILLEGGSKRITERIER). Tilbyr å deaktivere et ev. aktivt
# duplikat under det GAMLE fagfeltet (sletter ikke), slik at det ikke står
# aktivt to steder samtidig.
_dup_uu = finn_duplisert_kriterium(alle_kriterier, "Universell utforming")
if _dup_uu:
    with st.container(border=True):
        st.warning(
            f"**«Universell utforming»** er aktivt under **{_dup_uu['fagfelt']}** fra tidligere – det foreslås nå "
            "i stedet under **Førsteinntrykk** (se «Foreslåtte kriterier» lenger ned). Deaktiver duplikatet her "
            "(sletter ikke) når det nye er lagt til, så det ikke står aktivt to steder.",
            icon=":material/warning:",
        )
        if st.button(f"Deaktiver «Universell utforming» under {_dup_uu['fagfelt']}", key="deaktiver_dup_universell_utforming"):
            try:
                deaktiver_kriterium(sh, "Universell utforming")
            except Exception as e:
                vis_feil("Kunne ikke deaktivere", e)
            else:
                st.toast("Deaktivert", icon=":material/check_circle:")
                st.rerun()

st.divider()
st.subheader("Manglende kolonner for kriterier", anchor=False)
st.caption(
    "Oppdager kriterier som finnes i «Kriterier»-fanen, men IKKE har fått en tilsvarende kolonne i «"
    f"{FASE2_FANE}» og/eller «{JURY_FANE}» ennå – typisk fordi «Sett også inn ny kolonne»-avkrysningen ikke ble "
    "brukt, eller (en reell feil som er rettet nå) fordi Jury-kolonnen manglet selv om «Sett inn kolonne» ble "
    "krysset av. Uten en kolonne i «{JURY_FANE}» blir IKKE kriteriet lagret når du krysser det av på et "
    "jurymedlem – avkrysningen forsvinner stille.".format(JURY_FANE=JURY_FANE)
)
try:
    _mangler_fase2 = manglende_kriterium_kolonner(sh, FASE2_FANE, alle_kriterier)
    _mangler_jury = manglende_kriterium_kolonner(sh, JURY_FANE, alle_kriterier, grunnkolonner=["Navn", "E-post", "Farge"])
except Exception as e:
    _mangler_fase2, _mangler_jury = [], []
    vis_feil("Kunne ikke sjekke manglende kolonner", e)

if not _mangler_fase2 and not _mangler_jury:
    st.success("Alle aktive Fase 3-kriterier har kolonne i både «{}» og «{}».".format(FASE2_FANE, JURY_FANE), icon=":material/check_circle:")
else:
    if _mangler_fase2:
        st.warning(f"Mangler kolonne i «{FASE2_FANE}»: " + ", ".join(f"«{k}» ({f})" for f, k in _mangler_fase2), icon=":material/warning:")
    if _mangler_jury:
        st.warning(f"Mangler kolonne i «{JURY_FANE}»: " + ", ".join(f"«{k}» ({f})" for f, k in _mangler_jury), icon=":material/warning:")
    if st.button("Legg til de manglende kolonnene nå", icon=":material/add_box:"):
        st.session_state["_vis_manglende_kolonner_dialog"] = True


@st.dialog("Legge til manglende kolonner?")
def manglende_kolonner_dialog(mangler_fase2, mangler_jury):
    st.write(f"Setter inn én kolonne per manglende kriterium i «{FASE2_FANE}» og/eller «{JURY_FANE}», med samme farge/stil/bredde/nedtrekksliste som nabokolonnen. Sikkerhetskopi tas først.")
    c1, c2 = st.columns(2)
    if c1.button("Avbryt", use_container_width=True, key="avbryt_manglende_kolonner"):
        st.rerun()
    if c2.button("Ja, legg til nå", type="primary", use_container_width=True, icon=":material/add_box:", key="bekreft_manglende_kolonner"):
        feilet = []
        lagt_til = 0
        hoppet_over = 0
        with st.spinner("Sikkerhetskopierer og legger til kolonner …"):
            backup_navn = sikkerhetskopier_alle_faner(sh)
            for fagfelt, kriterium in mangler_fase2:
                try:
                    if legg_til_kriterium_kolonne(sh, FASE2_FANE, fagfelt, kriterium):
                        lagt_til += 1
                    else:
                        hoppet_over += 1
                except Exception as e:
                    feilet.append(f"«{kriterium}» i «{FASE2_FANE}»: {e}")
            for fagfelt, kriterium in mangler_jury:
                try:
                    if legg_til_kriterium_kolonne(sh, JURY_FANE, fagfelt, kriterium):
                        lagt_til += 1
                    else:
                        hoppet_over += 1
                except Exception as e:
                    feilet.append(f"«{kriterium}» i «{JURY_FANE}»: {e}")
        st.session_state["_manglende_kolonner_resultat"] = {"backup": backup_navn, "feilet": feilet, "antall": lagt_til, "hoppet_over": hoppet_over}
        st.rerun()


if st.session_state.get("_vis_manglende_kolonner_dialog"):
    st.session_state["_vis_manglende_kolonner_dialog"] = False
    manglende_kolonner_dialog(_mangler_fase2, _mangler_jury)

if st.session_state.get("_manglende_kolonner_resultat"):
    r = st.session_state.pop("_manglende_kolonner_resultat")
    st.success(f"Ferdig! {r['antall']} kolonne(r) lagt til.", icon=":material/check_circle:")
    if r.get("hoppet_over"):
        st.caption(f"{r['hoppet_over']} hoppet over (fantes allerede – diagnosen var foreldet, ingen duplikat laget).")
    st.caption(f"Sikkerhetskopier: {', '.join(r['backup'])}")
    if r["feilet"]:
        with st.expander(f"{len(r['feilet'])} feilet"):
            for feil in r["feilet"]:
                st.markdown(f"- {feil}")

st.divider()
st.subheader("Feilsøking lagring", anchor=False)
st.caption(
    f"Slår opp nøyaktig det appen leser for ÉN butikk + ETT jurymedlem, i BÅDE den fargede fanen (det som "
    f"faktisk vises) og «{VURDERINGER_FANE}»-loggen – rå verdi (med type), normalisert verdi, og hva skjemaet "
    "faktisk ville vist. Leser alltid ferskt (hopper forbi mellomlagringen) – lastes derfor IKKE før du "
    "eksplisitt åpner den, for ikke å gjøre hver side-visning tyngre enn nødvendig."
)
if not st.session_state.get("_vis_feilsoking_lagring"):
    if st.button("Åpne feilsøking", icon=":material/bug_report:"):
        st.session_state["_vis_feilsoking_lagring"] = True
        st.rerun()
else:
    @st.fragment
    def vis_feilsoking_lagring():
        """Egen fragment: å bytte jurymedlem/butikk her kjører KUN denne
        seksjonen på nytt (inkl. de alltid-ferske feilsøkingskallene) – ikke
        resten av Innstillinger."""
        st.markdown(f"Tilkoblet regneark akkurat nå: **{sh.title}** (ID `{sh.id}`)")
        fdc1, fdc2 = st.columns(2)
        feilsok_jurymedlem = fdc1.selectbox("Jurymedlem", navn_liste_jury, key="_feilsok_jurymedlem") if navn_liste_jury else None
        feilsok_butikk = fdc2.selectbox("Butikk", sorted(butikker.keys()), key="_feilsok_butikk") if butikker else None

        if feilsok_jurymedlem and feilsok_butikk:
            mine_krit = sorted(mine_kriterier(jury, feilsok_jurymedlem))
            if not mine_krit:
                st.info(f"{feilsok_jurymedlem} har ingen kriterier tildelt.", icon=":material/info:")
            else:
                krit_til_fagfelt_fs = {k: felt for felt, kriterier in felt_dict.items() for k in kriterier}

                st.markdown(f"**Den fargede fanen («{FASE2_FANE}») – det som faktisk vises i appen**")
                rader_grid = feilsok_farget_fane(sh, feilsok_butikk, [(krit_til_fagfelt_fs.get(k, ""), k) for k in mine_krit])
                st.dataframe(
                    [
                        {
                            "Kriterium": r["kriterium"], "Celle": r["celle"],
                            "Rå verdi": r["rå_score"], "Type": r["rå_score_type"],
                            "Normalisert": r["normalisert_score"], "Notat": r["rå_notat"],
                            "Ville vist i skjema": (
                                "– (ikke besvart)" if r["normalisert_score"] is None
                                else ("Kan ikke vurdere" if r["normalisert_score"] == "Kan ikke vurdere" else f"{r['normalisert_score']} markert")
                            ),
                        }
                        for r in rader_grid
                    ],
                    hide_index=True, use_container_width=True,
                )

                st.markdown(f"**«{VURDERINGER_FANE}»-loggen – {feilsok_jurymedlem} sine egne rader**")
                rader_feilsok = feilsok_vurdering(sh, feilsok_butikk, feilsok_jurymedlem, mine_krit)
                st.dataframe(
                    [
                        {
                            "Kriterium": r["kriterium"], "Celle": r["celle"],
                            "Rå verdi": r["rå_score"], "Type": r["rå_score_type"],
                            "Normalisert": r["normalisert_score"], "Kommentar (rå)": r["rå_kommentar"],
                        }
                        for r in rader_feilsok
                    ],
                    hide_index=True, use_container_width=True,
                )
                st.caption("«Rå verdi»/«Type» er nøyaktig det `get_all_values()` returnerte fra Google Sheets, før noe i appen har tolket det.")

    vis_feilsoking_lagring()


def _sheets_feilboks(e, handling="lagre"):
    vis_feil(f"Kunne ikke {handling} til regnearket", e)


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
            # VIKTIG: et @st.dialog sin innmat er internt en FRAGMENT (bekreftet
            # i streamlit sin egen kildekode – elements/dialog_decorator.py).
            # Et VANLIG st.rerun() (scope="app", standard) bryter ut av fragmentet
            # og LUKKER dermed dialogen – det er slik man ER MENT å lukke den (se
            # "Ja, fjern" lenger ned, som bevisst bruker vanlig st.rerun() for å
            # både lukke OG oppdatere jurylisten utenfor dialogen). Men for å
            # bare gå videre til NESTE steg INNI samme dialog (vise bekreftelsen)
            # må man bruke st.rerun(scope="fragment") – ellers forsvinner
            # bekreftelsen stille (flagget ble satt, men ingenting tegnet det
            # på nytt før dialogen uansett lukkes/åpnes igjen). Dette var den
            # faktiske grunnen til at «Fjern jurymedlem» ikke syntes å gjøre noe.
            if st.button("Fjern jurymedlem", icon=":material/delete:", use_container_width=True):
                st.session_state["_bekreft_slett_jury"] = True
                st.rerun(scope="fragment")
        else:
            st.warning(f"Fjerne **{redigerer_navn}**? Vurderinger personen allerede har gjort i regnearket beholdes.", icon=":material/warning:")
            w1, w2 = st.columns(2)
            if w1.button("Avbryt", key="avbryt_slett_jury", use_container_width=True):
                st.session_state["_bekreft_slett_jury"] = False
                st.rerun(scope="fragment")
            if w2.button("Ja, fjern", type="primary", key="bekreft_slett_jury", use_container_width=True):
                try:
                    slett_jurymedlem(sh, redigerer_navn)
                    st.toast("Fjernet", icon=":material/check_circle:")
                    st.session_state["_jury_dialog_for"] = None
                    st.rerun()
                except Exception as e:
                    _sheets_feilboks(e, "fjerne")


@st.dialog("Kriterium")
def kriterium_dialog(redigerer_kriterium=None, forslag=None):
    """forslag: valgfritt ferdigutfylt forslag til et NYTT kriterium (fra
    jury.FORESLATTE_TILLEGGSKRITERIER) – navnefeltet forblir redigerbart
    (i motsetning til ved redigering av et eksisterende kriterium), slik at
    du kan justere før lagring."""
    feil_plassholder_krit = st.empty()
    eksisterende = (next((k for k in alle_kriterier if k["kriterium"] == redigerer_kriterium), {}) if redigerer_kriterium else None) or forslag or {}
    fagfelt_valg = list(felt_dict.keys()) or fagfelt_liste(alle_kriterier)
    if eksisterende.get("fagfelt") and eksisterende["fagfelt"] not in fagfelt_valg:
        fagfelt_valg = [eksisterende["fagfelt"]] + fagfelt_valg  # forslag kan ha et fagfelt ingen AKTIVE kriterier bruker ennå
    fagfelt_sel = st.selectbox("Fagfelt", fagfelt_valg, index=fagfelt_valg.index(eksisterende["fagfelt"]) if eksisterende.get("fagfelt") in fagfelt_valg else 0)
    navn_sel = st.text_input("Kriterium (navn)", value=eksisterende.get("kriterium", ""), disabled=bool(redigerer_kriterium))
    kort_sel = st.text_input("Kort beskrivelse", value=eksisterende.get("kort", ""))
    utfyllende_sel = st.text_area("Utfyllende forklaring", value=eksisterende.get("utfyllende", ""), height=80)
    s1, s3, s5 = st.columns(3)
    skala1_sel = s1.text_input("Hva gir 1", value=eksisterende.get("skala1", ""))
    skala3_sel = s3.text_input("Hva gir 3", value=eksisterende.get("skala3", ""))
    skala5_sel = s5.text_input("Hva gir 5", value=eksisterende.get("skala5", ""))
    eksempler_sel = st.text_input("Eksempler", value=eksisterende.get("eksempler", ""))
    faser_sel = st.multiselect("Brukes i fase(r)", ["Fase 2", "Fase 3", "Testkjøp"], default=eksisterende.get("faser", ["Fase 3"]))
    aktiv_sel = st.checkbox("Aktiv", value=eksisterende.get("aktiv", True)) if redigerer_kriterium else True
    sett_inn_kolonne = st.checkbox("Sett også inn ny kolonne i Rangering-fanene nå", value=bool(forslag), disabled=bool(redigerer_kriterium), help="Kun aktuelt for nye kriterier.")

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
                            # VIKTIG (reell bug funnet): uten denne fikk det nye
                            # kriteriet ALDRI en kolonne i Jury-fanen – jury_dialog
                            # sine avkrysningsbokser bygges fra Kriterier-fanen
                            # (viste seg derfor fint), men write_jury() skriver KUN
                            # til kolonner som FAKTISK finnes i selve Jury-fanen, så
                            # avkrysningen ble stille forkastet uten feilmelding.
                            legg_til_kriterium_kolonne(sh, JURY_FANE, fagfelt_sel, navn_sel.strip())
                st.toast("Lagret", icon=":material/check_circle:")
                st.rerun()
            except Exception as e:
                with feil_plassholder_krit:
                    _sheets_feilboks(e)


@st.fragment
def vis_jury_og_kriterier_tabs():
    """Egen fragment: klikk her (fanebytte, Rediger, Legg til) kjører KUN
    denne delen på nytt – ikke resten av Innstillinger (Ytelse-logg,
    fane-oversikt, veiledning/kriterienavn-sjekker osv.), se punkt 7 om
    ytelse. Dialogene (jury_dialog/kriterium_dialog) sine TERMINALE
    handlinger (Lagre/Ja, fjern) bruker fortsatt vanlig st.rerun() – det
    bryter ALLTID ut til en full siderefresh uansett fragment, siden en
    dialog sin innmat også er en fragment i Streamlit (se forklaringen ved
    _bekreft_slett_jury) – så resten av siden oppdateres fortsatt riktig
    når noe faktisk er lagret/slettet."""
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
        manglende_forslag = manglende_foreslatte_kriterier(alle_kriterier)
        if manglende_forslag:
            with st.container(border=True):
                st.markdown("**Foreslåtte kriterier som ikke er lagt til ennå**")
                st.caption("Tekst foreslått/godkjent tidligere, men aldri faktisk skrevet inn i dette regnearket – juster gjerne før du lagrer.")
                for f in manglende_forslag:
                    fkc1, fkc2 = st.columns([5, 1])
                    fkc1.markdown(f"**{f['kriterium']}** _({f['fagfelt']})_ — {f['kort']}")
                    if fkc2.button("Legg til", key=f"legg_til_forslag_{f['kriterium']}", use_container_width=True):
                        st.session_state["_vis_forslag_dialog"] = f["kriterium"]
            st.write("")

        if st.session_state.get("_vis_forslag_dialog"):
            _valgt_forslag = next((f for f in manglende_forslag if f["kriterium"] == st.session_state["_vis_forslag_dialog"]), None)
            st.session_state["_vis_forslag_dialog"] = None
            if _valgt_forslag:
                kriterium_dialog(forslag=_valgt_forslag)

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


vis_jury_og_kriterier_tabs()

st.divider()
st.subheader("Fasestatus", anchor=False)
try:
    faser = read_faser(sh)
except Exception as e:
    faser = []
    vis_feil("Kunne ikke lese fasestatus", e)
if faser:
    faser_sortert = sorted(faser, key=lambda f: int(f.get("Fase", 0)))
    gjeldende = aktiv_fase(faser)
    navn_liste_faser = [f"{f.get('Fase')}. {f.get('Navn')}" for f in faser_sortert]
    standard_indeks = faser_sortert.index(gjeldende) if gjeldende in faser_sortert else 0
    fc1, fc2 = st.columns([3, 1])
    valgt_fase_tekst = fc1.selectbox("Gjeldende fase", navn_liste_faser, index=standard_indeks)
    if fc2.button("Sett som gjeldende", use_container_width=True):
        valgt_nummer = int(valgt_fase_tekst.split(".")[0])
        try:
            sett_gjeldende_fase(sh, valgt_nummer)
        except Exception as e:
            vis_feil("Kunne ikke oppdatere fasestatus", e)
        else:
            st.toast("Fasestatus oppdatert.", icon=":material/check_circle:")
            st.rerun()
    st.caption("Tidligere faser settes automatisk til «Fullført», senere til «Kommende». Kan overstyres manuelt i fanen «Faser» i regnearket etterpå.")
else:
    st.caption("Fanen «Faser» finnes ikke ennå – opprettes automatisk neste gang Oversikt-siden åpnes.")

st.divider()
st.subheader("Finale", anchor=False)
try:
    _finale_last = er_finale_last(sh)
except Exception as e:
    _finale_last = False
    vis_feil("Kunne ikke lese finale-status", e)
if _finale_last:
    av, tid = finale_las_info(sh)
    st.info(f"Finalelista er låst av **{av}** ({tid}). Endringer i Sheets påvirker ikke lenger rangeringen.", icon=":material/lock:")
    if st.button("Lås opp finalelista", icon=":material/lock_open:"):
        try:
            fjern_finale_las(sh)
        except Exception as e:
            vis_feil("Kunne ikke låse opp finalelista", e)
        else:
            st.rerun()
else:
    st.caption("Finalelista er ikke låst – rangeringen på Finale-siden oppdateres live. Lås den fra Finale-siden når resultatet er klart.")

st.divider()
_commit_hash, _commit_tid = hent_versjonsinfo()
if _commit_hash:
    st.caption(f"Kjørende versjon: commit `{_commit_hash}` · {_commit_tid} (norsk tid)")
else:
    st.caption("Kjørende versjon: ukjent (fant ikke git-informasjon i denne kjøringen).")
