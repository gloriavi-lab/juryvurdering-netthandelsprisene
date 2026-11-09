"""Side – Testkjøp. Jurymedlemmet gjennomfører et reelt kjøp hos tildelte
butikker og logger funn steg for steg (5 steg i en tidslinje + én generell
kommentar om butikken). Hvert steg lagres for seg (ett skrivekall per
lagring, se sheets.write_testkjop_steg) – ikke én stor skjema-innsending.

«Kjøp og levering» er bevisst et slått-sammen steg (tidligere Kassen+
Levering+Utpakking) – se jury.beregn_testkjop_status for hvordan status
utledes fra feltene INNENFOR det. Retur og Pengene tilbake er fortsatt to
separate steg.

Alt lagres per (butikk, jurymedlem), så to jurymedlemmer kan testkjøpe hos
samme butikk uten å overskrive hverandre – de får hver sin egen tidslinje."""

from datetime import datetime as _datetime
from html import escape as _escape

import streamlit as st

from components import kopier_knapp, topptekst, tom_tilstand, vis_feil
from data import naa_norsk
from jury import beregn_dager_til_refusjon, beregn_leveringsavvik, beregn_svartid, beregn_testkjop_status, read_jury
from pptx_eksport import bygg_testkjop_slide
from sheets import (
    read_stores, read_testkjop, read_testkjop_kundeservice, read_testkjop_tildeling, slett_testkjop_kundeservice_kanal,
    write_testkjop_kundeservice_kanal, write_testkjop_steg,
)

topptekst("Testkjøp")

sh = st.session_state.get("_sh")
if not sh:
    st.warning("Google Sheets-tilkoblingen mangler – gå til **Innstillinger**.", icon=":material/cloud_off:")
    st.stop()

try:
    jury = read_jury(sh)
    butikker, _ = read_stores(sh)
    tildeling = read_testkjop_tildeling(sh)
    testkjop_data = read_testkjop(sh)
    kundeservice_data = read_testkjop_kundeservice(sh)
except Exception as e:
    vis_feil("Kunne ikke lese testkjøp-data", e)
    st.stop()

navn_liste_jury = sorted(jury.keys())
if not navn_liste_jury:
    st.info("Ingen jurymedlemmer er lagt til ennå – gjør det under **Innstillinger → Jury og kriterier**.", icon=":material/info:")
    st.stop()

jurynavn = st.selectbox("Ditt navn (jurymedlem)", navn_liste_jury, key="_tk_jurynavn")
mine_butikker = sorted(tildeling.get(jurynavn, set()))

if not mine_butikker:
    tom_tilstand("🛍️", "Ingen testkjøp-butikker tildelt deg ennå", "Ta kontakt med juryleder for å bli tildelt butikker under Innstillinger.")
    st.stop()

STATUS_FARGE_TK = {
    "Ikke startet": "#8A8780", "Bestilt": "#4472C4", "Venter på levering": "#C8A200", "Levert": "#5B9BD5",
    "Retur sendt": "#ED7D31", "Venter på refusjon": "#C8A200", "Ferdig": "#1E8E5A",
}


def _status_badge(status):
    farge = STATUS_FARGE_TK.get(status, "#888")
    st.markdown(
        f'<span class="status-merkelapp" style="background:color-mix(in srgb, {farge} 12%, transparent);color:{farge};">{status}</span>',
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────
# Listevisning
# ─────────────────────────────────────────────
if not st.session_state.get("_tk_apnet_butikk"):
    st.subheader("Dine testkjøp-butikker", anchor=False)
    for butikk in mine_butikker:
        steg_for_butikk = testkjop_data.get((butikk, jurynavn), {})
        status = beregn_testkjop_status(steg_for_butikk)
        with st.container(border=True):
            rc1, rc2, rc3 = st.columns([3, 2, 1])
            with rc1:
                st.markdown(f"**{butikk}**")
                st.caption(butikker.get(butikk, {}).get("bransje", ""))
            with rc2:
                _status_badge(status)
            with rc3:
                if st.button("Åpne →", key=f"apne_tk_{butikk}", use_container_width=True):
                    st.session_state["_tk_apnet_butikk"] = butikk
                    st.rerun()
    st.stop()


# ─────────────────────────────────────────────
# Detaljvisning for én butikk
# ─────────────────────────────────────────────
apnet_butikk = st.session_state["_tk_apnet_butikk"]
if st.button("← Alle mine testkjøp-butikker"):
    st.session_state["_tk_apnet_butikk"] = None
    st.session_state["_tk_apent_steg"] = None
    st.rerun()

alle_steg = testkjop_data.get((apnet_butikk, jurynavn), {})
status = beregn_testkjop_status(alle_steg)

dc1, dc2 = st.columns([4, 1])
with dc1:
    st.markdown(f"## {apnet_butikk}")
with dc2:
    _status_badge(status)

st.write("")

# ── Generell kommentar til nettbutikken (ikke knyttet til ett spesifikt steg) ──
_generell_eksisterende = alle_steg.get("Generell kommentar", {}).get("Kommentar", "")
generell_kommentar = st.text_area(
    "Generell kommentar til nettbutikken",
    value=_generell_eksisterende,
    placeholder="F.eks. generelt inntrykk, produktside, søk, osv.",
    key=f"tk_{apnet_butikk}_{jurynavn}_generell_kommentar",
)
if st.button("Lagre kommentar", icon=":material/save:", key=f"tk_{apnet_butikk}_{jurynavn}_generell_kommentar_lagre"):
    try:
        write_testkjop_steg(sh, apnet_butikk, jurynavn, "Generell kommentar", {"Kommentar": generell_kommentar})
    except Exception as e:
        vis_feil("Kunne ikke lagre kommentaren", e)
    else:
        st.toast("Lagret", icon=":material/check_circle:")
        st.rerun()

st.divider()

TIDSLINJE_STEG = ["Kjøp og levering", "Kommunikasjon", "Kundeservice", "Retur", "Pengene tilbake"]

# ── Tidslinje: klikkbare steg, radvis (ny kolonnerad per 4 – holder rekkefølgen riktig når kolonnene stables på mobil) ──
for rad_start in range(0, len(TIDSLINJE_STEG), 4):
    steg_kolonner = st.columns(4)
    for j, steg in enumerate(TIDSLINJE_STEG[rad_start:rad_start + 4]):
        i = rad_start + j
        ferdig = steg in alle_steg
        merke = f"✓ {steg}" if ferdig else f"{i + 1}. {steg}"
        with steg_kolonner[j]:
            if st.button(merke, key=f"tidslinje_{steg}", use_container_width=True, type="primary" if ferdig else "secondary"):
                st.session_state["_tk_apent_steg"] = steg
                st.rerun()
_apent_steg = st.session_state.get("_tk_apent_steg")
if _apent_steg:
    st.caption(f"Åpent steg: **{_apent_steg}**")

st.divider()

SCORE_VALG = ["1", "2", "3", "4", "5", "Ikke aktuelt"]


def _score_widget(key, eksisterende=""):
    idx = SCORE_VALG.index(eksisterende) if eksisterende in SCORE_VALG else 0
    return st.selectbox("Score", SCORE_VALG, index=idx, key=key)


def _tidspunkt_widgets(key_prefix, eksisterende="", label="Tidspunkt"):
    naa = naa_norsk()
    try:
        eksisterende_dt = _datetime.strptime(eksisterende, "%Y-%m-%d %H:%M") if eksisterende else naa
    except ValueError:
        eksisterende_dt = naa
    st.caption(label)
    c1, c2 = st.columns(2)
    dato = c1.date_input("Dato", value=eksisterende_dt.date(), key=f"{key_prefix}_dato", label_visibility="collapsed")
    klokkeslett = c2.time_input("Klokkeslett", value=eksisterende_dt.time(), key=f"{key_prefix}_tid", label_visibility="collapsed")
    return f"{dato.isoformat()} {klokkeslett.strftime('%H:%M')}"


def _render_felt(feltnavn, typ, label, key_prefix, eksisterende):
    key = f"{key_prefix}_{feltnavn}".replace(" ", "_")
    if typ == "ja_nei":
        valg = ["", "Ja", "Nei"]
        idx = valg.index(eksisterende) if eksisterende in valg else 0
        return st.selectbox(label, valg, index=idx, key=key, format_func=lambda v: v or "– Velg –")
    if typ == "ja_delvis_nei":
        valg = ["", "Ja", "Delvis", "Nei"]
        idx = valg.index(eksisterende) if eksisterende in valg else 0
        return st.selectbox(label, valg, index=idx, key=key, format_func=lambda v: v or "– Velg –")
    if typ == "returlosning":
        valg = ["", "Ja", "Nei, kunden må ordne selv"]
        idx = valg.index(eksisterende) if eksisterende in valg else 0
        return st.selectbox(label, valg, index=idx, key=key, format_func=lambda v: v or "– Velg –")
    if typ == "number":
        try:
            default = int(eksisterende) if eksisterende else 0
        except ValueError:
            default = 0
        return str(st.number_input(label, min_value=0, value=default, step=1, key=key))
    if typ == "text":
        return st.text_input(label, value=eksisterende, key=key)
    if typ == "date":
        try:
            default_dato = _datetime.strptime(eksisterende, "%Y-%m-%d").date() if eksisterende else naa_norsk().date()
        except ValueError:
            default_dato = naa_norsk().date()
        return st.date_input(label, value=default_dato, key=key).isoformat()
    if typ == "tidspunkt":
        return _tidspunkt_widgets(key, eksisterende, label=label)
    return ""


STEG_FELT_SPEC = {
    "Kjøp og levering": [
        ("ETA vist", "ja_nei", "ETA vist?"),
        ("Lovet leveringsdato", "date", "Lovet leveringsdato"),
        ("Måtte opprette konto", "ja_nei", "Måtte opprette konto?"),
        ("Totalpris vist", "ja_nei", "Totalpris vist før betaling?"),
        ("Faktisk leveringsdato", "date", "Faktisk leveringsdato"),
        ("Emballasje", "text", "Emballasje (beskrivelse)"),
        ("Produkt som beskrevet", "ja_nei", "Produkt som beskrevet?"),
        ("Returinfo i pakken", "ja_nei", "Returinfo i pakken?"),
    ],
    "Kommunikasjon": [
        ("Ordrebekreftelse mottatt", "tidspunkt", "Ordrebekreftelse mottatt"),
        ("Info om retur", "ja_nei", "Info om retur?"),
        ("Mersalg", "ja_nei", "Mersalg?"),
        ("Råd og tips", "ja_nei", "Råd og tips?"),
    ],
    "Retur": [
        ("Har returløsning", "returlosning", "Har returløsning?"),
        ("Avstand innlevering", "text", "Avstand til innleveringssted (km eller fritekst)"),
        ("Beskjed retur mottatt", "ja_nei", "Beskjed om at retur er mottatt?"),
        ("Beskjed retur tidspunkt", "tidspunkt", "Tidspunkt for beskjeden om at retur er mottatt"),
    ],
    "Pengene tilbake": [
        ("Dato refusjon", "date", "Dato for refusjon"),
        ("Fikk beskjed refusjon", "ja_nei", "Fikk beskjed om refusjon?"),
    ],
}


def _render_generisk_steg(steg):
    eksisterende = alle_steg.get(steg, {})
    key_prefix = f"tk_{apnet_butikk}_{jurynavn}_{steg}".replace(" ", "_")

    if steg == "Kjøp og levering":
        lovet = eksisterende.get("Lovet leveringsdato", "")
        faktisk_na = eksisterende.get("Faktisk leveringsdato", "")
        if lovet and faktisk_na:
            avvik = beregn_leveringsavvik(lovet, faktisk_na)
            if avvik:
                st.info(avvik, icon=":material/local_shipping:")
    if steg == "Pengene tilbake":
        retur_tidspunkt = alle_steg.get("Retur", {}).get("Tidspunkt", "")
        dato_refusjon_na = eksisterende.get("Dato refusjon", "")
        if retur_tidspunkt and dato_refusjon_na:
            dager = beregn_dager_til_refusjon(retur_tidspunkt, dato_refusjon_na)
            if dager is not None:
                st.info(f"{dager} dag{'er' if dager != 1 else ''} fra innlevering til refusjon.", icon=":material/payments:")

    # «Kommunikasjon» og «Pengene tilbake» har ikke eget tidspunkt –
    # «Ordrebekreftelse mottatt» / «Dato for refusjon» er det som er
    # relevant der. «Retur» sitt tidspunkt har en egen, tydeligere etikett
    # siden det lett forveksles med det separate «Tidspunkt for beskjeden»-
    # feltet lenger ned (de to måler ulike ting - se STEG_FELT_SPEC).
    TIDSPUNKT_LABEL = {"Retur": "Tidspunkt returen ble sendt (brukes til å beregne dager til refusjon)"}
    viser_tidspunkt = steg not in ("Kommunikasjon", "Pengene tilbake")
    tidspunkt = (
        _tidspunkt_widgets(f"{key_prefix}_tidspunkt", eksisterende.get("Tidspunkt", ""), label=TIDSPUNKT_LABEL.get(steg, "Tidspunkt"))
        if viser_tidspunkt else ""
    )
    score = _score_widget(f"{key_prefix}_score", eksisterende.get("Score", ""))

    felter = {}
    for feltnavn, typ, label in STEG_FELT_SPEC.get(steg, []):
        felter[feltnavn] = _render_felt(feltnavn, typ, label, key_prefix, eksisterende.get(feltnavn, ""))
        if feltnavn == "Har returløsning" and felter[feltnavn] == "Nei, kunden må ordne selv":
            st.error("🚩 Rødt flagg: butikken har ingen returløsning – kunden må ordne returen selv.", icon=":material/flag:")

    kommentar = st.text_area("Kommentar", value=eksisterende.get("Kommentar", ""), key=f"{key_prefix}_kommentar")

    if st.button("Lagre steg", type="primary", icon=":material/save:", key=f"{key_prefix}_lagre"):
        if viser_tidspunkt:
            felter["Tidspunkt"] = tidspunkt
        felter["Score"] = score
        felter["Kommentar"] = kommentar
        try:
            write_testkjop_steg(sh, apnet_butikk, jurynavn, steg, felter)
        except Exception as e:
            vis_feil("Kunne ikke lagre steget", e)
        else:
            st.toast("Lagret", icon=":material/check_circle:")
            st.rerun()


KANAL_VALG = ["Chat", "E-post", "Telefon", "Sosiale medier", "Annet"]


@st.dialog("Kundeservice-kanal")
def _kanal_dialog(eksisterende_kanal=None):
    """eksisterende_kanal=None → legg til ny kanal. Satt → rediger/slett en
    allerede lagret kanal (kanaltypen er da fast, siden write_testkjop_
    kundeservice_kanal oppdaterer basert på kanalnavnet – å endre det ville
    opprettet en ny rad i stedet for å redigere den eksisterende)."""
    data = {}
    if eksisterende_kanal:
        data = next(
            (k for k in kundeservice_data.get((apnet_butikk, jurynavn), []) if k.get("Kanal") == eksisterende_kanal), {},
        )
        st.caption(f"Kanal: **{eksisterende_kanal}**")
        kanal = eksisterende_kanal
    else:
        kanal = st.selectbox("Kanal", KANAL_VALG)
    key_suffix = eksisterende_kanal or "ny"
    sporsmal = st.text_input("Spørsmål stilt", value=data.get("Spørsmål stilt", ""))
    sendt = _tidspunkt_widgets(f"kanal_{key_suffix}_sendt", data.get("Tidspunkt sendt", ""), label="Tidspunkt sendt")
    mottatt = _tidspunkt_widgets(f"kanal_{key_suffix}_mottatt", data.get("Tidspunkt svar mottatt", ""), label="Tidspunkt svar mottatt")
    kvalitet_valg = ["1", "2", "3", "4", "5"]
    kvalitet_idx = kvalitet_valg.index(data["Kvalitet"]) if data.get("Kvalitet") in kvalitet_valg else 2
    kvalitet = st.selectbox("Kvalitet", kvalitet_valg, index=kvalitet_idx)

    knapper = st.columns(3) if eksisterende_kanal else st.columns(2)
    if knapper[0].button("Avbryt", use_container_width=True):
        st.rerun()
    if eksisterende_kanal and knapper[1].button("Slett", use_container_width=True, icon=":material/delete:"):
        try:
            slett_testkjop_kundeservice_kanal(sh, apnet_butikk, jurynavn, eksisterende_kanal)
        except Exception as e:
            vis_feil("Kunne ikke slette kanalen", e)
        else:
            st.toast("Slettet", icon=":material/check_circle:")
            st.rerun()
    if knapper[-1].button("Lagre", type="primary", use_container_width=True, icon=":material/save:"):
        try:
            write_testkjop_kundeservice_kanal(
                sh, apnet_butikk, jurynavn, kanal,
                {"Spørsmål stilt": sporsmal, "Tidspunkt sendt": sendt, "Tidspunkt svar mottatt": mottatt, "Kvalitet": kvalitet},
            )
        except Exception as e:
            vis_feil("Kunne ikke lagre kanalen", e)
        else:
            st.toast("Lagret", icon=":material/check_circle:")
            st.rerun()


def _render_kundeservice_steg():
    kanaler = kundeservice_data.get((apnet_butikk, jurynavn), [])
    st.caption("Formål: kjøpshjelp (råd, anbefalinger, f.eks. julegavetips). Minst to kanaler.")
    if len(kanaler) < 2:
        st.warning(f"{len(kanaler)} av minst 2 kanaler registrert så langt.", icon=":material/warning:")
    for k in kanaler:
        svartid = beregn_svartid(k.get("Tidspunkt sendt", ""), k.get("Tidspunkt svar mottatt", ""))
        with st.container(border=True):
            kc1, kc2 = st.columns([5, 1])
            with kc1:
                st.markdown(f"**{k.get('Kanal', '')}** – {k.get('Spørsmål stilt', '')}")
                st.caption(f"Sendt {k.get('Tidspunkt sendt', '–')} · Svar {k.get('Tidspunkt svar mottatt', '–')}" + (f" · Svartid {svartid}" if svartid else "") + f" · Kvalitet {k.get('Kvalitet', '–')}")
            with kc2:
                if st.button("Rediger", key=f"rediger_kanal_{k.get('Kanal', '')}", use_container_width=True):
                    _kanal_dialog(eksisterende_kanal=k.get("Kanal", ""))
    if st.button("Legg til kanal", icon=":material/add_circle:"):
        _kanal_dialog()

    st.divider()
    eksisterende = alle_steg.get("Kundeservice", {})
    key_prefix = f"tk_{apnet_butikk}_{jurynavn}_Kundeservice".replace(" ", "_")
    # Ikke eget tidspunkt her – tiden fylles inn per kanal over (sendt/mottatt).
    score = _score_widget(f"{key_prefix}_score", eksisterende.get("Score", ""))
    kommentar = st.text_area("Kommentar (samlet vurdering av kundeservice)", value=eksisterende.get("Kommentar", ""), key=f"{key_prefix}_kommentar")
    if st.button("Lagre steg", type="primary", icon=":material/save:", key=f"{key_prefix}_lagre"):
        try:
            write_testkjop_steg(sh, apnet_butikk, jurynavn, "Kundeservice", {"Score": score, "Kommentar": kommentar})
        except Exception as e:
            vis_feil("Kunne ikke lagre steget", e)
        else:
            st.toast("Lagret", icon=":material/check_circle:")
            st.rerun()


if _apent_steg:
    with st.container(border=True):
        st.markdown(f"### {_apent_steg}")
        if _apent_steg == "Kundeservice":
            _render_kundeservice_steg()
        else:
            _render_generisk_steg(_apent_steg)

st.divider()

# ─────────────────────────────────────────────
# Oppsummering
# ─────────────────────────────────────────────
st.subheader("Oppsummering", anchor=False)


def _beregn_nokkeltall():
    """(liste av (etikett, verdi)-par, rødt_flagg) – delt mellom
    tekstoppsummeringen og PowerPoint-eksporten, så beregningen kun skjer
    ett sted."""
    linjer = []
    kjop = alle_steg.get("Kjøp og levering", {})
    avvik = beregn_leveringsavvik(kjop.get("Lovet leveringsdato", ""), kjop.get("Faktisk leveringsdato", ""))
    if avvik:
        linjer.append(("Leveringsavvik", avvik))

    kanaler = kundeservice_data.get((apnet_butikk, jurynavn), [])
    for k in kanaler:
        svartid = beregn_svartid(k.get("Tidspunkt sendt", ""), k.get("Tidspunkt svar mottatt", ""))
        if svartid:
            linjer.append((f"Svartid ({k.get('Kanal', '')})", svartid))

    retur = alle_steg.get("Retur", {})
    pengene = alle_steg.get("Pengene tilbake", {})
    dager = beregn_dager_til_refusjon(retur.get("Tidspunkt", ""), pengene.get("Dato refusjon", ""))
    if dager is not None:
        linjer.append(("Dager til refusjon", f"{dager} dag{'er' if dager != 1 else ''}"))

    # Kun steg som fortsatt finnes – gamle rader fra fjernede steg skal ikke
    # dra snittet i noen retning.
    scorer = [
        float(d["Score"]) for steg in TIDSLINJE_STEG
        if (d := alle_steg.get(steg)) and d.get("Score", "").replace(".", "", 1).isdigit()
    ]
    if scorer:
        linjer.append(("Snitt score (alle steg)", f"{sum(scorer) / len(scorer):.1f}"))

    rodt_flagg = retur.get("Har returløsning") == "Nei, kunden må ordne selv"
    return linjer, rodt_flagg


def _bygg_oppsummering_tekst(nokkeltall, rodt_flagg):
    linjer = [f"TESTKJØP – {apnet_butikk} ({jurynavn})", f"Status: {status}", ""]

    generell = alle_steg.get("Generell kommentar", {}).get("Kommentar", "")
    if generell:
        linjer.append(f"Generelt inntrykk: {generell}")
        linjer.append("")

    linjer.append("Tidslinje:")
    for steg in TIDSLINJE_STEG:
        d = alle_steg.get(steg)
        if d:
            nar = f" – {d['Tidspunkt']}" if d.get("Tidspunkt") else ""
            linjer.append(f"  ✓ {steg}{nar} – Score: {d.get('Score', '–')}")
        else:
            linjer.append(f"  ○ {steg} – ikke utført")
    linjer.append("")

    for etikett, verdi in nokkeltall:
        linjer.append(f"{etikett}: {verdi}")

    if rodt_flagg:
        linjer.append("🚩 RØDT FLAGG: Ingen returløsning – kunden må ordne returen selv.")

    linjer.append("")
    linjer.append("Kommentarer:")
    for steg in TIDSLINJE_STEG:
        d = alle_steg.get(steg)
        if d and d.get("Kommentar"):
            linjer.append(f"  {steg}: {d['Kommentar']}")

    return "\n".join(linjer)


def _render_oppsummering_kort(nokkeltall, rodt_flagg):
    """Samme informasjon som _bygg_oppsummering_tekst (brukt til kopiering
    og PowerPoint-eksport), men vist strukturert i appen i stedet for en
    rå monospace-tekstblokk. Fritekst fra brukeren escapes siden dette
    rendres med unsafe_allow_html=True."""
    farge = STATUS_FARGE_TK.get(status, "#888")
    deler = [
        '<div class="tk-oppsummering">',
        '<div class="tk-opp-header">',
        f'<div class="tk-opp-butikk">{_escape(apnet_butikk)}</div>',
        f'<span class="status-merkelapp" style="background:color-mix(in srgb, {farge} 12%, transparent);color:{farge};">{_escape(status)}</span>',
        "</div>",
    ]

    generell = alle_steg.get("Generell kommentar", {}).get("Kommentar", "")
    if generell:
        deler.append(f'<div class="tk-opp-sitat">«{_escape(generell)}»</div>')

    # Tidslinjen som en koblet stepper: hvert steg er en sirkel (✓ hvis
    # utført, ellers stegnummer) forbundet med en loddrett linje ned til
    # neste steg, slik det ser ut i en vanlig leveringssporing.
    deler.append('<div class="tk-opp-seksjon-tittel">Tidslinje</div><div class="tk-opp-tidslinje">')
    siste_indeks = len(TIDSLINJE_STEG) - 1
    for i, steg in enumerate(TIDSLINJE_STEG):
        d = alle_steg.get(steg)
        ferdig = bool(d)
        dot_klasse = " ferdig" if ferdig else ""
        dot_innhold = "✓" if ferdig else str(i + 1)
        linje_html = f'<div class="tk-opp-linje{" ferdig" if ferdig else ""}"></div>' if i < siste_indeks else ""
        score_html = (
            f'<div class="tk-opp-steg-score">Score {_escape(str(d.get("Score") or "–"))}</div>' if ferdig
            else '<div class="tk-opp-steg-score tk-dempet">Ikke utført</div>'
        )
        innhold_stil = ' style="padding-bottom:0"' if i == siste_indeks else ""
        deler.append(
            f'<div class="tk-opp-steg">'
            f'<div class="tk-opp-dot-col"><div class="tk-opp-dot{dot_klasse}">{dot_innhold}</div>{linje_html}</div>'
            f'<div class="tk-opp-steg-innhold"{innhold_stil}>'
            f'<div class="tk-opp-steg-navn{" tk-dempet" if not ferdig else ""}">{_escape(steg)}</div>{score_html}</div>'
            f"</div>"
        )
    deler.append("</div>")

    if nokkeltall:
        deler.append('<div class="tk-opp-seksjon-tittel">Nøkkeltall</div><div class="tk-opp-nokkeltall">')
        for etikett, verdi in nokkeltall:
            deler.append(
                f'<div class="tk-opp-stat"><div class="tk-opp-stat-label">{_escape(etikett)}</div>'
                f'<div class="tk-opp-stat-verdi">{_escape(str(verdi))}</div></div>'
            )
        deler.append("</div>")

    if rodt_flagg:
        deler.append('<div class="tk-opp-flagg">🚩 Ingen returløsning – kunden må ordne returen selv.</div>')

    kommentarer = [(s, alle_steg[s]["Kommentar"]) for s in TIDSLINJE_STEG if alle_steg.get(s, {}).get("Kommentar")]
    if kommentarer:
        deler.append('<div class="tk-opp-seksjon-tittel">Kommentarer</div><div class="tk-opp-kommentarer">')
        for steg, tekst in kommentarer:
            deler.append(f'<div class="tk-opp-kommentar"><b>{_escape(steg)}:</b> {_escape(tekst)}</div>')
        deler.append("</div>")

    deler.append("</div>")
    st.markdown("".join(deler), unsafe_allow_html=True)


_nokkeltall, _rodt_flagg = _beregn_nokkeltall()
oppsummering_tekst = _bygg_oppsummering_tekst(_nokkeltall, _rodt_flagg)
_render_oppsummering_kort(_nokkeltall, _rodt_flagg)
st.write("")
kc1, kc2 = st.columns(2)
with kc1:
    kopier_knapp(oppsummering_tekst)
with kc2:
    try:
        pptx_bytes = bygg_testkjop_slide(
            apnet_butikk, jurynavn, status, alle_steg, TIDSLINJE_STEG, _nokkeltall, _rodt_flagg,
            generell_kommentar=alle_steg.get("Generell kommentar", {}).get("Kommentar", ""),
        )
        st.download_button(
            "Last ned som PowerPoint", data=pptx_bytes, file_name=f"testkjop_{apnet_butikk}.pptx",
            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            icon=":material/slideshow:",
        )
    except Exception as e:
        vis_feil("Kunne ikke lage PowerPoint-slide", e)
