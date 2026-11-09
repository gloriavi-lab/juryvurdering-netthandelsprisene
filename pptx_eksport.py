"""Genererer én ferdig formatert PowerPoint-slide per testkjøp, slik at
jurymedlemmet kan laste den ned og importere den rett inn i master-
presentasjonen («Fil → Importer lysbilder» i Google Slides) i stedet for
å lime inn og formatere oppsummeringsteksten manuelt.

Rendrer samme informasjon som jury._bygg_oppsummering_tekst (tidslinje,
nøkkeltall, rødt flagg, kommentarer) – men som en visuelt formatert
slide, ikke ren tekst."""

from io import BytesIO

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

STATUS_FARGE = {
    "Ikke startet": "8A8780", "Bestilt": "4472C4", "Venter på levering": "C8A200", "Levert": "5B9BD5",
    "Retur sendt": "ED7D31", "Venter på refusjon": "C8A200", "Ferdig": "1E8E5A",
}
GRONN = RGBColor(0x1E, 0x8E, 0x5A)
MORK = RGBColor(0x1F, 0x24, 0x20)
GRA = RGBColor(0x5B, 0x64, 0x5D)
LYS_LINJE = RGBColor(0xEE, 0xE7, 0xD8)
FLAGG_BAKGRUNN = RGBColor(0xFD, 0xEC, 0xE8)
FLAGG_TEKST = RGBColor(0xA3, 0x39, 0x2A)
HVIT = RGBColor(0xFF, 0xFF, 0xFF)

SIDE_BREDDE = Inches(13.333)
SIDE_HOYDE = Inches(7.5)


def _farge(hex_tekst):
    return RGBColor.from_string(hex_tekst)


def _tekstboks(slide, venstre, topp, bredde, hoyde):
    boks = slide.shapes.add_textbox(venstre, topp, bredde, hoyde)
    tf = boks.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    return tf


def _skriv(tf, tekst, storrelse=14, farge=MORK, fet=False, kursiv=False, ny_avsnitt=True, justering=None):
    avsnitt = tf.add_paragraph() if (ny_avsnitt and (tf.paragraphs[0].runs or tf.paragraphs[0].text)) else tf.paragraphs[0]
    if justering:
        avsnitt.alignment = justering
    lope = avsnitt.add_run()
    lope.text = tekst
    lope.font.size = Pt(storrelse)
    lope.font.color.rgb = farge
    lope.font.bold = fet
    lope.font.italic = kursiv
    lope.font.name = "Calibri"
    return avsnitt


def bygg_testkjop_slide(butikk, jurymedlem, status, alle_steg, tidslinje_steg, nokkeltall, rodt_flagg, generell_kommentar=""):
    """Returnerer rå .pptx-bytes med ÉN slide for dette testkjøpet.

    alle_steg: {steg: {kolonnenavn: verdi}} - samme struktur som
    sheets.read_testkjop gir for (butikk, jurymedlem).
    tidslinje_steg: ordnet liste over stegnavn, samme som pages.testkjop
    sin TIDSLINJE_STEG.
    nokkeltall: liste av (etikett, verdi)-par, FERDIGBEREGNET av kalleren
    (leveringsavvik, svartid per kanal, dager til refusjon, snitt score -
    se jury.py) - denne modulen gjør ingen egne beregninger, kun rendring.
    rodt_flagg: bool, ferdigberegnet av kalleren."""
    pres = Presentation()
    pres.slide_width = SIDE_BREDDE
    pres.slide_height = SIDE_HOYDE
    slide = pres.slides.add_slide(pres.slide_layouts[6])  # blank layout

    # ── Topptekst-felt (grønn bakgrunn, butikknavn + status-pille) ──
    topp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SIDE_BREDDE, Inches(1.15))
    topp.fill.solid()
    topp.fill.fore_color.rgb = GRONN
    topp.line.fill.background()
    topp.shadow.inherit = False

    tittel_tf = topp.text_frame
    tittel_tf.margin_left = Inches(0.45)
    tittel_tf.margin_top = Inches(0.22)
    tittel_tf.word_wrap = True
    _skriv(tittel_tf, butikk, storrelse=26, farge=HVIT, fet=True, ny_avsnitt=False)
    _skriv(tittel_tf, f"Testkjøp – {jurymedlem}", storrelse=12, farge=RGBColor(0xDC, 0xEE, 0xE3))

    pille_bredde = Inches(2.1)
    pille = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE, SIDE_BREDDE - pille_bredde - Inches(0.45), Inches(0.37), pille_bredde, Inches(0.42),
    )
    pille.fill.solid()
    pille.fill.fore_color.rgb = HVIT
    pille.line.fill.background()
    pille.shadow.inherit = False
    pille.adjustments[0] = 0.5
    ptf = pille.text_frame
    ptf.margin_left = ptf.margin_right = Inches(0.08)
    ptf.word_wrap = False
    pp = _skriv(ptf, status, storrelse=13, farge=_farge(STATUS_FARGE.get(status, "888888")), fet=True, ny_avsnitt=False)
    pp.alignment = PP_ALIGN.CENTER

    # ── Generelt inntrykk (sitat rett under toppfeltet, hvis utfylt) ──
    y = Inches(1.4)
    if generell_kommentar:
        sitat_tf = _tekstboks(slide, Inches(0.45), y, SIDE_BREDDE - Inches(0.9), Inches(0.55))
        _skriv(sitat_tf, f"«{generell_kommentar}»", storrelse=13, farge=GRA, kursiv=True, ny_avsnitt=False)
        y += Inches(0.6)

    venstre_bredde = Inches(7.4)
    hoyre_x = Inches(8.1)
    hoyre_bredde = SIDE_BREDDE - hoyre_x - Inches(0.45)

    # ── Venstre kolonne: tidslinje ──
    tl_overskrift = _tekstboks(slide, Inches(0.45), y, venstre_bredde, Inches(0.35))
    _skriv(tl_overskrift, "TIDSLINJE", storrelse=12, farge=GRONN, fet=True, ny_avsnitt=False)

    tl_tf = _tekstboks(slide, Inches(0.45), y + Inches(0.4), venstre_bredde, Inches(3.0))
    forst = True
    for steg in tidslinje_steg:
        d = alle_steg.get(steg)
        if d:
            tekst = f"✓  {steg} — score {d.get('Score', '–')}"
            farge = GRONN
        else:
            tekst = f"○  {steg} — ikke utført"
            farge = GRA
        _skriv(tl_tf, tekst, storrelse=14, farge=farge, fet=bool(d), ny_avsnitt=not forst)
        forst = False

    # Kommentarer under tidslinjen
    kommentarer = [(steg, alle_steg[steg]["Kommentar"]) for steg in tidslinje_steg if alle_steg.get(steg, {}).get("Kommentar")]
    if kommentarer:
        kom_tf = _tekstboks(slide, Inches(0.45), Inches(5.1), venstre_bredde, Inches(1.9))
        forst = True
        for steg, tekst in kommentarer[:4]:
            _skriv(kom_tf, f"{steg}: {tekst}", storrelse=11.5, farge=GRA, kursiv=True, ny_avsnitt=not forst)
            forst = False

    # ── Høyre kolonne: nøkkeltall ──
    nt_overskrift = _tekstboks(slide, hoyre_x, y, hoyre_bredde, Inches(0.35))
    _skriv(nt_overskrift, "NØKKELTALL", storrelse=12, farge=GRONN, fet=True, ny_avsnitt=False)

    rad_y = y + Inches(0.45)
    for label, verdi in nokkeltall:
        rad = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, hoyre_x, rad_y, hoyre_bredde, Inches(0.01))
        rad.fill.solid()
        rad.fill.fore_color.rgb = LYS_LINJE
        rad.line.fill.background()
        rad.shadow.inherit = False
        rad_tf = _tekstboks(slide, hoyre_x, rad_y - Inches(0.34), hoyre_bredde, Inches(0.34))
        p = rad_tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        l1 = p.add_run(); l1.text = f"{label}: "; l1.font.size = Pt(11.5); l1.font.color.rgb = GRA; l1.font.name = "Calibri"
        l2 = p.add_run(); l2.text = verdi; l2.font.size = Pt(12.5); l2.font.color.rgb = MORK; l2.font.bold = True; l2.font.name = "Calibri"
        rad_y += Inches(0.42)

    if rodt_flagg:
        flagg = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, hoyre_x, rad_y + Inches(0.1), hoyre_bredde, Inches(0.7))
        flagg.fill.solid()
        flagg.fill.fore_color.rgb = FLAGG_BAKGRUNN
        flagg.line.fill.background()
        flagg.shadow.inherit = False
        flagg.adjustments[0] = 0.12
        ftf = flagg.text_frame
        ftf.word_wrap = True
        ftf.margin_left = ftf.margin_right = Inches(0.15)
        _skriv(ftf, "🚩 Ingen returløsning — kunden må ordne returen selv", storrelse=11.5, farge=FLAGG_TEKST, fet=True, ny_avsnitt=False)

    buffer = BytesIO()
    pres.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()
