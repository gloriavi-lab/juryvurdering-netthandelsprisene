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

from sheets import (
    FASE2_FANE, FORSTE_DATARAD, _bygg_gruppert_header, _header_data, _header_data_cached, _rå_formatert,
    _rå_formatert_cached, hent_eller_lag_fane, read_ratings, sikkerhetskopier_alle_faner,
)

KRITERIER_FANE = "Kriterier"
JURY_FANE = "Jury"
VEILEDNING_FANE = "Veiledning"
FASER_FANE = "Faser"

KRITERIER_HEADER = ["Fagfelt", "Kriterium", "Kort beskrivelse", "Utfyllende forklaring", "Skala 1", "Skala 3", "Skala 5", "Eksempler", "Fase", "Aktiv"]
JURY_GRUNNKOLONNER = ["Navn", "E-post", "Farge"]
VEILEDNING_HEADER = ["Overskrift", "Tekst"]
FASER_HEADER = ["Fase", "Navn", "Beskrivelse", "Status", "Startdato", "Sluttdato"]
FASE_STATUSER = ["Fullført", "Pågår", "Kommende"]

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
     "Hvor lett en kunde som starter i en AI-assistent (ChatGPT, Gemini e.l.) finner frem til og handler i butikken.",
     "Fase 3"),
]
_AGENTIC_UTFYLLENDE = (
    "Stadig flere starter handelen sin i en AI-chatbot i stedet for et tradisjonelt søkemotor eller direkte på "
    "butikkens side. Dette kriteriet vurderer OVERGANGEN fra AI-assistenten til selve nettbutikken – ikke om "
    "butikken har en egen AI-assistent: Blir kunden henvist med en fungerende, direkte lenke til riktig produkt "
    "(ikke bare forsiden)? Stemmer pris, lagerstatus og produktinformasjon som AI-assistenten oppga med det "
    "kunden faktisk møter i butikken? Er det en god opplevelse å fullføre kjøpet derfra, uten unødvendige "
    "omveier? God, strukturert og oppdatert produktdata (f.eks. korrekte produktfeeder og schema.org-merking) "
    "gjør det lettere for AI-tjenester å finne og henvise riktig til butikken i utgangspunktet."
)
_AGENTIC_SKALA = {
    "Skala 1": "Vanskelig eller umulig å finne frem til riktig produkt ut fra det en AI-assistent anbefalte – f.eks. brutte lenker, feil pris/lagerstatus, eller ingen direkte vei til produktet.",
    "Skala 3": "Mulig å finne frem, men med friksjon – noe sprik mellom det AI-assistenten oppga og det kunden møter, eller en omstendelig vei til kjøp.",
    "Skala 5": "Sømløs overgang: kunden kommer direkte til riktig produkt med korrekt pris/lagerstatus, og kan fullføre kjøpet uten unødvendige omveier.",
}
_GENERISK_SKALA = {
    "Skala 1": "Svak – mangler i stor grad eller fungerer dårlig.",
    "Skala 3": "Middels – til stede, men med tydelig forbedringspotensial.",
    "Skala 5": "Utmerket – blant de beste i konkurransen på dette punktet.",
}


_UNIVERSELL_UTFORMING_UTFYLLENDE = (
    "Hvor godt nettbutikken er tilrettelagt for brukere med ulike behov (syn, hørsel, motorikk, kognisjon). "
    "WCAG 2.1 nivå AA er en nyttig referanse, men du trenger ikke være ekspert – prøv å navigere med kun "
    "tastatur, sjekk kontrast og tekststørrelse, og se om bilder har alt-tekst."
)

# Forslag til NYE kriterier (foreslått og delvis godkjent tidligere i
# prosjektet, men ALDRI faktisk skrevet inn i et allerede eksisterende,
# levende Kriterier-ark – _seed_kriterier_rader() under kjører kun når
# fanen opprettes helt fra bunnen). Brukes av Innstillinger til å tilby å
# legge dem til i et ark som allerede finnes, uten å gjette på andre
# endringer i kriterielisten.
FORESLATTE_TILLEGGSKRITERIER = [
    {
        "fagfelt": "Innovasjon", "kriterium": "Agentic commerce",
        "kort": "Hvor lett en kunde som starter i en AI-assistent (ChatGPT, Gemini e.l.) finner frem til og handler i butikken.",
        "utfyllende": _AGENTIC_UTFYLLENDE,
        "skala1": _AGENTIC_SKALA["Skala 1"], "skala3": _AGENTIC_SKALA["Skala 3"], "skala5": _AGENTIC_SKALA["Skala 5"],
        "eksempler": "", "faser": ["Fase 3"],
    },
    {
        "fagfelt": "Førsteinntrykk", "kriterium": "Universell utforming",
        "kort": "Hvor godt nettbutikken er tilrettelagt for brukere med ulike behov (syn, hørsel, motorikk, kognisjon).",
        "utfyllende": _UNIVERSELL_UTFORMING_UTFYLLENDE,
        "skala1": "Store hindringer for brukere med nedsatt funksjonsevne – f.eks. umulig å navigere med tastatur, manglende alt-tekst, dårlig kontrast.",
        "skala3": "Grunnleggende tilrettelagt, men med tydelige mangler (enkelte uklare kontraster, mangelfull alt-tekst eller navigasjon).",
        "skala5": "Godt tilrettelagt etter anerkjente retningslinjer (f.eks. WCAG 2.1 AA) – god kontrast, navigerbar med tastatur/skjermleser, beskrivende alt-tekst.",
        "eksempler": "", "faser": ["Fase 3"],
    },
]


def manglende_foreslatte_kriterier(alle_kriterier):
    """De av FORESLATTE_TILLEGGSKRITERIER som ikke allerede finnes (uansett
    aktiv/inaktiv) UNDER NØYAKTIG DET SAMME FAGFELTET i det faktiske,
    levende Kriterier-arket – matcher på (kriterium, fagfelt), ikke bare
    navn, slik at f.eks. «Universell utforming» fortsatt tilbys under det
    NYE fagfeltet (Førsteinntrykk) selv om et likelydende kriterium alt
    finnes under et annet, gammelt fagfelt (se finn_duplisert_kriterium)."""
    eksisterende = {(k["kriterium"], k["fagfelt"]) for k in alle_kriterier}
    return [f for f in FORESLATTE_TILLEGGSKRITERIER if (f["kriterium"], f["fagfelt"]) not in eksisterende]


def finn_duplisert_kriterium(alle_kriterier, kriterium_navn):
    """Returnerer det AKTIVE kriteriet med dette navnet hvis det finnes et
    ANNET sted enn fagfeltet FORESLATTE_TILLEGGSKRITERIER nå foreslår for
    samme navn – brukes til å tilby deaktivering i Innstillinger, slik at
    et kriterium ikke ender opp aktivt to steder samtidig etter at det er
    flyttet til et nytt fagfelt (f.eks. «Universell utforming» som nå
    foreslås under Førsteinntrykk i stedet for Kundeservice & Tilgjengelighet)."""
    nytt_forslag = next((f for f in FORESLATTE_TILLEGGSKRITERIER if f["kriterium"] == kriterium_navn), None)
    if not nytt_forslag:
        return None
    return next(
        (k for k in alle_kriterier if k["kriterium"] == kriterium_navn and k["aktiv"] and k["fagfelt"] != nytt_forslag["fagfelt"]),
        None,
    )


def manglende_kriterium_kolonner(sh, fane_navn, alle_kriterier, fase="Fase 3", grunnkolonner=None):
    """Aktive kriterier (i gitt fase) som IKKE har en tilsvarende kolonne i
    den gitte fanen ennå – oppdager/reparerer tilfeller der et kriterium
    ble lagt til i Kriterier-fanen (og kanskje i Rangering ekspertvurdering),
    men IKKE i Jury-fanen (reell bug: write_jury() skriver kun til kolonner
    som faktisk finnes, så en avkrysning for et slikt kriterium ble stille
    forkastet uten feilmelding – se Innstillinger)."""
    aktive = aktive_kriterier(alle_kriterier, fase=fase)
    try:
        ws = sh.worksheet(fane_navn)
    except gspread.WorksheetNotFound:
        return [(k["fagfelt"], k["kriterium"]) for k in aktive]
    _, krit_eksisterende, _ = _header_data(ws, grunnkolonner=grunnkolonner)
    return [(k["fagfelt"], k["kriterium"]) for k in aktive if (k["fagfelt"], k["kriterium"]) not in krit_eksisterende]


_KRITERIUM_OMDOPINGER = {
    "E-post": {
        "nytt_navn": "Kundeklubb, nyhetsbrev, e-post og SMS",
        "ny_kort": "Bruk av kundeklubb, nyhetsbrev, e-post og SMS i kundedialogen.",
    },
}


def manglende_kriterium_omdopinger(alle_kriterier):
    """{gammelt_navn: (fagfelt, nytt_navn, ny_kort, gammel_kort)} for
    kriterier som fortsatt heter/beskrives med det gamle, avtalte innholdet
    i det levende arket – fagfeltet LESES fra selve kriteriet (ikke
    hardkodet), slik at det ikke spiller noen rolle nøyaktig hvordan
    fagfelt-navnet er stavet i akkurat dette regnearket."""
    eksisterende = {k["kriterium"]: k for k in alle_kriterier}
    resultat = {}
    for gammelt, info in _KRITERIUM_OMDOPINGER.items():
        if gammelt not in eksisterende or info["nytt_navn"] in eksisterende:
            continue
        k = eksisterende[gammelt]
        if k["kriterium"] == info["nytt_navn"] and k["kort"] == info["ny_kort"]:
            continue  # alt er alt oppdatert
        resultat[gammelt] = (k["fagfelt"], info["nytt_navn"], info["ny_kort"], k["kort"])
    return resultat


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


@st.cache_data(ttl=600, show_spinner=False)
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


def omdop_kriterium(sh, fagfelt, gammelt_navn, nytt_navn, ny_kort=None):
    """Endrer et kriteriums NAVN (og valgfritt «Kort beskrivelse») overalt
    det brukes – Kriterier-fanens egen rad, kolonneoverskriften i
    FASE2_FANE («Rangering ekspertvurdering»), og kolonneoverskriften i
    Jury-fanen – UTEN å røre selve kolonnen/raden (posisjonen bevares),
    slik at eksisterende scorer, kommentarer og jury-tildelinger følger
    automatisk med (de er knyttet til CELLEN, ikke navnet). Tar
    sikkerhetskopi av alt først. Returnerer hva som faktisk ble funnet og
    endret, slik at admin-UI kan vise det tydelig i stedet for å anta at
    alle stedene fantes."""
    backup_navn = sikkerhetskopier_alle_faner(sh)
    endret = {"kriterier": False, "fase2": False, "jury": False}

    ws_krit = sikre_kriterier_fane(sh)
    rader = ws_krit.get_all_values()
    for i, rad in enumerate(rader[1:], start=2):
        if len(rad) >= 2 and rad[1] == gammelt_navn:
            ws_krit.update([[nytt_navn]], range_name=f"B{i}")
            if ny_kort:
                ws_krit.update([[ny_kort]], range_name=f"C{i}")
            endret["kriterier"] = True
            break
    read_criteria.clear()

    try:
        ws_fase2 = sh.worksheet(FASE2_FANE)
        _, krit_fase2, _ = _header_data(ws_fase2)
        kolonne = krit_fase2.get((fagfelt, gammelt_navn))
        if kolonne:
            ws_fase2.update([[nytt_navn]], range_name=gspread.utils.rowcol_to_a1(2, kolonne))
            endret["fase2"] = True
    except gspread.WorksheetNotFound:
        pass
    _header_data_cached.clear()
    _rå_formatert_cached.clear()
    read_ratings.clear()

    ws_jury = sikre_jury_fane(sh)
    _, krit_jury, _ = _header_data(ws_jury, grunnkolonner=JURY_GRUNNKOLONNER)
    kolonne_jury = krit_jury.get((fagfelt, gammelt_navn))
    if kolonne_jury:
        ws_jury.update([[nytt_navn]], range_name=gspread.utils.rowcol_to_a1(2, kolonne_jury))
        endret["jury"] = True
    _header_data_cached.clear()
    read_jury.clear()

    return {"backup": backup_navn, "endret": endret}


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


@st.cache_data(ttl=600, show_spinner=False)
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
    ["Vurder som en vanlig kunde", "Besøk butikken slik en vanlig kunde ville gjort. Test på mobil er primært og et krav – PC er en ekstra bonus, ikke et krav. Det er et krav at nettbutikken er mobiltilpasset; dårlig mobiltilpasning skal trekke ned vurderingen. Du trenger ikke handle noe for å vurdere."],
    ["Skalaen 1–5", "1 = svak, under forventet nivå for en nettbutikk i denne klassen. 3 = middels, fungerer greit men har tydelig forbedringspotensial. 5 = utmerket, blant de beste i konkurransen på dette punktet. Se også skala-forklaringen under hvert enkelt kriterium."],
    ["«Kan ikke vurdere»", "Brukes når kriteriet rett og slett ikke lar seg bedømme for denne butikken (f.eks. en funksjon som ikke finnes eller ikke er relevant for bransjen) – ikke som en snarvei når du er usikker. Da bruker du heller midten av skalaen og skriver hvorfor i kommentarfeltet."],
    ["Begrunnelse", "Skriv kommentar på alt du vurderer, slik at vi kan bruke kommentarene i arbeidet mot finalen."],
    ["Inhabilitet", "Har du en tilknytning til butikken (ansatt, eier, nær relasjon, oppdrag for dem e.l.), skal du ikke vurdere den – meld fra til oss."],
]


@st.cache_data(ttl=600, show_spinner=False)
def read_veiledning(_sh):
    ws = hent_eller_lag_fane(_sh, VEILEDNING_FANE, VEILEDNING_HEADER)
    if len(ws.get_all_values()) <= 1:
        ws.append_rows(_VEILEDNING_SEED)
        read_veiledning.clear()
        return ws.get_all_records()
    return ws.get_all_records()


# Oppdaterte tekster (avtalt i en senere runde enn da _VEILEDNING_SEED sist
# ble skrevet inn i et allerede eksisterende, levende Veiledning-ark –
# _VEILEDNING_SEED over kjører kun ved førstegangsoppretting). Samme
# overskrift-nøkler som _VEILEDNING_SEED – brukes til å tilby en oppdatering
# av eksisterende rader i Innstillinger, i stedet for å gjette på om
# admin vil ha dem overskrevet stille.
_VEILEDNING_OPPDATERINGER = {
    "Vurder som en vanlig kunde": _VEILEDNING_SEED[0][1],
    "Begrunnelse": _VEILEDNING_SEED[3][1],
    "Inhabilitet": _VEILEDNING_SEED[4][1],
}


def manglende_veiledning_oppdateringer(_sh):
    """De av _VEILEDNING_OPPDATERINGER som faktisk avviker fra teksten i det
    levende Veiledning-arket akkurat nå – {overskrift: (gammel, ny)}."""
    eksisterende = {r.get("Overskrift"): r.get("Tekst", "") for r in read_veiledning(_sh)}
    return {
        overskrift: (eksisterende.get(overskrift, "(finnes ikke ennå)"), ny)
        for overskrift, ny in _VEILEDNING_OPPDATERINGER.items()
        if eksisterende.get(overskrift, "") != ny
    }


def oppdater_veiledning_rad(sh, overskrift, ny_tekst):
    """Oppdaterer TEKST-cellen for raden som matcher overskriften, eller
    legger til raden hvis den ikke finnes fra før."""
    ws = hent_eller_lag_fane(sh, VEILEDNING_FANE, VEILEDNING_HEADER)
    rader = ws.get_all_values()
    for i, rad in enumerate(rader[1:] if len(rader) > 1 else [], start=2):
        if len(rad) >= 1 and rad[0] == overskrift:
            ws.update([[ny_tekst]], range_name=f"B{i}")
            read_veiledning.clear()
            return
    ws.append_row([overskrift, ny_tekst])
    read_veiledning.clear()


# ─────────────────────────────────────────────
# Testkjøp – egen, enkel veiledningsfane (samme Overskrift/Tekst-oppsett som
# Veiledning, men en egen fane siden det er et annet tema/en annen fase).
# Guide-først, bevisst: siden selve registrering av funn fra et testkjøp
# ikke er spesifisert ennå (hva skal noteres, av hvem, delt per kriterium
# eller fritekst?), bygger denne siden KUN veiledningen – ingen ny
# datalagring er lagt til for å unngå å gjette feil på en datamodell som
# må endres igjen senere.
# ─────────────────────────────────────────────
TESTKJOP_VEILEDNING_FANE = "Testkjøp-veiledning"
_TESTKJOP_VEILEDNING_SEED = [
    ["Hva er et testkjøp?", "Du handler som en vanlig kunde ville gjort – fra første søk til varen er mottatt (eller returnert). Målet er å avdekke ting som er vanskelige å se uten faktisk å gjennomføre et kjøp: leveringstid, kommunikasjon underveis, og hvordan butikken håndterer en reell henvendelse."],
    ["Gjennomfør hele kjøpsløpet", "Søk/bla frem en vare → legg i handlekurv → gå gjennom kassen (betalingsalternativer, leveringsvalg, ordrebekreftelse) → følg leveringen til varen er mottatt. Ta gjerne skjermbilder underveis – de er nyttige om noe skal diskuteres i juryen senere."],
    ["Kundeservice", "Ta kontakt med kundeservice med et reelt, enkelt spørsmål (f.eks. om levering eller en vare) via minst én tilgjengelig kanal. Noter responstid, tone og om du faktisk fikk svar på det du spurte om."],
    ["Retur og angrerett", "Sjekk at angrerett, returvilkår og eventuelle returkostnader er tydelig opplyst FØR kjøp – ikke bare gjemt i de generelle vilkårene. Gjennomfør gjerne en retur hvis praktisk mulig, og noter hvor enkelt prosessen var."],
    ["Compliance / prisopplysning", "Er pris, totalkostnad (inkl. frakt), firmainformasjon og angrerett opplyst slik lovverket krever? Dette trenger ikke juridisk dybdevurdering – noter tydelige avvik du selv oppdager som vanlig kunde."],
    ["Universell utforming", "Prøv å navigere med kun tastatur, og sjekk kontrast og lesbarhet. Du trenger ikke være ekspert – noter konkrete ting som var vanskelig (f.eks. knapper du ikke fikk fokus på, tekst med dårlig kontrast, bilder uten beskrivelse for skjermlesere)."],
    ["Dokumenter underveis", "Noter tidspunkt og konkrete observasjoner mens de er ferske, i stedet for å stole på hukommelsen etterpå – spesielt leveringstid og kundeservice-responstid er lette å glemme nøyaktig på."],
]


@st.cache_data(ttl=600, show_spinner=False)
def read_testkjop_veiledning(_sh):
    ws = hent_eller_lag_fane(_sh, TESTKJOP_VEILEDNING_FANE, VEILEDNING_HEADER)
    if len(ws.get_all_values()) <= 1:
        ws.append_rows(_TESTKJOP_VEILEDNING_SEED)
        read_testkjop_veiledning.clear()
        return ws.get_all_records()
    return ws.get_all_records()


# ─────────────────────────────────────────────
# Faser
# ─────────────────────────────────────────────
_FASER_SEED = [
    [1, "Screening", "En AI-agent screener alle nominerte nettbutikker.", "Fullført", "", ""],
    [2, "Juryvurdering", "Juryen vurderer butikkene.", "Fullført", "", ""],
    [3, "Ekspertvurdering", "Jurymedlemmene vurderer kriteriene de er tildelt.", "Pågår", "", ""],
    [4, "Testkjøp", "Jurymedlemmene handler som en vanlig kunde og vurderer kundeservice, compliance og universell utforming.", "Kommende", "", ""],
    [5, "Finale", "De beste butikkene i hver størrelsesklasse kåres.", "Kommende", "", ""],
]


def _omdop_testhandel(ws):
    """«Testhandel» ble omdøpt til «Testkjøp» (avtalt med bruker) – retter
    opp automatisk i et ark som allerede har den gamle fasenavnet, uten å
    røre noe annet på raden (beskrivelse, status, datoer)."""
    rader = ws.get_all_values()
    for i, rad in enumerate(rader[1:], start=2):
        if len(rad) >= 2 and rad[1].strip() == "Testhandel":
            ws.update([["Testkjøp"]], range_name=f"B{i}")
            read_faser.clear()


def _migrer_gammelt_faser_format(ws):
    """Tidligere versjon brukte kolonnene Nummer/.../Aktiv (ja/nei). Bygger om
    til det nye skjemaet (Fase/.../Status/Startdato/Sluttdato) hvis det gamle
    formatet oppdages – Beskrivelse-teksten beholdes som den er."""
    rader = ws.get_all_values()
    if not rader or rader[0][:4] == FASER_HEADER[:4]:
        return  # allerede riktig format (eller tomt – sikre_fane seeder på nytt)
    if rader[0][:2] != ["Nummer", "Navn"]:
        return  # ukjent format – rør ikke
    aktivt_nummer = next((int(rad[0]) for rad in rader[1:] if len(rad) >= 4 and str(rad[3]).strip().lower() == "ja"), None)
    nye_rader = [FASER_HEADER]
    for rad in rader[1:]:
        if len(rad) < 4:
            continue
        try:
            nummer = int(rad[0])
        except ValueError:
            continue
        if aktivt_nummer is None:
            status = "Pågår" if str(rad[3]).strip().lower() == "ja" else "Kommende"
        else:
            status = "Fullført" if nummer < aktivt_nummer else ("Pågår" if nummer == aktivt_nummer else "Kommende")
        nye_rader.append([rad[0], rad[1], rad[2] if len(rad) > 2 else "", status, "", ""])
    ws.clear()
    ws.update(nye_rader)


@st.cache_data(ttl=600, show_spinner=False)
def read_faser(_sh):
    ws = hent_eller_lag_fane(_sh, FASER_FANE, FASER_HEADER)
    _migrer_gammelt_faser_format(ws)
    _omdop_testhandel(ws)
    if len(ws.get_all_values()) <= 1:
        ws.append_rows(_FASER_SEED)
        read_faser.clear()
        return [dict(zip(FASER_HEADER, r)) for r in _FASER_SEED]
    return ws.get_all_records()


def aktiv_fase(faser: list):
    aktive = [f for f in faser if str(f.get("Status", "")).strip() == "Pågår"]
    if len(aktive) == 1:
        return aktive[0]
    return faser[0] if faser else None


# Faser-fanens fasenummer -> samme fase-tekst-konvensjon som Kriterier-fanens
# «Fase»-felt («Fase 2»/«Fase 3»/«Testkjøp», se FORESLATTE_TILLEGGSKRITERIER)
# og butikklistens valgfrie «Fase»-kolonne (se sheets._les_butikkliste).
_FASE_NUMMER_TIL_STRENG = {2: "Fase 2", 3: "Fase 3", 4: "Testkjøp"}


def gjeldende_fase_streng(faser: list):
    """None hvis ingen aktiv fase er gjenkjent, eller hvis gjeldende fase
    ikke har en kjent tekst-motsvarighet (f.eks. Screening/Finale – disse
    filtrerer ikke butikklisten). Brukes til å filtrere butikklisten etter
    butikkens egen, valgfrie Fase-kolonne – se sheets._les_butikkliste()."""
    f = aktiv_fase(faser)
    if not f:
        return None
    try:
        nummer = int(f.get("Fase", 0))
    except (TypeError, ValueError):
        return None
    return _FASE_NUMMER_TIL_STRENG.get(nummer)


def sett_gjeldende_fase(sh, fase_nummer):
    """Setter Status for ALLE faser ut fra gjeldende fasenummer: tidligere
    faser blir «Fullført», den valgte blir «Pågår», senere blir «Kommende».
    En bevisst, eksplisitt handling (trykk i Innstillinger) – ikke noe som
    skjer stille i bakgrunnen. Kan overstyres manuelt i regnearket etterpå."""
    ws = hent_eller_lag_fane(sh, FASER_FANE, FASER_HEADER)
    rader = ws.get_all_values()
    if len(rader) <= 1:
        return
    kol_status = FASER_HEADER.index("Status") + 1
    oppdateringer = []
    for i, rad in enumerate(rader[1:], start=2):
        try:
            nummer = int(rad[0])
        except (ValueError, IndexError):
            continue
        status = "Fullført" if nummer < fase_nummer else ("Pågår" if nummer == fase_nummer else "Kommende")
        oppdateringer.append({"range": gspread.utils.rowcol_to_a1(i, kol_status), "values": [[status]]})
    if oppdateringer:
        ws.batch_update(oppdateringer)
    read_faser.clear()


# ─────────────────────────────────────────────
# Testkjøp – status, tidsavvik og andre utledede nøkkeltall
# ─────────────────────────────────────────────
from datetime import datetime as _datetime  # noqa: E402

TESTKJOP_STATUSER = [
    "Ikke startet", "Bestilt", "Venter på levering", "Levert", "Retur sendt", "Venter på refusjon", "Ferdig",
]


def beregn_testkjop_status(steg_data: dict) -> str:
    """steg_data: {steg: {kolonnenavn: verdi}} for ÉN butikk+jurymedlem
    (fra sheets.read_testkjop). Utleder status fra hvilke av de 8
    tidslinje-stegene som er fylt ut så langt.

    «Retur sendt» vs. «Venter på refusjon» skilles på om steg «Retur» sin
    «Beskjed retur mottatt» er besvart Ja (butikken har da bekreftet at de
    har mottatt returen - man venter nå SPESIFIKT på selve refusjonen,
    ikke lenger på at pakken skal komme frem)."""
    if "Pengene tilbake" in steg_data:
        return "Ferdig"
    if "Retur" in steg_data:
        if str(steg_data["Retur"].get("Beskjed retur mottatt", "")).strip().lower() == "ja":
            return "Venter på refusjon"
        return "Retur sendt"
    if "Utpakking" in steg_data or "Levering" in steg_data:
        return "Levert"
    if "Kommunikasjon" in steg_data:
        return "Venter på levering"
    if "Før kjøp" in steg_data or "Kassen" in steg_data:
        return "Bestilt"
    return "Ikke startet"


def _parse_dato(tekst):
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return _datetime.strptime(tekst.strip(), fmt)
        except (ValueError, AttributeError):
            continue
    return None


def beregn_leveringsavvik(lovet_dato: str, faktisk_dato: str):
    """«2 dager forsinket» / «Levert som lovet» / «1 dag tidligere» - None
    hvis en av datoene mangler eller ikke lar seg tolke."""
    lovet, faktisk = _parse_dato(lovet_dato), _parse_dato(faktisk_dato)
    if not lovet or not faktisk:
        return None
    avvik = (faktisk.date() - lovet.date()).days
    if avvik == 0:
        return "Levert som lovet"
    if avvik > 0:
        return f"{avvik} dag{'er' if avvik != 1 else ''} forsinket"
    return f"{-avvik} dag{'er' if avvik != -1 else ''} tidligere"


def beregn_svartid(tidspunkt_sendt: str, tidspunkt_mottatt: str):
    """Lesbar varighet («2t 15min», «45min») mellom to tidspunkt, eller
    None hvis en av dem mangler/ikke lar seg tolke."""
    sendt, mottatt = _parse_dato(tidspunkt_sendt), _parse_dato(tidspunkt_mottatt)
    if not sendt or not mottatt or mottatt < sendt:
        return None
    minutter = int((mottatt - sendt).total_seconds() // 60)
    timer, rest = divmod(minutter, 60)
    if timer:
        return f"{timer}t {rest}min"
    return f"{rest}min"


def beregn_dager_til_refusjon(retur_tidspunkt: str, dato_refusjon: str):
    """Antall dager fra returen ble registrert sendt (steg «Retur» sitt eget
    Tidspunkt - brukes som beste tilgjengelige anslag på innleverings-
    tidspunktet) til refusjonen kom. None hvis en av datoene mangler."""
    retur, refusjon = _parse_dato(retur_tidspunkt), _parse_dato(dato_refusjon)
    if not retur or not refusjon:
        return None
    return (refusjon.date() - retur.date()).days
