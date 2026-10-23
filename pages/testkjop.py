"""Side – Testkjøp. Jurymedlemmet gjennomfører et reelt kjøp hos tildelte
butikker og logger funn steg for steg (8 steg i en tidslinje + 3
tverrgående vurderinger). Hvert steg lagres for seg (ett skrivekall per
lagring, se sheets.write_testkjop_steg) – ikke én stor skjema-innsending."""

from datetime import datetime as _datetime

import streamlit as st

from components import kopier_knapp, topptekst, tom_tilstand, vis_feil
from data import naa_norsk
from jury import (
    beregn_dager_til_refusjon, beregn_leveringsavvik, beregn_svartid, beregn_testkjop_status, read_jury,
    read_testkjop_veiledning,
)
from sheets import (
    read_appinnstilling, read_stores, read_testkjop, read_testkjop_kundeservice, read_testkjop_tildeling,
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

_masterpresentasjon = read_appinnstilling(sh, "Lenke til masterpresentasjon")
if _masterpresentasjon:
    st.link_button("Åpne masterpresentasjonen", _masterpresentasjon, icon=":material/slideshow:")

st.divider()
st.subheader("Slik gjennomfører du et testkjøp", anchor=False)
try:
    veiledning = read_testkjop_veiledning(sh)
except Exception as e:
    veiledning = []
    vis_feil("Kunne ikke lese veiledningen", e)
if veiledning:
    for rad in veiledning:
        overskrift, tekst = rad.get("Overskrift", ""), rad.get("Tekst", "")
        if overskrift:
            st.markdown(f"**{overskrift}**  \n{tekst}")
else:
    tom_tilstand("📋", "Fant ingen veiledningstekst", "Sjekk fanen «Testkjøp-veiledning» i regnearket.")

st.divider()

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

TIDSLINJE_STEG = ["Før kjøp", "Kassen", "Kommunikasjon", "Levering", "Utpakking", "Kundeservice", "Retur", "Pengene tilbake"]

# ── Tidslinje: 8 klikkbare steg ──
steg_kolonner = st.columns(8)
for i, steg in enumerate(TIDSLINJE_STEG):
    ferdig = steg in alle_steg
    merke = "✓" if ferdig else str(i + 1)
    with steg_kolonner[i]:
        if st.button(merke, key=f"tidslinje_{steg}", help=steg, use_container_width=True, type="primary" if ferdig else "secondary"):
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
    "Før kjøp": [("Info om levering vist", "ja_nei", "Informasjon om levering vist før kassen? (et pluss hvis ja)")],
    "Kassen": [
        ("Antall leveringsalternativer", "number", "Antall leveringsalternativer"),
        ("Relevante alternativer", "ja_delvis_nei", "Relevante alternativer?"),
        ("ETA vist", "ja_nei", "ETA vist?"),
        ("Lovet leveringsdato", "date", "Lovet leveringsdato"),
        ("Betalingsmåter", "text", "Betalingsmåter"),
        ("Måtte opprette konto", "ja_nei", "Måtte opprette konto?"),
        ("Forhåndsavkrysset samtykke", "ja_nei", "Forhåndsavkryssede samtykker?"),
        ("Totalpris vist", "ja_nei", "Totalpris vist før betaling?"),
    ],
    "Kommunikasjon": [
        ("Ordrebekreftelse mottatt", "tidspunkt", "Ordrebekreftelse mottatt"),
        ("Info om retur", "ja_nei", "Info om retur?"),
        ("Mersalg", "ja_nei", "Mersalg?"),
        ("Råd og tips", "ja_nei", "Råd og tips?"),
    ],
    "Levering": [("Faktisk leveringsdato", "date", "Faktisk leveringsdato")],
    "Utpakking": [
        ("Emballasje", "text", "Emballasje (beskrivelse)"),
        ("Produkt som beskrevet", "ja_nei", "Produkt som beskrevet?"),
        ("Returinfo i pakken", "ja_nei", "Returinfo i pakken?"),
    ],
    "Retur": [
        ("Har returløsning", "returlosning", "Har returløsning?"),
        ("Avstand innlevering", "text", "Avstand til innleveringssted (km eller fritekst)"),
        ("Beskjed retur mottatt", "ja_nei", "Beskjed om at retur er mottatt?"),
        ("Beskjed retur tidspunkt", "tidspunkt", "Tidspunkt for beskjeden"),
    ],
    "Pengene tilbake": [
        ("Dato refusjon", "date", "Dato for refusjon"),
        ("Fikk beskjed refusjon", "ja_nei", "Fikk beskjed om refusjon?"),
    ],
}


def _render_generisk_steg(steg):
    eksisterende = alle_steg.get(steg, {})
    key_prefix = f"tk_{apnet_butikk}_{jurynavn}_{steg}".replace(" ", "_")

    if steg == "Levering":
        lovet = alle_steg.get("Kassen", {}).get("Lovet leveringsdato", "")
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

    tidspunkt = _tidspunkt_widgets(f"{key_prefix}_tidspunkt", eksisterende.get("Tidspunkt", ""))
    score = _score_widget(f"{key_prefix}_score", eksisterende.get("Score", ""))

    felter = {}
    for feltnavn, typ, label in STEG_FELT_SPEC.get(steg, []):
        felter[feltnavn] = _render_felt(feltnavn, typ, label, key_prefix, eksisterende.get(feltnavn, ""))
        if feltnavn == "Har returløsning" and felter[feltnavn] == "Nei, kunden må ordne selv":
            st.error("🚩 Rødt flagg: butikken har ingen returløsning – kunden må ordne returen selv.", icon=":material/flag:")

    kommentar = st.text_area("Kommentar", value=eksisterende.get("Kommentar", ""), key=f"{key_prefix}_kommentar")

    if st.button("Lagre steg", type="primary", icon=":material/save:", key=f"{key_prefix}_lagre"):
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


@st.dialog("Legg til kundeservice-kanal")
def _legg_til_kanal_dialog():
    kanal = st.selectbox("Kanal", KANAL_VALG)
    sporsmal = st.text_input("Spørsmål stilt")
    sendt = _tidspunkt_widgets("ny_kanal_sendt", label="Tidspunkt sendt")
    mottatt = _tidspunkt_widgets("ny_kanal_mottatt", label="Tidspunkt svar mottatt")
    kvalitet = st.selectbox("Kvalitet", ["1", "2", "3", "4", "5"], index=2)
    c1, c2 = st.columns(2)
    if c1.button("Avbryt", use_container_width=True):
        st.rerun()
    if c2.button("Lagre", type="primary", use_container_width=True, icon=":material/save:"):
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
            st.markdown(f"**{k.get('Kanal', '')}** – {k.get('Spørsmål stilt', '')}")
            st.caption(f"Sendt {k.get('Tidspunkt sendt', '–')} · Svar {k.get('Tidspunkt svar mottatt', '–')}" + (f" · Svartid {svartid}" if svartid else "") + f" · Kvalitet {k.get('Kvalitet', '–')}")
    if st.button("Legg til kanal", icon=":material/add_circle:"):
        _legg_til_kanal_dialog()

    st.divider()
    eksisterende = alle_steg.get("Kundeservice", {})
    key_prefix = f"tk_{apnet_butikk}_{jurynavn}_Kundeservice".replace(" ", "_")
    tidspunkt = _tidspunkt_widgets(f"{key_prefix}_tidspunkt", eksisterende.get("Tidspunkt", ""))
    score = _score_widget(f"{key_prefix}_score", eksisterende.get("Score", ""))
    kommentar = st.text_area("Kommentar (samlet vurdering av kundeservice)", value=eksisterende.get("Kommentar", ""), key=f"{key_prefix}_kommentar")
    if st.button("Lagre steg", type="primary", icon=":material/save:", key=f"{key_prefix}_lagre"):
        try:
            write_testkjop_steg(sh, apnet_butikk, jurynavn, "Kundeservice", {"Tidspunkt": tidspunkt, "Score": score, "Kommentar": kommentar})
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

# ── Tverrgående: eget lite skjema per butikk ──
st.subheader("Tverrgående vurdering", anchor=False)
TVERRGAENDE_STEG = ["Mobilopplevelse", "Compliance", "Universell utforming"]
tverrgaende_verdier = {}
tv_kolonner = st.columns(3)
for i, steg in enumerate(TVERRGAENDE_STEG):
    eksisterende = alle_steg.get(steg, {})
    key_prefix = f"tk_{apnet_butikk}_{jurynavn}_{steg}".replace(" ", "_")
    with tv_kolonner[i]:
        st.markdown(f"**{steg}**")
        score = _score_widget(f"{key_prefix}_score", eksisterende.get("Score", ""))
        kommentar = st.text_area("Kommentar", value=eksisterende.get("Kommentar", ""), key=f"{key_prefix}_kommentar", height=100)
        tverrgaende_verdier[steg] = (score, kommentar)

if st.button("Lagre tverrgående vurdering", icon=":material/save:"):
    try:
        for steg, (score, kommentar) in tverrgaende_verdier.items():
            write_testkjop_steg(sh, apnet_butikk, jurynavn, steg, {"Tidspunkt": naa_norsk().strftime("%Y-%m-%d %H:%M"), "Score": score, "Kommentar": kommentar})
    except Exception as e:
        vis_feil("Kunne ikke lagre tverrgående vurdering", e)
    else:
        st.toast("Lagret", icon=":material/check_circle:")
        st.rerun()

st.divider()

# ─────────────────────────────────────────────
# Oppsummering
# ─────────────────────────────────────────────
st.subheader("Oppsummering", anchor=False)


def _bygg_oppsummering_tekst():
    linjer = [f"TESTKJØP – {apnet_butikk} ({jurynavn})", f"Status: {status}", ""]
    linjer.append("Tidslinje:")
    for steg in TIDSLINJE_STEG:
        d = alle_steg.get(steg)
        if d:
            linjer.append(f"  ✓ {steg} – {d.get('Tidspunkt', '')} – Score: {d.get('Score', '–')}")
        else:
            linjer.append(f"  ○ {steg} – ikke utført")
    linjer.append("")

    lovet = alle_steg.get("Kassen", {}).get("Lovet leveringsdato", "")
    faktisk = alle_steg.get("Levering", {}).get("Faktisk leveringsdato", "")
    avvik = beregn_leveringsavvik(lovet, faktisk) if lovet and faktisk else None
    if avvik:
        linjer.append(f"Leveringsavvik: {avvik}")

    kanaler = kundeservice_data.get((apnet_butikk, jurynavn), [])
    for k in kanaler:
        svartid = beregn_svartid(k.get("Tidspunkt sendt", ""), k.get("Tidspunkt svar mottatt", ""))
        if svartid:
            linjer.append(f"Svartid ({k.get('Kanal', '')}): {svartid}")

    retur_tidspunkt = alle_steg.get("Retur", {}).get("Tidspunkt", "")
    dato_refusjon = alle_steg.get("Pengene tilbake", {}).get("Dato refusjon", "")
    dager = beregn_dager_til_refusjon(retur_tidspunkt, dato_refusjon) if retur_tidspunkt and dato_refusjon else None
    if dager is not None:
        linjer.append(f"Dager til refusjon: {dager}")

    scorer = [float(d["Score"]) for d in alle_steg.values() if d.get("Score", "").replace(".", "", 1).isdigit()]
    if scorer:
        linjer.append(f"Snitt score (alle steg): {sum(scorer) / len(scorer):.1f}")

    if alle_steg.get("Retur", {}).get("Har returløsning") == "Nei, kunden må ordne selv":
        linjer.append("🚩 RØDT FLAGG: Ingen returløsning – kunden må ordne returen selv.")

    linjer.append("")
    linjer.append("Kommentarer:")
    for steg in TIDSLINJE_STEG + TVERRGAENDE_STEG:
        d = alle_steg.get(steg)
        if d and d.get("Kommentar"):
            linjer.append(f"  {steg}: {d['Kommentar']}")

    return "\n".join(linjer)


oppsummering_tekst = _bygg_oppsummering_tekst()
st.text(oppsummering_tekst)
kopier_knapp(oppsummering_tekst)
