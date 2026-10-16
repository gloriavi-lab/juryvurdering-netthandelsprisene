"""Side 2 – Vurdering. Butikkliste er standardvisningen; klikk en butikk for
å vurdere den. Tall 1–5 i stedet for stjerner, kommentar per kriterium
(påkrevd ved 1–3), ingen fagfelt-nivå-kommentar.

DATAMODELL (se VIKTIG-avsnittet øverst i sheets.py for full forklaring):
appen leser og skriver DIREKTE til den fargede fanen for gjeldende fase
("Rangering ekspertvurdering" – FASE2_FANE) for score+kommentar (kommentar
som celle-notat) – det er DEN fanen jury/administrasjon faktisk ser og kan
rette manuelt i. "Vurderinger"-fanen er en LOGG (én rad per butikk +
jurymedlem + kriterium) som oppdateres ved hver lagring, brukt til å regne
ut riktig celleverdi når flere jurymedlemmer deler ett kriterium (snitt) –
den er IKKE det som vises i skjemaet.

VIKTIG tilstandshåndtering: nøklene for score/kommentar-widgetene nullstilles
EKSPLISITT når brukeren bytter til en ANNEN butikk (sammenlignet med forrige
rad i session_state), slik at visningen alltid viser det som faktisk er
lagret – ikke en tilfeldig gammel verdi fra en tidligere visning i samme
nettleserøkt. Det var roten til at en slettet kommentar kunne "komme
tilbake" og at en score kunne se ut til å forsvinne."""

import streamlit as st

from components import feilmelding_tekst, fremdriftslinje, klasse_badge, lagringsstatus, scroll_til_toppen, status_merkelapp_html, topptekst, tom_tilstand, vis_feil
from data import IKKE_VURDERT, grupper_vurderinger, mine_scorer, naa_norsk, normalize_score, offisiell_celleverdi, status_for_scorer
from jury import (
    aktive_kriterier, beskriv_tildeling, gjeldende_fase_streng, kriterier_per_fagfelt, mine_kriterier, read_criteria,
    read_faser, read_jury,
)
from sheets import (
    read_generelle_kommentarer, read_ratings, read_stores, read_vurderinger, skriv_mange_til_farget_fane,
    upsert_generell_kommentar, upsert_mange_vurderinger,
)
from theme import FAGFELT_FARGE, STATUS_FARGE, STATUS_TEKST, STATUS_TONE

topptekst("Vurdering")

# st.toast kalt INNE i en on_click-callback (se knappene lenger ned) er ikke
# garantert å rendres riktig – den callbacken kjører FØR denne scriptkjøringen
# i det hele tatt starter. Derfor: callbacken setter bare et flagg, og selve
# toast-kallet skjer her, tidlig i en vanlig scriptkjøring, uansett om vi
# etterpå havner på lista eller i vurderingsvisningen.
if st.session_state.pop("_toast_etter_rerun", None):
    st.toast("Lagret ✓", icon=":material/check_circle:")

sh = st.session_state.get("_sh")
if not sh:
    st.warning("Google Sheets-tilkoblingen mangler – gå til **Innstillinger**.", icon=":material/cloud_off:")
    st.stop()

try:
    butikker, _ = read_stores(sh)
    jury = read_jury(sh)
    alle_kriterier = read_criteria(sh)
except Exception as e:
    vis_feil("Kunne ikke lese regnearket", e)
    st.stop()

# Fase-styrt butikkliste: valgfri «Fase»-kolonne i butikklistens kildefane
# (se sheets._les_butikkliste) – en butikk skjules KUN hvis den kolonnen
# faktisk er fylt ut OG ikke matcher gjeldende fase. Tom kolonne (standard,
# ingenting endret ennå) betyr "vis i alle faser" – helt bakoverkompatibelt
# inntil noen faktisk tar den i bruk.
try:
    _gjeldende_fase_txt = gjeldende_fase_streng(read_faser(sh))
except Exception:
    _gjeldende_fase_txt = None
if _gjeldende_fase_txt:
    butikker = {navn: info for navn, info in butikker.items() if not info.get("fase") or info.get("fase") == _gjeldende_fase_txt}

kriterier_fase3 = aktive_kriterier(alle_kriterier, fase="Fase 3")
kriterier_per_felt_alle = kriterier_per_fagfelt(kriterier_fase3)
kriterium_info = {k["kriterium"]: k for k in kriterier_fase3}

if not butikker:
    tom_tilstand("📋", "Fant ingen butikker i regnearket", "Sjekk Innstillinger.")
    st.page_link("pages/innstillinger.py", label="Gå til Innstillinger", icon=":material/settings:")
    st.stop()
if not jury:
    st.info("Ingen jurymedlemmer er lagt til ennå – gjør det under **Innstillinger → Jury og kriterier**.", icon=":material/info:")
    st.page_link("pages/innstillinger.py", label="Gå til Innstillinger", icon=":material/settings:")
    st.stop()

# ── Topp: navn + tildeling + lenke til regnearket ──
navn_liste_jury = sorted(jury.keys())
tc1, tc2 = st.columns([4, 1])
with tc1:
    jurynavn = st.selectbox("Ditt navn (jurymedlem)", navn_liste_jury, key="_jurynavn")
    beskrivelse = beskriv_tildeling(jurynavn, jury, kriterier_per_felt_alle)
    if beskrivelse:
        st.caption(f"_{beskrivelse}_")
with tc2:
    st.link_button("Åpne regnearket", sh.url, icon=":material/open_in_new:", use_container_width=True)

mine = mine_kriterier(jury, jurynavn)
if not mine:
    tom_tilstand("🤷", "Ingen kriterier tildelt deg ennå", "Ta kontakt med juryleder for å bli tildelt kriterier å vurdere.")
    st.stop()

mine_per_felt = {felt: [k for k in krit if k in mine] for felt, krit in kriterier_per_felt_alle.items()}
mine_per_felt = {felt: krit for felt, krit in mine_per_felt.items() if krit}
mine_kriterier_flat = [k for krit in mine_per_felt.values() for k in krit]
krit_til_fagfelt = {k: felt for felt, krit in mine_per_felt.items() for k in krit}

try:
    alle_vurderinger = read_vurderinger(sh)
    alle_generelle = read_generelle_kommentarer(sh)
    fargede_fane_data = read_ratings(sh)
except Exception as e:
    vis_feil("Kunne ikke lese vurderinger", e)
    st.stop()

# mine_oppslag (LOGGEN, "Vurderinger") brukes KUN for å seede MIN EGEN
# kommentartekst per kriterium (det jeg selv sist skrev) – selve scoren/
# status vises fra den fargede fanen (fargede_fane_data), se DATAMODELL-
# avsnittet øverst i fila: det er DEN fanen manuelle rettelser skjer i.
mine_oppslag = mine_scorer(alle_vurderinger, jurynavn)  # (butikk,kriterium) -> {score,kommentar,sist_endret}
generell_per_butikk = {}
for g in alle_generelle:
    generell_per_butikk.setdefault(g["butikk"], []).append(g)

navn_liste_butikker = sorted(butikker.keys())


def grid_scorer_for(navn):
    """{kriterium: rå_verdi} fra DEN FARGEDE FANEN, begrenset til MINE
    tildelte kriterier – dette er den offisielle, synlige verdien (se
    DATAMODELL øverst i fila)."""
    alle_scorer = fargede_fane_data.get(navn, {}).get("scorer", {})
    return {k: alle_scorer[k] for k in mine_kriterier_flat if k in alle_scorer}


def status(navn):
    return status_for_scorer(grid_scorer_for(navn), mine_kriterier_flat)


def status_per_fagfelt(navn):
    scorer = grid_scorer_for(navn)
    resultat = {}
    for fagfelt, kriterier in mine_per_felt.items():
        besvart = sum(1 for k in kriterier if k in scorer)
        resultat[fagfelt] = (besvart, len(kriterier))
    return resultat


def har_kommentar(navn):
    return any(
        (navn, k) in mine_oppslag and mine_oppslag[(navn, k)]["kommentar"]
        for k in mine_kriterier_flat
    ) or bool(generell_per_butikk.get(navn))


antall_ferdig = sum(1 for n in navn_liste_butikker if status(n) == "Ferdig")
antall_pabegynt = sum(1 for n in navn_liste_butikker if status(n) == "Påbegynt")
antall_gjenstar = len(navn_liste_butikker) - antall_ferdig - antall_pabegynt


def _neste_anbefalt():
    """Neste PÅBEGYNTE butikk (fortsett der du slapp) – ellers neste
    IKKE STARTEDE, alfabetisk. None hvis alt er ferdig."""
    pabegynte = sorted(n for n in navn_liste_butikker if status(n) == "Påbegynt")
    if pabegynte:
        return pabegynte[0]
    gjenstaende = sorted(n for n in navn_liste_butikker if status(n) == "Ikke startet")
    return gjenstaende[0] if gjenstaende else None


def _nullstill_butikk_state(navn):
    """Fjerner session_state-nøklene for denne butikkens widgetar, slik at de
    seedes PÅ NYTT fra det ferske sheet-innholdet – kalles kun når visningen
    faktisk BYTTER til en annen butikk enn sist (se forklaring øverst i fila)."""
    for k in mine_kriterier_flat:
        for prefiks in ("seg_", "kom_krit_"):
            st.session_state.pop(f"{prefiks}{navn}_{k}", None)
    st.session_state.pop(f"generell_{navn}", None)


def _bytt_til(navn):
    forrige = st.session_state.get("_sist_vist_butikk")
    if forrige != navn:
        _nullstill_butikk_state(navn)
        st.session_state["_sist_vist_butikk"] = navn
    st.session_state["_apnet_butikk"] = navn


# ── Tre statuskort + grønn fremdriftslinje ──
status_kort = []
for s_navn, antall in [("Ikke startet", antall_gjenstar), ("Påbegynt", antall_pabegynt), ("Ferdig", antall_ferdig)]:
    farge, tone, tekst = STATUS_FARGE[s_navn], STATUS_TONE[s_navn], STATUS_TEKST[s_navn]
    status_kort.append(
        f'<div class="rutenett-kort" style="background:{tone};border-top-color:{farge};">'
        f'<div class="stor-tall" style="color:{farge};">{antall}</div><div style="font-weight:700;">{tekst}</div></div>'
    )
st.markdown(f'<div class="rutenett tre-per-rad">{"".join(status_kort)}</div>', unsafe_allow_html=True)
st.write("")
fremdriftslinje((antall_ferdig / len(navn_liste_butikker)) if navn_liste_butikker else 0, f"{antall_ferdig} av {len(navn_liste_butikker)} ferdig")
st.write("")

# ── Handlingskort: fortsett der du slapp (kun på listevisningen) ──
if not st.session_state.get("_apnet_butikk"):
    _neste_navn = _neste_anbefalt()
    if _neste_navn:
        neste_info = butikker[_neste_navn]
        with st.container(border=True):
            ac1, ac2 = st.columns([3, 1])
            ac1.markdown(f"**Neste butikk:** {_neste_navn} ({neste_info.get('klasse', '–')})")
            if ac2.button("Start vurdering →", type="primary", use_container_width=True):
                _bytt_til(_neste_navn)
                st.rerun()
    else:
        st.success("🎉 Du har vurdert alle dine butikker!", icon=":material/celebration:")
    st.write("")


def lagre_denne(navn):
    """Skriver, og – VIKTIG – leser så de akkurat skrevne cellene TILBAKE fra
    regnearket og sammenligner før "Lagret" vises. En bruker oppdaget at
    appen kunne vise "Lagret" selv om INGENTING faktisk sto i arket (fordi
    appen var koblet til et annet regneark enn forventet) – en try/except
    rundt selve skrive-kallet fanger ikke det, siden selve API-kallet kan gå
    helt fint mot FEIL regneark/fane. Derfor: ingen "Lagret" uten en fersk,
    bekreftet lesing som faktisk stemmer.

    VIKTIG (lagt til etter at appen traff Google sin lesekvote i
    produksjon): alle kriteriene for ÉN lagring skrives nå i ETT batch-kall
    (sheets.upsert_mange_vurderinger) i stedet for ett get_all_values()- og
    ett skrive-kall PER KRITERIUM, og selve bekreftelsen gjenbruker de
    vanlige, mellomlagrede read_vurderinger(sh)/read_ratings(sh) – som
    uansett blir friske fordi skrivingen akkurat tømte cachen deres – i
    stedet for separate, alltid-ferske feilsøkingskall. Dette endrer ANTALL
    API-kall drastisk, IKKE hva som faktisk valideres/lagres/vises."""
    manglende_kommentar = []
    kriterier_a_lagre = []  # (fagfelt, kriterium, score, kommentar) – validert, klar til å skrives
    for fagfelt, kriterier in mine_per_felt.items():
        for krit in kriterier:
            valg = st.session_state.get(f"seg_{navn}_{krit}")
            kommentar_krit = (st.session_state.get(f"kom_krit_{navn}_{krit}") or "").strip()

            if valg == "Kan ikke vurdere":
                score = IKKE_VURDERT
            elif valg is not None:
                score = str(valg)
            else:
                continue  # ikke besvart ennå – hopp over, lagre ikke noe

            normalisert = normalize_score(score)
            if isinstance(normalisert, (int, float)) and normalisert <= 3 and not kommentar_krit:
                manglende_kommentar.append(krit)
                continue

            kriterier_a_lagre.append((fagfelt, krit, score, kommentar_krit))

    if manglende_kommentar:
        ord = "kriterium" if len(manglende_kommentar) == 1 else "kriterier"
        st.session_state["_lagringstilstand"] = ("feil", f"{len(manglende_kommentar)} {ord} mangler kommentar: " + ", ".join(manglende_kommentar))
        return False

    skrevet = {krit: (score, kommentar) for _, krit, score, kommentar in kriterier_a_lagre}
    if kriterier_a_lagre:
        try:
            upsert_mange_vurderinger(sh, navn, jurynavn, [(f, k, s, c) for f, k, s, c in kriterier_a_lagre])
        except Exception as e:
            st.session_state["_lagringstilstand"] = ("feil", feilmelding_tekst("Kunne ikke skrive til loggen", e))
            return False

    # Skriv den OFFISIELLE verdien for hvert kriterium vi nettopp lagret inn
    # i DEN FARGEDE FANEN (se DATAMODELL øverst i fila – det er DEN jury og
    # administrasjon faktisk ser og kan rette manuelt i). Regnes ut fra en
    # FERSK lesing av loggen (cachen ble akkurat tømt av skrivingen over),
    # slik at et kriterium flere jurymedlemmer deler får riktig snitt i
    # stedet for at siste lagring bare overskriver de andres score. Samme
    # lesing brukes rett under til å BEKREFTE loggen – ingen ekstra kall.
    skrivejobb = []
    fersk_vurderinger = []
    if skrevet:
        try:
            fersk_vurderinger = read_vurderinger(sh)
        except Exception as e:
            st.session_state["_lagringstilstand"] = ("feil", feilmelding_tekst("Kunne ikke lese loggen for å oppdatere den fargede fanen", e))
            return False
        fersk_gruppert = grupper_vurderinger(fersk_vurderinger)
        for krit in skrevet:
            verdi, notat = offisiell_celleverdi(fersk_gruppert.get((navn, krit), []))
            skrivejobb.append((krit_til_fagfelt.get(krit), krit, verdi, notat))
        try:
            skriv_mange_til_farget_fane(sh, navn, skrivejobb)
        except Exception as e:
            st.session_state["_lagringstilstand"] = ("feil", feilmelding_tekst("Kunne ikke skrive til den fargede fanen", e))
            return False

    generell_tekst = (st.session_state.get(f"generell_{navn}") or "").strip()
    try:
        upsert_generell_kommentar(sh, navn, jurynavn, generell_tekst)
    except Exception as e:
        st.session_state["_lagringstilstand"] = ("feil", feilmelding_tekst("Kunne ikke skrive generell kommentar", e))
        return False

    avvik = []
    if skrevet:
        logg_oppslag = {(r["butikk"], r["kriterium"]): r for r in fersk_vurderinger if r["jurymedlem"] == jurynavn}
        for krit, (forventet_score, forventet_kommentar) in skrevet.items():
            rad = logg_oppslag.get((navn, krit))
            rå_score = rad["score"] if rad else None
            rå_kommentar = (rad["kommentar"] if rad else "") or ""
            if normalize_score(rå_score) != normalize_score(forventet_score):
                avvik.append(f"«{krit}» i loggen: skrev {forventet_score!r}, fant {rå_score!r}")
            elif rå_kommentar != (forventet_kommentar or ""):
                avvik.append(f"«{krit}»: kommentaren i loggen stemmer ikke med det som ble lagret")

    # Les den fargede fanen tilbake også – det er DEN som faktisk vises i
    # appen og som jury/administrasjon ser, så «Lagret» skal aldri vises
    # uten at NETTOPP denne stemmer, ikke bare loggen. read_ratings(sh) er
    # mellomlagret, men skriv_mange_til_farget_fane tømte akkurat cachen,
    # så dette er like ferskt som et eget, ekstra API-kall ville vært.
    if skrivejobb:
        try:
            fersk_grid = read_ratings(sh)
        except Exception as e:
            st.session_state["_lagringstilstand"] = ("feil", feilmelding_tekst("Kunne ikke lese tilbake fra den fargede fanen", e))
            return False
        grid_scorer = fersk_grid.get(navn, {}).get("scorer", {})
        for fagfelt, krit, forventet, _ in skrivejobb:
            faktisk = normalize_score(grid_scorer.get(krit))
            if faktisk != forventet:
                avvik.append(f"«{krit}» i den fargede fanen: skrev {forventet!r}, fant {grid_scorer.get(krit)!r}")

    try:
        kontroll_generelle = read_generelle_kommentarer(sh)
    except Exception as e:
        st.session_state["_lagringstilstand"] = ("feil", feilmelding_tekst("Kunne ikke lese tilbake generell kommentar", e))
        return False
    lagret_generell = next((g["kommentar"] for g in kontroll_generelle if g["butikk"] == navn and g["jurymedlem"] == jurynavn), "")
    if (lagret_generell or "") != (generell_tekst or ""):
        avvik.append("Generell kommentar ble ikke lagret riktig")

    if avvik:
        st.session_state["_lagringstilstand"] = ("feil", "Lagringen kunne IKKE bekreftes i regnearket: " + "; ".join(avvik))
        return False

    st.session_state["_lagringstilstand"] = ("lagret", naa_norsk().strftime("%H:%M"))
    return True


def neste_uferdige(gjeldende):
    if gjeldende not in navn_liste_butikker:
        return navn_liste_butikker[0] if navn_liste_butikker else None
    start = navn_liste_butikker.index(gjeldende)
    for n in navn_liste_butikker[start + 1:] + navn_liste_butikker[:start]:
        if status(n) != "Ferdig":
            return n
    return None


def _gyldig_status_tekst(navn):
    s = status(navn)
    return {"Ferdig": "✅ Ferdig", "Påbegynt": "◐ Påbegynt", "Ikke startet": "○ Ikke startet"}[s]


def _har_ulagrede_endringer(navn):
    """Sammenligner det som faktisk STÅR i skjemaet nå (session_state) mot
    sist lagrede verdi (den fargede fanen for score, loggen for MIN egen
    kommentar) – brukt av «← Forrige» til å avgjøre om den skal spørre før
    den navigerer bort fra noe som ikke er lagret ennå."""
    for krit in mine_kriterier_flat:
        valg = st.session_state.get(f"seg_{navn}_{krit}")
        kommentar_na = (st.session_state.get(f"kom_krit_{navn}_{krit}") or "").strip()
        if valg == "Kan ikke vurdere":
            verdi_na = IKKE_VURDERT
        elif valg is not None:
            verdi_na = str(valg)
        else:
            verdi_na = None
        verdi_lagret = fargede_fane_data.get(navn, {}).get("scorer", {}).get(krit)
        if normalize_score(verdi_na) != normalize_score(verdi_lagret):
            return True
        kommentar_lagret = mine_oppslag.get((navn, krit), {}).get("kommentar") or ""
        if kommentar_na != kommentar_lagret:
            return True
    generell_na = (st.session_state.get(f"generell_{navn}") or "").strip()
    generell_lagret = next((g["kommentar"] for g in generell_per_butikk.get(navn, []) if g["jurymedlem"] == jurynavn), "")
    return generell_na != (generell_lagret or "")


@st.dialog("Ulagrede endringer")
def _bekreft_forkast(melding, naviger_funksjon):
    """Delt bekreftelsesdialog for BÅDE «← Forrige» og «Lukk» – bevisst KUN
    to valg (Avbryt / Forkast), ingen «lagre og fortsett»-knapp her: appen
    skal ha ÉN lagreknapp («Lagre»), ikke en skjult andre lagreknapp gjemt
    inni denne dialogen."""
    st.write(melding)
    c1, c2 = st.columns(2)
    if c1.button("Avbryt", use_container_width=True):
        st.rerun()
    if c2.button("Forkast og fortsett", type="primary", use_container_width=True):
        naviger_funksjon()
        st.rerun()


@st.fragment
def vis_vurderingsvisning():
    navn = st.session_state.get("_apnet_butikk")
    if navn not in navn_liste_butikker:
        st.session_state["_apnet_butikk"] = None
        st.rerun()
    info = butikker[navn]
    i = navn_liste_butikker.index(navn)

    if st.session_state.pop("_scroll_til_topp", False):
        scroll_til_toppen()

    if st.button("← Alle mine butikker", icon=":material/arrow_back:"):
        st.session_state["_apnet_butikk"] = None
        st.rerun()
        return

    hc1, hc2 = st.columns([3, 1])
    with hc1:
        st.markdown(f"### {navn}")
        klasse_badge(info.get("klasse", "–"))
        st.caption(info.get("bransje", "–"))
        st.caption(f"Butikk {i + 1} av {len(navn_liste_butikker)} · {_gyldig_status_tekst(navn)}")
    with hc2:
        if info.get("url"):
            st.link_button("Besøk butikk", info["url"], icon=":material/open_in_new:", use_container_width=True)

    # VIKTIG (fant roten til "Lagre og neste går ikke videre"-feilen): denne
    # hadde FØR ingen key=, i troen på at den da alltid ville lese index=i
    # friskt. I praksis kunne Streamlit likevel gjenbruke sin egen, forrige
    # viste verdi på tvers av et fullt st.rerun() når butikken byttet via
    # knappene under (samme auto-genererte widget-identitet) – med resultat
    # at "hopp_til != navn" ble SANN rett etter et bytte (selv om BRUKEREN
    # ikke rørte denne selectboksen), noe som trigget en UMIDDELBAR
    # _bytt_til(hopp_til) TILBAKE til den gamle butikken, i SAMME kjøring
    # som bare NETTOPP hadde byttet TIL den nye. Derfor så det ut som
    # «Lagre og neste →» ikke gjorde noe. Fiks: en key= SCOPET TIL
    # butikknavnet gir en HELT NY, aldri-før-sett widget hver gang butikken
    # bytter – da er det umulig for den å «arve» en gammel verdi.
    hopp_til = st.selectbox(
        "Hopp direkte til en annen butikk", navn_liste_butikker,
        index=i, format_func=lambda n: f"{_gyldig_status_tekst(n).split(' ')[0]} {n}",
        key=f"hopp_til_{navn}",
    )
    if hopp_til != navn:
        lagre_denne(navn)
        _bytt_til(hopp_til)
        st.session_state["_scroll_til_topp"] = True
        st.rerun()

    st.write("")
    for fagfelt, kriterier in mine_per_felt.items():
        farge = FAGFELT_FARGE.get(fagfelt, "#888")
        st.markdown(f'<div style="border-left:4px solid {farge};padding-left:10px;margin:14px 0 10px 0;font-weight:700;">{fagfelt}</div>', unsafe_allow_html=True)
        for krit in kriterier:
            eksisterende = mine_oppslag.get((navn, krit), {})  # MIN egen kommentar (loggen)
            grid_score = normalize_score(fargede_fane_data.get(navn, {}).get("scorer", {}).get(krit))  # offisiell score (den fargede fanen)
            info_k = kriterium_info.get(krit, {})
            kom_key = f"kom_krit_{navn}_{krit}"
            seg_key = f"seg_{navn}_{krit}"

            # Mangler-kommentar er regnet ut LIVE (ikke bare etter en feilet
            # lagring) – oppdaterer seg selv idet man skriver en kommentar,
            # uten noen egen "sist forsøkt lagret"-tilstand å holde i synk.
            na_valgt = st.session_state.get(seg_key)
            na_kommentar = (st.session_state.get(kom_key) or "").strip()
            mangler_na = isinstance(na_valgt, (int, float)) and na_valgt <= 3 and not na_kommentar

            tittel_farge = "color:#C8102E;" if mangler_na else ""
            st.markdown(f"<span style='{tittel_farge}font-weight:700;'>{krit}</span>" + (f"  \n_{info_k['kort']}_" if info_k.get("kort") else ""), unsafe_allow_html=True)
            with st.popover("Les mer", icon=":material/help:"):
                if info_k.get("utfyllende"):
                    st.markdown(info_k["utfyllende"])
                st.markdown(f"**1:** {info_k.get('skala1', '–')}")
                st.markdown(f"**3:** {info_k.get('skala3', '–')}")
                st.markdown(f"**5:** {info_k.get('skala5', '–')}")
                if info_k.get("eksempler"):
                    st.caption(info_k["eksempler"])

            if seg_key not in st.session_state:
                st.session_state[seg_key] = grid_score if isinstance(grid_score, (int, str)) else None
            valg = st.segmented_control("Score", [1, 2, 3, 4, 5, "Kan ikke vurdere"], key=seg_key, label_visibility="collapsed")

            pakrevd = isinstance(valg, (int, float)) and valg <= 3
            st.text_area(
                "Kommentar", value=eksisterende.get("kommentar", ""),
                key=kom_key, placeholder=f"Kommentar til «{krit}»" + (" – påkrevd ved lav score" if pakrevd else "…"),
                height=68,
            )
            if mangler_na:
                st.markdown("<span style='color:#C8102E;font-size:13px;'>⚠ Kommentar mangler</span>", unsafe_allow_html=True)
            st.write("")

    st.divider()
    st.markdown("**Generell kommentar om butikken**")
    generell_key = f"generell_{navn}"
    min_generell = next((g["kommentar"] for g in generell_per_butikk.get(navn, []) if g["jurymedlem"] == jurynavn), "")
    if generell_key not in st.session_state:
        st.session_state[generell_key] = min_generell
    st.text_area("Din generelle kommentar", key=generell_key, placeholder="Valgfri generell kommentar om hele butikken …", height=68, label_visibility="collapsed")
    andre = [g for g in generell_per_butikk.get(navn, []) if g["jurymedlem"] != jurynavn]
    if andre:
        with st.expander(f"Se andres generelle kommentarer ({len(andre)})"):
            for g in andre:
                st.caption(f"**{g['jurymedlem']}** ({g['sist_endret']}): {g['kommentar']}")

    st.write("")
    antall_mangler_na = sum(
        1 for k in mine_kriterier_flat
        if isinstance(st.session_state.get(f"seg_{navn}_{k}"), (int, float))
        and st.session_state.get(f"seg_{navn}_{k}") <= 3
        and not (st.session_state.get(f"kom_krit_{navn}_{k}") or "").strip()
    )
    if antall_mangler_na:
        ord = "kriterium" if antall_mangler_na == 1 else "kriterier"
        st.markdown(f"<span style='color:#C8102E;font-weight:600;'>⚠ {antall_mangler_na} {ord} mangler kommentar</span>", unsafe_allow_html=True)

    tilstand = st.session_state.get("_lagringstilstand")
    if tilstand:
        lagringsstatus(tilstand[0], tilstand[1])

    _neste_navn_tekst = neste_uferdige(navn)
    if _neste_navn_tekst:
        st.markdown(f'<div class="vurdering-neste-tekst">Neste: {_neste_navn_tekst}</div>', unsafe_allow_html=True)

    # NB: IKKE on_click-callbacks her – Streamlit behandler st.rerun() kalt
    # INNE i en on_click-callback som en no-op (bekreftet empirisk: en
    # tidligere callback-basert variant viste Streamlit sin egen advarsel
    # "Calling st.rerun() within a callback is a no-op" i nettleseren, og
    # endte opp med å aldri faktisk bytte butikk). Vanlig
    # if-knapp-klikket-sjekk, med session_state satt FØR st.rerun() kalles
    # fra selve scriptkroppen, fungerer korrekt. Alle tre kaller en VANLIG
    # st.rerun() (ikke scope="fragment") – mine_oppslag/fargede_fane_data/
    # statuskortene beregnes KUN øverst i scriptet, utenfor dette
    # fragmentet, så en fragment-rerun ville aldri sett det som nettopp ble
    # lagret.
    #
    # KUN ÉN lagreknapp («Lagre» – lagrer OG åpner neste). «Lukk» og
    # «← Forrige» lagrer ALDRI – de spør via _bekreft_forkast() hvis det
    # finnes ulagrede endringer, ellers navigerer de rett. Fire kolonner i
    # fast DOM-rekkefølge (forrige, mellomrom, lukk, lagre) – se styles.py
    # for hvordan @media (max-width:640px) omorganiserer og stabler disse
    # fire på mobil via nth-child. st.container(key=...) gir den stabile
    # CSS-klassen "st-key-vurdering_knapperad" å style via. kol_lukk/
    # kol_lagre har LIK bredde (1.2/1.2) med vilje, slik at Streamlit sin
    # faste kolonne-avstand blir den eneste, jevne avstanden mellom dem.
    with st.container(key="vurdering_knapperad"):
        kol_forrige, _kol_mellomrom, kol_lukk, kol_lagre = st.columns([1.3, 3, 1.2, 1.2])
        with kol_forrige:
            if i > 0 and st.button("← Forrige", type="tertiary"):
                forrige_navn = navn_liste_butikker[i - 1]

                def _ga_forrige(forrige_navn=forrige_navn):
                    _bytt_til(forrige_navn)
                    st.session_state["_scroll_til_topp"] = True

                if _har_ulagrede_endringer(navn):
                    _bekreft_forkast(f"Du har endringer i **{navn}** som ikke er lagret. Gå til forrige butikk likevel?", _ga_forrige)
                else:
                    _ga_forrige()
                    st.rerun()
        with kol_lukk:
            if st.button("Lukk"):
                def _lukk():
                    st.session_state["_apnet_butikk"] = None

                if _har_ulagrede_endringer(navn):
                    _bekreft_forkast("Du har endringer som ikke er lagret – lukk likevel?", _lukk)
                else:
                    _lukk()
                    st.rerun()
        with kol_lagre:
            if st.button("Lagre", type="primary"):
                if lagre_denne(navn):
                    st.session_state["_toast_etter_rerun"] = True
                    neste = neste_uferdige(navn)
                    if neste:
                        _bytt_til(neste)
                        st.session_state["_scroll_til_topp"] = True
                    else:
                        st.session_state["_apnet_butikk"] = None
                st.rerun()


FANE_STATUS = {"gjenstar": "Ikke startet", "pabegynt": "Påbegynt", "ferdig": "Ferdig", "alle": None}
FANE_REKKEFOLGE = {"Påbegynt": 0, "Ikke startet": 1, "Ferdig": 2}


def vis_butikkliste():
    """Oppgaveliste-stil: faner (persistert via segmented_control – st.tabs
    hopper tilbake til første fane ved enhver rerun, så det duger ikke når
    man skal huske hvor brukeren stod). Paginert med «Vis flere» i stedet for
    én rad/knapp per butikk for alle 111 på én gang – det var den forrige,
    reelle ytelsesbuggen."""
    fane_valg = [("gjenstar", f"Gjenstår ({antall_gjenstar})"), ("pabegynt", f"Påbegynt ({antall_pabegynt})"), ("ferdig", f"Ferdig ({antall_ferdig})"), ("alle", "Alle")]
    fc1, fc2 = st.columns([3, 2])
    with fc1:
        # Streamlit nullstiller et NØKLET widgets session_state-verdi hvis
        # widgeten ikke blir rendret i en kjøring – og mens en butikk er
        # åpen, kjøres IKKE vis_butikkliste() (og dermed ikke dette
        # segmented_control-kallet) i det hele tatt. Uten mellomlageret under
        # ville valgt fane derfor «glemmes» hver gang man åpnet en butikk og
        # kom tilbake (bekreftet med en isolert repro under testing – fanen
        # hoppet til "Gjenstår" etter «Lagre og lukk», selv med key= satt).
        # "_vurdering_fane_sist" er en VANLIG session_state-nøkkel (ikke
        # bundet til noe widget), så den overlever uansett.
        if "_vurdering_fane" not in st.session_state:
            st.session_state["_vurdering_fane"] = st.session_state.get("_vurdering_fane_sist", "gjenstar")
        fane = st.segmented_control(
            "Fane", [v for v, _ in fane_valg], key="_vurdering_fane",
            format_func=dict(fane_valg).get, label_visibility="collapsed",
        )
        st.session_state["_vurdering_fane_sist"] = fane
    with fc2:
        sok = st.text_input("Søk", placeholder="Søk etter butikk …", icon=":material/search:", label_visibility="collapsed")

    # Nullstill paginering når fane/søk faktisk ENDRES (ikke når man bare går
    # tilbake til lista igjen – da skal man stå på samme «posisjon»).
    nokkel = (fane, sok)
    if st.session_state.get("_vurdering_forrige_filter") != nokkel:
        st.session_state["_vurdering_vis_antall"] = 20
        st.session_state["_vurdering_forrige_filter"] = nokkel
    vis_antall = st.session_state.get("_vurdering_vis_antall", 20)

    onsket_status = FANE_STATUS.get(fane, "Ikke startet")
    navn_filtrert = [n for n in navn_liste_butikker if (onsket_status is None or status(n) == onsket_status)]
    if sok:
        navn_filtrert = [n for n in navn_filtrert if sok.lower() in n.lower()]
    navn_filtrert.sort(key=lambda n: (FANE_REKKEFOLGE.get(status(n), 9), n))

    st.write("")
    if not navn_filtrert:
        tom_tekst = {
            "gjenstar": "Ingen gjenstående butikker 🎉", "pabegynt": "Ingen påbegynte butikker",
            "ferdig": "Ingen ferdige butikker ennå", "alle": "Ingen butikker matcher søket",
        }
        if fane == "alle" and not sok:
            tom_tekst["alle"] = "Alt er ferdig vurdert 🎉" if antall_ferdig == len(navn_liste_butikker) else "Ingen butikker funnet"
        st.caption(tom_tekst.get(fane, "Ingen treff"))
        return

    for navn in navn_filtrert[:vis_antall]:
        s = status(navn)
        info = butikker[navn]
        per_felt = status_per_fagfelt(navn)
        besvart_totalt = sum(b for b, _ in per_felt.values())
        totalt_mine = sum(t for _, t in per_felt.values())
        tooltip = " · ".join(f"{f}: {b}/{t}" for f, (b, t) in per_felt.items())

        slug = "".join(ch for ch in navn.lower() if ch.isalnum()) or "butikk"
        rad_nokkel = f"butikkrad_{'ferdig_' if s == 'Ferdig' else ''}{slug}"
        with st.container(key=rad_nokkel, border=True):
            c1, c2, c3, c4, c5 = st.columns([3, 1.3, 2, 1, 1.4])
            with c1:
                st.markdown(f'<div class="butikk-navn">{navn}</div><div class="butikk-bransje">{info.get("bransje", "–")}</div>', unsafe_allow_html=True)
            with c2:
                klasse_badge(info.get("klasse", "–"))
            with c3:
                st.markdown(f'<div class="butikk-fremdrift-tekst" title="{tooltip}">{besvart_totalt} av {totalt_mine} kriterier</div>', unsafe_allow_html=True)
                st.markdown(status_merkelapp_html(s), unsafe_allow_html=True)
            with c4:
                if har_kommentar(navn):
                    st.caption("💬")
                if info.get("url"):
                    st.link_button("Besøk ↗", info["url"], icon=":material/open_in_new:")
            with c5:
                if s == "Ferdig":
                    if st.button("Endre", key=f"endre_{navn}", use_container_width=True):
                        _bytt_til(navn)
                        st.rerun()
                else:
                    if st.button("Vurder →", key=f"vurder_{navn}", type="primary", use_container_width=True):
                        _bytt_til(navn)
                        st.rerun()

    if len(navn_filtrert) > vis_antall:
        if st.button(f"Vis flere ({len(navn_filtrert) - vis_antall} igjen)", use_container_width=True):
            st.session_state["_vurdering_vis_antall"] = vis_antall + 20
            st.rerun()


if st.session_state.get("_apnet_butikk"):
    with st.container(border=True):
        vis_vurderingsvisning()
else:
    vis_butikkliste()
