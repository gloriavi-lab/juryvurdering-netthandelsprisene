# Juryvurdering Netthandelsprisene – Ekspertvurdering (Fase 2)

Egen, lett Streamlit-app for **ekspertvurderingen (Fase 2)** i Netthandelsprisene.
Bygget adskilt fra hovedappen (`netthandelsprisen`) fordi den ble treg av å håndtere
screening av 1000 butikker og mange faner i ett og samme Google Sheet.

## Hvordan appen fungerer

1. Fase 1 gjøres fortsatt i et eget Excel-ark (utenfor appen), slik dere gjør i dag.
2. Resultatet fra Fase 1 (butikkliste + Klasse/Bransje/URL) lastes opp i denne appen
   sitt sidepanel.
3. Hvert jurymedlem skriver navnet sitt og velger sitt fagfelt.
4. Jurymedlemmet vurderer butikkene på kun sitt fagfelt – med akkurat de samme
   kriteriene (ord for ord) som i Fase 1 – pluss et kommentarfelt per kriterium.
5. Alt lagres i et **eget, lite Google Sheet**. Appen skriver kun raden(e) for
   butikken som akkurat ble lagret, aldri hele arket, slik at manuelle endringer
   gjort direkte i Google Sheets alltid overlever og vises i appen (innen 15 sek).

## Oppsett – Google Sheets

1. Opprett et **nytt, tomt Google Sheet** (kun for denne appen – IKKE gjenbruk
   hovedappens store ark, poenget er at det skal være lite og raskt).
2. Del arket med tjenestekontoens e-post (samme som hovedappen bruker – du finner
   `client_email` i hovedappens `secrets` på Streamlit Cloud, under
   `[gcp_service_account]`). Gi «Redigerer»-tilgang.
3. Kopier ark-ID-en fra URL-en
   (`https://docs.google.com/spreadsheets/d/ARK-ID-EN-HER/edit`).

## Oppsett – secrets

Lokalt: kopier `.streamlit/secrets.toml.example` til `.streamlit/secrets.toml` og
fyll inn. På Streamlit Cloud: lim samme innhold inn under **Settings → Secrets**
for denne appen.

- `[gcp_service_account]` — kan kopieres rått fra hovedappens secrets.
- `[google_sheets] sheet_id` — ark-ID-en fra steget over.

## Kjøre lokalt

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Deploy

Push til GitHub, koble repoet til en ny app på
[Streamlit Community Cloud](https://share.streamlit.io), sett `secrets` som
beskrevet over.
