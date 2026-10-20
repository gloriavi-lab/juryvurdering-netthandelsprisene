"""Felles fargetokens – lest fra/matchet mot det faktiske Excel-/Google
Sheets-oppsettet, slik at kriteriekort, tabeller og butikkort alltid bruker
NØYAKTIG samme farger som regnearket. Én kilde, brukt flere steder.

Fagfelt-fargene er hentet direkte fra cellefargene i "Rangering fase 1"
(rad 1/2, kolonne F, I, M, P, S) i Netthandelsprisene_Fase 1.xlsx.

Verdiene under er CSS-variabel-REFERANSER (var(--x)), ikke rå hex – selve
hex-verdiene (lys OG mørk modus) er definert ÉTT sted i styles.py sin
:root/@media (prefers-color-scheme: dark)-blokk. Dette er det som faktisk
gjør at fargene følger med når noen bytter til mørk modus i nettleser/OS,
siden Python/Streamlit rendrer HTML én gang og ikke kan vite på forhånd
hvilket fargeskjema nettleseren bruker – kun CSS kan reagere på det i
etterkant. Alle kall-steder (FAGFELT_FARGE.get(...) osv.) er UENDRET og
trenger ingen endring – de får bare en var(--x)-streng i stedet for en
hex-streng, noe som fungerer akkurat likt i et style=/color:-attributt."""

# FORELØPIG verdi – vi har ikke tilgang til Posten Brings interne
# profilmanual, så dette er Bring sin kjente offentlige merkegrønn som
# utgangspunkt. Bekreft/korriger mot de offisielle hex-verdiene.
BRING_GRONN = "#00703C"

FAGFELT_FARGE = {
    "Førsteinntrykk": "var(--fagfelt-forsteinntrykk)",
    "Kundeservice & Tilgjengelighet": "var(--fagfelt-kundeservice)",
    "Kjøp/inspirasjon/personalisering": "var(--fagfelt-kjop)",
    "Markedsføring/kundedialog": "var(--fagfelt-markedsforing)",
    "Innovasjon": "var(--fagfelt-innovasjon)",
}
GRUNNKOLONNE_FARGE = "#203864"  # Butikk/Jurymedlem/Klasse/Bransje/URL/Snitt totalt (foreløpig ubrukt i appen)

# Størrelsesklasser – samme toner brukt på Oversikt og Butikker-siden
KLASSE_IKON = {"Liten": "🌱", "Medium": "🌿", "Stor": "🌳"}
KLASSE_TONE = {"Liten": "var(--klasse-liten)", "Medium": "var(--klasse-medium)", "Stor": "var(--klasse-stor)"}

STATUS_FARGE = {"Ferdig": "var(--status-ferdig)", "Påbegynt": "var(--status-pabegynt)", "Ikke startet": "var(--status-ikke-startet)"}
STATUS_TONE = {"Ferdig": "var(--status-tone-ferdig)", "Påbegynt": "var(--status-tone-pabegynt)", "Ikke startet": "var(--status-tone-ikke-startet)"}
STATUS_TEKST = {"Ferdig": "Ferdig", "Påbegynt": "Påbegynt", "Ikke startet": "Gjenstår"}

# Radfarger per (Fase 1-)jurymedlem, hentet fra samme fil. Navnene her er
# skrevet EKSAKT som i regnearkets "Jurymedlem"-kolonne i dag (bl.a. "Ole" og
# "Stian/K", ikke "Ole Johan"/"Stian") – se spørsmål til bruker om hvordan
# dette henger sammen med Fase 2-ekspertlisten. Foreløpig ubrukt i appen –
# ligger klar, men ikke konvertert til CSS-variabler siden ingen side
# faktisk henter fra denne ennå.
JURYMEDLEM_FARGE = {
    "Guro": "#D9E1F2",
    "Marte": "#FCE4D6",
    "Nicholas": "#E2EFDA",
    "Ole": "#FFF2CC",
    "Stian/K": "#EAD1DC",
    "Torkel": "#D0E0E3",
    "Vikki": "#F4CCCC",
}
