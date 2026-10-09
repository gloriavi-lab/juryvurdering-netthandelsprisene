"""All lesing/skriving mot Google Sheets. Regnearket er fasiten – appen
ENDRER ALDRI strukturen i det (ingen ekstra faner/kolonner), kun verdiene i
kriteriecellene, og KUN via (butikknavn, kriterienavn) → cellereferanse slått
opp fra de faktiske overskriftene. Aldri faste kolonnebokstaver, aldri
radnummer.

Regnearket har to ark med IDENTISK oppsett (rad 1 = fagfelt-gruppeoverskrift,
rad 2 = kriterienavn, rad 3+ = én rad per butikk, kolonne A-E er
Butikk/Jurymedlem/Klasse/Bransje/URL, siste kolonne er "Snitt totalt"):
- "Rangering fase 1" – kun lest, ALDRI skrevet til av appen.
- "Rangering fase 2" – der jurys Fase 2-vurderinger lagres. Opprettes ved å
  DUPLISERE Fase 1-fanen (gspread duplicate_sheet) hvis den ikke finnes, slik
  at farger, sammenslåinger, nedtrekkslister og filter følger med automatisk
  – appen bygger ALDRI strukturen selv.

"Jurymedlem"-kolonnen brukes ikke i Fase 2 (hver ekspert dekker ett fast
fagfelt for ALLE butikker, ikke én butikk hver) – fagfelt→ekspert-listen
ligger i data.py, ikke i arket, etter avtale med bruker.
"""

import re
from datetime import datetime

import gspread
import streamlit as st
from google.oauth2.service_account import Credentials

from data import FAGFELT, IKKE_VURDERT, KRITERIER_PER_FAGFELT

FASE1_FANE = "Rangering juryvurdering"  # tidligere "Rangering fase 1" – omdøpt etter avtale (ny fase-nummerering, se jury.py/Faser-fanen)
FASE2_FANE = "Rangering ekspertvurdering"  # tidligere "Rangering fase 2"
_GAMLE_NAVN = {FASE1_FANE: "Rangering fase 1", FASE2_FANE: "Rangering fase 2"}
GRUNNKOLONNER = ["Butikk", "Jurymedlem", "Klasse", "Bransje", "URL"]
SNITT_KOLONNE_NAVN = "Snitt totalt"
KOMMENTAR_PREFIKS = "Kommentar – "
# Lagt til helt til høyre, FORESLÅTT til bruker (ikke i den opprinnelige fila):
# én kommentarkolonne per fagfelt (ikke per kriterium – 16 kolonner til ble
# vurdert som for mye), pluss sporing av siste endring.
EKSTRA_KOLONNER = [f"{KOMMENTAR_PREFIKS}{f}" for f in FAGFELT] + ["Sist endret", "Endret av"]
FORSTE_DATARAD = 3  # rad 1-2 er overskrifter, se modulens docstring


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


# ─────────────────────────────────────────────
# Header-oppslag – ALDRI faste kolonnebokstaver
# ─────────────────────────────────────────────
@st.cache_data(ttl=60, show_spinner=False)
def _header_data(_ws, grunnkolonner=None):
    """Leser rad 1+2 (med combine_merged_cells slik at en sammenslått
    gruppeoverskrift gjentas i hver kolonne den dekker) og bygger kolonne-
    oppslag for grunnkolonner og (fagfelt, kriterium)-par. Forward-fyller i
    tillegg manuelt som ekstra sikkerhet, i tilfelle en sammenslåing mangler.

    grunnkolonner er konfigurerbar (ikke bare Rangering-fanenes faste liste)
    siden samme funksjon nå også brukes for Jury-fanen (Navn/E-post/Farge).
    En kolonne regnes som en FAGFELT-gruppe (ikke en grunnkolonne) når den
    IKKE står i grunnkolonner-lista og har et eget navn i rad 2 – ikke lenger
    avhengig av en hardkodet liste med fagfeltnavn, siden Kriterier-fanen nå
    er den egentlige kilden til hvilke fagfelt som finnes."""
    grunnkolonner = grunnkolonner if grunnkolonner is not None else GRUNNKOLONNER + [SNITT_KOLONNE_NAVN]
    rader = _ws.get("A1:ZZ2", combine_merged_cells=True)
    rad1 = rader[0] if len(rader) > 0 else []
    rad2 = rader[1] if len(rader) > 1 else []

    siste = ""
    rad1_fylt = []
    for v in rad1:
        if v:
            siste = v
        rad1_fylt.append(siste)

    grunnkolonne_indeks = {}
    kriterium_indeks = {}  # (fagfelt, kriterium) -> 1-indeksert kolonne
    for i, (g1, g2) in enumerate(zip(rad1_fylt, rad2 + [""] * (len(rad1_fylt) - len(rad2))), start=1):
        if not g1:
            continue
        g2 = g2.strip() if g2 else ""
        if g1 in grunnkolonner:
            if not g2:  # grunnkolonner har IKKE eget navn i rad 2
                grunnkolonne_indeks[g1] = i
        elif g2:
            kriterium_indeks[(g1, g2)] = i

    siste_kolonne = max([*grunnkolonne_indeks.values(), *kriterium_indeks.values()], default=5)
    return grunnkolonne_indeks, kriterium_indeks, siste_kolonne


def _sikre_ekstra_kolonner(ws, grunnkolonne_indeks, siste_kolonne):
    """Legger til kommentarkolonner per fagfelt + «Sist endret»/«Endret av»
    helt til høyre HVIS de ikke finnes fra før – foreslått til bruker, ikke
    en skjult strukturendring (se EKSTRA_KOLONNER)."""
    if "Sist endret" in grunnkolonne_indeks:
        return grunnkolonne_indeks, siste_kolonne
    ny_kolonne_1 = siste_kolonne + 1
    bokstav = gspread.utils.rowcol_to_a1(1, ny_kolonne_1).rstrip("1")
    bokstav_slutt = gspread.utils.rowcol_to_a1(1, ny_kolonne_1 + len(EKSTRA_KOLONNER) - 1).rstrip("1")
    ws.update([EKSTRA_KOLONNER], range_name=f"{bokstav}1:{bokstav_slutt}1")
    _header_data.clear()
    for i, navn in enumerate(EKSTRA_KOLONNER):
        grunnkolonne_indeks[navn] = ny_kolonne_1 + i
    return grunnkolonne_indeks, ny_kolonne_1 + len(EKSTRA_KOLONNER) - 1


def _fane(sh, navn):
    """Henter fanen på nytt navn. Finner den et gammelt navn (fra før
    omdøpingen til den nye fase-inndelingen, avtalt med bruker), gir den
    automatisk det nye navnet og fortsetter – trygt, ingen data berøres."""
    try:
        return sh.worksheet(navn)
    except gspread.WorksheetNotFound:
        gammelt = _GAMLE_NAVN.get(navn)
        if gammelt:
            try:
                ws = sh.worksheet(gammelt)
                ws.update_title(navn)
                st.toast(f"Omdøpte «{gammelt}» til «{navn}».", icon=":material/drive_file_rename_outline:")
                return ws
            except gspread.WorksheetNotFound:
                pass
        raise


def hent_eller_lag_fane(sh, navn, header):
    """Enkel fane med ÉN overskriftsrad (ikke den grupperte Rangering-
    stilen) – brukt for Kriterier/Veiledning/Faser."""
    try:
        return sh.worksheet(navn)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=navn, rows=200, cols=max(len(header), 4))
        ws.append_row(header)
        return ws


def _bygg_gruppert_header(sh, fane_navn, grunnkolonner, kriterier_per_fagfelt_dict, checkbox=False):
    """Bygger en NY fane med samme grupperte, fargede to-rads-header som
    Rangering-fanene (rad 1 = fagfelt-gruppe, slått sammen og farget; rad 2 =
    kriterienavn) – men fra bunnen, siden dette er helt nye faner uten noe
    eksisterende Excel-oppsett å kopiere/bevare. Brukt av jury.py (Jury-
    fanen). checkbox=True gir BOOLEAN-datavalidering i stedet for 1-5-liste."""
    from theme import FAGFELT_FARGE, GRUNNKOLONNE_FARGE

    ws = sh.add_worksheet(title=fane_navn, rows=200, cols=max(len(grunnkolonner) + 20, 10))
    rad1, rad2 = list(grunnkolonner), [""] * len(grunnkolonner)
    merge_forespørsler = []
    kol = len(grunnkolonner) + 1
    for fagfelt, kriterier in kriterier_per_fagfelt_dict.items():
        start_kol = kol
        for krit in kriterier:
            rad1.append(fagfelt if krit == kriterier[0] else "")
            rad2.append(krit)
            kol += 1
        if len(kriterier) > 1:
            merge_forespørsler.append({
                "mergeCells": {
                    "range": {"sheetId": ws.id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": start_kol - 1, "endColumnIndex": kol - 1},
                    "mergeType": "MERGE_ALL",
                }
            })
    ws.update([rad1, rad2])

    formater = []
    for i, _ in enumerate(grunnkolonner, start=1):
        formater.append({"repeatCell": {
            "range": {"sheetId": ws.id, "startRowIndex": 0, "endRowIndex": 2, "startColumnIndex": i - 1, "endColumnIndex": i},
            "cell": {"userEnteredFormat": {"backgroundColor": _hex_til_rgb(GRUNNKOLONNE_FARGE), "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}}},
            "fields": "userEnteredFormat(backgroundColor,textFormat)",
        }})
    kol = len(grunnkolonner) + 1
    for fagfelt, kriterier in kriterier_per_fagfelt_dict.items():
        formater.append({"repeatCell": {
            "range": {"sheetId": ws.id, "startRowIndex": 0, "endRowIndex": 2, "startColumnIndex": kol - 1, "endColumnIndex": kol - 1 + len(kriterier)},
            "cell": {"userEnteredFormat": {"backgroundColor": _hex_til_rgb(FAGFELT_FARGE.get(fagfelt, "#888888")), "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}}},
            "fields": "userEnteredFormat(backgroundColor,textFormat)",
        }})
        if checkbox:
            formater.append({"setDataValidation": {
                "range": {"sheetId": ws.id, "startRowIndex": FORSTE_DATARAD - 1, "endRowIndex": 200, "startColumnIndex": kol - 1, "endColumnIndex": kol - 1 + len(kriterier)},
                "rule": {"condition": {"type": "BOOLEAN"}, "strict": True, "showCustomUi": True},
            }})
        kol += len(kriterier)

    ws.spreadsheet.batch_update({"requests": merge_forespørsler + formater})
    ws.freeze(rows=2, cols=len(grunnkolonner))
    _header_data.clear()
    return ws


def _hex_til_rgb(hex_farge: str) -> dict:
    hex_farge = hex_farge.lstrip("#")
    return {"red": int(hex_farge[0:2], 16) / 255, "green": int(hex_farge[2:4], 16) / 255, "blue": int(hex_farge[4:6], 16) / 255}


def legg_til_kriterium_kolonne(sh, fane_navn, fagfelt, nytt_kriterium):
    """Setter inn ÉN ny, tom kolonne for et nytt kriterium rett etter siste
    eksisterende kolonne i riktig fagfeltgruppe i en Rangering-fane.
    insertDimension(inheritFromBefore=True) kopierer formatering OG
    datavalidering fra nabokolonnen automatisk – ingen andre celler berøres,
    og alt annet skyves bare til høyre (ingen data går tapt).

    Dette er det ENESTE stedet appen endrer struktur/formatering i en
    Rangering-fane – skal KUN kalles etter eksplisitt bekreftelse fra
    brukeren (st.dialog), se pages/innstillinger.py. IKKE testet mot et
    ekte regneark ennå – vær forsiktig første gang, og sjekk resultatet i
    Sheets rett etterpå."""
    ws = _fane(sh, fane_navn)
    grunn, krit, siste = _header_data(ws)
    kolonner_i_gruppe = sorted(kol for (f, k), kol in krit.items() if f == fagfelt)
    if not kolonner_i_gruppe:
        raise ValueError(f"Fant ingen eksisterende kolonner for fagfeltet «{fagfelt}» i «{fane_navn}» å kopiere format fra.")
    siste_i_gruppe = max(kolonner_i_gruppe)  # 1-indeksert

    ws.spreadsheet.batch_update({"requests": [{
        "insertDimension": {
            "range": {"sheetId": ws.id, "dimension": "COLUMNS", "startIndex": siste_i_gruppe, "endIndex": siste_i_gruppe + 1},
            "inheritFromBefore": True,
        }
    }]})
    ws.update([[nytt_kriterium]], range_name=gspread.utils.rowcol_to_a1(2, siste_i_gruppe + 1))
    _header_data.clear()


def _sikre_fase2_fane(sh):
    """Oppretter "Rangering fase 2" ved å DUPLISERE Fase 1-fanen (beholder
    farger/sammenslåinger/nedtrekkslister/filter/frysing automatisk), og
    tømmer KUN verdiene i kriteriecellene – aldri formatering. Oppretter den
    ALDRI på nytt hvis den allerede finnes (ville slettet jurys vurderinger)."""
    try:
        return sh.worksheet(FASE2_FANE)
    except gspread.WorksheetNotFound:
        fase1 = sh.worksheet(FASE1_FANE)
        ny = sh.duplicate_sheet(fase1.id, new_sheet_name=FASE2_FANE)
        grunn, krit, siste = _header_data.__wrapped__(ny)
        antall_rader = len(ny.get_all_values())
        if antall_rader >= FORSTE_DATARAD and krit:
            forste_krit_kol = min(c for c in krit.values())
            siste_krit_kol = max(c for c in krit.values())
            a1_start = gspread.utils.rowcol_to_a1(FORSTE_DATARAD, forste_krit_kol)
            a1_slutt = gspread.utils.rowcol_to_a1(antall_rader, siste_krit_kol)
            tomme_rader = [[""] * (siste_krit_kol - forste_krit_kol + 1) for _ in range(antall_rader - FORSTE_DATARAD + 1)]
            ny.update(tomme_rader, range_name=f"{a1_start}:{a1_slutt}", value_input_option="USER_ENTERED")
        # "Jurymedlem"-kolonnen brukes ikke i Fase 2 (se moduldoc) – tømmes også.
        if "Jurymedlem" in grunn and antall_rader >= FORSTE_DATARAD:
            kol = grunn["Jurymedlem"]
            bokstav = gspread.utils.rowcol_to_a1(1, kol).rstrip("1")
            tomme_jurymedlem_rader = [[""] for _ in range(antall_rader - FORSTE_DATARAD + 1)]
            ny.update(tomme_jurymedlem_rader, range_name=f"{bokstav}{FORSTE_DATARAD}:{bokstav}{antall_rader}")
        return ny


def legg_til_na_i_datavalidering(sh):
    """Legger «Kan ikke vurdere» til som en ekstra tillatt verdi i kriterie-
    cellenes nedtrekksliste (på Fase 2-fanen), i tillegg til 1-5 – endrer kun
    selve datavalideringen, ingen annen formatering."""
    ws = _sikre_fase2_fane(sh)
    grunn, krit, siste = _header_data(ws)
    antall_rader = len(ws.get_all_values())
    if not krit:
        return
    forste_krit_kol, siste_krit_kol = min(krit.values()), max(krit.values())
    ws.spreadsheet.batch_update({"requests": [{
        "setDataValidation": {
            "range": {
                "sheetId": ws.id, "startRowIndex": FORSTE_DATARAD - 1, "endRowIndex": antall_rader,
                "startColumnIndex": forste_krit_kol - 1, "endColumnIndex": siste_krit_kol,
            },
            "rule": {
                "condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": v} for v in ["1", "2", "3", "4", "5", IKKE_VURDERT]]},
                "showCustomUi": True, "strict": True,
            },
        }
    }]})


# ─────────────────────────────────────────────
# Lesing
# ─────────────────────────────────────────────
@st.cache_data(ttl=60, show_spinner=False)
def _rå_formatert(_ws):
    return _ws.get_all_values(combine_merged_cells=True)


@st.cache_data(ttl=60, show_spinner=False)
def _rå_formel(_ws):
    """Kun brukt til å hente URL ut av =HYPERLINK(...)-formler – alt annet
    (tall, tekst) ser identisk ut i FORMULA-modus som i formatert modus."""
    return _ws.get_all_values(value_render_option="FORMULA", combine_merged_cells=True)


def _uthent_url(formel_verdi):
    if not formel_verdi:
        return ""
    treff = re.search(r'HYPERLINK\("([^"]+)"', str(formel_verdi))
    return treff.group(1) if treff else str(formel_verdi).strip()


def _les_butikkliste(ws, grunn):
    formatert = _rå_formatert(ws)
    formler = _rå_formel(ws)
    butikker, advarsler = {}, []
    gyldige_klasser = {"Liten", "Medium", "Stor"}
    kol_butikk, kol_klasse = grunn.get("Butikk"), grunn.get("Klasse")
    kol_bransje, kol_url = grunn.get("Bransje"), grunn.get("URL")
    for r in range(FORSTE_DATARAD, len(formatert) + 1):
        rad = formatert[r - 1]
        navn = (rad[kol_butikk - 1].strip() if kol_butikk and len(rad) >= kol_butikk else "")
        if not navn:
            continue
        klasse = rad[kol_klasse - 1].strip() if kol_klasse and len(rad) >= kol_klasse else ""
        if klasse and klasse not in gyldige_klasser:
            advarsler.append(f"Rad {r} i '{ws.title}': «{navn}» har ukjent størrelsesklasse «{klasse}» (ventet Liten/Medium/Stor).")
        url = ""
        if kol_url and len(formler[r - 1]) >= kol_url:
            url = _uthent_url(formler[r - 1][kol_url - 1])
        butikker[navn] = {
            "klasse": klasse,
            "bransje": rad[kol_bransje - 1].strip() if kol_bransje and len(rad) >= kol_bransje else "",
            "url": url,
            "rad": r,
        }
    return butikker, advarsler


@st.cache_data(ttl=60, show_spinner=False)
def read_stores(_sh):
    """Returnerer (butikker, advarsler) fra Fase 1-fanen (butikklisten endrer
    seg ikke mellom fasene – kun vurderingene gjør)."""
    ws = _fane(_sh, FASE1_FANE)
    grunn, _, _ = _header_data(ws)
    return _les_butikkliste(ws, grunn)


@st.cache_data(ttl=60, show_spinner=False)
def read_fase1_scores(_sh):
    """{butikknavn: {kriterium: score}} fra Fase 1-fanen, til bruk som
    referanse (f.eks. Fase1-snitt på Butikker-siden)."""
    ws = _fane(_sh, FASE1_FANE)
    grunn, krit, _ = _header_data(ws)
    formatert = _rå_formatert(ws)
    kol_butikk = grunn.get("Butikk")
    resultat = {}
    for r in range(FORSTE_DATARAD, len(formatert) + 1):
        rad = formatert[r - 1]
        navn = rad[kol_butikk - 1].strip() if kol_butikk and len(rad) >= kol_butikk else ""
        if not navn:
            continue
        scorer = {}
        for (fagfelt, kriterium), kol in krit.items():
            if len(rad) >= kol and rad[kol - 1]:
                scorer[kriterium] = rad[kol - 1]
        resultat[navn] = scorer
    return resultat


@st.cache_data(ttl=60, show_spinner=False)
def read_ratings(_sh):
    """{butikknavn: {"scorer": {kriterium: score}, "kommentarer": {fagfelt:
    kommentar}, "sist_endret":.., "endret_av":..}} fra Fase 2-fanen – scoren
    ER cellen i rutenettet, det finnes ingen egen Rådata-fane lenger."""
    ws = _sikre_fase2_fane(_sh)
    grunn, krit, _ = _header_data(ws)
    formatert = _rå_formatert(ws)
    kol_butikk = grunn.get("Butikk")
    resultat = {}
    for r in range(FORSTE_DATARAD, len(formatert) + 1):
        rad = formatert[r - 1]
        navn = rad[kol_butikk - 1].strip() if kol_butikk and len(rad) >= kol_butikk else ""
        if not navn:
            continue
        scorer = {}
        for (fagfelt, kriterium), kol in krit.items():
            if len(rad) >= kol and rad[kol - 1]:
                scorer[kriterium] = rad[kol - 1]
        kommentarer = {}
        for fagfelt in FAGFELT:
            kol = grunn.get(f"{KOMMENTAR_PREFIKS}{fagfelt}")
            if kol and len(rad) >= kol and rad[kol - 1]:
                kommentarer[fagfelt] = rad[kol - 1]
        resultat[navn] = {
            "scorer": scorer,
            "kommentarer": kommentarer,
            "sist_endret": rad[grunn["Sist endret"] - 1] if grunn.get("Sist endret") and len(rad) >= grunn["Sist endret"] else "",
            "endret_av": rad[grunn["Endret av"] - 1] if grunn.get("Endret av") and len(rad) >= grunn["Endret av"] else "",
        }
    return resultat


def upsert_rating(sh, butikk_navn, jurymedlem, fagfelt, vurderinger, kommentar=""):
    """vurderinger: liste av (kriterium, score). Skriver KUN cellene for denne
    butikkens rad: kriterie-kolonnene som faktisk ble vurdert, pluss ÉN delt
    kommentarkolonne for fagfeltet – aldri noe annet i arket. score er
    "1".."5" eller "Kan ikke vurdere"."""
    ws = _sikre_fase2_fane(sh)
    grunn, krit, siste = _header_data(ws)
    grunn, siste = _sikre_ekstra_kolonner(ws, grunn, siste)
    butikker, _ = _les_butikkliste(ws, grunn)
    if butikk_navn not in butikker:
        raise ValueError(f"Fant ikke «{butikk_navn}» i '{ws.title}' – kan ikke lagre.")
    rad_nr = butikker[butikk_navn]["rad"]

    tidsstempel = datetime.now().strftime("%Y-%m-%d %H:%M")
    oppdateringer = []
    for kriterium, score in vurderinger:
        kolonne = krit.get((fagfelt, kriterium))
        if not kolonne:
            continue
        a1 = gspread.utils.rowcol_to_a1(rad_nr, kolonne)
        oppdateringer.append({"range": a1, "values": [[score]]})
    kommentar_kolonne = grunn.get(f"{KOMMENTAR_PREFIKS}{fagfelt}")
    if kommentar_kolonne:
        oppdateringer.append({"range": gspread.utils.rowcol_to_a1(rad_nr, kommentar_kolonne), "values": [[kommentar]]})
    if "Sist endret" in grunn:
        oppdateringer.append({"range": gspread.utils.rowcol_to_a1(rad_nr, grunn["Sist endret"]), "values": [[tidsstempel]]})
        oppdateringer.append({"range": gspread.utils.rowcol_to_a1(rad_nr, grunn["Endret av"]), "values": [[jurymedlem]]})

    if oppdateringer:
        ws.batch_update(oppdateringer, value_input_option="USER_ENTERED")
    read_ratings.clear()


# ─────────────────────────────────────────────
# Finale-lås – egen, liten fane. Dette ER en ny fane, så den opprettes kun
# når noen faktisk ber om å låse (eksplisitt handling, varslet til bruker).
# ─────────────────────────────────────────────
FINALE_SNAPSHOT_FANE = "Finale_snapshot"
FINALE_SNAPSHOT_HEADER = ["Klasse", "Plass", "Butikk", "Snittscore", "AntallVurderinger", "LåstAv", "LåstTid"]


def er_finale_last(sh):
    try:
        ws = sh.worksheet(FINALE_SNAPSHOT_FANE)
        return len(ws.get_all_values()) > 1
    except gspread.WorksheetNotFound:
        return False


def finale_las_info(sh):
    try:
        ws = sh.worksheet(FINALE_SNAPSHOT_FANE)
        rader = ws.get_all_records()
        if rader:
            return rader[0]["LåstAv"], rader[0]["LåstTid"]
    except gspread.WorksheetNotFound:
        pass
    return None, None


@st.cache_data(ttl=10, show_spinner=False)
def hent_finale_snapshot(_sh):
    try:
        return _sh.worksheet(FINALE_SNAPSHOT_FANE).get_all_records()
    except gspread.WorksheetNotFound:
        return []


def las_finale(sh, rader, jurymedlem):
    try:
        ws = sh.worksheet(FINALE_SNAPSHOT_FANE)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=FINALE_SNAPSHOT_FANE, rows=100, cols=len(FINALE_SNAPSHOT_HEADER))
    ws.clear()
    tidsstempel = datetime.now().strftime("%Y-%m-%d %H:%M")
    utdata = [FINALE_SNAPSHOT_HEADER]
    for r in rader:
        utdata.append([r["klasse"], r["plass"], r["butikk"], f'{r["snitt"]:.2f}', r["antall"], jurymedlem, tidsstempel])
    ws.update(utdata)
    hent_finale_snapshot.clear()


def fjern_finale_las(sh):
    try:
        sh.worksheet(FINALE_SNAPSHOT_FANE).clear()
        hent_finale_snapshot.clear()
    except gspread.WorksheetNotFound:
        pass


# ─────────────────────────────────────────────
# Diagnostikk – «Test tilkobling» i Innstillinger
# ─────────────────────────────────────────────
def test_tilkobling(sh):
    """Kjører en serie konkrete sjekker og returnerer en liste med
    (ok: bool, tekst: str) – ment for å vises direkte til brukeren med
    grønn hake/rødt kryss, slik at et problem kan forklares presist i
    stedet for et generisk «noe gikk galt»."""
    resultater = []

    try:
        meta = sh.client.request(
            "get", f"https://www.googleapis.com/drive/v3/files/{sh.id}",
            params={"fields": "mimeType,name"},
        ).json()
        er_sheets = meta.get("mimeType") == "application/vnd.google-apps.spreadsheet"
        if er_sheets:
            resultater.append((True, f"«{meta.get('name', '?')}» er et ekte Google Regneark."))
        else:
            resultater.append((False, f"«{meta.get('name', '?')}» er IKKE et ekte Google Regneark (mimeType: {meta.get('mimeType')}). Åpne fila i Google Sheets og velg Fil → «Lagre som Google Regneark» – appen kan ikke skrive til en ren Office-fil."))
    except Exception as e:
        resultater.append((False, f"Kunne ikke sjekke dokumenttype via Drive-API: {e}"))

    try:
        faner = [w.title for w in sh.worksheets()]
        resultater.append((True, f"Appen har lesetilgang ({len(faner)} faner funnet)."))
    except Exception as e:
        resultater.append((False, f"Mangler lesetilgang til regnearket: {e}. Del det med tjenestekontoens e-post (Redigerer-tilgang)."))
        return resultater

    try:
        fase1 = sh.worksheet(FASE1_FANE)
        fase1.update([["test"]], range_name="ZZ500")
        fase1.update([[""]], range_name="ZZ500")
        resultater.append((True, "Appen har skrivetilgang."))
    except Exception as e:
        resultater.append((False, f"Mangler skrivetilgang: {e}. Del regnearket med tjenestekontoens e-post og gi Redigerer-tilgang (ikke bare Kan se)."))

    for navn in [FASE1_FANE, FASE2_FANE, "Jury", "Kriterier"]:
        try:
            ws = sh.worksheet(navn)
            if navn in (FASE1_FANE, FASE2_FANE, "Jury"):
                grunn, krit, _ = _header_data(ws, grunnkolonner=(["Navn", "E-post", "Farge"] if navn == "Jury" else None))
                if grunn and krit:
                    resultater.append((True, f"Fanen «{navn}» finnes, og overskriftene leses riktig ({len(krit)} kriterium-kolonner funnet)."))
                else:
                    resultater.append((False, f"Fanen «{navn}» finnes, men overskriftene i rad 1/2 kunne ikke leses riktig – sjekk at de ikke er endret manuelt."))
            else:
                resultater.append((True, f"Fanen «{navn}» finnes."))
        except gspread.WorksheetNotFound:
            resultater.append((False, f"Fanen «{navn}» mangler ennå." + (" Opprettes automatisk når noen lagrer en vurdering/jurymedlem." if navn in (FASE2_FANE, "Jury") else "")))

    return resultater


# ─────────────────────────────────────────────
# Kommentarer – én rad per butikk+jurymedlem+kriterium. Fasiten for
# kommentarer; notatet på selve scorecellen i Fase 2-fanen er bare en kopi
# til rask oversikt direkte i regnearket.
# ─────────────────────────────────────────────
KOMMENTARER_FANE = "Kommentarer"
KOMMENTARER_HEADER = ["Butikk", "Jurymedlem", "Fagfelt", "Kriterium", "Kommentar", "Sist endret"]


def _sikre_kommentarer_fane(sh):
    from theme import GRUNNKOLONNE_FARGE

    try:
        return sh.worksheet(KOMMENTARER_FANE)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=KOMMENTARER_FANE, rows=1000, cols=len(KOMMENTARER_HEADER))
        ws.append_row(KOMMENTARER_HEADER)
        try:
            ws.format("A1:F1", {"backgroundColor": _hex_til_rgb(GRUNNKOLONNE_FARGE), "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}})
            ws.freeze(rows=1)
        except Exception:
            pass
        return ws


@st.cache_data(ttl=20, show_spinner=False)
def read_kommentarer(_sh):
    """Liste av dicts – én per lagret kriterium-kommentar. rad-nummeret er
    med slik at upsert_kommentar kan oppdatere/slette presist."""
    ws = _sikre_kommentarer_fane(_sh)
    rader = ws.get_all_values()
    resultat = []
    for i, rad in enumerate(rader[1:] if len(rader) > 1 else [], start=2):
        if len(rad) >= 4 and rad[0]:
            resultat.append({
                "rad": i, "butikk": rad[0], "jurymedlem": rad[1], "fagfelt": rad[2],
                "kriterium": rad[3], "kommentar": rad[4] if len(rad) > 4 else "",
                "sist_endret": rad[5] if len(rad) > 5 else "",
            })
    return resultat


def upsert_kommentar(sh, butikk, jurymedlem, fagfelt, kriterium, kommentar):
    """Oppretter/oppdaterer raden i Kommentarer, eller SLETTER den hvis
    kommentarteksten er tømt. Speiler i tillegg kommentaren som notat på
    riktig scorecelle i Fase 2-fanen (kun en bekvemmelighet for de som
    jobber direkte i Sheets – Kommentarer-fanen er fasiten)."""
    ws = _sikre_kommentarer_fane(sh)
    rader = ws.get_all_values()
    rad_nr = None
    for i, rad in enumerate(rader[1:] if len(rader) > 1 else [], start=2):
        if len(rad) >= 4 and rad[0] == butikk and rad[1] == jurymedlem and rad[3] == kriterium:
            rad_nr = i
            break

    tidsstempel = datetime.now().strftime("%Y-%m-%d %H:%M")
    kommentar = (kommentar or "").strip()
    if kommentar:
        verdier = [butikk, jurymedlem, fagfelt, kriterium, kommentar, tidsstempel]
        if rad_nr:
            ws.update([verdier], range_name=f"A{rad_nr}:F{rad_nr}")
        else:
            ws.append_row(verdier)
    elif rad_nr:
        ws.spreadsheet.batch_update({"requests": [{
            "deleteDimension": {"range": {"sheetId": ws.id, "dimension": "ROWS", "startIndex": rad_nr - 1, "endIndex": rad_nr}}
        }]})
    read_kommentarer.clear()

    try:
        fase2 = _sikre_fase2_fane(sh)
        grunn2, krit2, _ = _header_data(fase2)
        butikker2, _ = _les_butikkliste(fase2, grunn2)
        if butikk in butikker2 and (fagfelt, kriterium) in krit2:
            celle = gspread.utils.rowcol_to_a1(butikker2[butikk]["rad"], krit2[(fagfelt, kriterium)])
            if kommentar:
                fase2.insert_note(celle, kommentar)
            else:
                fase2.clear_note(celle)
    except Exception:
        pass  # notatet er kun en bekvemmelighet – skal aldri blokkere selve lagringen


# ═════════════════════════════════════════════
# NY MODELL (etter brukertesting): én fane "Vurderinger" er eneste kilde til
# sannhet for score+kommentar per kriterium – erstatter den tidligere delte
# modellen (verdier i "Rangering ekspertvurdering"-rutenettet + en egen
# "Kommentarer"-fane + celle-notater). Den delte skrivingen (to separate
# upsert-kall per lagring, pluss notat-speiling) var rotårsaken til at en
# slettet kommentar kunne "komme tilbake": et av stedene kunne feile eller
# henge igjen uten at det andre visste om det. Med én fane og én upsert-
# operasjon per rad finnes ikke det problemet lenger – og det løser også at
# flere jurymedlemmer kan dele samme kriterium (hver får sin egen rad).
# ═════════════════════════════════════════════
VURDERINGER_FANE = "Vurderinger"
VURDERINGER_HEADER2 = ["Butikk", "Jurymedlem", "Fagfelt", "Kriterium", "Score", "Kommentar", "Sist endret"]
GENERELLE_KOMMENTARER_FANE = "Generelle kommentarer"
GENERELLE_KOMMENTARER_HEADER = ["Butikk", "Jurymedlem", "Kommentar", "Sist endret"]


def _sikre_enkel_fane_med_header(sh, navn, header):
    try:
        return sh.worksheet(navn)
    except gspread.WorksheetNotFound:
        from theme import GRUNNKOLONNE_FARGE
        ws = sh.add_worksheet(title=navn, rows=2000, cols=len(header))
        ws.append_row(header)
        try:
            ws.format("A1:" + gspread.utils.rowcol_to_a1(1, len(header)).rstrip("1") + "1", {
                "backgroundColor": _hex_til_rgb(GRUNNKOLONNE_FARGE),
                "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
            })
            ws.freeze(rows=1)
        except Exception:
            pass
        return ws


@st.cache_data(ttl=15, show_spinner=False)
def read_vurderinger(_sh):
    """Liste av dicts – én per lagret (butikk, jurymedlem, kriterium).
    rad-nummeret er med slik at upsert_vurdering kan oppdatere/slette presist."""
    ws = _sikre_enkel_fane_med_header(_sh, VURDERINGER_FANE, VURDERINGER_HEADER2)
    rader = ws.get_all_values()
    resultat = []
    for i, rad in enumerate(rader[1:] if len(rader) > 1 else [], start=2):
        if len(rad) >= 5 and rad[0] and rad[4]:
            resultat.append({
                "rad": i, "butikk": rad[0], "jurymedlem": rad[1], "fagfelt": rad[2],
                "kriterium": rad[3], "score": rad[4], "kommentar": rad[5] if len(rad) > 5 else "",
                "sist_endret": rad[6] if len(rad) > 6 else "",
            })
    return resultat


def upsert_vurdering(sh, butikk, jurymedlem, fagfelt, kriterium, score, kommentar=""):
    """Oppretter/oppdaterer raden for akkurat denne (butikk, jurymedlem,
    kriterium)-kombinasjonen. score=None/tom SLETTER raden (tilsvarer «ikke
    vurdert» – skal ikke stå igjen som noe i det hele tatt)."""
    ws = _sikre_enkel_fane_med_header(sh, VURDERINGER_FANE, VURDERINGER_HEADER2)
    rader = ws.get_all_values()
    rad_nr = None
    for i, rad in enumerate(rader[1:] if len(rader) > 1 else [], start=2):
        if len(rad) >= 4 and rad[0] == butikk and rad[1] == jurymedlem and rad[3] == kriterium:
            rad_nr = i
            break

    tidsstempel = datetime.now().strftime("%Y-%m-%d %H:%M")
    if score:
        verdier = [butikk, jurymedlem, fagfelt, kriterium, str(score), kommentar or "", tidsstempel]
        if rad_nr:
            ws.update([verdier], range_name=f"A{rad_nr}:G{rad_nr}")
        else:
            ws.append_row(verdier)
    elif rad_nr:
        ws.spreadsheet.batch_update({"requests": [{
            "deleteDimension": {"range": {"sheetId": ws.id, "dimension": "ROWS", "startIndex": rad_nr - 1, "endIndex": rad_nr}}
        }]})
    read_vurderinger.clear()


@st.cache_data(ttl=15, show_spinner=False)
def read_generelle_kommentarer(_sh):
    ws = _sikre_enkel_fane_med_header(_sh, GENERELLE_KOMMENTARER_FANE, GENERELLE_KOMMENTARER_HEADER)
    rader = ws.get_all_values()
    resultat = []
    for i, rad in enumerate(rader[1:] if len(rader) > 1 else [], start=2):
        if len(rad) >= 2 and rad[0]:
            resultat.append({"rad": i, "butikk": rad[0], "jurymedlem": rad[1], "kommentar": rad[2] if len(rad) > 2 else "", "sist_endret": rad[3] if len(rad) > 3 else ""})
    return resultat


def upsert_generell_kommentar(sh, butikk, jurymedlem, kommentar):
    ws = _sikre_enkel_fane_med_header(sh, GENERELLE_KOMMENTARER_FANE, GENERELLE_KOMMENTARER_HEADER)
    rader = ws.get_all_values()
    rad_nr = None
    for i, rad in enumerate(rader[1:] if len(rader) > 1 else [], start=2):
        if len(rad) >= 2 and rad[0] == butikk and rad[1] == jurymedlem:
            rad_nr = i
            break
    tidsstempel = datetime.now().strftime("%Y-%m-%d %H:%M")
    if kommentar and kommentar.strip():
        verdier = [butikk, jurymedlem, kommentar.strip(), tidsstempel]
        if rad_nr:
            ws.update([verdier], range_name=f"A{rad_nr}:D{rad_nr}")
        else:
            ws.append_row(verdier)
    elif rad_nr:
        ws.spreadsheet.batch_update({"requests": [{
            "deleteDimension": {"range": {"sheetId": ws.id, "dimension": "ROWS", "startIndex": rad_nr - 1, "endIndex": rad_nr}}
        }]})
    read_generelle_kommentarer.clear()


def sikkerhetskopier_alle_faner(sh):
    """Dupliserer HVER fane i regnearket med et tidsstempel i navnet, FØR en
    strukturendring. Returnerer listen med nye fanenavn."""
    tidsstempel = datetime.now().strftime("%Y%m%d-%H%M%S")
    nye_navn = []
    for ws in list(sh.worksheets()):
        if ws.title.startswith("Backup_"):
            continue  # ikke sikkerhetskopier gamle sikkerhetskopier
        nytt_navn = f"Backup_{tidsstempel}_{ws.title}"[:99]  # Google Sheets har en lengdegrense på fanenavn
        sh.duplicate_sheet(ws.id, new_sheet_name=nytt_navn)
        nye_navn.append(nytt_navn)
    return nye_navn


def migrer_til_vurderinger_fane(sh):
    """Flytter eksisterende data fra den gamle modellen (Rangering ekspert-
    vurdering-rutenettet + den gamle Kommentarer-fanen) inn i Vurderinger +
    Generelle kommentarer. Tar sikkerhetskopi av ALT først. Ingen rader går
    tapt, men historiske ENKELTSCORER manglet opprinnelig jurymedlem-
    attribusjon i rutenettet (feltet fantes rett og slett ikke) – disse
    attribueres best mulig (fra en matchende gammel kommentarrad, ellers
    radens "Endret av", ellers "Ukjent"). Returnerer en oppsummering."""
    backup_navn = sikkerhetskopier_alle_faner(sh)

    try:
        fase2 = sh.worksheet(FASE2_FANE)
    except gspread.WorksheetNotFound:
        return {"backup": backup_navn, "antall_for": 0, "antall_etter": 0, "detaljer": "Ingen «Rangering ekspertvurdering»-fane funnet – ingenting å flytte."}

    grunn, krit, _ = _header_data(fase2, grunnkolonner=GRUNNKOLONNER + [SNITT_KOLONNE_NAVN] + EKSTRA_KOLONNER)
    formatert = _rå_formatert(fase2)
    kol_butikk = grunn.get("Butikk")
    kol_endret_av = grunn.get("Endret av")

    try:
        gamle_kommentarer = read_kommentarer.__wrapped__(sh)
    except Exception:
        gamle_kommentarer = []
    kommentar_oppslag = {(r["butikk"], r["kriterium"]): (r["jurymedlem"], r["kommentar"]) for r in gamle_kommentarer}

    antall_for = 0
    antall_etter = 0
    generelle_samlet = {}  # (butikk, jurymedlem) -> [kommentartekster]

    for r in range(FORSTE_DATARAD, len(formatert) + 1):
        rad = formatert[r - 1]
        butikk = rad[kol_butikk - 1].strip() if kol_butikk and len(rad) >= kol_butikk else ""
        if not butikk:
            continue
        endret_av_fallback = rad[kol_endret_av - 1].strip() if kol_endret_av and len(rad) >= kol_endret_av else ""

        for (fagfelt, kriterium), kol in krit.items():
            verdi = rad[kol - 1].strip() if len(rad) >= kol else ""
            if not verdi:
                continue
            antall_for += 1
            if (butikk, kriterium) in kommentar_oppslag:
                jurymedlem, kommentar = kommentar_oppslag[(butikk, kriterium)]
            else:
                jurymedlem, kommentar = (endret_av_fallback or "Ukjent"), ""
            upsert_vurdering(sh, butikk, jurymedlem, fagfelt, kriterium, verdi, kommentar)
            antall_etter += 1

        for fagfelt in set(f for f, _ in krit.keys()):
            kol_generell = grunn.get(f"{KOMMENTAR_PREFIKS}{fagfelt}")
            if kol_generell and len(rad) >= kol_generell and rad[kol_generell - 1].strip():
                nokkel = (butikk, endret_av_fallback or "Ukjent")
                generelle_samlet.setdefault(nokkel, []).append(rad[kol_generell - 1].strip())

    for (butikk, jurymedlem), tekster in generelle_samlet.items():
        upsert_generell_kommentar(sh, butikk, jurymedlem, " | ".join(tekster))

    return {
        "backup": backup_navn, "antall_for": antall_for, "antall_etter": antall_etter,
        "detaljer": f"{antall_for} enkeltscorer funnet i det gamle rutenettet, {antall_etter} rader skrevet til Vurderinger. {len(generelle_samlet)} generelle kommentarer migrert.",
    }
