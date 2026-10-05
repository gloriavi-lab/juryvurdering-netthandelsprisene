"""Side 5 – Innstillinger: Google Sheets-tilkobling, validering, og finale-lås.
Butikklisten kommer direkte fra "Rangering fase 1"-fanen – ingen Excel-
opplasting her lenger (se brief del 3: regnearket ER fasiten, appen bygger
ingen egen struktur)."""

import pandas as pd
import streamlit as st

from components import status_prikk, topptekst
from jury import (
    add_criterion, aktive_kriterier, deaktiver_kriterium, fagfelt_liste, kriterier_per_fagfelt,
    read_criteria, read_jury, write_jury,
)
from sheets import (
    FASE1_FANE, FASE2_FANE, er_finale_last, finale_las_info, fjern_finale_las,
    legg_til_kriterium_kolonne, legg_til_na_i_datavalidering, read_fase1_scores, read_ratings, read_stores,
)

topptekst("Innstillinger")

sh = st.session_state.get("_sh")

st.subheader("Google Sheets", anchor=False)
status_prikk(sh is not None)
if sh:
    st.link_button("Åpne regnearket", sh.url, icon=":material/open_in_new:")
    if st.button("Hent siste fra regnearket", icon=":material/refresh:", help="Tømmer mellomlagringen – nyttig rett etter du har redigert noe manuelt i Sheets."):
        read_stores.clear()
        read_ratings.clear()
        read_fase1_scores.clear()
        st.toast("Hentet siste versjon fra regnearket.", icon=":material/check_circle:")
        st.rerun()
else:
    with st.expander("Feilmelding"):
        st.code(st.session_state.get("_gsheets_feil", "Ukjent feil"))
    st.stop()

try:
    butikker, advarsler = read_stores(sh)
except Exception as e:
    st.error(f"Fant ikke fanen «{FASE1_FANE}» i regnearket (eller noe annet gikk galt): {e}", icon=":material/error:")
    st.stop()

st.caption(f"Leser butikklisten direkte fra fanen «{FASE1_FANE}» – {len(butikker)} butikker funnet.")

if advarsler:
    st.warning(
        "Fant noen rader appen ikke forstår helt – resten fungerer som normalt:\n\n" + "\n".join(f"- {a}" for a in advarsler),
        icon=":material/warning:",
    )

st.divider()
st.subheader("Ekspertvurdering – vurderingsark", anchor=False)
st.caption(
    f"«{FASE2_FANE}» opprettes automatisk (som en nøyaktig kopi av «{FASE1_FANE}» – samme farger, "
    "sammenslåinger, nedtrekkslister og filter) første gang noen lagrer en vurdering, eller når du trykker knappen under."
)
try:
    sh.worksheet(FASE2_FANE)
    st.success(f"«{FASE2_FANE}» finnes allerede.", icon=":material/check_circle:")
except Exception:
    if st.button("Opprett «Rangering fase 2» nå", icon=":material/content_copy:"):
        read_ratings(sh)  # trigger _sikre_fase2_fane
        st.rerun()

with st.expander("🔓 Tillat «Kan ikke vurdere» i nedtrekkslisten"):
    st.caption(
        "Legger «Kan ikke vurdere» til som en ekstra gyldig verdi i kriteriecellenes nedtrekksliste på "
        f"«{FASE2_FANE}» (i tillegg til 1–5). Endrer kun datavalideringen, ingen annen formatering."
    )
    if st.button("Legg til nå", icon=":material/playlist_add_check:"):
        legg_til_na_i_datavalidering(sh)
        st.success("Lagt til.", icon=":material/check_circle:")

st.divider()
st.subheader("Jury og kriterier", anchor=False)

alle_kriterier = read_criteria(sh)
kriterier_fase3 = aktive_kriterier(alle_kriterier, fase="Fase 3")
felt_dict = kriterier_per_fagfelt(kriterier_fase3)
jury = read_jury(sh)

st.markdown("**Fordeling** – kryss av hvilke kriterier hvert jurymedlem skal vurdere.")

if not felt_dict:
    st.caption("Ingen aktive kriterier funnet for Fase 3 ennå.")
else:
    kolonner = [f"{fagfelt}: {k}" for fagfelt in felt_dict for k in felt_dict[fagfelt]]
    navn_liste_jury = sorted(jury.keys())
    rader = []
    for navn in navn_liste_jury:
        mine = jury[navn]["kriterier"]
        rad = {"Jurymedlem": navn}
        for kol in kolonner:
            k = kol.split(": ", 1)[1]
            rad[kol] = k in mine
        rader.append(rad)

    df = pd.DataFrame(rader) if rader else pd.DataFrame(columns=["Jurymedlem"] + kolonner)
    column_config = {"Jurymedlem": st.column_config.TextColumn("Jurymedlem", disabled=True)}
    for kol in kolonner:
        column_config[kol] = st.column_config.CheckboxColumn(kol.split(": ", 1)[1][:24])
    redigert = st.data_editor(df, column_config=column_config, hide_index=True, use_container_width=True, key="fordeling_editor")

    st.caption("«Velg hele fagfeltet» krysser av alle kriterier i ett fagfelt for én person med ett klikk (lagres med det samme).")
    vc1, vc2, vc3 = st.columns([2, 2, 1])
    valgt_navn_bulk = vc1.selectbox("Jurymedlem", navn_liste_jury, key="_bulk_navn") if navn_liste_jury else None
    valgt_fagfelt_bulk = vc2.selectbox("Fagfelt", list(felt_dict.keys()), key="_bulk_fagfelt")
    if vc3.button("Velg hele fagfeltet", use_container_width=True, disabled=not valgt_navn_bulk):
        nye = set(jury.get(valgt_navn_bulk, {}).get("kriterier", set())) | set(felt_dict[valgt_fagfelt_bulk])
        write_jury(sh, valgt_navn_bulk, nye, jury.get(valgt_navn_bulk, {}).get("epost", ""), jury.get(valgt_navn_bulk, {}).get("farge", ""))
        st.toast(f"{valgt_fagfelt_bulk} valgt for {valgt_navn_bulk}.", icon=":material/check_circle:")
        st.rerun()

    nc1, nc2, nc3 = st.columns([2, 2, 1])
    nytt_navn_jury = nc1.text_input("Nytt jurymedlem – navn", key="_nytt_jurymedlem_navn")
    ny_epost_jury = nc2.text_input("E-post (valgfri)", key="_nytt_jurymedlem_epost")
    if nc3.button("Legg til jurymedlem", use_container_width=True, disabled=not nytt_navn_jury.strip()):
        write_jury(sh, nytt_navn_jury.strip(), set(), ny_epost_jury.strip())
        st.rerun()

    if st.button("💾 Lagre fordeling", type="primary", icon=":material/save:"):
        for _, rad in redigert.iterrows():
            navn = rad["Jurymedlem"]
            valgt = {kol.split(": ", 1)[1] for kol in kolonner if rad.get(kol)}
            write_jury(sh, navn, valgt, jury.get(navn, {}).get("epost", ""), jury.get(navn, {}).get("farge", ""))
        st.success("Fordeling lagret.", icon=":material/check_circle:")
        st.rerun()

st.write("")
with st.expander("📋 Alle kriterier (aktive og inaktive)"):
    for k in alle_kriterier:
        kc1, kc2 = st.columns([5, 1])
        status_tekst = "" if k["aktiv"] else " _(inaktiv)_"
        kc1.markdown(f"**{k['kriterium']}**{status_tekst} — {k['fagfelt']} · {', '.join(k['faser'])}")
        if k["aktiv"] and kc2.button("Deaktiver", key=f"deaktiver_{k['kriterium']}", use_container_width=True):
            deaktiver_kriterium(sh, k["kriterium"])
            st.rerun()

@st.dialog("Sette inn ny kolonne i Rangering-fanene?")
def bekreft_nytt_kriterium(fagfelt, navn, kort, utfyllende, skala1, skala3, skala5, eksempler, faser):
    st.write(
        f"Dette setter inn én ny, tom kolonne for **{navn}** i fagfeltgruppen **{fagfelt}** i de valgte Rangering-fanene. "
        "Formatering og nedtrekksliste kopieres fra nabokolonnen. Dette er det eneste stedet appen endrer struktur i en Rangering-fane."
    )
    c1, c2 = st.columns(2)
    if c1.button("Avbryt", use_container_width=True):
        st.rerun()
    if c2.button("Ja, sett inn", type="primary", use_container_width=True, icon=":material/view_column:"):
        add_criterion(sh, fagfelt, navn, kort, utfyllende, skala1, skala3, skala5, eksempler, faser)
        if "Fase 2" in faser:
            legg_til_kriterium_kolonne(sh, FASE1_FANE, fagfelt, navn)
        if "Fase 3" in faser:
            legg_til_kriterium_kolonne(sh, FASE2_FANE, fagfelt, navn)
        st.success(f"«{navn}» lagt til og kolonne satt inn.", icon=":material/check_circle:")
        st.rerun()


with st.expander("➕ Legg til nytt kriterium"):
    with st.form("nytt_kriterium_form"):
        fagfelt_nytt = st.selectbox("Fagfelt", list(felt_dict.keys()) if felt_dict else fagfelt_liste(alle_kriterier))
        navn_nytt = st.text_input("Kriterium (navn)")
        kort_nytt = st.text_input("Kort beskrivelse")
        utfyllende_nytt = st.text_area("Utfyllende forklaring", height=80)
        s1, s3, s5 = st.columns(3)
        skala1_nytt = s1.text_input("Hva gir 1")
        skala3_nytt = s3.text_input("Hva gir 3")
        skala5_nytt = s5.text_input("Hva gir 5")
        eksempler_nytt = st.text_input("Eksempler")
        faser_nytt = st.multiselect("Brukes i fase(r)", ["Fase 2", "Fase 3", "Testhandel"], default=["Fase 3"])
        sett_inn_kolonne = st.checkbox("Sett også inn ny kolonne i Rangering-fanene for valgt(e) fase(r) nå", value=False)
        lagt_til = st.form_submit_button("Legg til kriterium", icon=":material/add_circle:")

    if lagt_til and navn_nytt.strip():
        if sett_inn_kolonne:
            bekreft_nytt_kriterium(fagfelt_nytt, navn_nytt.strip(), kort_nytt, utfyllende_nytt, skala1_nytt, skala3_nytt, skala5_nytt, eksempler_nytt, faser_nytt)
        else:
            add_criterion(sh, fagfelt_nytt, navn_nytt.strip(), kort_nytt, utfyllende_nytt, skala1_nytt, skala3_nytt, skala5_nytt, eksempler_nytt, faser_nytt)
            st.success(f"«{navn_nytt}» lagt til i Kriterier-fanen (ingen kolonne satt inn i Rangering-fanene).", icon=":material/check_circle:")

st.divider()
st.subheader("Finale", anchor=False)
if er_finale_last(sh):
    av, tid = finale_las_info(sh)
    st.info(f"Finalelista er låst av **{av}** ({tid}). Endringer i Sheets påvirker ikke lenger rangeringen.", icon=":material/lock:")
    if st.button("Lås opp finalelista", icon=":material/lock_open:"):
        fjern_finale_las(sh)
        st.rerun()
else:
    st.caption("Finalelista er ikke låst – rangeringen på Finale-siden oppdateres live. Lås den fra Finale-siden når resultatet er klart.")
