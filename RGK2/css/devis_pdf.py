"""Mise en page du devis en PDF (reportlab) et en image PNG (rendu du PDF)."""
from datetime import timedelta
from io import BytesIO

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

import logic

TEAL = colors.HexColor("#0F6B5C")
TEAL_L = colors.HexColor("#DDEFE8")
GREY = colors.HexColor("#55625C")
LINE = colors.HexColor("#D0D5D2")
INK = colors.HexColor("#16201C")

ST = {
    "t": ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=22, textColor=colors.white, leading=26),
    "tr": ParagraphStyle("tr", fontName="Helvetica", fontSize=10, textColor=colors.white, alignment=TA_RIGHT, leading=14),
    "h": ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=10, textColor=TEAL, leading=13, spaceAfter=2),
    "n": ParagraphStyle("n", fontName="Helvetica", fontSize=9.5, textColor=INK, leading=13),
    "s": ParagraphStyle("s", fontName="Helvetica", fontSize=8, textColor=GREY, leading=10.5),
    "b": ParagraphStyle("b", fontName="Helvetica-Bold", fontSize=9.5, textColor=INK, leading=13),
    "r": ParagraphStyle("r", fontName="Helvetica", fontSize=9.5, textColor=INK, leading=13, alignment=TA_RIGHT),
    "rb": ParagraphStyle("rb", fontName="Helvetica-Bold", fontSize=9.5, textColor=INK, leading=13, alignment=TA_RIGHT),
    "th": ParagraphStyle("th", fontName="Helvetica-Bold", fontSize=9, textColor=colors.white, leading=11),
    "thr": ParagraphStyle("thr", fontName="Helvetica-Bold", fontSize=9, textColor=colors.white, leading=11, alignment=TA_RIGHT),
}


def eur(v, dec=2):
    return f"{v:,.{dec}f}".replace(",", " ").replace(".", ",") + " €"


def mois(x):
    return f"{logic.MOIS_LONG[x.month - 1]} {x.year}"


def _esc(s):
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def devis_pdf(devis_id):
    dv = logic.q("SELECT * FROM devis WHERE id=?", (devis_id,)).iloc[0]
    cl = logic.q("SELECT * FROM clients WHERE id=?", (dv.client_id,)).iloc[0]
    lig = logic.devis_lignes_df(devis_id)
    det = logic.devis_detail(list(zip(lig.code, lig.qte)), dv.debut)
    rempl = dict(zip(lig.code, lig.remplace_lib))
    version = int(dv.version or 1) if "version" in dv and not pd.isna(dv.version) else 1
    tot = logic.devis_totaux(det, dv.debut, dv.duree)
    d_devis = logic.d(dv.date_devis)
    debut = logic.d(dv.debut)
    valide = d_devis + timedelta(days=int(dv.validite or 30))

    buf = BytesIO()
    W = A4[0] - 30 * mm

    def fond(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(GREY)
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(15 * mm, 10 * mm, f"IA Platform · Équipe A · centre de coûts · devis {devis_id}")
        canvas.drawRightString(A4[0] - 15 * mm, 10 * mm, f"Page {doc.page}")
        if dv.statut in ("Brouillon", "Refusé"):
            canvas.setFillColor(colors.Color(0.7, 0.2, 0.15, alpha=0.08))
            canvas.setFont("Helvetica-Bold", 90)
            canvas.translate(A4[0] / 2, A4[1] / 2)
            canvas.rotate(35)
            canvas.drawCentredString(0, 0, dv.statut.upper())
        canvas.restoreState()

    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=12 * mm, bottomMargin=18 * mm,
                            title=f"Devis {devis_id}", author="IA Platform — Équipe A")
    el = []
    # bandeau
    band = Table([[Paragraph("DEVIS", ST["t"]),
                   Paragraph(f"<b>{devis_id}</b>{f' · version {version}' if version > 1 else ''}<br/>Émis le {d_devis:%d/%m/%Y}<br/>Valable jusqu'au {valide:%d/%m/%Y}", ST["tr"])]],
                 colWidths=[W * 0.5, W * 0.5])
    band.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), TEAL), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                              ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                              ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10)]))
    el += [band, Spacer(1, 7 * mm)]
    # émetteur / client
    em = [Paragraph("ÉMETTEUR", ST["h"]), Paragraph("<b>Équipe A — IA Platform</b>", ST["n"]),
          Paragraph("Centre de coûts · refacturation interne", ST["n"]), Paragraph("Prix coûtant, sans marge", ST["s"])]
    cli = [Paragraph("CLIENT", ST["h"]), Paragraph(f"<b>{_esc(cl.nom)}</b> ({cl.id})", ST["n"]),
           Paragraph(f"{_esc(cl.entite)} · {_esc(cl.pays)}", ST["n"]),
           Paragraph(f"{_esc(cl.responsable)} · {_esc(cl.email)}", ST["s"])]
    t = Table([[em, cli]], colWidths=[W * 0.5, W * 0.5])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOX", (1, 0), (1, 0), 0.6, LINE),
                           ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#F6F8F7")), ("LEFTPADDING", (0, 0), (-1, -1), 8),
                           ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    el += [t, Spacer(1, 6 * mm)]
    # objet / période
    info = [[Paragraph("<b>Objet</b>", ST["n"]), Paragraph(_esc(dv.objet) or "—", ST["n"])],
            [Paragraph("<b>Période</b>", ST["n"]), Paragraph(f"de {mois(debut)} à {mois(tot['fin'])} · {int(dv.duree)} mois", ST["n"])],
            [Paragraph("<b>Tarifs</b>", ST["n"]), Paragraph(f"grille en vigueur en {mois(debut) if debut.year == logic.annee() else mois(logic.d(f'{logic.annee()}-{logic.mois_ref():02d}-01'))}", ST["n"])]]
    t = Table(info, colWidths=[28 * mm, W - 28 * mm])
    t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    el += [t, Spacer(1, 6 * mm)]
    # lignes
    data = [[Paragraph(x, ST["th"]) for x in ["Code", "Désignation"]] + [Paragraph(x, ST["thr"]) for x in ["Qté", "Tarif / mois", "Montant / mois", f"Total {int(dv.duree)} mois"]]]
    for r in det.itertuples():
        data.append([Paragraph(r.code, ST["n"]),
                     [Paragraph(f"<b>{_esc(r.designation)}</b>", ST["n"]), Paragraph(_esc(r.detail), ST["s"])]
                     + ([Paragraph(f"<font color='#C2702E'>Remplace : {_esc(rempl[r.code])}</font>", ST["s"])] if isinstance(rempl.get(r.code), str) else []),
                     Paragraph(f"{r.qte:g}".replace(".", ","), ST["r"]), Paragraph(eur(r.tarif), ST["r"]),
                     Paragraph(eur(r.mensuel), ST["r"]), Paragraph(eur(r.mensuel * int(dv.duree)), ST["r"])])
    t = Table(data, colWidths=[16 * mm, W - 16 * mm - 14 * mm - 26 * mm - 28 * mm - 30 * mm, 14 * mm, 26 * mm, 28 * mm, 30 * mm], repeatRows=1)
    sty = [("BACKGROUND", (0, 0), (-1, 0), TEAL), ("VALIGN", (0, 0), (-1, -1), "TOP"),
           ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINE), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]
    for i in range(2, len(data), 2):
        sty.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F6F8F7")))
    t.setStyle(TableStyle(sty))
    el += [t, Spacer(1, 5 * mm)]
    # totaux
    tt = [[Paragraph("Montant mensuel", ST["r"]), Paragraph(eur(tot["mensuel"]), ST["rb"])],
          [Paragraph(f"<b>Total de l'engagement ({int(dv.duree)} mois)</b>", ST["r"]), Paragraph(f"<b>{eur(tot['total'])}</b>", ST["rb"])],
          ] + ([[Paragraph(f"dont exercice {logic.annee()} ({tot['mois_exercice']} mois)", ST["r"]), Paragraph(eur(tot["exercice"]), ST["r"])]] if tot["mois_exercice"] else [])
    t = Table(tt, colWidths=[W - 70 * mm, 40 * mm], hAlign="RIGHT")
    t.setStyle(TableStyle([("BACKGROUND", (0, 1), (-1, 1), TEAL_L), ("LINEABOVE", (0, 1), (-1, 1), 1, TEAL),
                           ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    el += [t, Spacer(1, 7 * mm)]
    if dv.commentaire:
        el += [Paragraph("REMARQUES", ST["h"]), Paragraph(_esc(dv.commentaire), ST["n"]), Spacer(1, 5 * mm)]
    el += [Paragraph("CONDITIONS", ST["h"]),
           Paragraph("Refacturation interne à prix coûtant. Les montants sont refacturés chaque mois à partir du mois de début, "
                     "sur la base des ressources affectées. Une révision des prix des assets s'applique à compter de sa date d'effet. "
                     "Un écart de fin d'exercice entre coûts réels et montants refacturés peut être ventilé entre les entités.", ST["s"]),
           Spacer(1, 10 * mm)]
    sig = Table([[Paragraph("<b>Bon pour accord — client</b><br/>Nom, date et signature", ST["n"]),
                  Paragraph("<b>Équipe A — IA Platform</b><br/>Nom, date et signature", ST["n"])], ["", ""]],
                colWidths=[W * 0.48, W * 0.48], rowHeights=[None, 22 * mm], spaceBefore=0)
    sig.setStyle(TableStyle([("BOX", (0, 0), (0, -1), 0.6, LINE), ("BOX", (1, 0), (1, -1), 0.6, LINE),
                             ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6)]))
    el.append(sig)
    if dv.statut in ("Accepté", "Refusé") and dv.date_decision:
        el += [Spacer(1, 4 * mm), Paragraph(f"Statut : <b>{dv.statut}</b> le {logic.d(dv.date_decision):%d/%m/%Y}", ST["s"])]
    doc.build(el, onFirstPage=fond, onLaterPages=fond)
    return buf.getvalue()


def devis_png(devis_id, echelle=2.0):
    """Image PNG de la première page du devis."""
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(devis_pdf(devis_id))
    img = pdf[0].render(scale=echelle).to_pil()
    out = BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()
