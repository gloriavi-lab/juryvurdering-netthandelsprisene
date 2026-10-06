"""Side 1 – Oversikt: banner, veiledning, kriterier, fem-fases tidslinje og
jury-matrise. Kriteriene og fasene er nå DATASTYRT (Kriterier-/Faser-fanen i
regnearket), ikke lenger hardkodet."""

import os

import streamlit as st

from components import rutenett
from data import er_tall
from jury import aktive_kriterier, aktiv_fase, fagfelt_liste, kriterier_per_fagfelt, mine_kriterier, read_criteria, read_faser, read_jury, read_veiledning
from sheets import read_fase1_scores, read_ratings, read_stores
from theme import FAGFELT_FARGE, KLASSE_IKON, KLASSE_TONE


def _bryt_etter_skratrek(tekst: str) -> str:
    return tekst.replace("/", "/<wbr>")


sh = st.session_state.get("_sh")
butikker, jury, alle_kriterier, faser = {}, {}, [], []
if sh:
    try:
        butikker, _ = read_stores(sh)
        jury = read_jury(sh)
        alle_kriterier = read_criteria(sh)
        faser = read_faser(sh)
    except Exception:
        pass

kriterier_fase3 = aktive_kriterier(alle_kriterier, fase="Fase 3")
FAGFELT = fagfelt_liste(kriterier_fase3)
KRITERIER_PER_FAGFELT = kriterier_per_fagfelt(kriterier_fase3)
kriterium_info = {k["kriterium"]: k for k in kriterier_fase3}
gjeldende_fase = aktiv_fase(faser) if faser else None
fase_tekst = f"Fase {gjeldende_fase['Fase']} · {gjeldende_fase['Navn']}" if gjeldende_fase else "Fase 3 · Ekspertvurdering"

BANNER_HTML = (
    '<div class="banner">'
    f'<div class="fase">Netthandelsprisene · {fase_tekst}</div>'
    "<h1>Ekspertvurdering</h1>"
    "<p>Vurder butikkene på dine tildelte kriterier – gi score fra 1 til 5 og legg gjerne igjen en kommentar. "
    "Vurderingene lagres fortløpende i regnearket.</p>"
    "</div>"
)
if os.path.exists("assets/bring-logo.svg"):
    logo_kol, banner_kol = st.columns([1, 6])
    with logo_kol:
        st.image("assets/bring-logo.svg", width=64)
    with banner_kol:
        st.markdown(BANNER_HTML, unsafe_allow_html=True)
else:
    st.markdown(BANNER_HTML, unsafe_allow_html=True)
if st.button("Start vurdering →", type="primary", icon=":material/edit_note:"):
    st.switch_page("pages/vurdering.py")

# ── Hvordan bedømme ──
st.subheader("Hvordan bedømme", anchor=False)
veiledning = []
if sh:
    try:
        veiledning = read_veiledning(sh)
    except Exception:
        pass
if veiledning:
    for rad in veiledning:
        overskrift, tekst = rad.get("Overskrift", ""), rad.get("Tekst", "")
        if overskrift:
            with st.expander(overskrift):
                st.markdown(tekst)
else:
    st.caption("Veiledningsteksten lastes fra fanen «Veiledning» i regnearket.")

st.divider()

# ── Størrelsesklasser ──
st.subheader("Størrelsesklasser", anchor=False)
KLASSE_DEFINISJON = [("Liten", "Under 50 mill kr"), ("Medium", "50–250 mill kr"), ("Stor", "Over 250 mill kr")]
antall_per_klasse = {k: 0 for k, _ in KLASSE_DEFINISJON}
for info in butikker.values():
    if info.get("klasse") in antall_per_klasse:
        antall_per_klasse[info["klasse"]] += 1
deler = [
    f'<div class="rutenett-kort" style="background:{KLASSE_TONE.get(k, "")};border-top-color:transparent;">'
    f'<div class="kort-ikon">{KLASSE_IKON.get(k, "")}</div><div class="stor-tall">{antall_per_klasse[k]}</div>'
    f'<div style="font-weight:700;">{k}</div><div class="belop">{belop}</div></div>'
    for k, belop in KLASSE_DEFINISJON
]
st.markdown(f'<div class="rutenett tre-per-rad">{"".join(deler)}</div>', unsafe_allow_html=True)

st.divider()

# ── Kriterier per fagfelt ──
st.subheader("Kriterier per fagfelt", anchor=False)
jurynavn = st.session_state.get("_jurynavn")
mine = mine_kriterier(jury, jurynavn) if jurynavn else set()
if mine:
    st.caption("Dine tildelte kriterier er uthevet under. Klikk «Les mer» på et kriterium for skala og eksempler.")

if FAGFELT:
    kort_deler = []
    for kat in FAGFELT:
        krit_i_felt = KRITERIER_PER_FAGFELT[kat]
        har_mine = any(k in mine for k in krit_i_felt)
        klasse = " aktiv" if har_mine else ""
        toppstripe = "" if har_mine else f'style="border-top-color:{FAGFELT_FARGE.get(kat, "#888")};"'
        prikk = f'<span class="fagfelt-ikon" style="background:{FAGFELT_FARGE.get(kat, "#888")};"></span>'
        punkter = "".join(
            f'<li>{"<strong>" if k in mine else ""}{_bryt_etter_skratrek(k)}{"</strong>" if k in mine else ""}'
            + (f' — <span style="color:var(--tekst-dempet);">{kriterium_info.get(k, {}).get("kort", "")}</span>' if kriterium_info.get(k, {}).get("kort") else "")
            + "</li>"
            for k in krit_i_felt
        )
        kort_deler.append(f'<div class="rutenett-kort{klasse}" {toppstripe}><h4>{prikk}{_bryt_etter_skratrek(kat)}</h4><ul>{punkter}</ul></div>')
    st.markdown(f'<div class="rutenett">{"".join(kort_deler)}</div>', unsafe_allow_html=True)

    with st.expander("Les mer om hvert kriterium (skala og eksempler)"):
        for kat in FAGFELT:
            st.markdown(f"**{kat}**")
            for k in KRITERIER_PER_FAGFELT[kat]:
                info_k = kriterium_info.get(k, {})
                st.markdown(f"_{k}_")
                if info_k.get("utfyllende"):
                    st.caption(info_k["utfyllende"])
                st.caption(f"1: {info_k.get('skala1', '–')}  ·  3: {info_k.get('skala3', '–')}  ·  5: {info_k.get('skala5', '–')}")
                if info_k.get("eksempler"):
                    st.caption(f"Eksempler: {info_k['eksempler']}")
else:
    st.caption("Ingen kriterier funnet – sjekk fanen «Kriterier» i regnearket.")

st.divider()

# ── Jury og ekspertområder ──
st.subheader("Jury og ekspertområder", anchor=False)
if not jury:
    st.caption("Ingen jurymedlemmer lagt til ennå.")
else:
    from jury import beskriv_tildeling

    # Kompakt kort-variant (vises alltid øverst, og alene på mobil)
    FARGEPALETT = ["#4472C4", "#70AD47", "#ED7D31", "#7030A0", "#5B9BD5", "#C8102E"]
    kort = []
    for i, navn in enumerate(sorted(jury.keys())):
        beskrivelse = beskriv_tildeling(navn, jury, KRITERIER_PER_FAGFELT)
        merkelapper = "".join(
            f'<span class="klasse-badge" style="margin:2px 4px 2px 0;border-color:{FARGEPALETT[i % len(FARGEPALETT)]};">{d.strip()}</span>'
            for d in beskrivelse.split("·")
        ) if beskrivelse else '<span style="color:var(--tekst-dempet);font-size:13px;">Ingen kriterier tildelt</span>'
        kort.append(f'<h4>{navn}</h4><div>{merkelapper}</div>')
    kort_html = "".join(f'<div class="rutenett-kort">{k}</div>' for k in kort)
    st.markdown(f'<div class="rutenett kun-mobil-vis">{kort_html}</div>', unsafe_allow_html=True)

    # Full matrise (skjules på mobil via CSS)
    if FAGFELT:
        navn_rader = sorted(jury.keys())
        thead = "<tr><th style='text-align:left;padding:6px 10px;'>Jurymedlem</th>"
        for kat in FAGFELT:
            for k in KRITERIER_PER_FAGFELT[kat]:
                thead += f'<th style="background:{FAGFELT_FARGE.get(kat, "#888")};color:white;font-size:11px;padding:6px 4px;writing-mode:vertical-rl;text-orientation:mixed;max-width:26px;">{k[:28]}</th>'
        thead += "</tr>"

        rader_html = ""
        dekning = {k: 0 for kat in FAGFELT for k in KRITERIER_PER_FAGFELT[kat]}
        for navn in navn_rader:
            rad = f"<tr><td style='padding:6px 10px;font-weight:600;white-space:nowrap;'>{navn}</td>"
            for kat in FAGFELT:
                for k in KRITERIER_PER_FAGFELT[kat]:
                    tildelt = k in mine_kriterier(jury, navn)
                    if tildelt:
                        dekning[k] += 1
                    rad += f"<td style='text-align:center;background:{FAGFELT_FARGE.get(kat, '#888')}14;'>{'✅' if tildelt else ''}</td>"
            rad += "</tr>"
            rader_html += rad

        dekning_rad = "<tr><td style='padding:6px 10px;font-weight:700;'>Dekning</td>"
        for kat in FAGFELT:
            for k in KRITERIER_PER_FAGFELT[kat]:
                antall = dekning[k]
                farge = "color:var(--feil);font-weight:800;" if antall == 0 else "color:var(--tekst-dempet);"
                dekning_rad += f"<td style='text-align:center;{farge}'>{antall}</td>"
        dekning_rad += "</tr>"

        st.markdown(
            f'<div class="kun-desktop-vis" style="overflow-x:auto;"><table style="border-collapse:collapse;width:100%;">'
            f"<thead>{thead}</thead><tbody>{rader_html}{dekning_rad}</tbody></table></div>",
            unsafe_allow_html=True,
        )
        if any(v == 0 for v in dekning.values()):
            st.warning("Ett eller flere kriterier har ingen jurymedlem tildelt ennå (markert rødt i dekningsraden).", icon=":material/warning:")

st.divider()
st.subheader("Fasene i konkurransen", anchor=False)
if faser:
    faser_sortert = sorted(faser, key=lambda f: int(f.get("Fase", 0)))

    def _fase_fremdrift(navn_fase):
        """Henter fremdrift i prosent for faser vi faktisk har data for i
        appen – None for faser uten datakilde (vises da uten linje)."""
        if not sh:
            return None
        try:
            if navn_fase == "Ekspertvurdering":
                kriterier = [k["kriterium"] for k in aktive_kriterier(alle_kriterier, fase="Fase 3")]
                rating_data = read_ratings(sh)
                total = len(butikker) * len(kriterier)
                fylt = sum(1 for n in butikker for k in kriterier if rating_data.get(n, {}).get("scorer", {}).get(k))
            elif navn_fase == "Juryvurdering":
                kriterier = [k["kriterium"] for k in aktive_kriterier(alle_kriterier, fase="Fase 2")]
                fase1 = read_fase1_scores(sh)
                total = len(butikker) * len(kriterier)
                fylt = sum(1 for n in butikker for k in kriterier if fase1.get(n, {}).get(k))
            else:
                return None
            return round(fylt / total * 100) if total else None
        except Exception:
            return None

    deler = []
    for idx, f in enumerate(faser_sortert):
        status = str(f.get("Status", "")).strip() or "Kommende"
        css_klasse = {"Fullført": "fullfort", "Pågår": "pagar"}.get(status, "kommende")
        sirkel_innhold = "✓" if status == "Fullført" else str(f.get("Fase", idx + 1))
        beskrivelse = f.get("Beskrivelse", "").strip()
        beskrivelse_html = f'<div class="fase-beskrivelse">{beskrivelse}</div>' if beskrivelse else ""
        dato_start, dato_slutt = f.get("Startdato", "").strip(), f.get("Sluttdato", "").strip()
        dato_html = f'<div class="fase-dato">{dato_start}{" – " + dato_slutt if dato_slutt else ""}</div>' if (dato_start or dato_slutt) else ""
        fremdrift_html = ""
        if status == "Pågår":
            prosent = _fase_fremdrift(f.get("Navn", ""))
            if prosent is not None:
                fremdrift_html = (
                    f'<div class="fremdrift-bakgrunn" style="margin-top:8px;height:6px;">'
                    f'<div class="fremdrift-fyll" style="width:{prosent}%;"></div></div>'
                    f'<div class="fase-dato">{prosent}% vurdert</div>'
                )
        deler.append(
            f'<div class="fase-kort {css_klasse}"><div class="fase-sirkel">{sirkel_innhold}</div>'
            f'<div class="fase-badge {css_klasse}">{status}</div>'
            f'<div class="fase-navn">{f.get("Navn", "")}</div>'
            f'{beskrivelse_html}{dato_html}{fremdrift_html}</div>'
        )
        if idx < len(faser_sortert) - 1:
            linje_farge = "gronn" if status == "Fullført" else "gra"
            deler.append(f'<div class="fase-linje {linje_farge}"></div>')
    st.markdown(f'<div class="fase-rad">{"".join(deler)}</div>', unsafe_allow_html=True)
else:
    st.caption("Fasene lastes fra fanen «Faser» i regnearket.")
