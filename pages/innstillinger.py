"""Side 5 – Innstillinger: Google Sheets-tilkobling, jury/kriterier,
veiledningstekst og fasestatus. Ryddet ned til kun disse fire seksjonene
(se avtale) – ingenting annet skal vises her. Koden for tidsmåling
(sheets.mal_handling / hent_handling_logg / hent_api_kall_logg) ligger
fortsatt i sheets.py og brukes fortsatt internt (Lagre/sidebytte), men
vises ikke lenger noe sted i grensesnittet."""

import streamlit as st

from components import status_prikk, topptekst, vis_feil
from jury import (
    aktiv_fase, aktive_kriterier, kriterier_per_fagfelt, oppdater_veiledning_rad, read_criteria, read_faser,
    read_jury, read_veiledning, sett_gjeldende_fase, slett_jurymedlem, write_jury,
)
from sheets import fane_oversikt, read_fase1_scores, read_generelle_kommentarer, read_ratings, read_stores, read_vurderinger
from theme import FAGFELT_FARGE

topptekst("Innstillinger")
st.info("**Kun for administrator** – jurymedlemmer trenger ikke bruke denne siden.", icon=":material/admin_panel_settings:")

sh = st.session_state.get("_sh")
if not sh:
    st.error("Google Sheets-tilkoblingen mangler.", icon=":material/cloud_off:")
    with st.expander("Feilmelding"):
        st.code(st.session_state.get("_gsheets_feil", "Ukjent feil"))
    st.stop()

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


@st.fragment
def vis_jury_liste():
    """Egen fragment: Rediger/Legg til kjører KUN denne seksjonen på nytt."""
    manglende = [k for k, antall in antall_jury_per_kriterium.items() if antall == 0]
    if manglende:
        st.warning(f"{len(manglende)} kriterier mangler jurymedlem.", icon=":material/warning:")
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


st.subheader("Jury og kriterier", anchor=False)
vis_jury_liste()

st.divider()
st.subheader("Veiledningstekst («Hvordan bedømme»)", anchor=False)
try:
    _veiledning_rader = read_veiledning(sh)
except Exception as e:
    _veiledning_rader = []
    vis_feil("Kunne ikke lese veiledningen", e)

_veiledning_tekster = {}
for _rad in _veiledning_rader:
    _overskrift = _rad.get("Overskrift", "")
    if not _overskrift:
        continue
    _veiledning_tekster[_overskrift] = st.text_area(_overskrift, value=_rad.get("Tekst", ""), key=f"veiledning_{_overskrift}")

if st.button("Lagre", icon=":material/save:", key="lagre_veiledning"):
    try:
        for _overskrift, _ny_tekst in _veiledning_tekster.items():
            oppdater_veiledning_rad(sh, _overskrift, _ny_tekst)
    except Exception as e:
        vis_feil("Kunne ikke lagre veiledningen", e)
    else:
        st.toast("Lagret", icon=":material/check_circle:")
        st.rerun()

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
st.subheader("Google Sheets", anchor=False)
status_prikk(True)

FORVENTET_SHEET_ID = "18fvqNKEh7dFfA9S63uxkBOpigR8vzD31wrAq49yqOIQ"

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
bc1, bc2 = st.columns(2)
bc1.link_button("Åpne regnearket", sh.url, icon=":material/open_in_new:", use_container_width=True)
if bc2.button(
    "Hent siste fra regnearket", icon=":material/refresh:", use_container_width=True,
    help="Tømmer ALL mellomlagring – nyttig rett etter du har redigert noe manuelt i Sheets.",
):
    read_stores.clear()
    read_ratings.clear()
    read_fase1_scores.clear()
    read_criteria.clear()
    read_jury.clear()
    read_faser.clear()
    read_vurderinger.clear()
    read_generelle_kommentarer.clear()
    read_veiledning.clear()
    fane_oversikt.clear()
    st.toast("Hentet siste versjon fra regnearket.", icon=":material/check_circle:")
    st.rerun()
