"""Side 2 – Vurdering: kjerneopplevelsen. Hvert jurymedlem er nå tildelt
FRIE KRITERIER (ikke et helt fagfelt) via Jury-fanen – se jury.py. Navn
velges med en vanlig st.selectbox bundet direkte til session_state via
key=, bevisst IKKE en egen skjult/kollapset tilstand slik forrige versjon
hadde – det var roten til at navn/fagfelt ikke kunne endres."""

from datetime import datetime

import streamlit as st

from components import fremdriftslinje, klasse_badge, lagringsstatus, onboarding_steg, topptekst, tom_tilstand
from data import IKKE_VURDERT, er_tall, snitt_av_scorer, status_for_scorer
from jury import aktive_kriterier, beskriv_tildeling, kriterier_per_fagfelt, mine_kriterier, read_criteria, read_jury
from sheets import read_ratings, read_stores, upsert_rating
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

if not butikker:
    onboarding_steg(1)
    tom_tilstand("📋", "Fant ingen butikker i regnearket", "Sjekk Innstillinger.")
    st.page_link("pages/innstillinger.py", label="Gå til Innstillinger", icon=":material/settings:")
    st.stop()

if not jury:
    st.info("Ingen jurymedlemmer er lagt til ennå – gjør det under **Innstillinger → Jury og kriterier**.", icon=":material/info:")
    st.page_link("pages/innstillinger.py", label="Gå til Innstillinger", icon=":material/settings:")
    st.stop()

# ── Jurymedlem – vanlig selectbox bundet til session_state (ikke skjult tilstand) ──
navn_liste = sorted(jury.keys())
forrige = st.session_state.get("_jurynavn")
jurynavn = st.selectbox("Ditt navn (jurymedlem)", navn_liste, key="_jurynavn")

if forrige and forrige != jurynavn and st.session_state.get("_har_ulagrede_endringer"):
    st.warning(f"Du byttet fra **{forrige}** med ulagrede endringer på butikken du sto på – de ble ikke lagret.", icon=":material/warning:")
st.session_state["_har_ulagrede_endringer"] = False

mine = mine_kriterier(jury, jurynavn)
beskrivelse = beskriv_tildeling(jurynavn, jury, kriterier_per_felt_alle)
if beskrivelse:
    st.caption(f"_{beskrivelse}_")

if not mine:
    tom_tilstand("🤷", "Ingen kriterier tildelt deg ennå", "Ta kontakt med juryleder for å bli tildelt kriterier å vurdere.")
    st.stop()

onboarding_steg(2)

# Mine kriterier, gruppert per fagfelt (i samme rekkefølge som fagfeltene vises ellers)
mine_per_felt = {felt: [k for k in krit if k in mine] for felt, krit in kriterier_per_felt_alle.items()}
mine_per_felt = {felt: krit for felt, krit in mine_per_felt.items() if krit}
mine_kriterier_flat = [k for krit in mine_per_felt.values() for k in krit]
kriterium_info = {k["kriterium"]: k for k in kriterier_fase3}

try:
    rating_data = read_ratings(sh)
except Exception as e:
    st.error(f"Kunne ikke lese vurderinger: {e}", icon=":material/error:")
    st.stop()

navn_liste_butikker = sorted(butikker.keys())


def scorer(navn):
    return rating_data.get(navn, {}).get("scorer", {})


def status(navn):
    return status_for_scorer(scorer(navn), mine_kriterier_flat)


def snitt(navn):
    return snitt_av_scorer(scorer(navn), mine_kriterier_flat)


def kommentar_for(navn, fagfelt):
    return rating_data.get(navn, {}).get("kommentarer", {}).get(fagfelt, "")


antall_ferdig = sum(1 for n in navn_liste_butikker if status(n) == "Ferdig")
snitt_verdier = [snitt(n) for n in navn_liste_butikker if snitt(n) is not None]
eget_snitt = (sum(snitt_verdier) / len(snitt_verdier)) if snitt_verdier else None

fremdriftslinje(
    (antall_ferdig / len(navn_liste_butikker)) if navn_liste_butikker else 0,
    f"Vurdert: {antall_ferdig} av {len(navn_liste_butikker)}" + (f" · eget snitt {eget_snitt:.2f}" if eget_snitt else ""),
)

visning = st.segmented_control("Visning", ["Fokus", "Mine butikker"], key="_visning_vurdering", default="Fokus", label_visibility="collapsed")
st.write("")


def _marker_endret():
    st.session_state["_har_ulagrede_endringer"] = True


def lagre_denne(navn):
    ok = True
    for fagfelt, kriterier in mine_per_felt.items():
        vurderinger = []
        for krit in kriterier:
            if st.session_state.get(f"na_{navn}_{krit}"):
                score = IKKE_VURDERT
            else:
                feedback_verdi = st.session_state.get(f"score_{navn}_{krit}")
                score = (feedback_verdi if feedback_verdi is not None else 2) + 1
            vurderinger.append((krit, score))
        kommentar = st.session_state.get(f"kom_{navn}_{fagfelt}", "")
        try:
            upsert_rating(sh, navn, jurynavn, fagfelt, vurderinger, kommentar)
        except Exception as e:
            st.session_state["_lagringstilstand"] = ("feil", str(e))
            ok = False
    if ok:
        st.session_state["_lagringstilstand"] = ("lagret", datetime.now().strftime("%H:%M"))
        st.session_state["_har_ulagrede_endringer"] = False
    return ok


def neste_uferdige(gjeldende):
    if gjeldende not in navn_liste_butikker:
        return navn_liste_butikker[0] if navn_liste_butikker else None
    start = navn_liste_butikker.index(gjeldende)
    for n in navn_liste_butikker[start + 1:] + navn_liste_butikker[:start]:
        if status(n) != "Ferdig":
            return n
    return None


@st.fragment
def vis_butikkort(navn):
    info = butikker[navn]
    i = navn_liste_butikker.index(navn)

    hc1, hc2 = st.columns([3, 1])
    with hc1:
        st.markdown(f"### {navn}")
        klasse_badge(info.get("klasse", "–"))
        st.caption(info.get("bransje", "–"))
        st.caption(f"Butikk {i + 1} av {len(navn_liste_butikker)}" + (" · ✅ ferdig" if status(navn) == "Ferdig" else " · påbegynt" if status(navn) == "Påbegynt" else ""))
    with hc2:
        if info.get("url"):
            st.link_button("Besøk butikk", info["url"], icon=":material/open_in_new:", use_container_width=True)
        navn_snitt = snitt(navn)
        if navn_snitt is not None:
            st.metric("Mitt snitt", f"{navn_snitt:.2f}")

    st.write("")
    for fagfelt, kriterier in mine_per_felt.items():
        farge = FAGFELT_FARGE.get(fagfelt, "#888")
        st.markdown(f'<div style="border-left:4px solid {farge};padding-left:10px;margin:14px 0 8px 0;font-weight:700;">{fagfelt}</div>', unsafe_allow_html=True)
        for krit in kriterier:
            eksisterende_score = scorer(navn).get(krit)
            var_na = eksisterende_score == IKKE_VURDERT
            info_k = kriterium_info.get(krit, {})

            kc1, kc2 = st.columns([3, 1])
            with kc1:
                tc1, tc2 = st.columns([5, 1])
                tc1.markdown(f"**{krit}**" + (f" — _{info_k.get('kort', '')}_" if info_k.get("kort") else ""))
                with tc2.popover("Les mer", icon=":material/help:", use_container_width=True):
                    if info_k.get("utfyllende"):
                        st.markdown(info_k["utfyllende"])
                    st.markdown(f"**1:** {info_k.get('skala1', '–')}")
                    st.markdown(f"**3:** {info_k.get('skala3', '–')}")
                    st.markdown(f"**5:** {info_k.get('skala5', '–')}")
                    if info_k.get("eksempler"):
                        st.caption(info_k["eksempler"])

                na_key = f"na_{navn}_{krit}"
                if na_key not in st.session_state:
                    st.session_state[na_key] = var_na
                st.checkbox("Kan ikke vurdere", key=na_key, on_change=_marker_endret)
                score_key = f"score_{navn}_{krit}"
                if score_key not in st.session_state:
                    st.session_state[score_key] = (int(eksisterende_score) - 1) if er_tall(eksisterende_score) else 2
                if not st.session_state[na_key]:
                    st.feedback("stars", key=score_key, on_change=_marker_endret)
            st.write("")

        st.text_area(
            f"Kommentar – {fagfelt}", value=kommentar_for(navn, fagfelt), key=f"kom_{navn}_{fagfelt}",
            placeholder="Skriv en samlet kommentar for dette fagfeltet (valgfritt)…", height=70,
            on_change=_marker_endret,
        )

    st.write("")
    tilstand = st.session_state.get("_lagringstilstand")
    if tilstand:
        lagringsstatus(tilstand[0], tilstand[1])

    a1, a2, a3 = st.columns([1, 1, 2])
    if a1.button("← Forrige", disabled=(i == 0), use_container_width=True):
        lagre_denne(navn)
        st.session_state["_fokus_navn"] = navn_liste_butikker[max(0, i - 1)]
        st.rerun()
    if a2.button("Hopp over →", disabled=(i >= len(navn_liste_butikker) - 1), use_container_width=True, help="Går videre UTEN å lagre endringer på denne butikken."):
        st.session_state["_fokus_navn"] = navn_liste_butikker[i + 1]
        st.rerun()
    if a3.button("💾 Lagre og neste", type="primary", use_container_width=True):
        if lagre_denne(navn):
            st.session_state["_fokus_navn"] = neste_uferdige(navn)
            st.rerun()
        else:
            st.rerun()


if visning == "Mine butikker":
    sok = st.text_input("🔍 Søk etter butikk", "")
    fc1, fc2 = st.columns(2)
    status_filter = fc1.multiselect("Status", ["Ikke startet", "Påbegynt", "Ferdig"])
    klasse_filter = fc2.multiselect("Størrelsesklasse", sorted({butikker[n].get("klasse", "") for n in navn_liste_butikker if butikker[n].get("klasse")}))

    rader, navn_for_rad = [], []
    for navn in navn_liste_butikker:
        info = butikker[navn]
        if sok and sok.lower() not in navn.lower():
            continue
        s = status(navn)
        if status_filter and s not in status_filter:
            continue
        if klasse_filter and info.get("klasse") not in klasse_filter:
            continue
        sn = snitt(navn)
        rader.append({"Butikk": navn, "Klasse": info.get("klasse", "–"), "Bransje": info.get("bransje", "–"), "Status": s, "Mitt snitt": f"{sn:.2f}" if sn is not None else "–"})
        navn_for_rad.append(navn)

    rekkefolge_vekt = {"Ikke startet": 0, "Påbegynt": 1, "Ferdig": 2}
    sortert = sorted(zip(rader, navn_for_rad), key=lambda par: rekkefolge_vekt.get(par[0]["Status"], 0))
    rader = [r for r, _ in sortert]
    navn_for_rad = [n for _, n in sortert]

    st.caption(f"{len(rader)} av {len(navn_liste_butikker)} butikker")
    hendelse = st.dataframe(rader, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
    if hendelse and hendelse.selection and hendelse.selection.rows:
        valgt = hendelse.selection.rows[0]
        st.session_state["_fokus_navn"] = navn_for_rad[valgt]
        st.session_state["_visning_vurdering"] = "Fokus"
        st.rerun()

else:  # Fokus
    if "_fokus_navn" not in st.session_state or st.session_state["_fokus_navn"] not in navn_liste_butikker:
        st.session_state["_fokus_navn"] = next((n for n in navn_liste_butikker if status(n) != "Ferdig"), navn_liste_butikker[0])

    if antall_ferdig == len(navn_liste_butikker):
        st.success("🎉 Du har vurdert alle dine tildelte kriterier for alle butikkene!", icon=":material/celebration:")
        kol = st.columns(2)
        kol[0].metric("Vurdert", f"{antall_ferdig} av {len(navn_liste_butikker)}")
        kol[1].metric("Eget snitt", f"{eget_snitt:.2f}" if eget_snitt else "–")
        st.page_link("pages/butikker.py", label="Se totaloversikten over alle butikkene", icon=":material/storefront:")
        st.divider()
        st.caption("Du kan fortsatt åpne og redigere enkeltbutikker under.")

    with st.container(border=True):
        vis_butikkort(st.session_state["_fokus_navn"])
