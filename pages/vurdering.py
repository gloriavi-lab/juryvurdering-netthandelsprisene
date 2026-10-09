"""Side 2 – Vurdering. Butikkliste er standardvisningen; klikk en butikk for
å vurdere den. Lagrer til den nye "Vurderinger"-fanen (én rad per butikk +
jurymedlem + kriterium – se sheets.py). Tall 1–5 i stedet for stjerner,
kommentar per kriterium (påkrevd ved 1–3), ingen fagfelt-nivå-kommentar.

VIKTIG tilstandshåndtering: nøklene for score/kommentar-widgetene nullstilles
EKSPLISITT når brukeren bytter til en ANNEN butikk (sammenlignet med forrige
rad i session_state), slik at visningen alltid viser det som faktisk er
lagret – ikke en tilfeldig gammel verdi fra en tidligere visning i samme
nettleserøkt. Det var roten til at en slettet kommentar kunne "komme
tilbake" og at en score kunne se ut til å forsvinne."""

from datetime import datetime

import streamlit as st

from components import fremdriftslinje, klasse_badge, lagringsstatus, status_merkelapp_html, topptekst, tom_tilstand
from data import IKKE_VURDERT, grupper_vurderinger, mine_scorer, normalize_score, snitt_delt_kriterium, status_for_scorer
from jury import aktive_kriterier, beskriv_tildeling, kriterier_per_fagfelt, mine_kriterier, read_criteria, read_jury
from sheets import read_generelle_kommentarer, read_stores, read_vurderinger, upsert_generell_kommentar, upsert_vurdering
from theme import FAGFELT_FARGE, STATUS_FARGE, STATUS_TEKST, STATUS_TONE

topptekst("Vurdering")

sh = st.session_state.get("_sh")
if not sh:
    st.warning("Google Sheets-tilkoblingen mangler – gå til **Innstillinger**.", icon=":material/cloud_off:")
    st.stop()

try:
    butikker, _ = read_stores(sh)
    jury = read_jury(sh)
    alle_kriterier = read_criteria(sh)
except Exception as e:
    st.error(f"Kunne ikke lese regnearket: {e}", icon=":material/error:")
    st.stop()

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

try:
    alle_vurderinger = read_vurderinger(sh)
    alle_generelle = read_generelle_kommentarer(sh)
except Exception as e:
    st.error(f"Kunne ikke lese vurderinger: {e}", icon=":material/error:")
    st.stop()

mine_oppslag = mine_scorer(alle_vurderinger, jurynavn)  # (butikk,kriterium) -> {score,kommentar,sist_endret}
gruppert_alle = grupper_vurderinger(alle_vurderinger)  # for kommentar-ikon på tvers av jury
generell_per_butikk = {}
for g in alle_generelle:
    generell_per_butikk.setdefault(g["butikk"], []).append(g)

navn_liste_butikker = sorted(butikker.keys())


def mine_scorer_for(navn):
    return {krit: mine_oppslag[(navn, krit)]["score"] for krit in mine_kriterier_flat if (navn, krit) in mine_oppslag}


def status(navn):
    return status_for_scorer(mine_scorer_for(navn), mine_kriterier_flat)


def status_per_fagfelt(navn):
    resultat = {}
    for fagfelt, kriterier in mine_per_felt.items():
        besvart = sum(1 for k in kriterier if (navn, k) in mine_oppslag)
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
    ok = True
    manglende_kommentar = []
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

            try:
                upsert_vurdering(sh, navn, jurynavn, fagfelt, krit, score, kommentar_krit)
            except Exception as e:
                st.session_state["_lagringstilstand"] = ("feil", str(e))
                ok = False

    if manglende_kommentar:
        st.session_state["_lagringstilstand"] = ("feil", "Kommentar er påkrevd ved score 1–3: " + ", ".join(manglende_kommentar))
        return False

    generell_tekst = (st.session_state.get(f"generell_{navn}") or "").strip()
    try:
        upsert_generell_kommentar(sh, navn, jurynavn, generell_tekst)
    except Exception as e:
        st.session_state["_lagringstilstand"] = ("feil", str(e))
        ok = False

    if ok:
        st.session_state["_lagringstilstand"] = ("lagret", datetime.now().strftime("%H:%M"))
    return ok


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


@st.fragment
def vis_vurderingsvisning():
    navn = st.session_state.get("_apnet_butikk")
    if navn not in navn_liste_butikker:
        st.session_state["_apnet_butikk"] = None
        st.rerun()
    info = butikker[navn]
    i = navn_liste_butikker.index(navn)

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

    hopp_til = st.selectbox(
        "Hopp direkte til en annen butikk", navn_liste_butikker,
        index=i, key="_hopp_til_butikk",
        format_func=lambda n: f"{_gyldig_status_tekst(n).split(' ')[0]} {n}",
    )
    if hopp_til != navn:
        lagre_denne(navn)
        _bytt_til(hopp_til)
        st.rerun()

    st.write("")
    for fagfelt, kriterier in mine_per_felt.items():
        farge = FAGFELT_FARGE.get(fagfelt, "#888")
        st.markdown(f'<div style="border-left:4px solid {farge};padding-left:10px;margin:14px 0 10px 0;font-weight:700;">{fagfelt}</div>', unsafe_allow_html=True)
        for krit in kriterier:
            eksisterende = mine_oppslag.get((navn, krit), {})
            eksisterende_score = normalize_score(eksisterende.get("score"))
            info_k = kriterium_info.get(krit, {})

            st.markdown(f"**{krit}**" + (f"  \n_{info_k['kort']}_" if info_k.get("kort") else ""))
            with st.popover("Les mer", icon=":material/help:"):
                if info_k.get("utfyllende"):
                    st.markdown(info_k["utfyllende"])
                st.markdown(f"**1:** {info_k.get('skala1', '–')}")
                st.markdown(f"**3:** {info_k.get('skala3', '–')}")
                st.markdown(f"**5:** {info_k.get('skala5', '–')}")
                if info_k.get("eksempler"):
                    st.caption(info_k["eksempler"])

            seg_key = f"seg_{navn}_{krit}"
            if seg_key not in st.session_state:
                st.session_state[seg_key] = eksisterende_score if isinstance(eksisterende_score, (int, str)) else None
            valg = st.segmented_control("Score", [1, 2, 3, 4, 5, "Kan ikke vurdere"], key=seg_key, label_visibility="collapsed")

            kom_key = f"kom_krit_{navn}_{krit}"
            pakrevd = isinstance(valg, (int, float)) and valg <= 3
            st.text_area(
                "Kommentar" + (" (påkrevd ved 1–3)" if pakrevd else " (valgfritt)"), value=eksisterende.get("kommentar", ""),
                key=kom_key, placeholder=f"Kommentar til «{krit}»" + (" – påkrevd ved lav score" if pakrevd else "…"),
                height=68,
            )
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
    tilstand = st.session_state.get("_lagringstilstand")
    if tilstand:
        lagringsstatus(tilstand[0], tilstand[1])

    # NB: disse rerunner HELE siden (ikke scope="fragment"), bevisst – de
    # følger alltid etter en lagre_denne()-skriving. alle_vurderinger/
    # mine_oppslag/statuskortene øverst beregnes KUN i toppen av scriptet,
    # UTENFOR dette fragmentet, så en fragment-rerun ville aldri sett det
    # som nettopp ble lagret (det var den reelle årsaken til at en butikk
    # kunne vise "ingen score markert" rett etter lagring – scriptet hadde
    # bare ikke kjørt på nytt ennå og viste fortsatt den gamle, før-lagring
    # dataen, se bruker-rapportert feil).
    a1, a2 = st.columns(2)
    if a1.button("← Forrige", disabled=(i == 0), use_container_width=True):
        lagre_denne(navn)
        _bytt_til(navn_liste_butikker[max(0, i - 1)])
        st.rerun()
    if a2.button("💾 Lagre og neste", type="primary", use_container_width=True):
        if lagre_denne(navn):
            st.toast("Lagret ✓", icon=":material/check_circle:")
            _bytt_til(neste_uferdige(navn) or navn)
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
        fane = st.segmented_control(
            "Fane", [v for v, _ in fane_valg], key="_vurdering_fane", default="gjenstar",
            format_func=dict(fane_valg).get, label_visibility="collapsed",
        )
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
