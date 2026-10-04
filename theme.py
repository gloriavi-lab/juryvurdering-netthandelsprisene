"""Felles fargetokens – lest fra/matchet mot det faktiske Excel-/Google
Sheets-oppsettet, slik at kriteriekort, tabeller og butikkort alltid bruker
NØYAKTIG samme farger som regnearket. Én kilde, brukt flere steder.

Fagfelt-fargene er hentet direkte fra cellefargene i "Rangering fase 1"
(rad 1/2, kolonne F, I, M, P, S) i Netthandelsprisene_Fase 1.xlsx.
"""

# FORELØPIG verdi – vi har ikke tilgang til Posten Brings interne
# profilmanual, så dette er Bring sin kjente offentlige merkegrønn som
# utgangspunkt. Bekreft/korriger mot de offisielle hex-verdiene.
BRING_GRONN = "#00703C"

FAGFELT_FARGE = {
    "Førsteinntrykk": "#4472C4",
    "Kundeservice & Tilgjengelighet": "#5B9BD5",
    "Kjøp/inspirasjon/personalisering": "#70AD47",
    "Markedsføring/kundedialog": "#ED7D31",
    "Innovasjon": "#7030A0",
}
GRUNNKOLONNE_FARGE = "#203864"  # Butikk/Jurymedlem/Klasse/Bransje/URL/Snitt totalt

# Radfarger per (Fase 1-)jurymedlem, hentet fra samme fil. Navnene her er
# skrevet EKSAKT som i regnearkets "Jurymedlem"-kolonne i dag (bl.a. "Ole" og
# "Stian/K", ikke "Ole Johan"/"Stian") – se spørsmål til bruker om hvordan
# dette henger sammen med Fase 2-ekspertlisten.
JURYMEDLEM_FARGE = {
    "Guro": "#D9E1F2",
    "Marte": "#FCE4D6",
    "Nicholas": "#E2EFDA",
    "Ole": "#FFF2CC",
    "Stian/K": "#EAD1DC",
    "Torkel": "#D0E0E3",
    "Vikki": "#F4CCCC",
}
