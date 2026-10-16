"""All lesing/skriving mot Google Sheets.

VIKTIG – hvilken fane er hvilken, og hvilken er AKTIV (les her først –
dette har vært kilde til reell forvirring i brukertesting, se historikken i
git-loggen for sheets.py hvis du lurer på hvorfor dette har endret seg):

- FASE2_FANE ("Rangering ekspertvurdering") ER DEN AKTIVE FANEN – den
  fargede fanen i samme stil som resten av regnearket, som jury og
  administrasjon faktisk jobber i og ser. Scoren for hvert (butikk,
  kriterium) står DIREKTE i cellen, som et TALL (eller teksten
  "Kan ikke vurdere"), og kommentaren ligger som et celle-NOTAT på samme
  celle. Appen skriver hit ved hver lagring (skriv_mange_til_farget_fane) og
  LESER også herfra for alt den viser (read_ratings) – manuelle rettelser
  direkte i arket vises derfor i appen ved neste lasting. Den er OGSÅ (etter
  eksplisitt avtale) den autoritative BUTIKKLISTEN nå (read_stores) – ALLE
  sider (Vurdering/Butikker/Oversikt/Finale/Innstillinger) viser kun de
  butikkene som faktisk står her, ikke hele Fase 1-lista.
- "Vurderinger" (VURDERINGER_FANE) er en LOGG, ikke det appen viser: én rad
  per butikk + jurymedlem + kriterium, oppdatert ved hver lagring (se
  upsert_vurdering/read_vurderinger). Finnes for historikk/sporbarhet og for
  å kunne regne ut riktig verdi når flere jurymedlemmer deler ett kriterium
  (se data.offisiell_celleverdi) – IKKE for visning i appen.
- "Generelle kommentarer" (GENERELLE_KOMMENTARER_FANE) er butikk-nivå-
  kommentarer (flere jurymedlemmer kan ha hver sin) – egen, liten logg, ikke
  del av den fargede fanen (den har ingen naturlig énkelt-celle for en
  kommentar som ikke hører til ett bestemt kriterium).
- FASE1_FANE ("Rangering juryvurdering") leses KUN for Fase 1-SCORER som
  referanse (read_fase1_scores, f.eks. Fase1-snitt på Butikker-siden) –
  aldri skrevet til, og IKKE lenger kilden til butikklisten (se FASE2_FANE
  over – byttet fordi Fase 1-fanen kan inneholde flere butikker enn de som
  faktisk skal ekspertvurderes). Fortsatt i aktiv bruk, IKKE en arkiv-fane,
  selv om navnet kan forveksles med FASE2_FANE.
- Alle andre faner som måtte hete noe i stil med "Rangering ..." og som
  IKKE er en av de fire over, er historiske levninger appen ikke rører –
  merkes "ARKIV – " i Innstillinger (aldri slettet automatisk).

Regnearket er ellers fasiten for struktur – appen bygger ALDRI nye
faner/kolonner utover det som er eksplisitt dokumentert her, og finner alltid
cellene sine via de faktiske overskriftene (aldri faste kolonnebokstaver,
aldri radnummer) når den skriver til en eksisterende fane.
"""

import re
import time
from collections import deque

import gspread
import streamlit as st
from google.oauth2.service_account import Credentials

from data import FAGFELT, IKKE_VURDERT, KRITERIER_PER_FAGFELT, grupper_vurderinger, naa_norsk, normalize_score, offisiell_celleverdi

FASE1_FANE = "Rangering juryvurdering"  # tidligere "Rangering fase 1" – omdøpt etter avtale (ny fase-nummerering, se jury.py/Faser-fanen)
FASE2_FANE = "Rangering ekspertvurdering"  # tidligere "Rangering fase 2"
_GAMLE_NAVN = {FASE1_FANE: "Rangering fase 1", FASE2_FANE: "Rangering fase 2"}
GRUNNKOLONNER = ["Butikk", "Jurymedlem", "Klasse", "Bransje", "URL", "Fase"]
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
# Ytelsesmåling (se Innstillinger → Ytelse): ALLE gspread-kall går gjennom
# ÉTT sted – http_client.request() – så tidtaking pakkes inn DER i stedet
# for rundt hvert eneste kall-sted i sheets.py/jury.py enkeltvis. NB: gc er
# @st.cache_resource (prosessvidt, delt av ALLE brukere samtidig), så denne
# loggen viser samlet trafikk for hele appen – fortsatt nyttig for å se
# hvilke SIDER/handlinger som er tregest totalt sett, bare ikke isolert per
# bruker. Begrenset til de siste 500 kallene (deque maxlen) for å unngå at
# minnebruken vokser ubegrenset over en lang kjøretid.
_API_KALL_LOGG = deque(maxlen=500)


def _instrumenter_klient(gc):
    opprinnelig_request = gc.http_client.request

    def _med_tidtaking(method, endpoint, *args, **kwargs):
        start = time.monotonic()
        try:
            return opprinnelig_request(method, endpoint, *args, **kwargs)
        finally:
            _API_KALL_LOGG.append({
                "tid": naa_norsk().strftime("%H:%M:%S"),
                "metode": method,
                "endepunkt": str(endpoint).split("?")[0][-70:],
                "varighet_ms": round((time.monotonic() - start) * 1000, 1),
                "side": st.session_state.get("_gjeldende_side", "?"),
            })

    gc.http_client.request = _med_tidtaking
    return gc


def hent_api_kall_logg():
    """Kopi av de siste (maks 500) målte Sheets-API-kallene, nyeste sist –
    til bruk i Innstillinger → Ytelse. Rører ikke selve loggen."""
    return list(_API_KALL_LOGG)


@st.cache_resource(ttl=3600, show_spinner=False)
def _gc_klient():
    try:
        creds_info = st.secrets["gcp_service_account"]
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_info, scopes=scope)
        return _instrumenter_klient(gspread.authorize(creds))
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
    kol_fase = grunn.get("Fase")
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
            # Valgfri kolonne – tom betyr «vis i alle faser» (bakoverkompatibelt,
            # ingenting filtreres bort før noen faktisk fyller den ut). Se
            # jury.gjeldende_fase_streng() for hvordan den brukes.
            "fase": rad[kol_fase - 1].strip() if kol_fase and len(rad) >= kol_fase else "",
            "rad": r,
        }
    return butikker, advarsler


@st.cache_data(ttl=600, show_spinner=False)
def read_stores(_sh):
    """Returnerer (butikker, advarsler) fra FASE2_FANE («Rangering
    ekspertvurdering») – BYTTET (etter eksplisitt avtale) fra Fase 1-fanen,
    siden Fase 1-fanen kan inneholde FLERE butikker enn de som faktisk skal
    ekspertvurderes (f.eks. 111 der mot 48 ryddede rader her). «Rangering
    ekspertvurdering» er nå den autoritative butikklisten for Vurdering/
    Butikker/Oversikt/Finale/Innstillinger – ALLE leser via denne ene
    funksjonen, se grep av read_stores()-kallene.

    read_fase1_scores() leser FORTSATT direkte fra Fase 1-fanen – det er en
    egen, separat ting (Fase 1-SCORER som referanse), ikke butikklisten."""
    ws = _sikre_fase2_fane(_sh)
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

    tidsstempel = naa_norsk().strftime("%Y-%m-%d %H:%M")
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
    _rå_formatert.clear()
    read_ratings.clear()


def skriv_mange_til_farget_fane(sh, butikk, verdier_og_notater: list):
    """Skriver DEN OFFISIELLE verdien for flere kriterier samtidig direkte
    til den fargede fanen for gjeldende fase (FASE2_FANE) – dette ER fanen
    jury og administrasjon faktisk jobber i og ser, så den må alltid speile
    det "Vurderinger"-loggen til enhver tid mener er riktig verdi (se
    data.offisiell_celleverdi). ÉTT batch_update-kall for selve scorene
    (value_input_option=USER_ENTERED, slik at tall faktisk blir TALL i
    arket – ikke tekst), pluss ETT update_notes-kall for ALLE kommentarene
    samtidig (gspread batcher notater internt i ett eneste API-kall – se
    Worksheet.update_notes – i stedet for ett insert_note/clear_note-kall
    per celle, som før brukte opptil N ekstra API-kall per lagring).

    verdier_og_notater: liste av (fagfelt, kriterium, verdi, notat_tekst).
    verdi er et tall, IKKE_VURDERT-teksten, eller None (tømmer cellen).
    Returnerer {kriterium: a1-celle} for de som faktisk ble skrevet – brukes
    til å lese akkurat disse cellene tilbake for å bekrefte lagringen."""
    ws = _sikre_fase2_fane(sh)
    grunn, krit, _ = _header_data(ws)
    butikker, _ = _les_butikkliste(ws, grunn)
    if butikk not in butikker:
        raise ValueError(f"Fant ikke «{butikk}» i «{ws.title}» – kan ikke lagre.")
    rad_nr = butikker[butikk]["rad"]

    oppdateringer, notater, celler = [], {}, {}
    for fagfelt, kriterium, verdi, notat in verdier_og_notater:
        kolonne = krit.get((fagfelt, kriterium))
        if not kolonne:
            raise ValueError(f"Fant ikke kolonnen for «{kriterium}» under «{fagfelt}» i «{ws.title}».")
        celle = gspread.utils.rowcol_to_a1(rad_nr, kolonne)
        oppdateringer.append({"range": celle, "values": [[verdi if verdi is not None else ""]]})
        notater[celle] = notat or ""
        celler[kriterium] = celle

    if oppdateringer:
        ws.batch_update(oppdateringer, value_input_option="USER_ENTERED")
    try:
        if notater:
            ws.update_notes(notater)
    except Exception:
        pass  # notatet er kun en bekvemmelighet – skal aldri blokkere selve scoren
    _rå_formatert.clear()  # read_ratings/_les_butikkliste leser via denne – MÅ tømmes, ikke bare read_ratings sin egen cache
    read_ratings.clear()
    return celler


def feilsok_farget_fane(sh, butikk, kriterier_med_fagfelt: list):
    """Som feilsok_vurdering, men mot DEN FARGEDE FANEN (FASE2_FANE) – rå
    celleverdi (med type) og celle-notat for hvert kriterium, lest helt
    ferskt (ingen mellomlagring). kriterier_med_fagfelt: liste av
    (fagfelt, kriterium)."""
    from data import normalize_score

    ws = _sikre_fase2_fane(sh)
    grunn, krit, _ = _header_data(ws)
    butikker, _ = _les_butikkliste(ws, grunn)
    rad_nr = butikker.get(butikk, {}).get("rad")
    formatert = ws.get_all_values(combine_merged_cells=True) if rad_nr else []

    resultat = []
    for fagfelt, kriterium in kriterier_med_fagfelt:
        kolonne = krit.get((fagfelt, kriterium))
        celle, rå, notat = "(fant ikke kolonnen)", None, ""
        if rad_nr and kolonne:
            celle = gspread.utils.rowcol_to_a1(rad_nr, kolonne)
            rad = formatert[rad_nr - 1] if len(formatert) >= rad_nr else []
            rå = rad[kolonne - 1] if len(rad) >= kolonne else ""
            try:
                notat = ws.get_note(celle) or ""
            except Exception:
                notat = ""
        resultat.append({
            "kriterium": kriterium, "fane": FASE2_FANE, "celle": celle,
            "rå_score": rå, "rå_score_type": type(rå).__name__,
            "rå_notat": notat, "normalisert_score": normalize_score(rå),
        })
    return resultat


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
    tidsstempel = naa_norsk().strftime("%Y-%m-%d %H:%M")
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

    tidsstempel = naa_norsk().strftime("%Y-%m-%d %H:%M")
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


def sett_opp_kommentarer_som_formelvisning(sh):
    """«Kommentarer»-fanen sluttet å bli oppdatert av appen etter at
    kommentarer flyttet til å ligge som en kolonne i «Vurderinger» (appen
    IKKE skriver hit noen steder lenger – bekreftet med søk i hele
    kildekoden) – den sto igjen med gamle testrader. Gjør den i stedet om
    til en LIVE, automatisk oppdatert VISNING av «Vurderinger», med én
    QUERY-formel i A2 som Google Sheets selv holder oppdatert – appen
    skriver ALDRI hit igjen. Tar sikkerhetskopi FØRST, tømmer så fanen
    (de gamle testradene forsvinner fra selve fanen, men ligger urørt i
    sikkerhetskopien) og setter opp header + formel på nytt.

    NB: formelen forutsetter at «Vurderinger» sine kolonner forblir i
    rekkefølgen Butikk,Jurymedlem,Fagfelt,Kriterium,Score,Kommentar,
    Sist endret (se VURDERINGER_HEADER2) – endres den rekkefølgen må
    formelen oppdateres til match."""
    backup_navn = sikkerhetskopier_alle_faner(sh)
    try:
        ws = sh.worksheet(KOMMENTARER_FANE)
        ws.clear()
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=KOMMENTARER_FANE, rows=200, cols=7)

    ws.update([VURDERINGER_HEADER2], range_name="A1:G1")
    formel = f"=QUERY('{VURDERINGER_FANE}'!A2:G; \"select A,B,C,D,E,F,G where F != '' order by A\"; 0)"
    ws.update([[formel]], range_name="A2", value_input_option="USER_ENTERED")
    try:
        from theme import GRUNNKOLONNE_FARGE
        ws.format("A1:G1", {"backgroundColor": _hex_til_rgb(GRUNNKOLONNE_FARGE), "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}})
        ws.freeze(rows=1)
    except Exception:
        pass
    read_kommentarer.clear()
    return backup_navn


# ═════════════════════════════════════════════
# "Vurderinger" er LOGGEN (ikke det som vises – se VIKTIG-avsnittet øverst i
# fila): én rad per butikk+jurymedlem+kriterium, oppdatert ved hver lagring.
# Brukt til å regne ut riktig snitt når flere jurymedlemmer deler ett
# kriterium (se data.offisiell_celleverdi), og som grunnlag for den
# automatisk oppdaterte «Kommentarer»-formelvisningen over.
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


def _finn_vurdering_rad(rader, butikk, jurymedlem, kriterium):
    """Felles oppslags-logikk for upsert_vurdering OG feilsøkingsvisningen i
    Innstillinger, slik at de aldri kan vise/skrive til ulike rader for
    «samme» celle. rader er resultatet av ws.get_all_values() på
    Vurderinger-fanen. Returnerer (rad_nr, rad_verdier) eller (None, None)."""
    for i, rad in enumerate(rader[1:] if len(rader) > 1 else [], start=2):
        if len(rad) >= 4 and rad[0] == butikk and rad[1] == jurymedlem and rad[3] == kriterium:
            return i, rad
    return None, None


def upsert_vurdering(sh, butikk, jurymedlem, fagfelt, kriterium, score, kommentar=""):
    """Oppretter/oppdaterer raden for akkurat denne (butikk, jurymedlem,
    kriterium)-kombinasjonen. score=None/tom SLETTER raden (tilsvarer «ikke
    vurdert» – skal ikke stå igjen som noe i det hele tatt)."""
    ws = _sikre_enkel_fane_med_header(sh, VURDERINGER_FANE, VURDERINGER_HEADER2)
    rader = ws.get_all_values()
    rad_nr, _ = _finn_vurdering_rad(rader, butikk, jurymedlem, kriterium)

    tidsstempel = naa_norsk().strftime("%Y-%m-%d %H:%M")
    if score:
        # Skriv scoren som en EKTE Python int/float når den er numerisk, ikke
        # en streng – en verdi som allerede er et JSON-tall trenger ingen
        # "tolkning" (det er det value_input_option RAW/USER_ENTERED gjelder,
        # kun for strenger), så den lagres som et TALL i Sheets uansett.
        # IKKE_VURDERT forblir tekst (den er ikke numerisk). Kun selve
        # verditypen endres her – skrive-mekanikken ellers er urørt.
        normalisert_score = normalize_score(score)
        lagret_score = normalisert_score if normalisert_score is not None else score
        verdier = [butikk, jurymedlem, fagfelt, kriterium, lagret_score, kommentar or "", tidsstempel]
        if rad_nr:
            ws.update([verdier], range_name=f"A{rad_nr}:G{rad_nr}")
        else:
            ws.append_row(verdier)
    elif rad_nr:
        ws.spreadsheet.batch_update({"requests": [{
            "deleteDimension": {"range": {"sheetId": ws.id, "dimension": "ROWS", "startIndex": rad_nr - 1, "endIndex": rad_nr}}
        }]})
    read_vurderinger.clear()


def upsert_mange_vurderinger(sh, butikk, jurymedlem, kriterier: list):
    """BATCHED variant av upsert_vurdering – skriver ALLE kriteriene for én
    "Lagre og neste"-handling i maks to API-kall (ett batch_update for
    eksisterende rader, ett append_rows for nye), i stedet for ett
    get_all_values()-kall OG ett skrive-kall PER KRITERIUM. Lagt til etter
    at appen traff Google sin kvote for leseforespørsler i produksjon – en
    lagring med 5 kriterier gjorde før 10 separate API-kall her alene.
    Oppfører seg funksjonelt IDENTISK med å kalle upsert_vurdering per
    kriterium (samme rad-gjenfinning, samme tall-vs-tekst-regel) – kun
    ANTALL API-kall er redusert, ingen endring i hva som faktisk lagres.

    kriterier: liste av (fagfelt, kriterium, score, kommentar)."""
    ws = _sikre_enkel_fane_med_header(sh, VURDERINGER_FANE, VURDERINGER_HEADER2)
    rader = ws.get_all_values()
    tidsstempel = naa_norsk().strftime("%Y-%m-%d %H:%M")

    oppdateringer, nye_rader, slett_rad_nr = [], [], []
    for fagfelt, kriterium, score, kommentar in kriterier:
        rad_nr, _ = _finn_vurdering_rad(rader, butikk, jurymedlem, kriterium)
        if score:
            normalisert_score = normalize_score(score)
            lagret_score = normalisert_score if normalisert_score is not None else score
            verdier = [butikk, jurymedlem, fagfelt, kriterium, lagret_score, kommentar or "", tidsstempel]
            if rad_nr:
                oppdateringer.append({"range": f"A{rad_nr}:G{rad_nr}", "values": [verdier]})
            else:
                nye_rader.append(verdier)
        elif rad_nr:
            slett_rad_nr.append(rad_nr)

    if oppdateringer:
        ws.batch_update(oppdateringer)
    if nye_rader:
        ws.append_rows(nye_rader)
    for rad_nr in sorted(slett_rad_nr, reverse=True):  # bakfra, ellers forskyves radnumrene under sletting
        ws.spreadsheet.batch_update({"requests": [{
            "deleteDimension": {"range": {"sheetId": ws.id, "dimension": "ROWS", "startIndex": rad_nr - 1, "endIndex": rad_nr}}
        }]})
    read_vurderinger.clear()


def feilsok_vurdering(sh, butikk, jurymedlem, kriterier: list):
    """For «Feilsøking lagring» i Innstillinger: EKSAKT samme
    oppslagslogikk (_finn_vurdering_rad) som upsert_vurdering selv bruker,
    pluss normalize_score, slik at visningen her garantert stemmer overens
    med det appen faktisk gjør – ikke en forenklet kopi som kan drifte fra
    virkeligheten. Gjør ALLTID en fersk lesing (hopper forbi 15s-cachen),
    siden hele poenget er å se det som faktisk står i arket akkurat nå."""
    from data import normalize_score

    read_vurderinger.clear()
    ws = _sikre_enkel_fane_med_header(sh, VURDERINGER_FANE, VURDERINGER_HEADER2)
    rader = ws.get_all_values()
    resultat = []
    for krit in kriterier:
        rad_nr, rad = _finn_vurdering_rad(rader, butikk, jurymedlem, krit)
        rå_score = rad[4] if rad and len(rad) > 4 else None
        rå_kommentar = rad[5] if rad and len(rad) > 5 else ""
        resultat.append({
            "kriterium": krit,
            "fane": VURDERINGER_FANE,
            "celle": f"E{rad_nr}" if rad_nr else "(ingen rad ennå)",
            "rad_nr": rad_nr,
            "rå_score": rå_score,
            "rå_score_type": type(rå_score).__name__,
            "rå_kommentar": rå_kommentar,
            "normalisert_score": normalize_score(rå_score),
        })
    return resultat


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
    tidsstempel = naa_norsk().strftime("%Y-%m-%d %H:%M")
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
    tidsstempel = naa_norsk().strftime("%Y%m%d-%H%M%S")
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


def migrer_vurderinger_til_farget_fane(sh):
    """Flytter alt som står i "Vurderinger"-loggen inn i den fargede fanen
    (FASE2_FANE) – nødvendig etter at appen byttet fra å VISE loggen til å
    vise/redigere den fargede fanen igjen, slik at ingenting fra loggen
    "forsvinner" fra det jury faktisk ser. Tar sikkerhetskopi av ALT først.
    Bruker samme offisiell_celleverdi-regel som vanlig lagring (snitt hvis
    flere deler et kriterium). Returnerer en oppsummering med antall celler
    skrevet og eventuelle feil (f.eks. en butikk eller et kriterium i loggen
    som ikke lenger finnes i den fargede fanen)."""
    backup_navn = sikkerhetskopier_alle_faner(sh)
    alle = read_vurderinger(sh)
    gruppert = grupper_vurderinger(alle)
    fagfelt_for_kriterium = {r["kriterium"]: r["fagfelt"] for r in alle}

    per_butikk = {}
    for (butikk, kriterium), oppforinger in gruppert.items():
        verdi, notat = offisiell_celleverdi(oppforinger)
        if verdi is None:
            continue
        per_butikk.setdefault(butikk, []).append((fagfelt_for_kriterium.get(kriterium, ""), kriterium, verdi, notat))

    antall_skrevet, butikker_skrevet, feilet = 0, 0, []
    for butikk, jobb in per_butikk.items():
        try:
            celler = skriv_mange_til_farget_fane(sh, butikk, jobb)
            antall_skrevet += len(celler)
            butikker_skrevet += 1
        except Exception as e:
            feilet.append(f"«{butikk}»: {e}")

    return {
        "backup": backup_navn, "antall_skrevet": antall_skrevet, "antall_butikker": butikker_skrevet,
        "feilet": feilet,
        "detaljer": f"{antall_skrevet} celler skrevet til «{FASE2_FANE}» fordelt på {butikker_skrevet} butikker." + (f" {len(feilet)} feilet." if feilet else ""),
    }


@st.cache_data(ttl=30, show_spinner=False)
def fane_oversikt(_sh):
    """Lister ALLE faner i regnearket med en kort forklaring på hva appen
    bruker den til (eller ikke) – til Innstillinger, slik at det alltid er
    synlig nøyaktig hvilken fane som er aktiv kontra en gammel levning.
    Rører ingenting, kun lesing.

    Mellomlagret (var UCACHET) – denne gjør et eget metadata-kall
    (sh.worksheets()) som gjentas på HVER rerun av Innstillinger, og
    Innstillinger har mange knapper som hver trigger en full rerun. Lagt til
    etter at flere admin-handlinger rett etter hverandre (f.eks. å godkjenne
    3 veiledningstekster på rad) traff Google sin lesekvote. Handlinger som
    faktisk ENDRER fane-lista (arkivering, ombytting, orphan-migrering,
    oppretting av Fase 2) tømmer denne cachen eksplisitt etterpå, så admin
    ser oppdatert status med én gang – se kall til fane_oversikt.clear() i
    pages/innstillinger.py."""
    sh = _sh
    kjente = {
        FASE2_FANE: ("AKTIV", f"Appen leser og skriver hit – score som tall, kommentar som celle-notat."),
        FASE1_FANE: ("I bruk", "Kilde til butikklisten (Butikk/Klasse/Bransje/URL) – aldri skrevet til."),
        VURDERINGER_FANE: ("Logg", "Oppdateres ved hver lagring – IKKE det som vises i skjemaet."),
        GENERELLE_KOMMENTARER_FANE: ("Logg", "Generelle butikk-kommentarer per jurymedlem."),
        KOMMENTARER_FANE: ("Gammel logg", "Fra en tidligere modell – ikke lenger lest eller skrevet."),
        "Jury": ("I bruk", "Jurymedlemmer og kriterietildeling."),
        "Kriterier": ("I bruk", "Kriterietekster og skalaforklaringer."),
        "Veiledning": ("I bruk", "Veiledningstekst vist på Vurdering-siden."),
        "Faser": ("I bruk", "Fasestatus/-tidslinje."),
        FINALE_SNAPSHOT_FANE: ("I bruk", "Finale-lås – kun til stede hvis finalen er låst."),
    }
    resultat = []
    for ws in sh.worksheets():
        navn = ws.title
        if navn in kjente:
            status, forklaring = kjente[navn]
        elif navn.startswith("ARKIV – "):
            status, forklaring = ("Arkivert", "Allerede merket som arkiv.")
        elif navn.startswith("Backup_"):
            status, forklaring = ("Sikkerhetskopi", "Automatisk sikkerhetskopi, aldri rørt av appen.")
        else:
            status, forklaring = ("Ukjent", "Ikke brukt av appen i dagens modell – kandidat for arkiv-merking.")
        resultat.append({"navn": navn, "status": status, "forklaring": forklaring, "kan_arkiveres": status == "Ukjent"})
    return resultat


def merk_som_arkiv(sh, fane_navn):
    """Gir fanen prefikset «ARKIV – » i tittelen OG flytter den sist blant
    fanene – endrer INGENTING annet (ingen data, ingen formatering, slettes
    ikke). Kalles kun fra Innstillinger, kun for faner fane_oversikt() selv
    har merket som "Ukjent" – rører aldri en fane appen faktisk bruker."""
    if fane_navn.startswith("ARKIV – "):
        return fane_navn
    ws = sh.worksheet(fane_navn)
    nytt_navn = f"ARKIV – {fane_navn}"[:99]
    ws.update_title(nytt_navn)
    flytt_fane_til_slutt(sh, nytt_navn)
    return nytt_navn


def flytt_fane_til_slutt(sh, fane_navn):
    """Flytter fanen til siste posisjon blant fanene i regnearket – endrer
    kun rekkefølgen, ingen data/formatering."""
    ws = sh.worksheet(fane_navn)
    siste_indeks = len(sh.worksheets())  # Sheets API klemmer til faktisk siste plass uansett
    ws.spreadsheet.batch_update({"requests": [{
        "updateSheetProperties": {"properties": {"sheetId": ws.id, "index": siste_indeks}, "fields": "index"}
    }]})


def flytt_fane_til_forst(sh, fane_navn):
    """Flytter fanen til FØRSTE posisjon – brukt til å gi den aktive fanen
    («Rangering ekspertvurdering») en tydelig, fremtredende plass."""
    ws = sh.worksheet(fane_navn)
    ws.spreadsheet.batch_update({"requests": [{
        "updateSheetProperties": {"properties": {"sheetId": ws.id, "index": 0}, "fields": "index"}
    }]})


def sjekk_gammel_fane_for_orphan_data(sh, gammel_fane_navn):
    """Sjekker om en fane med dette navnet finnes SOM EN EGEN FANE (adskilt
    fra FASE1_FANE/FASE2_FANE) og i så fall om den inneholder kriterie-
    scorer som IKKE finnes i «Vurderinger»-loggen for noe jurymedlem ennå –
    altså data som ville forsvinne fra det jury faktisk ser hvis fanen ble
    arkivert/ignorert. Rører INGENTING, kun lesing. Returnerer None hvis
    fanen ikke finnes (ingenting å bekymre seg for)."""
    if gammel_fane_navn in (FASE1_FANE, FASE2_FANE):
        return None
    try:
        ws = sh.worksheet(gammel_fane_navn)
    except gspread.WorksheetNotFound:
        return None

    grunn, krit, _ = _header_data(ws)
    butikker_i_fane, _ = _les_butikkliste(ws, grunn)
    rader = ws.get_all_values()
    dekket = {(r["butikk"], r["kriterium"]) for r in read_vurderinger(sh)}

    orphans = []
    for navn, info in butikker_i_fane.items():
        rad_nr = info["rad"]
        if rad_nr > len(rader):
            continue
        rad = rader[rad_nr - 1]
        for (fagfelt, kriterium), kol in krit.items():
            if len(rad) >= kol and rad[kol - 1] and (navn, kriterium) not in dekket:
                orphans.append({"butikk": navn, "fagfelt": fagfelt, "kriterium": kriterium, "rå_verdi": rad[kol - 1]})
    return {"fane": gammel_fane_navn, "antall_butikker_i_fane": len(butikker_i_fane), "orphans": orphans}


def migrer_orphan_fane(sh, gammel_fane_navn):
    """Flytter orphan-dataen sjekk_gammel_fane_for_orphan_data() fant inn i
    BÅDE «Vurderinger»-loggen (jurymedlem="Ukjent (migrert fra <fane>)") OG
    den aktive fargede fanen – bruker samme offisiell_celleverdi-regel som
    vanlig lagring. Tar sikkerhetskopi av ALT først. Rører aldri den gamle
    fanen selv (den kan arkiveres separat med merk_som_arkiv etterpå)."""
    resultat = sjekk_gammel_fane_for_orphan_data(sh, gammel_fane_navn)
    if not resultat or not resultat["orphans"]:
        return {"backup": [], "antall_migrert": 0, "antall_butikker": 0, "feilet": []}

    backup_navn = sikkerhetskopier_alle_faner(sh)
    tidsstempel = naa_norsk().strftime("%Y-%m-%d %H:%M")
    jurymedlem_merke = f"Ukjent (migrert fra {gammel_fane_navn})"
    for o in resultat["orphans"]:
        upsert_vurdering(sh, o["butikk"], jurymedlem_merke, o["fagfelt"], o["kriterium"], o["rå_verdi"], "")

    alle = read_vurderinger(sh)
    gruppert = grupper_vurderinger(alle)
    per_butikk = {}
    for o in resultat["orphans"]:
        verdi, notat = offisiell_celleverdi(gruppert.get((o["butikk"], o["kriterium"]), []))
        if verdi is not None:
            per_butikk.setdefault(o["butikk"], []).append((o["fagfelt"], o["kriterium"], verdi, notat))
    feilet = []
    antall_butikker_ok = 0
    for butikk, jobb in per_butikk.items():
        try:
            skriv_mange_til_farget_fane(sh, butikk, jobb)
            antall_butikker_ok += 1
        except Exception as e:
            # Data er allerede trygt i Vurderinger-loggen uansett (se over) –
            # en butikk som ikke lenger finnes i den aktive fargede fanen
            # skal ikke få HELE migreringen til å krasje og miste resten.
            feilet.append(f"«{butikk}»: {e}")

    return {
        "backup": backup_navn, "antall_migrert": len(resultat["orphans"]), "antall_butikker": antall_butikker_ok,
        "feilet": feilet,
    }


def konverter_scorer_til_tall(sh):
    """Konverterer eksisterende TEKST-scorer («5») til ekte tall, i BÅDE den
    fargede fanen og «Vurderinger»-loggen. Idempotent og trygt å kjøre flere
    ganger – en celle som allerede er et tall skrives bare tilbake uendret.
    IKKE_VURDERT-teksten røres aldri. Tar sikkerhetskopi først."""
    backup_navn = sikkerhetskopier_alle_faner(sh)

    ws = _sikre_fase2_fane(sh)
    grunn, krit, _ = _header_data(ws)
    rader = ws.get_all_values()
    oppdateringer = []
    for r in range(FORSTE_DATARAD, len(rader) + 1):
        rad = rader[r - 1]
        for (_, _), kol in krit.items():
            if len(rad) >= kol and rad[kol - 1]:
                verdi = normalize_score(rad[kol - 1])
                if isinstance(verdi, (int, float)):
                    oppdateringer.append({"range": gspread.utils.rowcol_to_a1(r, kol), "values": [[verdi]]})
    if oppdateringer:
        ws.batch_update(oppdateringer, value_input_option="USER_ENTERED")
    _rå_formatert.clear()
    read_ratings.clear()

    ws2 = _sikre_enkel_fane_med_header(sh, VURDERINGER_FANE, VURDERINGER_HEADER2)
    rader2 = ws2.get_all_values()
    oppdateringer2 = []
    for i, rad in enumerate(rader2[1:] if len(rader2) > 1 else [], start=2):
        if len(rad) >= 5 and rad[4]:
            verdi = normalize_score(rad[4])
            if isinstance(verdi, (int, float)):
                oppdateringer2.append({"range": f"E{i}", "values": [[verdi]]})
    if oppdateringer2:
        ws2.batch_update(oppdateringer2, value_input_option="USER_ENTERED")
    read_vurderinger.clear()

    return {"backup": backup_navn, "antall_farget_fane": len(oppdateringer), "antall_vurderinger": len(oppdateringer2)}


def nullstill_vurderinger(sh):
    """Nullstiller ALT fra en vurderingsrunde, til bruk rett før en ny fase
    starter helt fra bunnen: tømmer kriteriecellene OG celle-notatene for
    alle butikkrader i FASE2_FANE, og fjerner alle datarader (header
    beholdes) i VURDERINGER_FANE og GENERELLE_KOMMENTARER_FANE. Rører
    ALDRI jury, kriterier, fordeling, veiledning eller faser.

    NB: «Kommentarer»-fanen er BEVISST ikke med her – den er en LIVE
    QUERY-formelvisning av «Vurderinger» (se
    sett_opp_kommentarer_som_formelvisning), ikke egne rader lenger. Den
    viser seg selv tom automatisk når «Vurderinger» tømmes – å kjøre
    ws.clear() på den ville tvert imot ha ØDELAGT selve formelen.

    Tar sikkerhetskopi av alt først."""
    backup_navn = sikkerhetskopier_alle_faner(sh)
    resultat = {
        "backup": backup_navn, "fase2_celler": 0, "fase2_notater": 0,
        "vurderinger_rader": 0, "generelle_rader": 0,
    }

    try:
        ws = sh.worksheet(FASE2_FANE)
    except gspread.WorksheetNotFound:
        ws = None
    if ws:
        grunn, krit, _ = _header_data(ws)
        kol_butikk = grunn.get("Butikk")
        rader = ws.get_all_values()
        oppdateringer, notat_celler = [], []
        for r in range(FORSTE_DATARAD, len(rader) + 1):
            rad = rader[r - 1]
            navn = rad[kol_butikk - 1].strip() if kol_butikk and len(rad) >= kol_butikk else ""
            if not navn:
                continue
            for (_, _), kol in krit.items():
                celle = gspread.utils.rowcol_to_a1(r, kol)
                if len(rad) >= kol and rad[kol - 1]:
                    oppdateringer.append({"range": celle, "values": [[""]]})
                    resultat["fase2_celler"] += 1
                notat_celler.append(celle)
        if oppdateringer:
            ws.batch_update(oppdateringer)
        if notat_celler:
            try:
                ws.update_notes({c: "" for c in notat_celler})
                resultat["fase2_notater"] = len(notat_celler)
            except Exception:
                pass  # notater er en bekvemmelighet – skal aldri blokkere selve nullstillingen
        _rå_formatert.clear()
        read_ratings.clear()

    for fane_navn, nokkel in [(VURDERINGER_FANE, "vurderinger_rader"), (GENERELLE_KOMMENTARER_FANE, "generelle_rader")]:
        try:
            ws2 = sh.worksheet(fane_navn)
        except gspread.WorksheetNotFound:
            continue
        rader2 = ws2.get_all_values()
        resultat[nokkel] = max(0, len(rader2) - 1)
        header = rader2[0] if rader2 else []
        ws2.clear()
        if header:
            ws2.update([header], range_name=f"A1:{gspread.utils.rowcol_to_a1(1, len(header))}")

    read_vurderinger.clear()
    read_generelle_kommentarer.clear()
    read_kommentarer.clear()
    return resultat


def fjern_formatering_fra_rad(sh, fane_navn, fra_rad):
    """Fjerner ALL celleformatering (bakgrunnsfarge, skrift, kantlinjer osv.)
    fra og med gitt rad og ut til fanens siste rad/kolonne – rører ALDRI
    selve celleverdiene eller notater. Bruker en rå repeatCell-forespørsel
    med fields="userEnteredFormat" – ws.format() kan KUN sette formatering
    til noe spesifikt, ikke nullstille den (se gspread sin batch_format(),
    som bygger fields ut fra nøklene i dict-en du gir den – en tom dict gir
    en tom, ugyldig feltmaske). Tar sikkerhetskopi først.

    startRowIndex er 0-indeksert i Sheets API (derfor fra_rad - 1); å
    utelate endRowIndex/startColumnIndex/endColumnIndex betyr "til slutten
    av fanen i den retningen", per API-konvensjon."""
    backup_navn = sikkerhetskopier_alle_faner(sh)
    ws = sh.worksheet(fane_navn)
    ws.spreadsheet.batch_update({
        "requests": [{
            "repeatCell": {
                "range": {"sheetId": ws.id, "startRowIndex": fra_rad - 1},
                "cell": {"userEnteredFormat": {}},
                "fields": "userEnteredFormat",
            }
        }]
    })
    _rå_formatert.clear()
    return {"backup": backup_navn, "fane": fane_navn, "fra_rad": fra_rad}


def ensrett_butikkrader(sh, fane_navn, mal_rad, fra_rad, til_rad):
    """Gjør butikkradene (fra_rad–til_rad) visuelt like en MAL-rad (typisk
    en butikkrad du vet ser riktig ut) – kopierer celleformatering (skrift,
    størrelse, bakgrunnsfarge, kantlinjer, justering) OG radhøyde dit.
    Rører ALDRI selve celleVERDIENE – kun formatering/dimensjoner. Bruker
    gspread sin copy_range() med paste_type=PASTE_FORMAT (samme mekanisme
    som å kopiere én rad og lime inn «kun formatering» over et større
    område i Sheets sitt brukergrensesnitt). Tar sikkerhetskopi først.

    Radhøyde kopieres som et eget steg (CopyPasteRequest dekker kun
    celleformatering, ikke rad-/kolonnedimensjoner) – hvis mal-radens høyde
    ikke er eksplisitt satt (dvs. den bruker fanens standardhøyde), hoppes
    dette steget bare over, siden alt da allerede er likt."""
    backup_navn = sikkerhetskopier_alle_faner(sh)
    ws = sh.worksheet(fane_navn)
    ws.copy_range(f"{mal_rad}:{mal_rad}", f"{fra_rad}:{til_rad}", paste_type=gspread.utils.PasteType.format)

    radhoyde_satt = False
    try:
        meta = sh.fetch_sheet_metadata(params={
            "ranges": [f"'{fane_navn}'!A{mal_rad}"],
            "fields": "sheets.data.rowMetadata",
            "includeGridData": "true",
        })
        pixel_size = meta["sheets"][0]["data"][0]["rowMetadata"][0].get("pixelSize")
    except Exception:
        pixel_size = None
    if pixel_size:
        ws.spreadsheet.batch_update({"requests": [{
            "updateDimensionProperties": {
                "range": {"sheetId": ws.id, "dimension": "ROWS", "startIndex": fra_rad - 1, "endIndex": til_rad},
                "properties": {"pixelSize": pixel_size},
                "fields": "pixelSize",
            }
        }]})
        radhoyde_satt = True

    _rå_formatert.clear()
    return {"backup": backup_navn, "fane": fane_navn, "mal_rad": mal_rad, "fra_rad": fra_rad, "til_rad": til_rad, "radhoyde_satt": radhoyde_satt}


def ensrett_url_lenker(sh, fane_navn, fra_rad, til_rad):
    """Skriver om URL-kolonnen til formelen =HYPERLINK("url";"Besøk →") for
    alle rader i intervallet som faktisk har en URL (enten som ren tekst
    eller en eksisterende HYPERLINK-formel) – endrer ALDRI selve
    nettadressen, kun hvordan den vises. Rader uten URL hoppes over. Tar
    sikkerhetskopi først."""
    backup_navn = sikkerhetskopier_alle_faner(sh)
    ws = sh.worksheet(fane_navn)
    grunn, _, _ = _header_data(ws)
    kol_url = grunn.get("URL")
    if not kol_url:
        return {"backup": backup_navn, "antall": 0, "feil": "Fant ingen «URL»-kolonne."}

    formler = ws.get_all_values(value_render_option="FORMULA")
    oppdateringer = []
    for r in range(fra_rad, til_rad + 1):
        if r > len(formler):
            continue
        rad = formler[r - 1]
        rå = rad[kol_url - 1] if len(rad) >= kol_url else ""
        url = _uthent_url(rå)
        if url:
            celle = gspread.utils.rowcol_to_a1(r, kol_url)
            oppdateringer.append({"range": celle, "values": [[f'=HYPERLINK("{url}";"Besøk →")']]})

    if oppdateringer:
        ws.batch_update(oppdateringer, value_input_option="USER_ENTERED")
    _rå_formatert.clear()
    _rå_formel.clear()
    read_ratings.clear()
    return {"backup": backup_navn, "antall": len(oppdateringer)}


def finn_tomme_butikkrader(sh, fane_navn, fra_rad, til_rad):
    """Kun lesing: lister rader i intervallet der Butikk-kolonnen er tom –
    til bruk for å bekrefte at det ikke står igjen tomme rader blant
    butikkradene."""
    ws = sh.worksheet(fane_navn)
    grunn, _, _ = _header_data(ws)
    kol_butikk = grunn.get("Butikk")
    if not kol_butikk:
        return []
    rader = ws.get_all_values()
    tomme = []
    for r in range(fra_rad, til_rad + 1):
        if r > len(rader):
            tomme.append(r)
            continue
        rad = rader[r - 1]
        navn = rad[kol_butikk - 1].strip() if len(rad) >= kol_butikk else ""
        if not navn:
            tomme.append(r)
    return tomme
