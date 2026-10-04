"""Side 2 – Vurdering: kjerneopplevelsen. Fokusmodus (én butikk om gangen) og
"Mine butikker" (søkbar/filtrerbar oversikt). Siden hvert fagfelt dekkes av
ÉN fast ekspert for ALLE butikker (ikke en tildelt delmengde), er "mine
butikker" nå alle butikkene – filtrert/sortert for akkurat ditt fagfelt."""

from datetime import datetime

import streamlit as st

from components import fremdriftslinje, jury_velger, klasse_badge, lagringsstatus, onboarding_steg, topptekst, tom_tilstand
from data import IKKE_VURDERT, JURY_FAGFELT_FORSLAG, KRITERIER_PER_FAGFELT, SKALA_FORKLARING, er_tall, snitt_av_scorer, status_for_scorer
from sheets import read_ratings, read_stores, upsert_rating

topptekst("Vurdering")

sh = st.session_state.get("_sh")
if not sh:
    st.warning("Google Sheets-tilkoblingen mangler – gå til **Innstillinger** for å sjekke tilkoblingen.", icon=":material/cloud_off:")
    st.stop()

try:
    butikker, _ = read_stores(sh)
except Exception as e:
    st.error(f"Kunne ikke lese butikklisten fra regnearket: {e}", icon=":material/error:")
    st.stop()

if not butikker:
    onboarding_steg(1)
    tom_tilstand("📋", "Fant ingen butikker i regnearket", "Sjekk at fanen «Rangering fase 1» finnes og har data, under Innstillinger.")
    st.page_link("pages/innstillinger.py", label="Gå til Innstillinger", icon=":material/settings:")
    st.stop()

# ── Jurymedlem + fagfelt – kompakt når valgt, full velger når ikke ──
if st.session_state.get("_jurynavn") and not st.session_state.get("_rediger_jury"):
    c1, c2 = st.columns([6, 1])
    c1.markdown(f"**{st.session_state['_jurynavn']}** · {st.session_state['_fagfelt']}")
    if c2.button("Endre", use_container_width=True):
        st.session_state["_rediger_jury"] = True
        st.rerun()
    jurynavn, fagfelt_valgt = st.session_state["_jurynavn"], st.session_state["_fagfelt"]
else:
    jurynavn, fagfelt_valgt = jury_velger(JURY_FAGFELT_FORSLAG)
    if jurynavn:
        st.session_state["_rediger_jury"] = False

if not jurynavn:
    onboarding_steg(1)
    st.info("Velg (eller skriv inn) deg selv over for å begynne å vurdere.", icon=":material/badge:")
    st.stop()

onboarding_steg(2)
kriterier_denne = KRITERIER_PER_FAGFELT[fagfelt_valgt]

try:
    rating_data = read_ratings(sh)
except Exception as e:
    st.error(f"Kunne ikke lese vurderinger fra regnearket: {e}", icon=":material/error:")
    st.stop()

navn_liste = sorted(butikker.keys())


def scorer(navn):
    return rating_data.get(navn, {}).get("scorer", {})


def status(navn):
    return status_for_scorer(scorer(navn), kriterier_denne)


def snitt(navn):
    return snitt_av_scorer(scorer(navn), kriterier_denne)


def kommentar_for(navn):
    return rating_data.get(navn, {}).get("kommentarer", {}).get(fagfelt_valgt, "")


def sist_endret(navn):
    return rating_data.get(navn, {}).get("sist_endret", "")


antall_ferdig = sum(1 for n in navn_liste if status(n) == "Ferdig")
snitt_verdier = [snitt(n) for n in navn_liste if snitt(n) is not None]
eget_snitt = (sum(snitt_verdier) / len(snitt_verdier)) if snitt_verdier else None

fremdriftslinje(
    (antall_ferdig / len(navn_liste)) if navn_liste else 0,
    f"Vurdert: {antall_ferdig} av {len(navn_liste)} · {fagfelt_valgt}" + (f" · eget snitt {eget_snitt:.2f}" if eget_snitt else ""),
)

visning = st.segmented_control("Visning", ["Fokus", "Mine butikker"], key="_visning_vurdering", default="Fokus", label_visibility="collapsed")
st.write("")


def lagre_denne(navn):
    vurderinger = []
    for krit in kriterier_denne:
        if st.session_state.get(f"na_{navn}_{krit}"):
            score = IKKE_VURDERT
        else:
            feedback_verdi = st.session_state.get(f"score_{navn}_{krit}")
            score = (feedback_verdi if feedback_verdi is not None else 2) + 1  # 0-4 -> 1-5
        vurderinger.append((krit, score))
    kommentar = st.session_state.get(f"kom_{navn}", "")
    try:
        upsert_rating(sh, navn, jurynavn, fagfelt_valgt, vurderinger, kommentar)
        st.session_state["_lagringstilstand"] = ("lagret", datetime.now().strftime("%H:%M"))
        return True
    except Exception as e:
        st.session_state["_lagringstilstand"] = ("feil", str(e))
        return False


def neste_uferdige(gjeldende):
    if gjeldende not in navn_liste:
        return navn_liste[0] if navn_liste else None
    start = navn_liste.index(gjeldende)
    rekkefolge = navn_liste[start + 1:] + navn_liste[:start]
    for n in rekkefolge:
        if status(n) != "Ferdig":
            return n
    return None


@st.fragment
def vis_butikkort(navn):
    info = butikker[navn]
    i = navn_liste.index(navn)

    hc1, hc2 = st.columns([3, 1])
    with hc1:
        st.markdown(f"### {navn}")
        klasse_badge(info.get("klasse", "–"))
        st.caption(info.get("bransje", "–"))
        st.caption(f"Butikk {i + 1} av {len(navn_liste)}" + (" · ✅ ferdig" if status(navn) == "Ferdig" else " · påbegynt" if status(navn) == "Påbegynt" else ""))
    with hc2:
        if info.get("url"):
            st.link_button("Besøk butikk", info["url"], icon=":material/open_in_new:", use_container_width=True)
        navn_snitt = snitt(navn)
        if navn_snitt is not None:
            st.metric("Snitt (dette fagfeltet)", f"{navn_snitt:.2f}")

    st.write("")
    for krit in kriterier_denne:
        eksisterende_score = scorer(navn).get(krit)
        var_na = eksisterende_score == IKKE_VURDERT
        kc1, kc2 = st.columns([3, 1])
        with kc1:
            st.markdown(f"**{krit}**", help=SKALA_FORKLARING)
            na_key = f"na_{navn}_{krit}"
            if na_key not in st.session_state:
                st.session_state[na_key] = var_na
            ikke_vurder = st.checkbox("Kan ikke vurdere", key=na_key)
            score_key = f"score_{navn}_{krit}"
            if score_key not in st.session_state:
                st.session_state[score_key] = (int(eksisterende_score) - 1) if er_tall(eksisterende_score) else 2
            if not ikke_vurder:
                st.feedback("stars", key=score_key)
        st.write("")

    st.text_area(
        f"Kommentar – {fagfelt_valgt}", value=kommentar_for(navn), key=f"kom_{navn}",
        placeholder="Skriv en samlet kommentar for dette fagfeltet (valgfritt)…", height=80,
    )

    st.write("")
    tilstand = st.session_state.get("_lagringstilstand")
    if tilstand:
        lagringsstatus(tilstand[0], tilstand[1])
    sist = sist_endret(navn)
    if sist:
        st.caption(f"Sist endret {sist}")

    a1, a2, a3 = st.columns([1, 1, 2])
    if a1.button("← Forrige", disabled=(i == 0), use_container_width=True):
        lagre_denne(navn)
        st.session_state["_fokus_navn"] = navn_liste[max(0, i - 1)]
        st.rerun()
    if a2.button("Hopp over →", disabled=(i >= len(navn_liste) - 1), use_container_width=True, help="Går videre UTEN å lagre endringer på denne butikken."):
        st.session_state["_fokus_navn"] = navn_liste[i + 1]
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
    klasse_filter = fc2.multiselect("Størrelsesklasse", sorted({butikker[n].get("klasse", "") for n in navn_liste if butikker[n].get("klasse")}))

    rader, navn_for_rad = [], []
    for navn in navn_liste:
        info = butikker[navn]
        if sok and sok.lower() not in navn.lower():
            continue
        s = status(navn)
        if status_filter and s not in status_filter:
            continue
        if klasse_filter and info.get("klasse") not in klasse_filter:
            continue
        har_na = any(scorer(navn).get(k) == IKKE_VURDERT for k in kriterier_denne)
        sn = snitt(navn)
        rader.append({
            "Butikk": navn, "Klasse": info.get("klasse", "–"), "Bransje": info.get("bransje", "–"),
            "Status": s, "Mitt snitt": f"{sn:.2f}" if sn is not None else "–",
            "Kan ikke vurdere brukt": "Ja" if har_na else "", "Sist endret": sist_endret(navn),
        })
        navn_for_rad.append(navn)

    rekkefolge_vekt = {"Ikke startet": 0, "Påbegynt": 1, "Ferdig": 2}
    sortert = sorted(zip(rader, navn_for_rad), key=lambda par: rekkefolge_vekt.get(par[0]["Status"], 0))
    rader = [r for r, _ in sortert]
    navn_for_rad = [n for _, n in sortert]

    st.caption(f"{len(rader)} av {len(navn_liste)} butikker")
    hendelse = st.dataframe(rader, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
    if hendelse and hendelse.selection and hendelse.selection.rows:
        valgt = hendelse.selection.rows[0]
        st.session_state["_fokus_navn"] = navn_for_rad[valgt]
        st.session_state["_visning_vurdering"] = "Fokus"
        st.rerun()

else:  # Fokus
    if "_fokus_navn" not in st.session_state or st.session_state["_fokus_navn"] not in navn_liste:
        st.session_state["_fokus_navn"] = next((n for n in navn_liste if status(n) != "Ferdig"), navn_liste[0])

    if antall_ferdig == len(navn_liste):
        st.success("🎉 Du har vurdert alle butikkene på ditt fagfelt!", icon=":material/celebration:")
        klasser_i_bruk = sorted({butikker[n].get("klasse", "") for n in navn_liste if butikker[n].get("klasse")})
        kol = st.columns(2 + len(klasser_i_bruk))
        kol[0].metric("Vurdert", f"{antall_ferdig} av {len(navn_liste)}")
        kol[1].metric("Eget snitt", f"{eget_snitt:.2f}" if eget_snitt else "–")
        for idx, klasse in enumerate(klasser_i_bruk):
            i_klasse = [n for n in navn_liste if butikker[n].get("klasse") == klasse]
            ferdig_i_klasse = sum(1 for n in i_klasse if status(n) == "Ferdig")
            kol[2 + idx].metric(klasse, f"{ferdig_i_klasse}/{len(i_klasse)}")
        st.page_link("pages/butikker.py", label="Se totaloversikten over alle butikkene", icon=":material/storefront:")
        st.divider()
        st.caption("Du kan fortsatt åpne og redigere enkeltbutikker under.")

    with st.container(border=True):
        vis_butikkort(st.session_state["_fokus_navn"])
