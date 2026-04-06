"""
MALT IAC Report PDF Generator
Produces a PDF matching the MALT IAC report template using reportlab.

Structure:
  Cover Page
  Disclaimer (boilerplate)
  Preface (boilerplate)
  Section 1: Executive Summary (1.1 utility table, 1.2 AR summary table)
  Section 2: General Facility Background (2.1–2.6)
  Section 3: Assessment Recommendations (one subsection per AR)
  Section 4: Cybersecurity (boilerplate)
"""
import io
import os
from copy import deepcopy
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether
)
from reportlab.platypus.flowables import Flowable


# ── Constants ────────────────────────────────────────────────────────────────

PAGE_W, PAGE_H = letter
MARGIN = 1.0 * inch
BODY_W = PAGE_W - 2 * MARGIN

MALT_BLUE  = colors.HexColor("#003366")
MALT_LIGHT = colors.HexColor("#E8EEF4")
HEADER_GRAY= colors.HexColor("#F2F2F2")

DISCLAIMER_TEXT = (
    "This report is prepared for the exclusive use of the facility identified herein. "
    "The Industrial Assessment Center (IAC) at the University of Louisiana at Lafayette (UL Lafayette), "
    "funded by the U.S. Department of Energy (DOE), conducted this energy assessment. "
    "The findings, recommendations, and calculations presented herein represent "
    "the professional judgment of the assessment team based on conditions observed during the site visit. "
    "Actual savings may vary. The United States Government, the DOE, UL Lafayette, and the assessment team "
    "make no warranty, express or implied, and assume no legal liability or responsibility for the accuracy, "
    "completeness, or usefulness of any information herein. "
    "Reference to any specific commercial product, process, or service does not necessarily constitute "
    "or imply its endorsement, recommendation, or favoring by the United States Government or any agency thereof."
)

PREFACE_TEXT = (
    "The MALT Industrial Assessment Center (IAC) at the University of Louisiana at Lafayette "
    "provides no-cost energy assessments to small and medium-sized manufacturers as part of the "
    "U.S. Department of Energy's IAC Program. "
    "The purpose of this assessment was to identify opportunities for energy savings, "
    "waste reduction, and productivity improvements at the assessed facility. "
    "The assessment team visited the facility, reviewed utility bills, inspected equipment, "
    "and analyzed energy use patterns. The resulting recommendations are presented in this report "
    "along with estimated savings and implementation costs. "
    "For questions regarding this report, contact the MALT IAC at the University of Louisiana at Lafayette."
)

CYBERSECURITY_TEXT = (
    "As manufacturing facilities increasingly integrate digital technologies — including smart sensors, "
    "building automation systems, networked HVAC controls, and Industrial Internet of Things (IIoT) devices — "
    "cybersecurity becomes an essential component of operational resilience. "
    "During this assessment, the team noted the following general cybersecurity observations: "
    "Facilities are encouraged to implement network segmentation between operational technology (OT) "
    "and information technology (IT) networks; regularly update firmware and software on all networked devices; "
    "establish and enforce strong password policies for all control systems; "
    "conduct regular cybersecurity risk assessments in accordance with the NIST Cybersecurity Framework; "
    "and develop and exercise incident response plans for cybersecurity events. "
    "The MALT IAC recommends consulting with a qualified cybersecurity professional "
    "to perform a thorough assessment of all networked systems at this facility."
)


# ── Helper: styled table ─────────────────────────────────────────────────────

def malt_table(data, col_widths=None, header_row=True):
    """Build a styled Table matching MALT IAC formatting."""
    t = Table(data, colWidths=col_widths, repeatRows=1 if header_row else 0)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0 if header_row else -1), MALT_BLUE),
        ("TEXTCOLOR",  (0, 0), (-1, 0 if header_row else -1), colors.white),
        ("FONTNAME",   (0, 0), (-1, 0 if header_row else -1), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 9),
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, MALT_LIGHT]),
        ("LEFTPADDING",  (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING",   (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 3),
    ]
    t.setStyle(TableStyle(style))
    return t


# ── Header/Footer callback ───────────────────────────────────────────────────

def make_header_footer(report_number: str, director_name: str):
    def on_page(canvas, doc):
        canvas.saveState()
        # Header: thin blue line + director info + report number
        canvas.setFillColor(MALT_BLUE)
        canvas.rect(MARGIN, PAGE_H - 0.75*inch, BODY_W, 0.35*inch, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawString(MARGIN + 4, PAGE_H - 0.75*inch + 12,
                          f"MALT IAC  |  {director_name}")
        canvas.drawRightString(MARGIN + BODY_W - 4, PAGE_H - 0.75*inch + 12,
                               f"Report No: {report_number}")
        # Footer: page number
        canvas.setFillColor(colors.grey)
        canvas.setFont("Helvetica", 8)
        canvas.drawCentredString(PAGE_W / 2, 0.5*inch, f"Page {doc.page}")
        canvas.drawString(MARGIN, 0.5*inch,
                          "University of Louisiana at Lafayette — MALT IAC")
        canvas.drawRightString(MARGIN + BODY_W, 0.5*inch,
                               "U.S. Department of Energy")
        canvas.restoreState()
    return on_page


# ── Styles ───────────────────────────────────────────────────────────────────

def build_styles():
    base = getSampleStyleSheet()
    styles = {}
    styles["title"] = ParagraphStyle(
        "title", fontName="Helvetica-Bold", fontSize=20,
        textColor=MALT_BLUE, alignment=TA_CENTER, spaceAfter=10
    )
    styles["subtitle"] = ParagraphStyle(
        "subtitle", fontName="Helvetica", fontSize=12,
        textColor=colors.black, alignment=TA_CENTER, spaceAfter=6
    )
    styles["section"] = ParagraphStyle(
        "section", fontName="Helvetica-Bold", fontSize=13,
        textColor=MALT_BLUE, spaceBefore=14, spaceAfter=6,
        borderPad=2,
    )
    styles["subsection"] = ParagraphStyle(
        "subsection", fontName="Helvetica-Bold", fontSize=11,
        textColor=MALT_BLUE, spaceBefore=10, spaceAfter=4
    )
    styles["body"] = ParagraphStyle(
        "body", fontName="Helvetica", fontSize=10,
        alignment=TA_JUSTIFY, spaceAfter=6, leading=14
    )
    styles["caption"] = ParagraphStyle(
        "caption", fontName="Helvetica-Oblique", fontSize=9,
        textColor=colors.grey, alignment=TA_CENTER, spaceAfter=4
    )
    styles["bold"] = ParagraphStyle(
        "bold", fontName="Helvetica-Bold", fontSize=10, spaceAfter=4
    )
    return styles


# ── Main generator ───────────────────────────────────────────────────────────

def generate_report(session: dict) -> bytes:
    """
    Generate a MALT IAC PDF report from session state dict.
    Returns bytes of the PDF.
    """
    buf = io.BytesIO()
    S = build_styles()
    report_number = session.get("report_number", "IAC-XXXX")
    director_name = session.get("lead_faculty", "Dr. Peng \"Solomon\" Yin")

    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=1.1*inch, bottomMargin=0.85*inch,
        title=f"MALT IAC Report {report_number}",
        author="MALT IAC — University of Louisiana at Lafayette",
    )

    on_page = make_header_footer(report_number, director_name)
    story = []

    # ── COVER PAGE ────────────────────────────────────────────────────────────
    story.append(Spacer(1, 1.5*inch))
    story.append(Paragraph("MALT Industrial Assessment Center", S["title"]))
    story.append(Paragraph("Energy Assessment Report", S["subtitle"]))
    story.append(HRFlowable(width=BODY_W, color=MALT_BLUE, thickness=2, spaceAfter=16))
    story.append(Spacer(1, 0.3*inch))

    cover_data = [
        ["Report Number:", report_number],
        ["Site Visit Date:", str(session.get("site_visit_date", "")) or "—"],
        ["Facility Location:", session.get("location", "—")],
        ["Principal Products:", session.get("principal_products", "—")],
        ["NAICS Code:", session.get("naics_code", "—")],
        ["SIC Code:", session.get("sic_code", "—")],
        ["Annual Sales:", session.get("annual_sales", "—")],
        ["Number of Employees:", str(session.get("num_employees", "—"))],
    ]
    t = Table(cover_data, colWidths=[2.2*inch, 4.3*inch])
    t.setStyle(TableStyle([
        ("FONTNAME",  (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME",  (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE",  (0, 0), (-1, -1), 11),
        ("ALIGN",     (0, 0), (-1, -1), "LEFT"),
        ("VALIGN",    (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",(0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0,0),(-1,-1), 5),
        ("LINEABOVE", (0, 0), (-1, 0), 0.5, colors.lightgrey),
        ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.lightgrey),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.5*inch))

    story.append(Paragraph("Assessment Team", S["subsection"]))
    team_data = [
        ["Role", "Name"],
        ["Lead Faculty / IAC Director", director_name],
        ["Lead Student", session.get("lead_student", "—")],
        ["Safety Student", session.get("safety_student", "—")],
        ["Additional Student(s)", session.get("other_students", "—")],
    ]
    story.append(malt_table(team_data, col_widths=[3*inch, 3.5*inch]))
    story.append(Spacer(1, 0.5*inch))
    story.append(Paragraph(
        "University of Louisiana at Lafayette — MALT Industrial Assessment Center<br/>"
        "Funded by the U.S. Department of Energy, Office of Energy Efficiency and Renewable Energy",
        S["caption"]
    ))
    story.append(PageBreak())

    # ── DISCLAIMER ────────────────────────────────────────────────────────────
    story.append(Paragraph("DISCLAIMER", S["section"]))
    story.append(HRFlowable(width=BODY_W, color=MALT_BLUE, thickness=1, spaceAfter=8))
    story.append(Paragraph(DISCLAIMER_TEXT, S["body"]))
    story.append(PageBreak())

    # ── PREFACE ───────────────────────────────────────────────────────────────
    story.append(Paragraph("PREFACE", S["section"]))
    story.append(HRFlowable(width=BODY_W, color=MALT_BLUE, thickness=1, spaceAfter=8))
    story.append(Paragraph(PREFACE_TEXT, S["body"]))
    story.append(PageBreak())

    # ── SECTION 1: EXECUTIVE SUMMARY ─────────────────────────────────────────
    story.append(Paragraph("SECTION 1 — EXECUTIVE SUMMARY", S["section"]))
    story.append(HRFlowable(width=BODY_W, color=MALT_BLUE, thickness=1, spaceAfter=8))

    # 1.1 Utility table
    story.append(Paragraph("1.1  Annual Utility Usage and Cost", S["subsection"]))
    from utils.session import get_utility_rates_from_dict
    rates = get_utility_rates_from_dict(session)

    util_header = ["Utility", "Consumption", "Peak Demand", "Energy Cost", "Demand Cost", "Other Fees", "Total Cost"]
    util_rows   = [util_header]
    ann_elec_total = rates.get("ann_elec_cost",0) + rates.get("ann_demand_cost",0) + rates.get("ann_elec_fee",0)
    ann_gas_total  = rates.get("ann_gas_cost",0) + rates.get("ann_gas_fee",0)
    ann_wtr_total  = rates.get("ann_water_cost",0) + rates.get("ann_sewer_cost",0) + rates.get("ann_water_fee",0)
    total_util = ann_elec_total + ann_gas_total + ann_wtr_total

    ann_kw = max((r.get("kw",0) for r in session.get("elec_rows",[])), default=0)
    if rates.get("ann_kwh",0) > 0:
        util_rows.append(["Electricity", f"{rates['ann_kwh']:,.0f} kWh", f"{ann_kw:,.0f} kW",
                           f"${rates['ann_elec_cost']:,.0f}", f"${rates['ann_demand_cost']:,.0f}",
                           f"${rates['ann_elec_fee']:,.0f}", f"${ann_elec_total:,.0f}"])
    if rates.get("ann_mmbtu",0) > 0:
        util_rows.append(["Natural Gas", f"{rates['ann_mmbtu']:,.1f} MMBtu", "—",
                           f"${rates['ann_gas_cost']:,.0f}", "—",
                           f"${rates['ann_gas_fee']:,.0f}", f"${ann_gas_total:,.0f}"])
    if rates.get("ann_tgal",0) > 0:
        util_rows.append(["Water/Sewer", f"{rates['ann_tgal']:,.3f} Tgal", "—",
                           f"${rates['ann_water_cost']+rates['ann_sewer_cost']:,.0f}", "—",
                           f"${rates['ann_water_fee']:,.0f}", f"${ann_wtr_total:,.0f}"])
    util_rows.append(["TOTAL", "—", "—", "—", "—", "—", f"${total_util:,.0f}"])
    cw = [1.1*inch, 1.1*inch, 1.0*inch, 0.9*inch, 0.9*inch, 0.9*inch, 1.0*inch]
    story.append(malt_table(util_rows, col_widths=cw))
    story.append(Spacer(1, 0.15*inch))

    # 1.2 AR Summary table
    story.append(Paragraph("1.2  Summary of Recommended Energy-Saving Measures", S["subsection"]))
    ar_list = session.get("ar_list", [])
    if ar_list:
        ar_header = ["AR #", "ARC Code", "Recommendation", "Resource Savings", "Cost Savings\n($/yr)", "Impl. Cost\n($)", "Payback\n(yr)"]
        ar_rows = [ar_header]
        tot_cost = 0; tot_impl = 0
        for ar in ar_list:
            res_parts = []
            for r in ar.get("resources",[]):
                if r.get("savings",0) > 0:
                    res_parts.append(f"{r['type']}: {r['savings']:,.0f} {r['unit']}")
            pb = ar.get("payback", float("inf"))
            ar_rows.append([
                ar.get("ar_number","—"), ar.get("arc_code","—"), ar.get("title","—"),
                "\n".join(res_parts) or "—",
                f"${ar.get('total_cost_savings',0):,.0f}",
                f"${ar.get('implementation_cost',0):,.0f}",
                f"{pb:.1f}" if pb != float("inf") else "N/A",
            ])
            tot_cost += ar.get("total_cost_savings",0)
            tot_impl += ar.get("implementation_cost",0)
        avg_pb = tot_impl / tot_cost if tot_cost > 0 else float("inf")
        ar_rows.append(["—", "—", "TOTALS", "—",
                        f"${tot_cost:,.0f}", f"${tot_impl:,.0f}",
                        f"{avg_pb:.1f}" if avg_pb != float("inf") else "—"])
        cw2 = [0.55*inch, 0.75*inch, 1.8*inch, 1.4*inch, 0.8*inch, 0.8*inch, 0.75*inch]
        story.append(malt_table(ar_rows, col_widths=cw2))

    # Narrative
    exec_narrative = session.get("exec_narrative", "")
    if exec_narrative:
        story.append(Spacer(1, 0.1*inch))
        story.append(Paragraph(exec_narrative, S["body"]))

    story.append(PageBreak())

    # ── SECTION 2: FACILITY BACKGROUND ───────────────────────────────────────
    story.append(Paragraph("SECTION 2 — GENERAL FACILITY BACKGROUND", S["section"]))
    story.append(HRFlowable(width=BODY_W, color=MALT_BLUE, thickness=1, spaceAfter=8))

    story.append(Paragraph("2.1  Facility Description", S["subsection"]))
    story.append(Paragraph(session.get("facility_description", "—"), S["body"]))

    story.append(Paragraph("2.2  Process Description", S["subsection"]))
    story.append(Paragraph(session.get("process_description", "—"), S["body"]))

    story.append(Paragraph("2.3  Best Practices", S["subsection"]))
    bps = session.get("best_practices", [])
    bp_text = " ".join(b for b in bps if b)
    story.append(Paragraph(bp_text or "No best practices recorded.", S["body"]))

    story.append(Paragraph("2.4  Forms of Energy Usage", S["subsection"]))
    elec_uses  = session.get("elec_used_for", [])
    gas_uses   = session.get("gas_used_for", [])
    if elec_uses:
        story.append(Paragraph(f"<b>Electricity is used for:</b> {', '.join(elec_uses)}", S["body"]))
    if gas_uses:
        story.append(Paragraph(f"<b>Natural Gas is used for:</b> {', '.join(gas_uses)}", S["body"]))

    story.append(Paragraph("2.5  Major Energy Consuming Equipment", S["subsection"]))
    eq_rows = session.get("equipment_rows", [])
    if eq_rows:
        eq_header = ["Equipment", "Specifications", "Qty / Capacity", "Energy Form"]
        eq_data   = [eq_header] + [
            [r.get("equipment",""), r.get("specs",""), r.get("qty_capacity",""), r.get("energy_form","")]
            for r in eq_rows
        ]
        cw3 = [2.0*inch, 2.0*inch, 1.5*inch, 1.0*inch]
        story.append(malt_table(eq_data, col_widths=cw3))

    story.append(Paragraph("2.6  Energy and Water Consumption with Cost", S["subsection"]))
    # Electricity billing table
    elec_rows = session.get("elec_rows", [])
    if any(r.get("kwh", 0) > 0 for r in elec_rows):
        story.append(Paragraph("<b>Electricity Consumption and Cost</b>", S["bold"]))
        eh = ["Month", "kWh", "Elec Cost", "kW Demand", "Demand Cost", "Fees", "Total"]
        ed = [eh] + [
            [r.get("month",""), f"{r.get('kwh',0):,.0f}", f"${r.get('elec_cost',0):,.2f}",
             f"{r.get('kw',0):,.0f}", f"${r.get('demand_cost',0):,.2f}",
             f"${r.get('fee',0):,.2f}",
             f"${r.get('elec_cost',0)+r.get('demand_cost',0)+r.get('fee',0):,.2f}"]
            for r in elec_rows if r.get("kwh",0) > 0
        ]
        # Totals row
        t_kwh = sum(r.get("kwh",0) for r in elec_rows)
        t_ec  = sum(r.get("elec_cost",0) for r in elec_rows)
        t_dc  = sum(r.get("demand_cost",0) for r in elec_rows)
        t_ef  = sum(r.get("fee",0) for r in elec_rows)
        ed.append(["TOTAL", f"{t_kwh:,.0f}", f"${t_ec:,.2f}", "—", f"${t_dc:,.2f}", f"${t_ef:,.2f}", f"${t_ec+t_dc+t_ef:,.2f}"])
        cw4 = [0.7*inch, 1.0*inch, 1.0*inch, 1.0*inch, 1.0*inch, 0.8*inch, 0.9*inch]
        story.append(malt_table(ed, col_widths=cw4))
        story.append(Spacer(1, 0.1*inch))

    # Gas billing table
    gas_rows = session.get("gas_rows", [])
    if any(r.get("mmbtu", 0) > 0 for r in gas_rows):
        story.append(Paragraph("<b>Natural Gas Consumption and Cost</b>", S["bold"]))
        gh = ["Month", "MMBtu", "Gas Cost", "Fees", "Total"]
        gd = [gh] + [
            [r.get("month",""), f"{r.get('mmbtu',0):,.1f}", f"${r.get('cost',0):,.2f}",
             f"${r.get('fee',0):,.2f}", f"${r.get('cost',0)+r.get('fee',0):,.2f}"]
            for r in gas_rows if r.get("mmbtu",0) > 0
        ]
        t_m  = sum(r.get("mmbtu",0) for r in gas_rows)
        t_gc = sum(r.get("cost",0) for r in gas_rows)
        t_gf = sum(r.get("fee",0) for r in gas_rows)
        gd.append(["TOTAL", f"{t_m:,.1f}", f"${t_gc:,.2f}", f"${t_gf:,.2f}", f"${t_gc+t_gf:,.2f}"])
        cw5 = [0.8*inch, 1.0*inch, 1.1*inch, 1.0*inch, 1.0*inch]
        story.append(malt_table(gd, col_widths=cw5))
        story.append(Spacer(1, 0.1*inch))

    story.append(PageBreak())

    # ── SECTION 3: ASSESSMENT RECOMMENDATIONS ────────────────────────────────
    story.append(Paragraph("SECTION 3 — ENERGY ASSESSMENT RECOMMENDATIONS", S["section"]))
    story.append(HRFlowable(width=BODY_W, color=MALT_BLUE, thickness=1, spaceAfter=8))

    for idx, ar in enumerate(ar_list):
        ar_num   = ar.get("ar_number", f"AR-{idx+1}")
        arc_code = ar.get("arc_code", "")
        title    = ar.get("title", "")
        cost_sav = ar.get("total_cost_savings", 0)
        impl_cost= ar.get("implementation_cost", 0)
        payback  = ar.get("payback", float("inf"))

        # AR heading
        story.append(Paragraph(f"3.{idx+1}  {ar_num} — {title} (ARC {arc_code})", S["subsection"]))

        # Summary box table
        sum_data = [
            ["AR #", "ARC Code", "Annual Cost Savings", "Impl. Cost", "Simple Payback"],
            [ar_num, arc_code, f"${cost_sav:,.0f}/yr", f"${impl_cost:,.0f}",
             f"{payback:.1f} yr" if payback != float("inf") else "N/A"]
        ]
        story.append(malt_table(sum_data, col_widths=[0.9*inch, 1.0*inch, 1.7*inch, 1.3*inch, 1.5*inch]))
        story.append(Spacer(1, 0.08*inch))

        # Resource savings
        res_list = ar.get("resources", [])
        if res_list:
            res_text = " | ".join(f"{r['type']}: {r['savings']:,.0f} {r['unit']}" for r in res_list if r.get("savings",0)>0)
            story.append(Paragraph(f"<b>Resource Savings:</b> {res_text}", S["body"]))

        # Observation
        if ar.get("observation"):
            story.append(Paragraph("<b>Observation</b>", S["bold"]))
            story.append(Paragraph(ar["observation"], S["body"]))

        # Recommendation
        if ar.get("recommendation"):
            story.append(Paragraph("<b>Recommendation</b>", S["bold"]))
            story.append(Paragraph(ar["recommendation"], S["body"]))

        # Technology Description
        if ar.get("tech_description"):
            story.append(Paragraph("<b>Technology Description</b>", S["bold"]))
            story.append(Paragraph(ar["tech_description"], S["body"]))

        # Calculation narrative
        calc = ar.get("calculation_details", {})
        if calc:
            story.append(Paragraph("<b>Calculation</b>", S["bold"]))
            narrative = calc.get("narrative", "")
            if narrative:
                story.append(Paragraph(narrative, S["body"]))
            else:
                # Build auto-narrative from calc dict
                lines = []
                if "ann_kwh" in calc:
                    lines.append(f"Annual electricity savings: {calc['ann_kwh']:,.0f} kWh")
                if "ann_cost" in calc:
                    lines.append(f"Annual cost savings: ${calc['ann_cost']:,.0f}")
                if "model" in calc:
                    model_names = {"2P":"2-Parameter","3PC":"3-Parameter Cooling","3PH":"3-Parameter Heating","4P":"4-Parameter","5P":"5-Parameter"}
                    lines.append(f"Regression model: {model_names.get(calc['model'], calc['model'])}, R² = {calc.get('r2',0):.4f}")
                if "total_ann_kwh" in calc:
                    lines.append(f"Total annual kWh saved: {calc['total_ann_kwh']:,.0f} kWh")
                if "ann_kwh_savings" in calc:
                    lines.append(f"Annual kWh savings: {calc['ann_kwh_savings']:,.0f} kWh")
                if "cop_current" in calc:
                    lines.append(f"COP improvement: {calc['cop_current']:.3f} → {calc.get('cop_proposed',0):.3f}")
                if lines:
                    story.append(Paragraph("<br/>".join(lines), S["body"]))

        if idx < len(ar_list) - 1:
            story.append(HRFlowable(width=BODY_W, color=colors.lightgrey, thickness=0.5, spaceAfter=8))

    story.append(PageBreak())

    # ── SECTION 4: CYBERSECURITY ──────────────────────────────────────────────
    story.append(Paragraph("SECTION 4 — CYBERSECURITY", S["section"]))
    story.append(HRFlowable(width=BODY_W, color=MALT_BLUE, thickness=1, spaceAfter=8))
    story.append(Paragraph(CYBERSECURITY_TEXT, S["body"]))

    # ── Build PDF ─────────────────────────────────────────────────────────────
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    buf.seek(0)
    return buf.read()
