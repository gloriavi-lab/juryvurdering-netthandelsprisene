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

from components import fremdriftslinje, klasse_badge, lagringsstatus, topptekst, tom_tilstand
from data import IKKE_VURDERT, er_tall, grupper_vurderinger, mine_scorer, snitt_delt_kriterium, status_for_scorer
from jury import aktive_kriterier, beskriv_tildeling, kriterier_per_fagfelt, mine_kriterier, read_criteria, read_jury
from sheets import read_generelle_kommentarer, read_stores, read_vurderinger, upsert_generell_kommentar, upsert_vurdering
from theme import FAGFELT_FARGE

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

fremdriftslinje(
    (antall_ferdig / len(navn_liste_butikker)) if navn_liste_butikker else 0,
    f"{antall_ferdig} av {len(navn_liste_butikker)} butikker ferdig · {antall_pabegynt} påbegynt",
)
st.write("")


def _nullstill_butikk_state(navn):
    """Fjerner session_state-nøklene for denne butikkens widgetar, slik at de
    seedes PÅ NYTT fra det ferske sheet-innholdet – kalles kun når visningen
    faktisk BYTTER til en annen butikk enn sist (se forklaring øverst i fila)."""
    for k in mine_kriterier_flat:
        for prefiks in ("seg_", "kom_krit_"):
            st.session_state.pop(f"{prefiks}{navn}_{k}", None)
    st.session_state.pop(f"generell_{navn}", None)


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

            if er_tall(score) and int(score) <= 3 and not kommentar_krit:
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


def _bytt_til(navn):
    forrige = st.session_state.get("_sist_vist_butikk")
    if forrige != navn:
        _nullstill_butikk_state(navn)
        st.session_state["_sist_vist_butikk"] = navn
    st.session_state["_apnet_butikk"] = navn


@st.fragment
def vis_vurderingsvisning():
    navn = st.session_state.get("_apnet_butikk")
    if navn not in navn_liste_butikker:
        st.session_state["_apnet_butikk"] = None
        st.rerun()
    info = butikker[navn]
    i = navn_liste_butikker.index(navn)

    if st.button("← Tilbake til lista", icon=":material/arrow_back:"):
        st.session_state["_apnet_butikk"] = None
        st.rerun(scope="fragment")
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
        st.rerun(scope="fragment")

    st.write("")
    for fagfelt, kriterier in mine_per_felt.items():
        farge = FAGFELT_FARGE.get(fagfelt, "#888")
        st.markdown(f'<div style="border-left:4px solid {farge};padding-left:10px;margin:14px 0 10px 0;font-weight:700;">{fagfelt}</div>', unsafe_allow_html=True)
        for krit in kriterier:
            eksisterende = mine_oppslag.get((navn, krit), {})
            eksisterende_score = eksisterende.get("score")
            var_na = eksisterende_score == IKKE_VURDERT
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
                st.session_state[seg_key] = "Kan ikke vurdere" if var_na else (int(eksisterende_score) if er_tall(eksisterende_score) else None)
            valg = st.segmented_control("Score", [1, 2, 3, 4, 5, "Kan ikke vurdere"], key=seg_key, label_visibility="collapsed")

            kom_key = f"kom_krit_{navn}_{krit}"
            pakrevd = isinstance(valg, int) and valg <= 3
            st.text_area(
                "Kommentar" + (" (påkrevd)" if pakrevd else " (valgfritt)"), value=eksisterende.get("kommentar", ""),
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

    a1, a2 = st.columns(2)
    if a1.button("← Forrige", disabled=(i == 0), use_container_width=True):
        lagre_denne(navn)
        _bytt_til(navn_liste_butikker[max(0, i - 1)])
        st.rerun(scope="fragment")
    if a2.button("💾 Lagre og neste", type="primary", use_container_width=True):
        if lagre_denne(navn):
            _bytt_til(neste_uferdige(navn) or navn)
            st.rerun(scope="fragment")
        else:
            st.rerun(scope="fragment")


def vis_butikkliste():
    """Bruker ÉN st.dataframe med klikk-på-rad, ikke ett eget knapp+boks per
    butikk (opptil 111 stykker) – det siste gjorde siden tung nok til at det
    kunne føles helt fastlåst/uresponsiv (sannsynlig årsak til at vurdering
    sluttet å fungere etter forrige runde)."""
    sok = st.text_input("Søk", placeholder="Søk etter butikk …", icon=":material/search:", label_visibility="collapsed")
    fc1, fc2 = st.columns([2, 1])
    status_filter = fc1.multiselect("Status", ["Ikke startet", "Påbegynt", "Ferdig"], placeholder="Alle statuser", label_visibility="collapsed")
    kun_uferdige = fc2.checkbox("Vis kun ikke ferdige")

    rader, navn_for_rad = [], []
    for navn in navn_liste_butikker:
        if sok and sok.lower() not in navn.lower():
            continue
        s = status(navn)
        if status_filter and s not in status_filter:
            continue
        if kun_uferdige and s == "Ferdig":
            continue
        info = butikker[navn]
        per_felt = status_per_fagfelt(navn)
        rader.append({
            "Butikk": navn, "Klasse": info.get("klasse", "–"),
            "Status": _gyldig_status_tekst(navn),
            "Mine kriterier": " · ".join(f"{b}/{t} {f[:3]}" for f, (b, t) in per_felt.items()),
            "💬": "💬" if har_kommentar(navn) else "",
            "Besøk": info.get("url", ""),
        })
        navn_for_rad.append(navn)

    st.caption(f"{len(rader)} av {len(navn_liste_butikker)} butikker – klikk en rad for å vurdere")
    hendelse = st.dataframe(
        rader, hide_index=True, use_container_width=True, on_select="rerun", selection_mode="single-row",
        column_config={"Besøk": st.column_config.LinkColumn("Besøk", display_text="Besøk →")},
    )
    if hendelse and hendelse.selection and hendelse.selection.rows:
        _bytt_til(navn_for_rad[hendelse.selection.rows[0]])
        st.rerun()


if st.session_state.get("_apnet_butikk"):
    with st.container(border=True):
        vis_vurderingsvisning()
else:
    vis_butikkliste()
