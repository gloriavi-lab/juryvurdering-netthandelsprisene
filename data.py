"""All forretningslogikk: Google Sheets, Excel-import, lagring og poengberegning.

Selve lagrings-/beregningslogikken er UENDRET fra tidligere versjon av appen –
kun flyttet hit fra app.py, og utvidet med deling av butikklisten via Google
Sheets (se `hent_butikkliste`/`lagre_butikkliste` nederst). Det løser et reelt
problem: lokale filer på Streamlit Cloud nullstilles ved hver ny utrulling, så
en butikkliste lastet opp rett før vi pusher ny kode forsvinner "sporløst" –
det er ikke en bug i appen, men hvordan Streamlit Cloud sitt filsystem virker.
Nå er Google Sheets alltid primærkilden; den lokale JSON-fila er kun en rask
snarvei innad i én økt.
"""

import re
from collections import defaultdict
from datetime import datetime

import gspread
import openpyxl
import streamlit as st
from google.oauth2.service_account import Credentials

# ─────────────────────────────────────────────
# Kriterier – IDENTISK ordlyd som i Fase 1-arket (5 kategorier, 16 kriterier)
# ─────────────────────────────────────────────
KRITERIER = [
    ("Førsteinntrykk", "Opplevelse: Bildebruk, beskrivelser o.l."),
    ("Førsteinntrykk", "Navigasjon / UX"),
    ("Førsteinntrykk", "Søk: auto-korrektur, synonymer, utlisting, forslag"),
    ("Kundeservice & Tilgjengelighet", "Lett tilgjengelig info om levering, retur og kjøpsvilkår"),
    ("Kundeservice & Tilgjengelighet", "Google/Trustpilot/andre åpne løsninger for kundetilfredshet"),
    ("Kundeservice & Tilgjengelighet", "Tilgjengelighet, åpningstider, kanaler, responstid"),
    ("Kundeservice & Tilgjengelighet", "Bærekraft"),
    ("Kjøp/inspirasjon/personalisering", "Kassen: Levering, betaling"),
    ("Kjøp/inspirasjon/personalisering", "Inspirasjon"),
    ("Kjøp/inspirasjon/personalisering", "Mersalg/anbefalinger/personalisering"),
    ("Markedsføring/kundedialog", "Bruk av SoMe"),
    ("Markedsføring/kundedialog", "Betalt og organisk synlighet"),
    ("Markedsføring/kundedialog", "E-post"),
    ("Innovasjon", "Innovative løsninger"),
    ("Innovasjon", "Adopsjon av nye teknologier for styrke konkurransekraft"),
    ("Innovasjon", "Kommersielt håndverk"),
]
FAGFELT = list(dict.fromkeys(kat for kat, _ in KRITERIER))
KRITERIER_PER_FAGFELT = {kat: [krit for k, krit in KRITERIER if k == kat] for kat in FAGFELT}

KLASSE_DEFINISJON = [
    ("Liten", "Under 50 mill kr"),
    ("Medium", "50–250 mill kr"),
    ("Stor", "Over 250 mill kr"),
]
KLASSER = [k for k, _ in KLASSE_DEFINISJON]

# Forslag til fagfelt per jurymedlem (brukes kun til å forhåndsvelge i dropdown –
# jurymedlemmet kan alltid overstyre selv). Matcher på om navnet DE skriver inn
# inneholder nøkkelordet (små bokstaver).
JURY_FAGFELT_FORSLAG = {
    "ole johan": "Førsteinntrykk",
    "stian": "Kundeservice & Tilgjengelighet",
    "torkel": "Kjøp/inspirasjon/personalisering",
    "marte": "Kjøp/inspirasjon/personalisering",
    "vikki": "Markedsføring/kundedialog",
    "nicholas": "Markedsføring/kundedialog",
    "guro": "Innovasjon",
}

VURDERINGER_HEADER = ["Butikk", "Jurymedlem", "Fagfelt", "Kriterium", "Score", "Kommentar", "Sist oppdatert"]
BUTIKKLISTE_HEADER = ["Butikk", "Klasse", "Bransje", "URL", "Filnavn"]
BUTIKKLISTE_FIL = "butikkliste.json"


# ─────────────────────────────────────────────
# Lokal snarvei (kun innad i én økt/container – Google Sheets er primærkilden)
# ─────────────────────────────────────────────
def lagre_lokalt(data):
    import json
    with open(BUTIKKLISTE_FIL, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def last_lokalt():
    import json, os
    if not os.path.exists(BUTIKKLISTE_FIL):
        return None
    try:
        with open(BUTIKKLISTE_FIL, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


# ─────────────────────────────────────────────
# Google Sheets – eget, lite regneark
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


def hent_vurderinger_ark(sh):
    """Henter "Vurderinger"-fanen, oppretter den KUN hvis den ikke finnes fra før –
    aldri gjenoppbygger en fane som allerede eksisterer (det var det som gjorde at
    manuelle Sheets-endringer forsvant i den gamle hovedappen)."""
    try:
        return sh.worksheet("Vurderinger")
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title="Vurderinger", rows=1000, cols=len(VURDERINGER_HEADER))
        ws.append_row(VURDERINGER_HEADER)
        return ws


@st.cache_data(ttl=15, show_spinner=False)
def hent_vurderinger(_sh):
    """Leser rå verdier direkte fra arket (kort mellomlagring på 15 sek, kun for å
    unngå å sprenge API-kvoten ved rask klikking – manuelle Sheets-endringer dukker
    uansett opp i appen i løpet av maks 15 sekunder)."""
    ws = hent_vurderinger_ark(_sh)
    return ws.get_all_values()


def lagre_vurderinger_batch(sh, butikk, jurymedlem, fagfelt, vurderinger):
    """vurderinger: liste av (kriterium, score, kommentar).
    Skriver KUN radene som gjelder akkurat denne butikken + dette jurymedlemmet –
    ALDRI hele arket – slik at manuelle endringer andre gjør direkte i Google Sheets
    ikke blir overskrevet av appen."""
    ws = hent_vurderinger_ark(sh)
    rå = ws.get_all_values()
    rader = rå[1:] if rå else []
    nokkel_til_rad = {}
    for i, rad in enumerate(rader, start=2):
        if len(rad) >= 4:
            nokkel_til_rad[(rad[0], rad[1], rad[3])] = i

    tidsstempel = datetime.now().strftime("%Y-%m-%d %H:%M")
    oppdateringer = []
    nye_rader = []
    for kriterium, score, kommentar in vurderinger:
        nokkel = (butikk, jurymedlem, kriterium)
        rad_data = [butikk, jurymedlem, fagfelt, kriterium, str(score), kommentar, tidsstempel]
        if nokkel in nokkel_til_rad:
            radnr = nokkel_til_rad[nokkel]
            oppdateringer.append({"range": f"A{radnr}:G{radnr}", "values": [rad_data]})
        else:
            nye_rader.append(rad_data)

    if oppdateringer:
        ws.batch_update(oppdateringer)
    if nye_rader:
        ws.append_rows(nye_rader)
    hent_vurderinger.clear()


# ─────────────────────────────────────────────
# Butikkliste – delt via Google Sheets (overlever redeploy, lik for alle)
# ─────────────────────────────────────────────
def hent_butikkliste_ark(sh):
    try:
        return sh.worksheet("Butikkliste")
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title="Butikkliste", rows=500, cols=len(BUTIKKLISTE_HEADER))
        ws.append_row(BUTIKKLISTE_HEADER)
        return ws


@st.cache_data(ttl=10, show_spinner=False)
def hent_butikkliste(_sh):
    """Henter butikklisten fra det delte arket – samme liste for alle jurymedlemmer,
    og den overlever at appen redeployes (i motsetning til en lokal fil)."""
    ws = hent_butikkliste_ark(_sh)
    rader = ws.get_all_records()
    if not rader:
        return None, None
    butikker = {
        str(r["Butikk"]).strip(): {
            "klasse": str(r.get("Klasse", "")).strip(),
            "bransje": str(r.get("Bransje", "")).strip(),
            "url": str(r.get("URL", "")).strip(),
        }
        for r in rader if str(r.get("Butikk", "")).strip()
    }
    filnavn = str(rader[0].get("Filnavn", "")).strip() if rader else ""
    return (butikker or None), (filnavn or None)


def lagre_butikkliste(sh, butikkliste: dict, filnavn: str):
    """Skriver butikklisten til sitt eget, lille ark. Dette skjer KUN når noen
    aktivt laster opp en ny liste – en bevisst, eksplisitt handling fra brukeren,
    ikke noe appen gjør i bakgrunnen – så det bryter ikke prinsippet om å aldri
    overskrive data uten at noen ber om det (det prinsippet gjelder selve
    VURDERINGENE, som flere jobber i samtidig)."""
    ws = hent_butikkliste_ark(sh)
    ws.clear()
    rader = [BUTIKKLISTE_HEADER]
    for navn, info in butikkliste.items():
        rader.append([navn, info.get("klasse", ""), info.get("bransje", ""), info.get("url", ""), filnavn])
    ws.update(rader)
    hent_butikkliste.clear()


def prosesser_opplastet_fil(fil, sh):
    """Leser og lagrer en opplastet Fase 1-fil. Vernet mot at samme fil prosesseres
    på nytt ved hver rerun (file_uploader beholder valgt fil i session_state helt
    til brukeren bevisst bytter den ut)."""
    fil_id = f"{fil.name}_{fil.size}"
    if st.session_state.get("_sist_prosesserte_fil") == fil_id:
        return False
    ny_liste = les_fase1_liste(fil)
    if not ny_liste:
        return False
    st.session_state.butikkliste = ny_liste
    st.session_state.butikkliste_filnavn = fil.name
    st.session_state["_sist_prosesserte_fil"] = fil_id
    lagre_lokalt({"butikker": ny_liste, "filnavn": fil.name})
    if sh:
        try:
            lagre_butikkliste(sh, ny_liste, fil.name)
        except Exception as e:
            st.warning(f"Listen er lastet inn i appen, men kunne ikke lagres delt til Google Sheets ennå: {e}", icon=":material/warning:")
    return True


# ─────────────────────────────────────────────
# Import av Fase 1-Excel-fila → butikkliste for denne fasen
# ─────────────────────────────────────────────
def les_fase1_liste(opplastet_fil):
    """Leser butikkliste fra Fase 1-arket. Forventer en rad med "Butikk" i kolonne A
    (samme header-rad som Fase 1-malen "Netthandelsprisene_Fase 1.xlsx"), og kolonner
    "Klasse", "Bransje", "URL" et sted i samme rad (rekkefølge spiller ingen rolle).
    URL-kolonnen kan enten være ren tekst eller en =HYPERLINK(...)-formel."""
    try:
        wb = openpyxl.load_workbook(opplastet_fil, data_only=False)
    except Exception as e:
        st.error(f"Kunne ikke lese Excel-filen: {e}", icon=":material/error:")
        return None

    ws = wb.worksheets[0]
    header_rad = None
    for r in range(1, min(ws.max_row, 10) + 1):
        if str(ws.cell(row=r, column=1).value or "").strip().lower() == "butikk":
            header_rad = r
            break
    if header_rad is None:
        st.error('Fant ikke en rad med "Butikk" i kolonne A i fila.', icon=":material/error:")
        return None

    kolonner = {}
    for c in range(1, ws.max_column + 1):
        v = ws.cell(row=header_rad, column=c).value
        if v:
            kolonner[str(v).strip().lower()] = c

    kol_butikk = kolonner.get("butikk")
    kol_klasse = kolonner.get("klasse")
    kol_bransje = kolonner.get("bransje")
    kol_url = kolonner.get("url")

    butikker = {}
    for r in range(header_rad + 1, ws.max_row + 1):
        navn_celle = ws.cell(row=r, column=kol_butikk).value
        if not navn_celle or not str(navn_celle).strip():
            continue
        navn = str(navn_celle).strip()

        url = ""
        if kol_url:
            url_verdi = ws.cell(row=r, column=kol_url).value
            if url_verdi:
                treff = re.search(r'HYPERLINK\("([^"]+)"', str(url_verdi))
                url = treff.group(1) if treff else str(url_verdi).strip()

        butikker[navn] = {
            "klasse": str(ws.cell(row=r, column=kol_klasse).value or "").strip() if kol_klasse else "",
            "bransje": str(ws.cell(row=r, column=kol_bransje).value or "").strip() if kol_bransje else "",
            "url": url,
        }
    if not butikker:
        st.error('Fant raden med "Butikk", men ingen butikker under den. Sjekk at fila har data under header-raden.', icon=":material/error:")
        return None
    return butikker


# ─────────────────────────────────────────────
# Finale – aggregering av alle registrerte ekspertscorer
# ─────────────────────────────────────────────
def beregn_finale_data(alle_rader, butikkliste):
    """Returnerer:
    - snitt_per_butikk: {butikk: (snittscore, antall_scorer)}
    - detaljer_per_butikk: {butikk: [(fagfelt, kriterium, score, kommentar, jurymedlem), ...]}
    Bruker ALLE registrerte vurderinger uansett jurymedlem – finalen skal reflektere
    summen av ekspertenes vurderinger, ikke kun én person sine."""
    detaljer = defaultdict(list)
    scorer = defaultdict(list)
    if len(alle_rader) > 1:
        for rad in alle_rader[1:]:
            if len(rad) < 6:
                continue
            butikk, jurymedlem, fagfelt, kriterium, score, kommentar = rad[:6]
            try:
                score_num = float(score)
            except (ValueError, TypeError):
                continue
            scorer[butikk].append(score_num)
            detaljer[butikk].append((fagfelt, kriterium, score_num, kommentar, jurymedlem))
    snitt = {b: (sum(v) / len(v), len(v)) for b, v in scorer.items()}
    return snitt, detaljer
