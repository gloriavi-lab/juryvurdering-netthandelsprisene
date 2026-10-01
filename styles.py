"""Visuelt tema og egendefinert CSS – samlet ett sted, slik at sidene kan
bruke native Streamlit-komponenter uten å style dem enkeltvis. Fargene matcher
.streamlit/config.toml (theme-fargene der styrer selve widget-fargene, denne
fila styrer kun layout/kort/badges som Streamlit ikke har innebygd)."""

import streamlit as st

RØD = "#C8102E"
MØRK = "#1C1C1C"
LYS_BAKGRUNN = "#FAFAF9"
KORT_BAKGRUNN = "#FFFFFF"
KANT = "#E5E3DF"
TEKST_DEMPET = "#5B5955"  # WCAG AA (4.5:1+) mot hvit/lys bakgrunn

CSS = f"""
<style>
.stApp {{ background-color: {LYS_BAKGRUNN}; }}
section[data-testid="stSidebar"] > div {{ background-color: {KORT_BAKGRUNN} !important; border-right: 1px solid {KANT}; }}
div[data-testid="stExpander"] {{ background-color: {KORT_BAKGRUNN}; border-radius: 12px; border: 1px solid {KANT}; }}
div[data-testid="stForm"] {{ border: 1px solid {KANT}; border-radius: 14px; padding: 20px; background: {KORT_BAKGRUNN}; }}

.topptekst {{ display:flex; align-items:center; justify-content:space-between; padding: 10px 2px 16px 2px; margin-bottom: 6px; border-bottom: 1px solid {KANT}; }}
.topptekst .merke {{ font-weight:800; font-size:13px; letter-spacing:.4px; color:{TEKST_DEMPET}; text-transform:uppercase; margin-bottom: 2px; }}
.topptekst .sidetittel {{ font-size:26px; font-weight:800; color:{MØRK}; }}

.status-prikk {{ display:inline-flex; align-items:center; gap:6px; font-size:13px; color:{TEKST_DEMPET}; }}
.status-prikk .prikk {{ width:8px; height:8px; border-radius:50%; display:inline-block; flex-shrink:0; }}
.status-prikk .ok {{ background:#1E8E5A; }}
.status-prikk .feil {{ background:{RØD}; }}

.kort-kompakt {{ background:{LYS_BAKGRUNN}; border:1px solid {KANT}; border-radius:10px; padding:10px 14px; font-size:13px; line-height:1.5; }}

.klasse-badge {{ display:inline-block; font-size:12px; font-weight:700; padding:3px 10px; border-radius:20px; background:{LYS_BAKGRUNN}; border:1px solid {KANT}; color:{MØRK}; }}

.kat-kort {{ background:{KORT_BAKGRUNN}; border:1px solid {KANT}; border-radius:14px; padding:16px 18px; height:100%; }}
.kat-kort.aktiv {{ border:1.5px solid {RØD}; box-shadow: 0 0 0 3px {RØD}14; }}
.kat-kort h4 {{ margin:0 0 10px 0; font-size:14.5px; line-height:1.3; }}
.kat-kort .merke-tekst {{ color:{RØD}; font-weight:700; }}
.kat-kort ul {{ margin:0; padding-left:18px; }}
.kat-kort li {{ margin-bottom:7px; color:#333; overflow-wrap:break-word; hyphens:auto; font-size:13.5px; line-height:1.4; }}

.finale-rad {{ background:{KORT_BAKGRUNN}; border:1px solid {KANT}; border-left:4px solid {RØD}; border-radius:10px; padding:12px 16px; margin-bottom:8px; }}
.finale-plass {{ font-weight:800; font-size:18px; color:{RØD}; margin-right:10px; }}
.scorelinje-bakgrunn {{ background:{LYS_BAKGRUNN}; border-radius:6px; height:7px; width:100%; overflow:hidden; margin-top:6px; }}
.scorelinje-fyll {{ background:{RØD}; height:100%; border-radius:6px; }}

.steg-rad {{ display:flex; align-items:center; gap:6px; margin: 2px 0 20px 0; flex-wrap:wrap; }}
.steg {{ display:flex; align-items:center; gap:6px; padding:5px 13px; border-radius:20px; font-size:12.5px; font-weight:600; background:{LYS_BAKGRUNN}; color:{TEKST_DEMPET}; border:1px solid {KANT}; }}
.steg.aktiv {{ background:{RØD}; color:white; border-color:{RØD}; }}
.steg.ferdig {{ background:#E6F4EC; color:#1E8E5A; border-color:#1E8E5A55; }}
.steg-linje {{ flex:0 0 20px; height:1px; background:{KANT}; }}

.tom-tilstand {{ text-align:center; padding: 44px 24px 28px 24px; }}
.tom-tilstand .ikon {{ font-size:38px; margin-bottom:12px; }}
.tom-tilstand .tittel {{ font-size:17px; font-weight:700; margin-bottom:6px; color:{MØRK}; }}
.tom-tilstand .tekst {{ color:{TEKST_DEMPET}; font-size:14px; }}
</style>
"""


def injiser_css():
    st.markdown(CSS, unsafe_allow_html=True)
