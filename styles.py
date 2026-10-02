"""Visuelt tema og egendefinert CSS – samlet ett sted, slik at sidene kan
bruke native Streamlit-komponenter uten å style dem enkeltvis.

Fargene defineres som CSS-variabler med lyse verdier som standard, og byttes
ut under @media (prefers-color-scheme: dark) – det eneste som faktisk gjør at
EGNE kort/klasser (ikke bare Streamlit sine innebygde widgets) følger med når
noen bytter til mørk modus i nettleser/OS.
"""

import streamlit as st

RØD = "#C8102E"  # samme i begge modus – selve merkefargen

CSS = f"""
<style>
:root {{
    --lys-bakgrunn: #FAFAF9;
    --kort-bakgrunn: #FFFFFF;
    --kant: #E5E3DF;
    --tekst: #1C1C1C;
    --tekst-dempet: #5B5955;  /* WCAG AA (4.5:1+) mot lys bakgrunn */
    --rod: {RØD};
    --gronn: #1E8E5A;
}}
@media (prefers-color-scheme: dark) {{
    :root {{
        --lys-bakgrunn: #1A1A1A;
        --kort-bakgrunn: #262626;
        --kant: #3A3A3A;
        --tekst: #F2F2F2;
        --tekst-dempet: #B5B3AE;  /* WCAG AA mot mørk bakgrunn */
    }}
}}

/* La Streamlits "legg til lenke"-anker-ikon ved overskrifter være usynlig – vi
   bruker anchor=False de fleste steder, men dette er et vern i tillegg. */
[data-testid="stHeaderActionElements"] {{ display:none; }}

/* Nok bunnmarg til at Streamlits flytende "Manage app"/profil-knapper nederst
   til høyre aldri dekker innhold. */
.block-container {{ padding-bottom: 72px; overflow-wrap: break-word; }}
* {{ hyphens: none !important; -webkit-hyphens: none !important; }}

.stApp {{ background-color: var(--lys-bakgrunn); }}
div[data-testid="stExpander"] {{ background-color: var(--kort-bakgrunn); border-radius: 12px; border: 1px solid var(--kant); }}
div[data-testid="stForm"] {{ border: 1px solid var(--kant); border-radius: 14px; padding: 20px; background: var(--kort-bakgrunn); }}

/* Egen fremdriftslinje (ikke st.progress) – gir full kontroll på kontrast/høyde,
   så den aldri blir "nesten usynlig" uavhengig av Streamlit-versjon. */
.fremdrift-rad {{ display:flex; align-items:center; gap:12px; }}
.fremdrift-tekst {{ font-size:13.5px; font-weight:600; color:var(--tekst); white-space:nowrap; }}
.fremdrift-bakgrunn {{ background: var(--kant); border-radius:8px; height:12px; width:100%; overflow:hidden; }}
.fremdrift-fyll {{ background: var(--rod); height:100%; border-radius:8px; transition: width .2s ease; }}

.topptekst {{ display:flex; align-items:flex-end; justify-content:space-between; padding: 10px 2px 16px 2px; margin-bottom: 14px; border-bottom: 1px solid var(--kant); gap: 16px; flex-wrap: wrap; }}
.topptekst .merke {{ font-weight:800; font-size:13px; letter-spacing:.4px; color:var(--tekst-dempet); text-transform:uppercase; margin-bottom: 2px; }}
.topptekst .sidetittel {{ font-size:26px; font-weight:800; color:var(--tekst); }}
.topptekst .hoyre {{ display:flex; align-items:center; gap:14px; padding-bottom: 4px; }}

.status-prikk {{ display:inline-flex; align-items:center; gap:6px; font-size:13px; color:var(--tekst-dempet); white-space:nowrap; }}
.status-prikk .prikk {{ width:8px; height:8px; border-radius:50%; display:inline-block; flex-shrink:0; }}
.status-prikk .ok {{ background:var(--gronn); }}
.status-prikk .feil {{ background:var(--rod); }}

.jurymedlem-brikke {{ background:var(--lys-bakgrunn); border:1px solid var(--kant); border-radius:20px; padding:4px 12px; font-size:13px; font-weight:600; color:var(--tekst); white-space:nowrap; }}

.kort-kompakt {{ background:var(--lys-bakgrunn); border:1px solid var(--kant); border-radius:10px; padding:10px 14px; font-size:13px; line-height:1.5; color:var(--tekst); }}

.klasse-badge {{ display:inline-block; font-size:12px; font-weight:700; padding:3px 10px; border-radius:20px; background:var(--lys-bakgrunn); border:1px solid var(--kant); color:var(--tekst); }}

/* Rutenett med garantert lik kort-høyde per rad – bygget som ÉN html-blokk
   (ikke st.columns), slik at CSS grid kan styre både responsivitet og høyde. */
.rutenett {{ display:grid; gap:16px; grid-template-columns: repeat(5, 1fr); align-items: stretch; }}
.rutenett.tre-per-rad {{ grid-template-columns: repeat(3, 1fr); }}
@media (max-width: 1100px) {{ .rutenett {{ grid-template-columns: repeat(3, 1fr); }} }}
@media (max-width: 640px) {{ .rutenett, .rutenett.tre-per-rad {{ grid-template-columns: 1fr; }} }}
.rutenett-kort {{ background:var(--kort-bakgrunn); border:1px solid var(--kant); border-radius:14px; padding:16px 18px; display:flex; flex-direction:column; }}
.rutenett-kort.aktiv {{ border:1.5px solid var(--rod); box-shadow: 0 0 0 3px rgba(200,16,46,0.08); }}
.rutenett-kort h4 {{ margin:0 0 10px 0; font-size:14.5px; line-height:1.3; color:var(--tekst); }}
.rutenett-kort .merke-tekst {{ color:var(--rod); font-weight:700; }}
.rutenett-kort ul {{ margin:0; padding-left:18px; flex:1; }}
.rutenett-kort li {{ margin-bottom:7px; color:var(--tekst); font-size:13.5px; line-height:1.4; }}
.rutenett-kort .belop {{ color:var(--tekst-dempet); font-size:13px; margin-top:2px; }}
.rutenett-kort .antall {{ color:var(--tekst-dempet); font-size:12.5px; margin-top:auto; padding-top:8px; }}
.rutenett-kort .stor-tall {{ font-size:26px; font-weight:800; color:var(--tekst); }}

.finale-rad {{ background:var(--kort-bakgrunn); border:1px solid var(--kant); border-left:4px solid var(--rod); border-radius:10px; padding:12px 16px; margin-bottom:8px; }}
.scorelinje-bakgrunn {{ background:var(--lys-bakgrunn); border-radius:6px; height:7px; width:100%; overflow:hidden; margin-top:6px; }}
.scorelinje-fyll {{ background:var(--rod); height:100%; border-radius:6px; }}

.steg-rad {{ display:flex; align-items:center; gap:6px; margin: 2px 0 20px 0; flex-wrap:wrap; }}
.steg {{ display:flex; align-items:center; gap:6px; padding:5px 13px; border-radius:20px; font-size:12.5px; font-weight:600; background:var(--lys-bakgrunn); color:var(--tekst-dempet); border:1px solid var(--kant); }}
.steg.aktiv {{ background:var(--rod); color:white; border-color:var(--rod); }}
.steg.ferdig {{ background:rgba(30,142,90,0.12); color:var(--gronn); border-color:rgba(30,142,90,0.3); }}
.steg-linje {{ flex:0 0 20px; height:1px; background:var(--kant); }}

.tom-tilstand {{ text-align:center; padding: 44px 24px 28px 24px; }}
.tom-tilstand .ikon {{ font-size:38px; margin-bottom:12px; }}
.tom-tilstand .tittel {{ font-size:17px; font-weight:700; margin-bottom:6px; color:var(--tekst); }}
.tom-tilstand .tekst {{ color:var(--tekst-dempet); font-size:14px; }}

.lagringsstatus {{ font-size:12.5px; color:var(--tekst-dempet); display:flex; align-items:center; gap:6px; }}
.lagringsstatus.feil {{ color:var(--rod); font-weight:600; }}
.lagringsstatus.ok {{ color:var(--gronn); }}
</style>
"""


def injiser_css():
    st.markdown(CSS, unsafe_allow_html=True)
