"""Visuelt tema og egendefinert CSS – samlet ett sted, slik at sidene kan
bruke native Streamlit-komponenter uten å style dem enkeltvis.

Fargene defineres som CSS-variabler med lyse verdier som standard, og byttes
ut under @media (prefers-color-scheme: dark) – det eneste som faktisk gjør at
EGNE kort/klasser (ikke bare Streamlit sine innebygde widgets) følger med når
noen bytter til mørk modus i nettleser/OS.

Merkefarge (--merke) = Bring-grønn, brukt til primærknapper/aktiv tilstand/
fremdrift. Rødt (--feil) er reservert til feil/advarsler, jf. brief – de to
konkurrerer derfor ikke lenger om oppmerksomheten."""

import streamlit as st

from theme import BRING_GRONN

CSS = f"""
<style>
:root {{
    --lys-bakgrunn: #FAFAF9;
    --kort-bakgrunn: #FFFFFF;
    --kant: #E5E3DF;
    --tekst: #1C1C1C;
    --tekst-dempet: #4A4944;  /* mørkere enn forrige runde for bedre WCAG AA-kontrast */
    --merke: {BRING_GRONN};
    --feil: #C8102E;
    --gronn: #1E8E5A;
}}
@media (prefers-color-scheme: dark) {{
    :root {{
        --lys-bakgrunn: #1A1A1A;
        --kort-bakgrunn: #262626;
        --kant: #3A3A3A;
        --tekst: #F2F2F2;
        --tekst-dempet: #C2C0BB;  /* WCAG AA mot mørk bakgrunn */
    }}
}}

/* La Streamlits "legg til lenke"-anker-ikon ved overskrifter være usynlig – vi
   bruker anchor=False de fleste steder, men dette er et vern i tillegg. */
[data-testid="stHeaderActionElements"] {{ display:none; }}

/* Nok bunnmarg til at Streamlits flytende "Manage app"/profil-knapper nederst
   til høyre aldri dekker innhold. */
/* Nok toppmarg til at innholdet aldri kommer under Streamlits egen
   toppmeny (st.navigation position="top") – gjelder alle sider. */
.block-container {{ padding-bottom: 72px; padding-top: 4rem; }}
* {{ hyphens: none !important; -webkit-hyphens: none !important; }}
/* VIKTIG: ingen global overflow-wrap:break-word – den tvinger brudd MIDT I
   ord når en lang sammensatt tekst ("Markedsføring/kundedialog") ikke får
   plass. Linjeskift skal kun skje ved mellomrom eller <wbr> (satt inn etter
   hver "/" i komponentene selv), derfor normal/normal som default. */
body {{ overflow-wrap: normal; word-break: normal; }}

.stApp {{ background-color: var(--lys-bakgrunn); }}
div[data-testid="stExpander"] {{ background-color: var(--kort-bakgrunn); border-radius: 12px; border: 1px solid var(--kant); }}
div[data-testid="stForm"] {{ border: 1px solid var(--kant); border-radius: 14px; padding: 20px; background: var(--kort-bakgrunn); }}

/* Egen fremdriftslinje (ikke st.progress) – gir full kontroll på kontrast/høyde,
   så den aldri blir "nesten usynlig" uavhengig av Streamlit-versjon. */
.fremdrift-rad {{ display:flex; align-items:center; gap:12px; }}
.fremdrift-tekst {{ font-size:13.5px; font-weight:600; color:var(--tekst); white-space:nowrap; }}
.fremdrift-bakgrunn {{ background: var(--kant); border-radius:8px; height:12px; width:100%; overflow:hidden; }}
.fremdrift-fyll {{ background: var(--merke); height:100%; border-radius:8px; transition: width .2s ease; }}

/* Toppbanner på Oversikt – farget i merkefarge, logo + tittel + CTA */
.banner {{ background: linear-gradient(135deg, var(--merke) 0%, color-mix(in srgb, var(--merke) 75%, black) 100%); color:white; border-radius:16px; padding:28px 32px; margin: 4px 0 24px 0; }}
.banner h1 {{ margin:0 0 4px 0; font-size:28px; font-weight:800; color:white; }}
.banner .fase {{ font-size:14px; font-weight:600; opacity:0.9; text-transform:uppercase; letter-spacing:0.4px; }}
.banner p {{ margin:10px 0 0 0; font-size:15px; opacity:0.95; max-width:560px; }}

.topptekst {{ display:flex; align-items:flex-end; justify-content:space-between; padding: 10px 2px 16px 2px; margin-bottom: 14px; border-bottom: 1px solid var(--kant); gap: 16px; flex-wrap: wrap; }}
.topptekst .merke-label {{ font-weight:800; font-size:13px; letter-spacing:.4px; color:var(--tekst-dempet); text-transform:uppercase; margin-bottom: 2px; }}
.topptekst .sidetittel {{ font-size:26px; font-weight:800; color:var(--tekst); }}
.topptekst .hoyre {{ display:flex; align-items:center; gap:14px; padding-bottom: 4px; }}

.status-prikk {{ display:inline-flex; align-items:center; gap:6px; font-size:13px; color:var(--tekst-dempet); white-space:nowrap; }}
.status-prikk .prikk {{ width:8px; height:8px; border-radius:50%; display:inline-block; flex-shrink:0; }}
.status-prikk .ok {{ background:var(--gronn); }}
.status-prikk .feil {{ background:var(--feil); }}

.jurymedlem-brikke {{ background:var(--lys-bakgrunn); border:1px solid var(--kant); border-radius:20px; padding:4px 12px; font-size:13px; font-weight:600; color:var(--tekst); white-space:nowrap; }}

.kort-kompakt {{ background:var(--lys-bakgrunn); border:1px solid var(--kant); border-radius:10px; padding:10px 14px; font-size:13px; line-height:1.5; color:var(--tekst); }}

.klasse-badge {{ display:inline-block; font-size:12px; font-weight:700; padding:3px 10px; border-radius:20px; background:var(--lys-bakgrunn); border:1px solid var(--kant); color:var(--tekst); }}

/* Rutenett med garantert lik kort-BREDDE OG -høyde per rad – bygget som ÉN
   html-blokk (ikke st.columns). minmax(0,1fr), ikke bare 1fr, er det som
   faktisk tvinger lik bredde uansett innhold. */
.rutenett {{ display:grid; gap:16px; grid-template-columns: repeat(5, minmax(0, 1fr)); align-items: stretch; }}
.rutenett.tre-per-rad {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
@media (max-width: 1100px) {{ .rutenett {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }} }}
@media (max-width: 640px) {{ .rutenett, .rutenett.tre-per-rad {{ grid-template-columns: minmax(0, 1fr); }} }}
.rutenett-kort {{ background:var(--kort-bakgrunn); border:1px solid var(--kant); border-radius:14px; padding:20px 22px; display:flex; flex-direction:column; border-top:4px solid var(--kant); min-width:0; }}
.rutenett-kort.aktiv {{ border:1.5px solid var(--merke); border-top:4px solid var(--merke); box-shadow: 0 0 0 3px color-mix(in srgb, var(--merke) 15%, transparent); }}
.rutenett-kort.farget {{ color:white; }}
.rutenett-kort h4 {{ margin:0 0 12px 0; font-size:14.5px; line-height:1.3; color:var(--tekst); min-height:2.6em; display:flex; align-items:flex-start; }}
.rutenett-kort .merke-tekst {{ color:var(--merke); font-weight:700; }}
.rutenett-kort ul {{ margin:0; padding-left:18px; flex:1; }}
.rutenett-kort li {{ margin-bottom:7px; color:var(--tekst); font-size:13.5px; line-height:1.4; }}
.rutenett-kort .belop {{ color:var(--tekst-dempet); font-size:13px; margin-top:2px; }}
.rutenett-kort .antall {{ color:var(--tekst-dempet); font-size:12.5px; margin-top:auto; padding-top:8px; }}
.rutenett-kort .stor-tall {{ font-size:26px; font-weight:800; color:var(--tekst); }}
.rutenett-kort .fagfelt-ikon {{ display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:7px; flex-shrink:0; margin-top:6px; }}
.rutenett-kort .kort-ikon {{ font-size:22px; margin-bottom:6px; }}

.finale-rad {{ background:var(--kort-bakgrunn); border:1px solid var(--kant); border-left:4px solid var(--merke); border-radius:10px; padding:12px 16px; margin-bottom:8px; }}
.scorelinje-bakgrunn {{ background:var(--lys-bakgrunn); border-radius:6px; height:7px; width:100%; overflow:hidden; margin-top:6px; }}
.scorelinje-fyll {{ background:var(--merke); height:100%; border-radius:6px; }}

.steg-rad {{ display:flex; align-items:center; gap:6px; margin: 2px 0 20px 0; flex-wrap:wrap; }}
.steg {{ display:flex; align-items:center; gap:6px; padding:5px 13px; border-radius:20px; font-size:12.5px; font-weight:600; background:var(--lys-bakgrunn); color:var(--tekst-dempet); border:1px solid var(--kant); }}
.steg.aktiv {{ background:var(--merke); color:white; border-color:var(--merke); }}
.steg.ferdig {{ background:rgba(30,142,90,0.12); color:var(--gronn); border-color:rgba(30,142,90,0.3); }}
.steg-linje {{ flex:0 0 20px; height:1px; background:var(--kant); }}

.tom-tilstand {{ text-align:center; padding: 44px 24px 28px 24px; }}
.tom-tilstand .ikon {{ font-size:38px; margin-bottom:12px; }}
.tom-tilstand .tittel {{ font-size:17px; font-weight:700; margin-bottom:6px; color:var(--tekst); }}
.tom-tilstand .tekst {{ color:var(--tekst-dempet); font-size:14px; }}

.lagringsstatus {{ font-size:12.5px; color:var(--tekst-dempet); display:flex; align-items:center; gap:6px; }}
.lagringsstatus.feil {{ color:var(--feil); font-weight:600; }}
.lagringsstatus.ok {{ color:var(--gronn); }}

/* Jurymatrise på Oversikt: full tabell på desktop, kompakte kort på mobil. */
.kun-mobil-vis {{ display:none; }}
.kun-desktop-vis {{ display:block; }}
@media (max-width: 640px) {{
    .kun-mobil-vis {{ display:grid; }}
    .kun-desktop-vis {{ display:none; }}
}}

/* Fasetidslinje på Oversikt – kort forbundet med en linje, farget grønn
   frem til gjeldende fase og grå etter. */
.fase-rad {{ display:flex; align-items:stretch; gap:0; margin: 6px 0 4px 0; }}
.fase-kort {{ flex:1; min-width:0; background:var(--kort-bakgrunn); border:2px solid var(--kant); border-radius:14px; padding:18px 14px; text-align:center; }}
.fase-kort.fullfort {{ border-color: rgba(30,142,90,0.45); }}
.fase-kort.pagar {{ border-color: var(--merke); box-shadow: 0 0 0 3px rgba(0,112,60,0.12); }}
.fase-kort.kommende {{ border-color: var(--kant); opacity: 0.55; }}
.fase-sirkel {{ width:30px; height:30px; border-radius:50%; display:flex; align-items:center; justify-content:center; margin: 0 auto 8px auto; font-weight:800; font-size:13px; }}
.fase-kort.fullfort .fase-sirkel {{ background: rgba(30,142,90,0.15); color: var(--gronn); }}
.fase-kort.pagar .fase-sirkel {{ background: var(--merke); color: white; }}
.fase-kort.kommende .fase-sirkel {{ background: var(--lys-bakgrunn); color: var(--tekst-dempet); border:1px solid var(--kant); }}
.fase-navn {{ font-weight:700; font-size:14px; margin-bottom:4px; color:var(--tekst); }}
.fase-kort.kommende .fase-navn {{ color: var(--tekst-dempet); }}
.fase-badge {{ display:inline-block; font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:.3px; padding:2px 8px; border-radius:10px; margin-bottom:6px; }}
.fase-badge.fullfort {{ background: rgba(30,142,90,0.14); color: var(--gronn); }}
.fase-badge.pagar {{ background: var(--merke); color: white; }}
.fase-badge.kommende {{ background: var(--lys-bakgrunn); color: var(--tekst-dempet); border:1px solid var(--kant); }}
.fase-beskrivelse {{ font-size:12px; color: var(--tekst-dempet); margin-top:4px; line-height:1.4; }}
.fase-dato {{ font-size:10.5px; color: var(--tekst-dempet); margin-top:4px; }}
.fase-linje {{ flex:0 0 22px; align-self:center; height:3px; margin: 0 -1px; }}
.fase-linje.gronn {{ background: var(--gronn); }}
.fase-linje.gra {{ background: var(--kant); }}
@media (max-width: 768px) {{
    .fase-rad {{ flex-direction:column; gap:10px; }}
    .fase-linje {{ display:none; }}
}}

/* Butikkliste på Vurdering – oppgaveliste-stil, ikke regneark */
.status-merkelapp {{ display:inline-flex; align-items:center; gap:4px; font-size:12px; font-weight:700; padding:3px 10px; border-radius:20px; white-space:nowrap; }}
/* Hver butikkrad er en ekte st.container(key=..., border=True) – IKKE en rå
   <div> åpnet i én st.markdown-kall og lukket i en annen, siden Streamlit
   rendrer hvert st.*-kall som sitt eget, isolerte DOM-element: en uferdig
   tag fra ett kall pakker ALDRI inn elementer fra senere kall. st.container
   sin key= gir en ekte, stabil CSS-klasse (st-key-<key>) på den faktiske
   wrapper-diven å style via. */
div[class*="st-key-butikkrad_"] {{ transition: background-color .12s ease, box-shadow .12s ease; margin-bottom:10px; }}
div[class*="st-key-butikkrad_"]:hover {{ box-shadow: 0 2px 10px rgba(0,0,0,0.06); }}
div[class*="st-key-butikkrad_ferdig_"] {{ background: rgba(30,142,90,0.06); }}
.butikk-navn {{ font-weight:700; font-size:15px; color:var(--tekst); }}
.butikk-bransje {{ font-size:12.5px; color:var(--tekst-dempet); }}
.butikk-fremdrift-tekst {{ font-size:12.5px; color:var(--tekst-dempet); }}
@media (max-width: 640px) {{
    div[class*="st-key-butikkrad_"] {{ padding:2px; }}
}}
</style>
"""


def injiser_css():
    st.markdown(CSS, unsafe_allow_html=True)
