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
                "rule": {"condition": {"type": "BOOLEAN"}, "strict": True},
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
