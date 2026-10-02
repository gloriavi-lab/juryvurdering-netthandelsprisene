"""Side 2 – Vurdering: kjerneopplevelsen. Fokusmodus (én tildelt butikk om
gangen) og "Mine butikker" (søkbar/filtrerbar oversikt over EGNE tildelte
butikker, erstatter tidligere Liste-modus). All tilstand (navn, fagfelt)
ligger i st.session_state og brukes likt på alle sider."""

from datetime import datetime

import streamlit as st

from components import fremdriftslinje, jury_velger, klasse_badge, lagringsstatus, onboarding_steg, topptekst, tom_tilstand
from data import KRITERIER_PER_FAGFELT, SKALA_FORKLARING, er_tall, snitt_for_butikk, status_for_butikk
from sheets import butikker_for_jurymedlem, read_assignments, read_jury, read_ratings, read_stores, upsert_rating

IKKE_VURDERT = "N/A"

topptekst("Vurdering")

sh = st.session_state.get("_sh")
if not sh:
    st.warning("Google Sheets-tilkoblingen mangler – gå til **Innstillinger** for å sjekke tilkoblingen.", icon=":material/cloud_off:")
    st.stop()

butikker, _ = read_stores(sh)
jury = read_jury(sh)

if not butikker:
    onboarding_steg(1)
    tom_tilstand("📋", "Regnearket er ikke satt opp ennå", "Gå til Innstillinger og last opp Fase 1-Excel-fila for å komme i gang.")
    st.page_link("pages/innstillinger.py", label="Gå til Innstillinger", icon=":material/settings:")
    st.stop()

if not jury:
    st.info("Ingen jurymedlemmer registrert ennå i 'Jury'-fanen – legg til deg selv under.", icon=":material/info:")

# ── Jurymedlem + fagfelt – kompakt når valgt, full velger når ikke ──
if st.session_state.get("_jurynavn") and not st.session_state.get("_rediger_jury"):
    c1, c2 = st.columns([6, 1])
    c1.markdown(f"**{st.session_state['_jurynavn']}** · {st.session_state['_fagfelt']}")
    if c2.button("Endre", use_container_width=True):
        st.session_state["_rediger_jury"] = True
        st.rerun()
    jurynavn, fagfelt_valgt = st.session_state["_jurynavn"], st.session_state["_fagfelt"]
else:
    jurynavn, fagfelt_valgt = jury_velger(jury)
    if jurynavn:
        st.session_state["_rediger_jury"] = False

if not jurynavn:
    onboarding_steg(1)
    st.info("Velg (eller legg til) deg selv over for å begynne å vurdere.", icon=":material/badge:")
    st.stop()

onboarding_steg(2)
kriterier_denne = KRITERIER_PER_FAGFELT[fagfelt_valgt]

# ── Data for denne økten ──
tildeling = read_assignments(sh)
alle_ider = sorted(butikker.keys(), key=lambda i: butikker[i]["navn"])
mine_ider = butikker_for_jurymedlem(tildeling, jurynavn, alle_ider)

rå_rader = read_ratings(sh)
mine_vurderinger = {}  # (butikk_id, kriterium) -> {score, kommentar, sist_endret}
for rad in (rå_rader[1:] if len(rå_rader) > 1 else []):
    if len(rad) >= 7 and rad[2] == jurynavn:
        mine_vurderinger[(rad[0], rad[4])] = {"score": rad[5], "kommentar": rad[6], "sist_endret": rad[7] if len(rad) > 7 else ""}


def status(butikk_id):
    return status_for_butikk(butikk_id, kriterier_denne, mine_vurderinger)


def snitt(butikk_id):
    return snitt_for_butikk(butikk_id, kriterier_denne, mine_vurderinger)


def sist_endret(butikk_id):
    tider = [mine_vurderinger[(butikk_id, k)]["sist_endret"] for k in kriterier_denne if (butikk_id, k) in mine_vurderinger]
    return max(tider) if tider else ""


antall_ferdig = sum(1 for i in mine_ider if status(i) == "Ferdig")
antall_pabegynt = sum(1 for i in mine_ider if status(i) == "Påbegynt")
antall_ikke_startet = len(mine_ider) - antall_ferdig - antall_pabegynt
snitt_verdier = [snitt(i) for i in mine_ider if snitt(i) is not None]
eget_snitt = (sum(snitt_verdier) / len(snitt_verdier)) if snitt_verdier else None

# ── Fremdrift (basert på TILDELTE butikker, ikke alle 111) ──
fremdriftslinje(
    (antall_ferdig / len(mine_ider)) if mine_ider else 0,
    f"Vurdert: {antall_ferdig} av {len(mine_ider)} · {fagfelt_valgt}" + (f" · eget snitt {eget_snitt:.2f}" if eget_snitt else ""),
)

visning = st.segmented_control("Visning", ["Fokus", "Mine butikker"], key="_visning_vurdering", default="Fokus", label_visibility="collapsed")
st.write("")


def lagre_denne(butikk_id):
    vurderinger = []
    for krit in kriterier_denne:
        ikke_vurdert_key = f"na_{butikk_id}_{krit}"
        if st.session_state.get(ikke_vurdert_key):
            score = IKKE_VURDERT
        else:
            feedback_verdi = st.session_state.get(f"score_{butikk_id}_{krit}")
            score = (feedback_verdi if feedback_verdi is not None else 2) + 1  # 0-4 -> 1-5
        kommentar = st.session_state.get(f"kom_{butikk_id}_{krit}", "")
        vurderinger.append((krit, score, kommentar))
    try:
        upsert_rating(sh, butikk_id, butikker[butikk_id]["navn"], jurynavn, fagfelt_valgt, vurderinger)
        st.session_state["_lagringstilstand"] = ("lagret", datetime.now().strftime("%H:%M"))
        return True
    except Exception as e:
        st.session_state["_lagringstilstand"] = ("feil", str(e))
        return False


def neste_uferdige(gjeldende_id):
    """Finner neste butikk i min tildelte liste som ikke er ferdig, med wrap-around."""
    if gjeldende_id not in mine_ider:
        return mine_ider[0] if mine_ider else None
    start = mine_ider.index(gjeldende_id)
    rekkefolge = mine_ider[start + 1:] + mine_ider[:start]
    for i in rekkefolge:
        if status(i) != "Ferdig":
            return i
    return None  # alt ferdig


@st.fragment
def vis_butikkort(butikk_id):
    info = butikker[butikk_id]
    i = mine_ider.index(butikk_id)

    hc1, hc2 = st.columns([3, 1])
    with hc1:
        st.markdown(f"### {info['navn']}")
        klasse_badge(info.get("klasse", "–"))
        st.caption(info.get("bransje", "–"))
        st.caption(f"Butikk {i + 1} av {len(mine_ider)}" + (" · ✅ ferdig" if status(butikk_id) == "Ferdig" else " · påbegynt" if status(butikk_id) == "Påbegynt" else ""))
    with hc2:
        if info.get("url"):
            st.link_button("Besøk butikk", info["url"], icon=":material/open_in_new:", use_container_width=True)
        butikk_snitt = snitt(butikk_id)
        if butikk_snitt is not None:
            st.metric("Mitt snitt", f"{butikk_snitt:.2f}")

    st.write("")
    for krit in kriterier_denne:
        eksisterende = mine_vurderinger.get((butikk_id, krit), {})
        var_na = eksisterende.get("score") == IKKE_VURDERT
        kc1, kc2 = st.columns([1, 2])
        with kc1:
            st.markdown(f"**{krit}**", help=SKALA_FORKLARING)
            na_key = f"na_{butikk_id}_{krit}"
            if na_key not in st.session_state:
                st.session_state[na_key] = var_na
            ikke_vurder = st.checkbox("Kan ikke vurdere", key=na_key)
            score_key = f"score_{butikk_id}_{krit}"
            if score_key not in st.session_state:
                st.session_state[score_key] = (int(eksisterende["score"]) - 1) if er_tall(eksisterende.get("score")) else 2
            if not ikke_vurder:
                st.feedback("stars", key=score_key)
        with kc2:
            st.text_area(
                "Kommentar", value=eksisterende.get("kommentar", ""),
                key=f"kom_{butikk_id}_{krit}", label_visibility="collapsed",
                placeholder="Skriv en kommentar (valgfritt)…", height=68,
            )

    st.write("")
    tilstand = st.session_state.get("_lagringstilstand")
    if tilstand:
        lagringsstatus(tilstand[0], tilstand[1])

    a1, a2, a3 = st.columns([1, 1, 2])
    if a1.button("← Forrige", disabled=(i == 0), use_container_width=True):
        lagre_denne(butikk_id)
        st.session_state["_fokus_id"] = mine_ider[max(0, i - 1)]
        st.rerun()
    if a2.button("Hopp over →", disabled=(i >= len(mine_ider) - 1), use_container_width=True, help="Går videre UTEN å lagre endringer på denne butikken."):
        st.session_state["_fokus_id"] = mine_ider[i + 1]
        st.rerun()
    if a3.button("💾 Lagre og neste", type="primary", use_container_width=True):
        if lagre_denne(butikk_id):
            neste = neste_uferdige(butikk_id)
            st.session_state["_fokus_id"] = neste
            st.rerun()
        else:
            st.rerun()


if not mine_ider:
    tom_tilstand("🎉", "Ingen butikker tildelt deg", "Det er ikke registrert noen tildeling for deg i 'Tildeling'-fanen – be en administrator sjekke oppsettet.")
elif visning == "Mine butikker":
    sok = st.text_input("🔍 Søk etter butikk", "")
    fc1, fc2 = st.columns(2)
    status_filter = fc1.multiselect("Status", ["Ikke startet", "Påbegynt", "Ferdig"])
    klasse_filter = fc2.multiselect("Størrelsesklasse", sorted({butikker[i].get("klasse", "") for i in mine_ider if butikker[i].get("klasse")}))

    rader, id_for_rad = [], []
    for butikk_id in mine_ider:
        info = butikker[butikk_id]
        if sok and sok.lower() not in info["navn"].lower():
            continue
        s = status(butikk_id)
        if status_filter and s not in status_filter:
            continue
        if klasse_filter and info.get("klasse") not in klasse_filter:
            continue
        har_na = any(mine_vurderinger.get((butikk_id, k), {}).get("score") == IKKE_VURDERT for k in kriterier_denne)
        sn = snitt(butikk_id)
        rader.append({
            "Butikk": info["navn"], "Klasse": info.get("klasse", "–"), "Bransje": info.get("bransje", "–"),
            "Status": s, "Mitt snitt": f"{sn:.2f}" if sn is not None else "–",
            "Kan ikke vurdere brukt": "Ja" if har_na else "", "Sist endret": sist_endret(butikk_id),
        })
        id_for_rad.append(butikk_id)

    rekkefolge_vekt = {"Ikke startet": 0, "Påbegynt": 1, "Ferdig": 2}
    sortert = sorted(zip(rader, id_for_rad), key=lambda par: rekkefolge_vekt.get(par[0]["Status"], 0))
    rader = [r for r, _ in sortert]
    id_for_rad = [i for _, i in sortert]

    st.caption(f"{len(rader)} av {len(mine_ider)} tildelte butikker")
    hendelse = st.dataframe(rader, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
    if hendelse and hendelse.selection and hendelse.selection.rows:
        valgt = hendelse.selection.rows[0]
        st.session_state["_fokus_id"] = id_for_rad[valgt]
        st.session_state["_visning_vurdering"] = "Fokus"
        st.rerun()

else:  # Fokus
    if "_fokus_id" not in st.session_state or st.session_state["_fokus_id"] not in mine_ider:
        st.session_state["_fokus_id"] = next((i for i in mine_ider if status(i) != "Ferdig"), mine_ider[0])

    if antall_ferdig == len(mine_ider):
        st.success("🎉 Du har vurdert alle dine tildelte butikker!", icon=":material/celebration:")
        klasser_i_bruk = sorted({butikker[i].get("klasse", "") for i in mine_ider if butikker[i].get("klasse")})
        kol = st.columns(2 + len(klasser_i_bruk))
        kol[0].metric("Vurdert", f"{antall_ferdig} av {len(mine_ider)}")
        kol[1].metric("Eget snitt", f"{eget_snitt:.2f}" if eget_snitt else "–")
        for idx, klasse in enumerate(klasser_i_bruk):
            i_klasse = [i for i in mine_ider if butikker[i].get("klasse") == klasse]
            ferdig_i_klasse = sum(1 for i in i_klasse if status(i) == "Ferdig")
            kol[2 + idx].metric(klasse, f"{ferdig_i_klasse}/{len(i_klasse)}")
        st.page_link("pages/butikker.py", label="Se totaloversikten over alle butikkene", icon=":material/storefront:")
        st.divider()
        st.caption("Du kan fortsatt åpne og redigere enkeltbutikker under.")

    with st.container(border=True):
        vis_butikkort(st.session_state["_fokus_id"])
