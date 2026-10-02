# Juryvurdering Netthandelsprisene – Ekspertvurdering (Fase 2)

Egen, lett Streamlit-app for **ekspertvurderingen (Fase 2)** i Netthandelsprisene.
Bygget adskilt fra hovedappen (`netthandelsprisen`) fordi den ble treg av å håndtere
screening av 1000 butikker og mange faner i ett og samme Google Sheet.

## Kodestruktur

- `app.py` – oppsett, tilkobling, navigasjon
- `sheets.py` – ALL lesing/skriving mot Google Sheets (`read_stores()`, `read_jury()`,
  `read_assignments()`, `read_ratings()`, `upsert_rating()`, `setup_from_excel()`, m.fl.)
- `data.py` – domenekonstanter (kriterier, klasser), Excel-import, ren beregningslogikk
- `styles.py` – alt av egendefinert CSS/tema, ett sted
- `components.py` – gjenbrukbare UI-deler (topptekst, kort-rutenett, jury-velger, m.m.)
- `pages/` – de fem sidene (Oversikt, Vurdering, Butikker, Finale, Innstillinger)

## Fanestruktur i Google Sheet-et

Regnearket er fasiten og kan redigeres manuelt når som helst – appen leser med
kort cache (10-60 sek) og skriver kun de konkrete cellene som endres.

| Fane | Kolonner | Redigeres manuelt? |
|---|---|---|
| **Butikker** | ID, Butikk, Klasse, Bransje, URL, Fase1_snitt | Ja – via "Sett opp regnearket på nytt fra Excel" i Innstillinger, eller direkte |
| **Jury** | Navn, Fagfelt | Ja – legg til/endre jurymedlemmer direkte her |
| **Tildeling** | Jurymedlem, ButikkID | Ja, valgfri – mangler et jurymedlem her, får de ALLE butikkene |
| **Rådata** | ButikkID, Butikk, Jurymedlem, Fagfelt, Kriterium, Score, Kommentar, SistEndret, EndretAv | Kan redigeres, men appen eier normalt denne (upsert per rad) |
| **Innstillinger_app** | Nøkkel, Verdi | Nei – styrer bl.a. finale-lås |
| **Finale_snapshot** | Klasse, Plass, ButikkID, Butikk, Snittscore, AntallVurderinger, LåstAv, LåstTid | Nei – skrives kun ved eksplisitt låsing av finalen |
| **Butikker_backup_&lt;tidsstempel&gt;** | (samme som Butikker) | Automatisk sikkerhetskopi før hvert "sett opp på nytt" |

**ID-kolonnen** i Butikker er stabil (generert fra butikknavnet, f.eks. "Boxo" → `boxo`,
med `-2`/`-3` ved navnekollisjon). Appen slår ALLTID opp rader på denne ID-en, aldri
på radnummer – du kan trygt sortere eller legge til rader manuelt i Sheets.

**Score**-kolonnen i Rådata er enten et tall 1–5, eller teksten `N/A` ("Kan ikke
vurdere" – telles ikke med i snittet).

## Oppsett – Google Sheets

1. Opprett et nytt, tomt Google Sheet kun for denne appen.
2. Del det med samme tjenestekonto-e-post som hovedappen bruker (`client_email`
   i hovedappens secrets på Streamlit Cloud).
3. Kopier ark-ID-en fra URL-en.
4. Åpne **Innstillinger**-siden i denne appen → "Sett opp regnearket på nytt fra
   Excel" → last opp Fase 1-resultatfila. Dette bygger hele fanestrukturen.

## Oppsett – secrets

Kopier `.streamlit/secrets.toml.example` til `.streamlit/secrets.toml` lokalt,
eller lim samme innhold inn under Streamlit Cloud → Settings → Secrets:
- `[gcp_service_account]` – kan kopieres rått fra hovedappens secrets.
- `[google_sheets] sheet_id` – ark-ID-en fra steget over.

## Kjøre lokalt

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```
