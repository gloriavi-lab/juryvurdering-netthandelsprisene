"""Visuelt tema og egendefinert CSS – samlet ett sted, slik at sidene kan
bruke native Streamlit-komponenter uten å style dem enkeltvis.

Fargene defineres som CSS-variabler med lyse verdier som standard, og byttes
ut under @media (prefers-color-scheme: dark) – det er det eneste som faktisk
gjør at EGNE kort/klasser (ikke bare Streamlit sine innebygde widgets) følger
med når noen bytter til mørk modus i nettleser/OS.
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

.stApp {{ background-color: var(--lys-bakgrunn); }}
section[data-testid="stSidebar"] > div {{ background-color: var(--kort-bakgrunn) !important; border-right: 1px solid var(--kant); }}
div[data-testid="stExpander"] {{ background-color: var(--kort-bakgrunn); border-radius: 12px; border: 1px solid var(--kant); }}
div[data-testid="stForm"] {{ border: 1px solid var(--kant); border-radius: 14px; padding: 20px; background: var(--kort-bakgrunn); }}

.topptekst {{ display:flex; align-items:center; justify-content:space-between; padding: 10px 2px 16px 2px; margin-bottom: 6px; border-bottom: 1px solid var(--kant); }}
.topptekst .merke {{ font-weight:800; font-size:13px; letter-spacing:.4px; color:var(--tekst-dempet); text-transform:uppercase; margin-bottom: 2px; }}
.topptekst .sidetittel {{ font-size:26px; font-weight:800; color:var(--tekst); }}

.status-prikk {{ display:inline-flex; align-items:center; gap:6px; font-size:13px; color:var(--tekst-dempet); }}
.status-prikk .prikk {{ width:8px; height:8px; border-radius:50%; display:inline-block; flex-shrink:0; }}
.status-prikk .ok {{ background:#1E8E5A; }}
.status-prikk .feil {{ background:var(--rod); }}

.kort-kompakt {{ background:var(--lys-bakgrunn); border:1px solid var(--kant); border-radius:10px; padding:10px 14px; font-size:13px; line-height:1.5; color:var(--tekst); }}

.klasse-badge {{ display:inline-block; font-size:12px; font-weight:700; padding:3px 10px; border-radius:20px; background:var(--lys-bakgrunn); border:1px solid var(--kant); color:var(--tekst); }}

.kat-kort {{ background:var(--kort-bakgrunn); border:1px solid var(--kant); border-radius:14px; padding:16px 18px; height:100%; }}
.kat-kort.aktiv {{ border:1.5px solid var(--rod); box-shadow: 0 0 0 3px rgba(200,16,46,0.08); }}
.kat-kort h4 {{ margin:0 0 10px 0; font-size:14.5px; line-height:1.3; color:var(--tekst); }}
.kat-kort .merke-tekst {{ color:var(--rod); font-weight:700; }}
.kat-kort ul {{ margin:0; padding-left:18px; }}
.kat-kort li {{ margin-bottom:7px; color:var(--tekst); overflow-wrap:break-word; hyphens:auto; font-size:13.5px; line-height:1.4; }}

.finale-rad {{ background:var(--kort-bakgrunn); border:1px solid var(--kant); border-left:4px solid var(--rod); border-radius:10px; padding:12px 16px; margin-bottom:8px; }}
.finale-plass {{ font-weight:800; font-size:18px; color:var(--rod); margin-right:10px; }}
.scorelinje-bakgrunn {{ background:var(--lys-bakgrunn); border-radius:6px; height:7px; width:100%; overflow:hidden; margin-top:6px; }}
.scorelinje-fyll {{ background:var(--rod); height:100%; border-radius:6px; }}

.steg-rad {{ display:flex; align-items:center; gap:6px; margin: 2px 0 20px 0; flex-wrap:wrap; }}
.steg {{ display:flex; align-items:center; gap:6px; padding:5px 13px; border-radius:20px; font-size:12.5px; font-weight:600; background:var(--lys-bakgrunn); color:var(--tekst-dempet); border:1px solid var(--kant); }}
.steg.aktiv {{ background:var(--rod); color:white; border-color:var(--rod); }}
.steg.ferdig {{ background:rgba(30,142,90,0.12); color:#1E8E5A; border-color:rgba(30,142,90,0.3); }}
.steg-linje {{ flex:0 0 20px; height:1px; background:var(--kant); }}

.tom-tilstand {{ text-align:center; padding: 44px 24px 28px 24px; }}
.tom-tilstand .ikon {{ font-size:38px; margin-bottom:12px; }}
.tom-tilstand .tittel {{ font-size:17px; font-weight:700; margin-bottom:6px; color:var(--tekst); }}
.tom-tilstand .tekst {{ color:var(--tekst-dempet); font-size:14px; }}
</style>
"""


def injiser_css():
    st.markdown(CSS, unsafe_allow_html=True)
