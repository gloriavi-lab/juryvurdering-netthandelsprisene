"""
Juryvurdering Netthandelsprisene – Ekspertvurdering (Fase 2)
==============================================================
Rendyrket, lett vurderingsverktøy for ekspertvurderingen (Fase 2) i
Netthandelsprisene. Bygget som en EGEN app – bevisst adskilt fra
hovedappen (screening + database over alle nettbutikker) – fordi
hovedappen ble treg av å håndtere 1000 butikker og mange faner i ett
og samme Google Sheet.

Arbeidsflyt:
1. Fase 1 gjøres i et eget Excel-ark (utenfor denne appen). Resultatet
   (butikkliste + Klasse/Bransje/URL) lastes opp her i sidepanelet.
2. Hvert jurymedlem skriver navnet sitt og velger sitt fagfelt (samme
   5 kategorier som i Fase 1).
3. Jurymedlemmet vurderer butikkene på KUN sitt fagfelt, med akkurat
   de samme kriteriene (ord for ord) som ble brukt i Fase 1 – pluss et
   kommentarfelt per kriterium, som ikke fantes i Fase 1-arket.
4. Lagring skjer i et eget, lite Google Sheet (IKKE hovedappens store
   ark). Appen skriver KUN raden(e) for butikken som akkurat ble
   lagret – aldri hele arket – slik at manuelle endringer gjort
   direkte i Google Sheets alltid overlever og vises i appen.
"""

import re
from datetime import datetime

import gspread
import openpyxl
import streamlit as st
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Ekspertvurdering – Netthandelsprisene", page_icon="🎓", layout="wide")

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
KRITERIER_PER_FAGFELT = {
    kat: [krit for k, krit in KRITERIER if k == kat] for kat in FAGFELT
}

VURDERINGER_HEADER = ["Butikk", "Jurymedlem", "Fagfelt", "Kriterium", "Score", "Kommentar", "Sist oppdatert"]
BUTIKKLISTE_FIL = "butikkliste.json"


# ─────────────────────────────────────────────
# Lokal lagring av opplastet butikkliste (overlever refresh, ikke deploy-restart)
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
# Google Sheets – egen, liten regneark. Samme secrets-mønster som hovedappen
# (gcp_service_account kan gjenbrukes – bare del et NYTT ark med samme
# tjenestekonto og legg inn dets ID under [google_sheets] sheet_id).
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
    manuelle Sheets-endringer forsvant i den gamle appen)."""
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
    header = rå[0] if rå else VURDERINGER_HEADER
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
        st.error(f"Kunne ikke lese Excel-filen: {e}")
        return None

    ws = wb.worksheets[0]
    header_rad = None
    for r in range(1, min(ws.max_row, 10) + 1):
        if str(ws.cell(row=r, column=1).value or "").strip().lower() == "butikk":
            header_rad = r
            break
    if header_rad is None:
        st.error('Fant ikke en rad med "Butikk" i kolonne A i fila.')
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
    return butikker


# ─────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────
st.title("🎓 Ekspertvurdering – Netthandelsprisene")
st.caption("Fase 2 · egen, lett app – uavhengig av hoved-/screeningappen")

sh = koble_sheets()

with st.sidebar:
    st.header("⚙️ Oppsett")
    if sh:
        st.success("✅ Koblet til Google Sheets")
        st.markdown(f"[📊 Åpne arket]({sh.url})")
    else:
        st.error("❌ Ikke koblet til Google Sheets ennå")
        with st.expander("Feilmelding"):
            st.code(st.session_state.get("_gsheets_feil", "Ukjent feil"))

    st.markdown("---")
    st.subheader("📤 Butikkliste for denne fasen")
    if "butikkliste" not in st.session_state:
        st.session_state.butikkliste = last_lokalt()

    if st.session_state.butikkliste:
        st.success(f"{len(st.session_state.butikkliste)} butikker lastet inn.")
        if st.button("🗑️ Fjern liste"):
            st.session_state.butikkliste = None
            lagre_lokalt(None)
            st.rerun()

    opplastet = st.file_uploader("Last opp Fase 1-Excel (.xlsx)", type=["xlsx"])
    if opplastet is not None:
        ny_liste = les_fase1_liste(opplastet)
        if ny_liste:
            st.session_state.butikkliste = ny_liste
            lagre_lokalt(ny_liste)
            st.success(f"✅ {len(ny_liste)} butikker lastet inn!")
            st.rerun()

if not sh:
    st.warning("Google Sheets-tilkoblingen mangler. Sjekk `secrets` (se README for oppsett) før vurderinger kan lagres.")
    st.stop()

if not st.session_state.get("butikkliste"):
    st.info("💡 Last opp Fase 1-Excel-fila i sidepanelet til venstre for å komme i gang.")
    st.stop()

butikkliste = st.session_state.butikkliste

col1, col2 = st.columns(2)
with col1:
    jurynavn = st.text_input("Ditt navn (jurymedlem)", value=st.session_state.get("_jurynavn", ""))
    st.session_state["_jurynavn"] = jurynavn
with col2:
    fagfelt_valgt = st.selectbox("Ditt fagfelt (kategorien du er ekspert på)", FAGFELT)

if not jurynavn:
    st.warning("Skriv inn navnet ditt for å begynne å vurdere.")
    st.stop()

kriterier_denne = KRITERIER_PER_FAGFELT[fagfelt_valgt]

alle_rader = hent_vurderinger(sh)
mine_vurderinger = {}
if len(alle_rader) > 1:
    for rad in alle_rader[1:]:
        if len(rad) >= 6 and rad[1] == jurynavn:
            mine_vurderinger[(rad[0], rad[3])] = {"score": rad[4], "kommentar": rad[5]}

sok = st.text_input("🔍 Søk etter butikk", "")
navn_liste = sorted(butikkliste.keys())
if sok:
    navn_liste = [n for n in navn_liste if sok.lower() in n.lower()]

antall_fullfort = sum(
    1 for n in butikkliste
    if all((n, krit) in mine_vurderinger for krit in kriterier_denne)
)
st.caption(f"**{fagfelt_valgt}** · {antall_fullfort} av {len(butikkliste)} butikker fullført av deg")
st.progress(antall_fullfort / len(butikkliste) if butikkliste else 0)

for navn in navn_liste:
    info = butikkliste[navn]
    alt_ferdig = all((navn, krit) in mine_vurderinger for krit in kriterier_denne)
    merke = "✅ " if alt_ferdig else ""
    with st.expander(f"{merke}**{navn}** — {info.get('klasse', '–')} · {info.get('bransje', '–')}"):
        if info.get("url"):
            st.markdown(f"🌐 [Besøk nettbutikk]({info['url']})")
        st.markdown("---")
        for krit in kriterier_denne:
            eksisterende = mine_vurderinger.get((navn, krit), {})
            kc1, kc2 = st.columns([1, 3])
            with kc1:
                score = st.select_slider(
                    krit, [1, 2, 3, 4, 5],
                    value=int(eksisterende.get("score") or 3),
                    format_func=lambda x: "⭐" * x,
                    key=f"score_{navn}_{krit}",
                    label_visibility="collapsed",
                )
            with kc2:
                st.text_input(
                    "Kommentar", value=eksisterende.get("kommentar", ""),
                    key=f"kom_{navn}_{krit}", label_visibility="collapsed", placeholder=krit,
                )
        if st.button("💾 Lagre vurdering for denne butikken", key=f"lagre_{navn}"):
            vurderinger = [
                (krit, st.session_state.get(f"score_{navn}_{krit}", 3), st.session_state.get(f"kom_{navn}_{krit}", ""))
                for krit in kriterier_denne
            ]
            lagre_vurderinger_batch(sh, navn, jurynavn, fagfelt_valgt, vurderinger)
            st.success(f"Lagret vurdering for {navn}!")
            st.rerun()
