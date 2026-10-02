"""All lesing/skriving mot Google Sheets. Regnearket er fasiten (kan redigeres
manuelt når som helst) – appen leser med kort cache og skriver kun de konkrete
cellene som faktisk endres (upsert via stabil ID), aldri hele faner.

Fanestruktur (se README.md for full beskrivelse):
- Butikker     – ID, Butikk, Klasse, Bransje, URL, Fase1_snitt
- Jury         – Navn, Fagfelt                              (redigeres manuelt)
- Tildeling    – Jurymedlem, ButikkID                        (redigeres manuelt, valgfri)
- Rådata       – ButikkID, Butikk, Jurymedlem, Fagfelt, Kriterium, Score, Kommentar, SistEndret, EndretAv
- Innstillinger_app – Nøkkel, Verdi                          (bl.a. finale-lås)
- Finale_snapshot   – låst finale-rangering, skrives kun ved eksplisitt låsing
"""

import re
from datetime import datetime

import gspread
import streamlit as st
from google.oauth2.service_account import Credentials

# ─────────────────────────────────────────────
# Tilkobling
# ─────────────────────────────────────────────
@st.cache_resource(ttl=3600, show_spinner=False)
def _gc_klient():
    try:
        creds_info = st.secrets["gcp_service_account"]
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_info, scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.session_state["_gsheets_feil"] = str(e)
        return None


@st.cache_resource(ttl=3600, show_spinner=False)
def koble_sheets():
    gc = _gc_klient()
    if not gc:
        return None
    try:
        return gc.open_by_key(st.secrets["google_sheets"]["sheet_id"])
    except Exception as e:
        st.session_state["_gsheets_feil"] = str(e)
        return None

BUTIKKER_HEADER = ["ID", "Butikk", "Klasse", "Bransje", "URL", "Fase1_snitt"]
JURY_HEADER = ["Navn", "Fagfelt"]
TILDELING_HEADER = ["Jurymedlem", "ButikkID"]
RÅDATA_HEADER = ["ButikkID", "Butikk", "Jurymedlem", "Fagfelt", "Kriterium", "Score", "Kommentar", "SistEndret", "EndretAv"]
INNSTILLINGER_HEADER = ["Nøkkel", "Verdi"]
FINALE_SNAPSHOT_HEADER = ["Klasse", "Plass", "ButikkID", "Butikk", "Snittscore", "AntallVurderinger", "LåstAv", "LåstTid"]

NAVY = {"red": 0.125, "green": 0.219, "blue": 0.392}  # #203864 – hovedoverskrift
BLÅ = {"red": 0.267, "green": 0.447, "blue": 0.769}  # #4472C4 – underoverskrift
HVIT = {"red": 1, "green": 1, "blue": 1}


def _slugify(tekst: str) -> str:
    """Lager en stabil, lesbar ID fra butikknavnet. Genereres KUN når en ny
    butikk opprettes – selve ID-verdien som havner i arket er det appen alltid
    slår opp rader på, aldri radnummer eller navnet på nytt."""
    t = tekst.lower()
    for a, b in {"æ": "ae", "ø": "o", "å": "a"}.items():
        t = t.replace(a, b)
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t or "butikk"


def _unike_ider(navn_liste):
    brukt = {}
    resultat = {}
    for navn in navn_liste:
        base = _slugify(navn)
        n = brukt.get(base, 0)
        ny_id = base if n == 0 else f"{base}-{n + 1}"
        brukt[base] = n + 1
        resultat[navn] = ny_id
    return resultat


def hent_eller_lag_fane(sh, navn, header):
    try:
        return sh.worksheet(navn)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=navn, rows=1000, cols=max(len(header), 4))
        ws.append_row(header)
        return ws


def _formater_header(ws, antall_kolonner, farge=NAVY):
    try:
        siste_kolonne = gspread.utils.rowcol_to_a1(1, antall_kolonner).rstrip("1")
        ws.format(f"A1:{siste_kolonne}1", {
            "backgroundColor": farge,
            "textFormat": {"bold": True, "foregroundColor": HVIT},
            "horizontalAlignment": "CENTER",
        })
        ws.freeze(rows=1)
    except Exception:
        pass  # formatering er kosmetikk – skal aldri stoppe appen


def _sett_kolonnebredder(ws, bredder: dict):
    """bredder: {kolonneindeks (0-basert): pikselbredde}. gspread har ingen
    column_width-metode, så dette går via et rått batch_update-kall."""
    try:
        forespørsler = [{
            "updateDimensionProperties": {
                "range": {"sheetId": ws.id, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
                "properties": {"pixelSize": px},
                "fields": "pixelSize",
            }
        } for i, px in bredder.items()]
        ws.spreadsheet.batch_update({"requests": forespørsler})
    except Exception:
        pass  # kosmetikk – skal aldri stoppe appen


# ─────────────────────────────────────────────
# Butikker
# ─────────────────────────────────────────────
@st.cache_data(ttl=60, show_spinner=False)
def read_stores(_sh):
    """Returnerer (butikker, advarsler). butikker: {id: {navn, klasse, bransje,
    url, fase1_snitt}}. advarsler: liste med tekst om rader appen ikke forsto."""
    ws = hent_eller_lag_fane(_sh, "Butikker", BUTIKKER_HEADER)
    rader = ws.get_all_records()
    butikker, advarsler = {}, []
    gyldige_klasser = {"Liten", "Medium", "Stor"}
    for i, r in enumerate(rader, start=2):
        butikk_id = str(r.get("ID", "")).strip()
        navn = str(r.get("Butikk", "")).strip()
        if not navn:
            continue
        if not butikk_id:
            advarsler.append(f"Rad {i} i 'Butikker': «{navn}» mangler ID og hoppes over – legg til en ID-verdi for at den skal tas med.")
            continue
        klasse = str(r.get("Klasse", "")).strip()
        if klasse and klasse not in gyldige_klasser:
            advarsler.append(f"Rad {i} i 'Butikker': «{navn}» har ukjent størrelsesklasse «{klasse}» (ventet Liten/Medium/Stor).")
        fase1_snitt = None
        try:
            if str(r.get("Fase1_snitt", "")).strip():
                fase1_snitt = float(r["Fase1_snitt"])
        except (ValueError, TypeError):
            advarsler.append(f"Rad {i} i 'Butikker': «{navn}» har en Fase1_snitt-verdi som ikke er et tall.")
        butikker[butikk_id] = {
            "navn": navn,
            "klasse": klasse,
            "bransje": str(r.get("Bransje", "")).strip(),
            "url": str(r.get("URL", "")).strip(),
            "fase1_snitt": fase1_snitt,
        }
    return butikker, advarsler


def _skriv_butikker(sh, butikker: dict):
    ws = hent_eller_lag_fane(sh, "Butikker", BUTIKKER_HEADER)
    ws.clear()
    rader = [BUTIKKER_HEADER]
    for butikk_id, info in butikker.items():
        rader.append([
            butikk_id, info.get("navn", ""), info.get("klasse", ""),
            info.get("bransje", ""), info.get("url", ""),
            info.get("fase1_snitt", "") if info.get("fase1_snitt") is not None else "",
        ])
    ws.update(rader)
    _sett_kolonnebredder(ws, {0: 90, 1: 180, 3: 180, 4: 220})
    _formater_header(ws, len(BUTIKKER_HEADER))
    read_stores.clear()
    return ws


# ─────────────────────────────────────────────
# Jury – navn + fagfelt, redigeres manuelt
# ─────────────────────────────────────────────
@st.cache_data(ttl=60, show_spinner=False)
def read_jury(_sh):
    ws = hent_eller_lag_fane(_sh, "Jury", JURY_HEADER)
    rader = ws.get_all_records()
    return {str(r["Navn"]).strip(): str(r.get("Fagfelt", "")).strip() for r in rader if str(r.get("Navn", "")).strip()}


def legg_til_jurymedlem(sh, navn: str, fagfelt: str):
    """Legger til ett nytt jurymedlem nederst i Jury-fanen – skriver aldri om
    resten av fanen, så manuelle endringer andre har gjort der bevares."""
    ws = hent_eller_lag_fane(sh, "Jury", JURY_HEADER)
    ws.append_row([navn, fagfelt])
    read_jury.clear()


def _seed_jury_hvis_tom(sh, forslag: dict):
    ws = hent_eller_lag_fane(sh, "Jury", JURY_HEADER)
    if len(ws.get_all_values()) <= 1:
        ws.append_rows([[navn, fagfelt] for navn, fagfelt in forslag.items()])
        _formater_header(ws, len(JURY_HEADER), farge=BLÅ)
        read_jury.clear()


# ─────────────────────────────────────────────
# Tildeling – hvilke butikker hvert jurymedlem skal vurdere (valgfri fane)
# ─────────────────────────────────────────────
@st.cache_data(ttl=60, show_spinner=False)
def read_assignments(_sh):
    """Returnerer {jurymedlem: set(butikk_id)}. Et jurymedlem som ikke finnes i
    denne fanen i det hele tatt får ALLE butikkene (sikkerhetsnett), jf. brief."""
    ws = hent_eller_lag_fane(_sh, "Tildeling", TILDELING_HEADER)
    rader = ws.get_all_records()
    tildeling = {}
    for r in rader:
        navn = str(r.get("Jurymedlem", "")).strip()
        butikk_id = str(r.get("ButikkID", "")).strip()
        if navn and butikk_id:
            tildeling.setdefault(navn, set()).add(butikk_id)
    return tildeling


def butikker_for_jurymedlem(tildeling: dict, jurymedlem: str, alle_ider: list):
    if jurymedlem in tildeling:
        return [i for i in alle_ider if i in tildeling[jurymedlem]]
    return list(alle_ider)  # ingen tildeling registrert => alle butikker


# ─────────────────────────────────────────────
# Rådata – én rad per (butikk, jurymedlem, kriterium)
# ─────────────────────────────────────────────
@st.cache_data(ttl=20, show_spinner=False)
def read_ratings(_sh):
    """Rå verdier (ikke get_all_records) – vi trenger radnummer for upsert, og
    vil ikke krasje på rader med avvikende kolonnetall."""
    ws = hent_eller_lag_fane(_sh, "Rådata", RÅDATA_HEADER)
    return ws.get_all_values()


def upsert_rating(sh, butikk_id, butikk_navn, jurymedlem, fagfelt, vurderinger):
    """vurderinger: liste av (kriterium, score, kommentar). score er enten 1-5
    eller strengen "N/A". Oppdaterer KUN radene for akkurat denne butikken +
    dette jurymedlemmet – aldri hele arket."""
    ws = hent_eller_lag_fane(sh, "Rådata", RÅDATA_HEADER)
    rå = ws.get_all_values()
    rader = rå[1:] if rå else []
    nokkel_til_rad = {}
    for i, rad in enumerate(rader, start=2):
        if len(rad) >= 5:
            nokkel_til_rad[(rad[0], rad[2], rad[4])] = i  # ButikkID, Jurymedlem, Kriterium

    tidsstempel = datetime.now().strftime("%Y-%m-%d %H:%M")
    oppdateringer, nye_rader = [], []
    for kriterium, score, kommentar in vurderinger:
        nokkel = (butikk_id, jurymedlem, kriterium)
        rad_data = [butikk_id, butikk_navn, jurymedlem, fagfelt, kriterium, str(score), kommentar, tidsstempel, jurymedlem]
        if nokkel in nokkel_til_rad:
            radnr = nokkel_til_rad[nokkel]
            oppdateringer.append({"range": f"A{radnr}:I{radnr}", "values": [rad_data]})
        else:
            nye_rader.append(rad_data)

    if oppdateringer:
        ws.batch_update(oppdateringer)
    if nye_rader:
        ws.append_rows(nye_rader)
    read_ratings.clear()


# ─────────────────────────────────────────────
# Innstillinger (nøkkel/verdi) + finale-lås
# ─────────────────────────────────────────────
@st.cache_data(ttl=10, show_spinner=False)
def _les_innstillinger(_sh):
    ws = hent_eller_lag_fane(_sh, "Innstillinger_app", INNSTILLINGER_HEADER)
    return {r["Nøkkel"]: r["Verdi"] for r in ws.get_all_records()}


def er_finale_last(sh):
    return _les_innstillinger(sh).get("finale_last") == "true"


def finale_las_info(sh):
    data = _les_innstillinger(sh)
    return data.get("finale_last_av"), data.get("finale_last_tid")


def _sett_innstilling(sh, nokkel, verdi):
    ws = hent_eller_lag_fane(sh, "Innstillinger_app", INNSTILLINGER_HEADER)
    rader = ws.get_all_values()
    for i, rad in enumerate(rader[1:], start=2):
        if rad and rad[0] == nokkel:
            ws.update(f"A{i}:B{i}", [[nokkel, verdi]])
            _les_innstillinger.clear()
            return
    ws.append_row([nokkel, verdi])
    _les_innstillinger.clear()


def las_finale(sh, rader, jurymedlem):
    """rader: liste av dicts med klasse/plass/butikk_id/butikk/snitt/antall."""
    ws = hent_eller_lag_fane(sh, "Finale_snapshot", FINALE_SNAPSHOT_HEADER)
    ws.clear()
    tidsstempel = datetime.now().strftime("%Y-%m-%d %H:%M")
    utdata = [FINALE_SNAPSHOT_HEADER]
    for r in rader:
        utdata.append([r["klasse"], r["plass"], r["butikk_id"], r["butikk"], f'{r["snitt"]:.2f}', r["antall"], jurymedlem, tidsstempel])
    ws.update(utdata)
    _sett_innstilling(sh, "finale_last", "true")
    _sett_innstilling(sh, "finale_last_av", jurymedlem)
    _sett_innstilling(sh, "finale_last_tid", tidsstempel)


def fjern_finale_las(sh):
    _sett_innstilling(sh, "finale_last", "false")


@st.cache_data(ttl=10, show_spinner=False)
def hent_finale_snapshot(_sh):
    ws = hent_eller_lag_fane(_sh, "Finale_snapshot", FINALE_SNAPSHOT_HEADER)
    return ws.get_all_records()


# ─────────────────────────────────────────────
# Oppsett av hele regnearket fra en opplastet Excel-fil
# ─────────────────────────────────────────────
def setup_from_excel(sh, butikker_fra_excel: dict, jury_forslag: dict):
    """Bygger/oppdaterer fanestrukturen fra en opplastet Fase 1-Excel.
    - Sikkerhetskopierer eksisterende 'Butikker'-fane før den skrives om.
    - 'Jury' sås KUN hvis fanen er tom fra før – overskrives aldri, slik at
      manuelle endringer i jurylisten bevares mellom opplastinger.
    - Eksisterende butikker beholder sin ID (matchet på navn); kun nye butikker
      får ny, generert ID – gamle vurderinger i Rådata mister ikke koblingen.
    Returnerer en kort oppsummeringstekst."""
    eksisterende, _ = read_stores(sh)
    navn_til_id = {info["navn"]: bid for bid, info in eksisterende.items()}

    if eksisterende:
        tidsstempel = datetime.now().strftime("%Y%m%d-%H%M%S")
        try:
            gammel_ws = sh.worksheet("Butikker")
            sh.duplicate_sheet(gammel_ws.id, new_sheet_name=f"Butikker_backup_{tidsstempel}")
        except Exception:
            pass  # sikkerhetskopi er en bonus, skal ikke blokkere selve oppsettet

    nye_navn = [navn for navn in butikker_fra_excel if navn not in navn_til_id]
    nye_ider = _unike_ider(nye_navn)

    butikker = {}
    for navn, info in butikker_fra_excel.items():
        butikk_id = navn_til_id.get(navn) or nye_ider[navn]
        butikker[butikk_id] = {
            "navn": navn,
            "klasse": info.get("klasse", ""),
            "bransje": info.get("bransje", ""),
            "url": info.get("url", ""),
            "fase1_snitt": info.get("fase1_snitt"),
        }

    _skriv_butikker(sh, butikker)
    _seed_jury_hvis_tom(sh, jury_forslag)
    hent_eller_lag_fane(sh, "Tildeling", TILDELING_HEADER)
    hent_eller_lag_fane(sh, "Rådata", RÅDATA_HEADER)
    hent_eller_lag_fane(sh, "Innstillinger_app", INNSTILLINGER_HEADER)

    return f"{len(butikker)} butikker satt opp ({len(nye_navn)} nye, {len(eksisterende)} beholdt fra før)."
