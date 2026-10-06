"""Jury- og kriterielogikk: hvem vurderer hva. Kriterier-fanen er ENESTE
kilde til kriterier i appen (erstatter den tidligere hardkodede lista i
data.py, som nå kun brukes til å SÅ fanen første gang). Jury-fanen styrer
hvilke kriterier hvert jurymedlem er tildelt – ikke lenger ett helt fagfelt
hver, men en fri avkrysning per kriterium.

Begge faner bygges med samme grupperte, fargede header-stil som Rangering-
fanene (se sheets._bygg_gruppert_header) – det er en bevisst, avtalt
UNNTAK fra "ikke bygg struktur med kode", siden dette er helt nye faner uten
noe eksisterende Excel-oppsett å bevare.
"""

from collections import defaultdict

import gspread
import streamlit as st

from sheets import FORSTE_DATARAD, _bygg_gruppert_header, _header_data, hent_eller_lag_fane

KRITERIER_FANE = "Kriterier"
JURY_FANE = "Jury"
VEILEDNING_FANE = "Veiledning"
FASER_FANE = "Faser"

KRITERIER_HEADER = ["Fagfelt", "Kriterium", "Kort beskrivelse", "Utfyllende forklaring", "Skala 1", "Skala 3", "Skala 5", "Eksempler", "Fase", "Aktiv"]
JURY_GRUNNKOLONNER = ["Navn", "E-post", "Farge"]
VEILEDNING_HEADER = ["Overskrift", "Tekst"]
FASER_HEADER = ["Nummer", "Navn", "Beskrivelse", "Aktiv"]

# ─────────────────────────────────────────────
# Kriterier
# ─────────────────────────────────────────────
_STANDARD_KRITERIER_SEED = [
    # (fagfelt, kriterium, kort, faser)
    ("Førsteinntrykk", "Opplevelse: Bildebruk, beskrivelser o.l.", "Førsteinntrykk av butikkens visuelle presentasjon.", "Fase 2,Fase 3"),
    ("Førsteinntrykk", "Navigasjon / UX", "Hvor lett det er å finne fram i butikken.", "Fase 2,Fase 3"),
    ("Førsteinntrykk", "Søk: auto-korrektur, synonymer, utlisting, forslag", "Kvaliteten på søkefunksjonen.", "Fase 2,Fase 3"),
    ("Kundeservice & Tilgjengelighet", "Lett tilgjengelig info om levering, retur og kjøpsvilkår", "Hvor lett kjøpsvilkår er å finne.", "Fase 2,Fase 3"),
    ("Kundeservice & Tilgjengelighet", "Google/Trustpilot/andre åpne løsninger for kundetilfredshet", "Omdømme på åpne vurderingstjenester.", "Fase 2,Fase 3"),
    ("Kundeservice & Tilgjengelighet", "Tilgjengelighet, åpningstider, kanaler, responstid", "Hvor lett kundeservice er å nå.", "Fase 2,Fase 3"),
    ("Kundeservice & Tilgjengelighet", "Bærekraft", "Butikkens arbeid med bærekraft.", "Fase 2,Fase 3"),
    ("Kjøp/inspirasjon/personalisering", "Kassen: Levering, betaling", "Kjøpsopplevelsen i kassen.", "Fase 2,Fase 3"),
    ("Kjøp/inspirasjon/personalisering", "Inspirasjon", "Hvor inspirerende butikken er.", "Fase 2,Fase 3"),
    ("Kjøp/inspirasjon/personalisering", "Mersalg/anbefalinger/personalisering", "Bruk av mersalg og personalisering.", "Fase 2,Fase 3"),
    ("Markedsføring/kundedialog", "Bruk av SoMe", "Aktivitet i sosiale medier.", "Fase 2,Fase 3"),
    ("Markedsføring/kundedialog", "Betalt og organisk synlighet", "Synlighet i søk/annonsering.", "Fase 2,Fase 3"),
    ("Markedsføring/kundedialog", "E-post", "Bruk av e-postmarkedsføring.", "Fase 2,Fase 3"),
    ("Innovasjon", "Innovative løsninger", "Nytenkende løsninger i butikken.", "Fase 2,Fase 3"),
    ("Innovasjon", "Adopsjon av nye teknologier for styrke konkurransekraft", "Bruk av ny teknologi.", "Fase 2,Fase 3"),
    ("Innovasjon", "Kommersielt håndverk", "Generelt kommersielt håndverk.", "Fase 2,Fase 3"),
    ("Innovasjon", "Agentic commerce",
     "Hvor godt butikken er rustet for at AI-assistenter og shoppingagenter kan finne, sammenligne og kjøpe produkter på vegne av kunden.",
     "Fase 3"),
]
_AGENTIC_UTFYLLENDE = (
    "Agentic commerce betyr at AI-agenter (f.eks. i ChatGPT, Gemini eller Perplexity) søker etter produkter, "
    "sammenligner tilbud og i økende grad gjennomfører kjøpet for kunden. Butikker som stiller sterkt, har: "
    "god og strukturert produktdata (komplette produktfeeder, schema.org-merking), maskinlesbar informasjon om "
    "pris, lagerstatus, levering og retur, synlighet i AI-søk, og eventuelt støtte for nye protokoller for "
    "agentkjøp eller en egen AI-shoppingassistent."
)
_AGENTIC_SKALA = {
    "Skala 1": "Lite strukturert data, vanskelig for agenter å lese.",
    "Skala 3": "Godt strukturert produktdata og grunnleggende synlighet.",
    "Skala 5": "Tydelig tilrettelagt for agenter, med strukturert data, synlighet i AI-søk og/eller agentbasert kjøp eller assistent.",
}
_GENERISK_SKALA = {
    "Skala 1": "Svak – mangler i stor grad eller fungerer dårlig.",
    "Skala 3": "Middels – til stede, men med tydelig forbedringspotensial.",
    "Skala 5": "Utmerket – blant de beste i konkurransen på dette punktet.",
}


def _seed_kriterier_rader():
    rader = []
    for fagfelt, kriterium, kort, faser in _STANDARD_KRITERIER_SEED:
        if kriterium == "Agentic commerce":
            rader.append([fagfelt, kriterium, kort, _AGENTIC_UTFYLLENDE, _AGENTIC_SKALA["Skala 1"], _AGENTIC_SKALA["Skala 3"], _AGENTIC_SKALA["Skala 5"], "", faser, "Ja"])
        else:
            rader.append([fagfelt, kriterium, kort, "", _GENERISK_SKALA["Skala 1"], _GENERISK_SKALA["Skala 3"], _GENERISK_SKALA["Skala 5"], "", faser, "Ja"])
    return rader


def sikre_kriterier_fane(sh):
    ws = hent_eller_lag_fane(sh, KRITERIER_FANE, KRITERIER_HEADER)
    if len(ws.get_all_values()) <= 1:
        ws.append_rows(_seed_kriterier_rader())
        try:
            ws.format("A1:J1", {"backgroundColor": {"red": 0.125, "green": 0.219, "blue": 0.392}, "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}})
            ws.freeze(rows=1)
        except Exception:
            pass
        read_criteria.clear()
    return ws


@st.cache_data(ttl=60, show_spinner=False)
def read_criteria(_sh):
    """Returnerer ALLE kriterierader (inkl. inaktive – admin-UI trenger dem).
    Hver rad: {fagfelt, kriterium, kort, utfyllende, skala1, skala3, skala5,
    eksempler, faser: [liste], aktiv: bool}."""
    ws = sikre_kriterier_fane(_sh)
    rader = ws.get_all_records()
    resultat = []
    for i, r in enumerate(rader, start=2):
        if not str(r.get("Kriterium", "")).strip():
            continue
        resultat.append({
            "rad": i,
            "fagfelt": str(r.get("Fagfelt", "")).strip(),
            "kriterium": str(r.get("Kriterium", "")).strip(),
            "kort": str(r.get("Kort beskrivelse", "")).strip(),
            "utfyllende": str(r.get("Utfyllende forklaring", "")).strip(),
            "skala1": str(r.get("Skala 1", "")).strip(),
            "skala3": str(r.get("Skala 3", "")).strip(),
            "skala5": str(r.get("Skala 5", "")).strip(),
            "eksempler": str(r.get("Eksempler", "")).strip(),
            "faser": [f.strip() for f in str(r.get("Fase", "")).split(",") if f.strip()],
            "aktiv": str(r.get("Aktiv", "")).strip().lower() == "ja",
        })
    return resultat


def aktive_kriterier(alle_kriterier, fase: str = None):
    return [k for k in alle_kriterier if k["aktiv"] and (fase is None or fase in k["faser"])]


def fagfelt_liste(kriterier):
    return list(dict.fromkeys(k["fagfelt"] for k in kriterier))


def kriterier_per_fagfelt(kriterier):
    d = defaultdict(list)
    for k in kriterier:
        d[k["fagfelt"]].append(k["kriterium"])
    return dict(d)


def add_criterion(sh, fagfelt, kriterium, kort, utfyllende, skala1, skala3, skala5, eksempler, faser: list):
    """Legger til én rad i Kriterier-fanen. Setter IKKE inn kolonne i
    Rangering-fanene selv – det gjøres eksplisitt via
    sheets.legg_til_kriterium_kolonne() etter bekreftelse i grensesnittet
    (se pages/innstillinger.py), siden det er en strukturendring."""
    ws = sikre_kriterier_fane(sh)
    ws.append_row([fagfelt, kriterium, kort, utfyllende, skala1, skala3, skala5, eksempler, ",".join(faser), "Ja"])
    read_criteria.clear()


def deaktiver_kriterium(sh, kriterium_tekst):
    ws = sikre_kriterier_fane(sh)
    rader = ws.get_all_values()
    for i, rad in enumerate(rader[1:], start=2):
        if len(rad) >= 2 and rad[1] == kriterium_tekst:
            ws.update([["Nei"]], range_name=f"J{i}")
            read_criteria.clear()
            return True
    return False


def oppdater_kriterium(sh, kriterium_tekst, **felter):
    """felter: valgfrie nøkler kort/utfyllende/skala1/skala3/skala5/eksempler."""
    kolonne_for_felt = {"kort": "C", "utfyllende": "D", "skala1": "E", "skala3": "F", "skala5": "G", "eksempler": "H"}
    ws = sikre_kriterier_fane(sh)
    rader = ws.get_all_values()
    for i, rad in enumerate(rader[1:], start=2):
        if len(rad) >= 2 and rad[1] == kriterium_tekst:
            oppdateringer = [{"range": f"{kolonne_for_felt[felt]}{i}", "values": [[verdi]]} for felt, verdi in felter.items() if felt in kolonne_for_felt]
            if oppdateringer:
                ws.batch_update(oppdateringer)
                read_criteria.clear()
            return True
    return False


# ─────────────────────────────────────────────
# Jury – hvem er tildelt hvilke kriterier
# ─────────────────────────────────────────────
def sikre_jury_fane(sh):
    """Oppretter Jury-fanen med gruppert, farget header (som Rangering-
    fanene) hvis den ikke finnes – bygget fra de AKTIVE kriteriene."""
    try:
        return sh.worksheet(JURY_FANE)
    except gspread.WorksheetNotFound:
        kriterier = aktive_kriterier(read_criteria(sh), fase="Fase 3")
        ws = _bygg_gruppert_header(sh, JURY_FANE, JURY_GRUNNKOLONNER, kriterier_per_fagfelt(kriterier), checkbox=True)
        return ws


@st.cache_data(ttl=30, show_spinner=False)
def read_jury(_sh):
    """{navn: {"epost":, "farge":, "kriterier": set(kriterium-tekst der boksen er avkrysset)}}."""
    ws = sikre_jury_fane(_sh)
    grunn, krit, _ = _header_data(ws, grunnkolonner=JURY_GRUNNKOLONNER)
    formatert = ws.get_all_values(combine_merged_cells=True)
    kol_navn, kol_epost, kol_farge = grunn.get("Navn"), grunn.get("E-post"), grunn.get("Farge")
    resultat = {}
    for r in range(FORSTE_DATARAD, len(formatert) + 1):
        rad = formatert[r - 1]
        navn = rad[kol_navn - 1].strip() if kol_navn and len(rad) >= kol_navn else ""
        if not navn:
            continue
        valgt = {kriterium for (fagfelt, kriterium), kol in krit.items() if len(rad) >= kol and str(rad[kol - 1]).strip().upper() in ("TRUE", "SANN", "JA", "X")}
        resultat[navn] = {
            "epost": rad[kol_epost - 1].strip() if kol_epost and len(rad) >= kol_epost else "",
            "farge": rad[kol_farge - 1].strip() if kol_farge and len(rad) >= kol_farge else "",
            "kriterier": valgt,
            "rad": r,
        }
    return resultat


def write_jury(sh, navn, kriterier_valgt: set, epost="", farge=""):
    """Oppretter raden for jurymedlemmet hvis den mangler, ellers oppdaterer
    kun DENNE radens celler – aldri resten av fanen. Finner cellene for
    Navn/E-post/Farge på overskriftene (ALDRI faste bokstaver), akkurat som
    kriterium-cellene."""
    ws = sikre_jury_fane(sh)
    grunn, krit, siste = _header_data(ws, grunnkolonner=JURY_GRUNNKOLONNER)
    jury = read_jury(sh)

    if navn in jury:
        rad_nr = jury[navn]["rad"]
    else:
        # IKKE len(ws.get_all_values())+1 – get_all_values() er PADDET til
        # arkets fulle rutenett (200 rader) uansett hvor mye som faktisk er
        # fylt ut, så det ga alltid rad 201 og en "exceeds grid limits"-feil
        # for enhver ny person. Finn i stedet den første virkelig TOMME
        # raden, basert på siste faktisk brukte rad blant eksisterende
        # jurymedlemmer.
        siste_brukte_rad = max((p["rad"] for p in jury.values()), default=FORSTE_DATARAD - 1)
        rad_nr = siste_brukte_rad + 1
        if rad_nr > ws.row_count:
            ws.add_rows(rad_nr - ws.row_count + 20)  # litt buffer for neste par personer også

    oppdateringer = []
    for kolonnenavn, verdi in [("Navn", navn), ("E-post", epost), ("Farge", farge)]:
        kol = grunn.get(kolonnenavn)
        if kol:
            oppdateringer.append({"range": gspread.utils.rowcol_to_a1(rad_nr, kol), "values": [[verdi]]})
    for (fagfelt, kriterium), kol in krit.items():
        a1 = gspread.utils.rowcol_to_a1(rad_nr, kol)
        oppdateringer.append({"range": a1, "values": [[kriterium in kriterier_valgt]]})

    if not oppdateringer:
        raise ValueError("Fant ingen kolonner å skrive til i Jury-fanen – sjekk at overskriftene i rad 1/2 ikke er endret manuelt.")
    ws.batch_update(oppdateringer, value_input_option="USER_ENTERED")
    read_jury.clear()


def slett_jurymedlem(sh, navn):
    """Fjerner jurymedlemmets RAD i Jury-fanen (deleteDimension – skyver
    radene under oppover). Rører ALDRI Rangering-fanene, så vurderinger
    personen har gjort der ligger urørt."""
    ws = sikre_jury_fane(sh)
    jury = read_jury(sh)
    if navn not in jury:
        return
    rad_nr = jury[navn]["rad"]
    ws.spreadsheet.batch_update({"requests": [{
        "deleteDimension": {"range": {"sheetId": ws.id, "dimension": "ROWS", "startIndex": rad_nr - 1, "endIndex": rad_nr}}
    }]})
    read_jury.clear()


def mine_kriterier(jury: dict, navn: str) -> set:
    return jury.get(navn, {}).get("kriterier", set())


def beskriv_tildeling(navn: str, jury: dict, kriterier_per_felt: dict) -> str:
    """«Innovasjon» hvis hele fagfeltet er tildelt, ellers «Kundeservice &
    Tilgjengelighet – 2 av 4 kriterier». Flere fagfelt skilt med «·»."""
    mine = mine_kriterier(jury, navn)
    if not mine:
        return ""
    deler = []
    for fagfelt, alle in kriterier_per_felt.items():
        mine_i_felt = [k for k in alle if k in mine]
        if not mine_i_felt:
            continue
        if len(mine_i_felt) == len(alle):
            deler.append(fagfelt)
        else:
            deler.append(f"{fagfelt} – {len(mine_i_felt)} av {len(alle)} kriterier")
    return " · ".join(deler)


# ─────────────────────────────────────────────
# Veiledning
# ─────────────────────────────────────────────
_VEILEDNING_SEED = [
    ["Vurder som en vanlig kunde", "Besøk butikken slik en vanlig kunde ville gjort – gjerne på både mobil og PC, siden opplevelsen ofte er ulik. Du trenger ikke handle noe for å vurdere."],
    ["Skalaen 1–5", "1 = svak, under forventet nivå for en nettbutikk i denne klassen. 3 = middels, fungerer greit men har tydelig forbedringspotensial. 5 = utmerket, blant de beste i konkurransen på dette punktet. Se også skala-forklaringen under hvert enkelt kriterium."],
    ["«Kan ikke vurdere»", "Brukes når kriteriet rett og slett ikke lar seg bedømme for denne butikken (f.eks. en funksjon som ikke finnes eller ikke er relevant for bransjen) – ikke som en snarvei når du er usikker. Da bruker du heller midten av skalaen og skriver hvorfor i kommentarfeltet."],
    ["Begrunnelse", "Skriv alltid en kort kommentar ved 1 eller 5 – det gjør resultatet lettere å etterprøve og diskutere i juryen. Ved 2–4 er det valgfritt, men ofte nyttig."],
    ["Inhabilitet", "Har du en tilknytning til butikken (ansatt, eier, nær relasjon, oppdrag for dem e.l.), skal du ikke vurdere den – meld fra til juryleder, så blir den omfordelt."],
]


@st.cache_data(ttl=120, show_spinner=False)
def read_veiledning(_sh):
    ws = hent_eller_lag_fane(_sh, VEILEDNING_FANE, VEILEDNING_HEADER)
    if len(ws.get_all_values()) <= 1:
        ws.append_rows(_VEILEDNING_SEED)
        read_veiledning.clear()
        return ws.get_all_records()
    return ws.get_all_records()


# ─────────────────────────────────────────────
# Faser
# ─────────────────────────────────────────────
_FASER_SEED = [
    [1, "Screening", "En AI-agent screener alle nominerte nettbutikker.", "Nei"],
    [2, "Juryvurdering", "Juryen vurderer butikkene.", "Nei"],
    [3, "Ekspertvurdering", "Jurymedlemmene vurderer kriteriene de er tildelt.", "Ja"],
    [4, "Testhandel", "Testkjøp, kundeservice, compliance og universell utforming.", "Nei"],
    [5, "Finale", "", "Nei"],
]


@st.cache_data(ttl=120, show_spinner=False)
def read_faser(_sh):
    ws = hent_eller_lag_fane(_sh, FASER_FANE, FASER_HEADER)
    if len(ws.get_all_values()) <= 1:
        ws.append_rows(_FASER_SEED)
        read_faser.clear()
        return [{"Nummer": r[0], "Navn": r[1], "Beskrivelse": r[2], "Aktiv": r[3]} for r in _FASER_SEED]
    return ws.get_all_records()


def aktiv_fase(faser: list):
    aktive = [f for f in faser if str(f.get("Aktiv", "")).strip().lower() == "ja"]
    if len(aktive) == 1:
        return aktive[0]
    return faser[0] if faser else None
