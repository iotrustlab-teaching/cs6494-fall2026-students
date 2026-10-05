#!/usr/bin/env python3
"""Build the fictional Riverbend substation functional-specification excerpt."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "static" / "docs" / "riverbend_substation_fds_excerpt.pdf"
START_PAGE = 173
TOTAL_PAGES = 412

NAVY = colors.HexColor("#19313A")
BLUE = colors.HexColor("#176A91")
TEAL = colors.HexColor("#087F6D")
RED = colors.HexColor("#A52931")
AMBER = colors.HexColor("#A45A00")
MID = colors.HexColor("#596970")
LINE = colors.HexColor("#AEBBC0")
PALE = colors.HexColor("#EDF3F5")
PALE_BLUE = colors.HexColor("#E8F2F6")
WHITE = colors.white


class OneLineDiagram(Flowable):
    def __init__(self) -> None:
        super().__init__()
        self.width = 7.18 * inch
        self.height = 1.76 * inch

    def draw(self) -> None:
        c = self.canv
        w, h = self.width, self.height
        c.setStrokeColor(LINE)
        c.setFillColor(colors.HexColor("#F8FAFA"))
        c.roundRect(0, 0, w, h, 4, stroke=1, fill=1)

        c.setFont("Helvetica-Bold", 7)
        c.setFillColor(NAVY)
        c.drawString(12, h - 16, "FIGURE 8-12  STATION 12 TEACHING ONE-LINE (NOT FOR CONSTRUCTION)")

        source_x = w / 2
        bus_y = 54
        c.setStrokeColor(NAVY)
        c.setLineWidth(1.4)
        c.circle(source_x, h - 39, 12, stroke=1, fill=0)
        c.setFont("Helvetica", 6.8)
        c.drawString(source_x + 20, h - 41, "120 V TEACHING SOURCE")
        c.line(source_x, h - 51, source_x, h - 57)
        self._breaker(source_x, h - 59, "B0", "MAIN")
        c.line(source_x, h - 69, source_x, bus_y)
        c.setLineWidth(3)
        c.line(78, bus_y, w - 78, bus_y)
        c.setFont("Helvetica-Bold", 6.8)
        c.drawString(80, bus_y + 7, "BUS 12A")

        xs = (130, source_x, w - 130)
        labels = (("S1", "LOAD 1", False), ("S2", "LOAD 2", False), ("S3", "MAINTENANCE ZONE", True))
        for x, (device, label, out_of_service) in zip(xs, labels):
            c.setStrokeColor(RED if out_of_service else NAVY)
            c.setFillColor(RED if out_of_service else NAVY)
            c.setLineWidth(1.2)
            c.line(x, bus_y, x, 43)
            self._breaker(x, 40, device, "BRANCH", out_of_service)
            c.line(x, 30, x, 16)
            c.setFont("Helvetica-Bold", 7)
            c.drawCentredString(x, 5, label)

    def _breaker(self, x: float, y: float, tag: str, role: str, alert: bool = False) -> None:
        c = self.canv
        c.setStrokeColor(RED if alert else NAVY)
        c.setFillColor(RED if alert else NAVY)
        c.setLineWidth(1.2)
        c.line(x, y + 8, x, y + 2)
        c.circle(x, y, 1.8, stroke=1, fill=1)
        c.circle(x, y - 10, 1.8, stroke=1, fill=1)
        c.line(x, y, x + 8, y - 8)
        c.setFont("Helvetica-Bold", 7)
        c.drawString(x + 12, y - 2, tag)
        c.setFont("Helvetica", 5.8)
        c.drawString(x + 12, y - 10, role)


def header_footer(canvas, doc) -> None:
    canvas.saveState()
    page_no = START_PAGE + canvas.getPageNumber() - 1
    width, height = letter

    canvas.setFillColor(NAVY)
    canvas.rect(0, height - 33, width, 33, stroke=0, fill=1)
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica-Bold", 8.2)
    canvas.drawString(40, height - 20, "RIVERBEND MUNICIPAL POWER  |  DISTRIBUTION AUTOMATION FDS")
    canvas.setFont("Helvetica", 7.2)
    right = "RBMP-FDS-DA-004  |  REV 4"
    canvas.drawRightString(width - 40, height - 20, right)

    canvas.setFillColor(colors.HexColor("#F7E5E6"))
    canvas.rect(0, height - 48, width, 15, stroke=0, fill=1)
    canvas.setFillColor(RED)
    canvas.setFont("Helvetica-Bold", 6.7)
    canvas.drawCentredString(width / 2, height - 43, "AUTHORED COURSE ARTIFACT - FICTIONAL UTILITY - NOT FOR OPERATIONAL USE")

    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.6)
    canvas.line(40, 37, width - 40, 37)
    canvas.setFillColor(MID)
    canvas.setFont("Helvetica", 6.7)
    canvas.drawString(40, 25, "CONTROLLED TRAINING COPY")
    canvas.drawCentredString(width / 2, 25, "Printed copies are uncontrolled")
    canvas.setFont("Helvetica-Bold", 7)
    canvas.drawRightString(width - 40, 25, f"Page {page_no} of {TOTAL_PAGES}")
    canvas.restoreState()


def paragraph(text: str, style) -> Paragraph:
    return Paragraph(text, style)


def make_table(data, widths, *, header=True, font_size=7.3, row_backgrounds=None) -> Table:
    cell_style = ParagraphStyle(
        "TableCell", fontName="Helvetica", fontSize=font_size, leading=font_size + 1.8,
        textColor=NAVY, alignment=TA_LEFT,
    )
    header_style = ParagraphStyle(
        "TableHeader", parent=cell_style, fontName="Helvetica-Bold", textColor=WHITE,
    )
    normalized = []
    for row_index, row in enumerate(data):
        normalized.append([
            value if isinstance(value, Flowable) else Paragraph(
                str(value).replace("\n", "<br/>"),
                header_style if header and row_index == 0 else cell_style,
            )
            for value in row
        ])
    table = Table(normalized, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.45, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("TEXTCOLOR", (0, 0), (-1, -1), NAVY),
    ]
    if header:
        commands.extend([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ])
    for row, color in row_backgrounds or []:
        commands.append(("BACKGROUND", (0, row), (-1, row), color))
    table.setStyle(TableStyle(commands))
    return table


def build_story():
    sample = getSampleStyleSheet()
    body = ParagraphStyle(
        "Body",
        parent=sample["BodyText"],
        fontName="Helvetica",
        fontSize=8.4,
        leading=11,
        textColor=NAVY,
        spaceAfter=5,
    )
    small = ParagraphStyle("Small", parent=body, fontSize=7.2, leading=9, textColor=MID)
    h1 = ParagraphStyle(
        "H1", parent=sample["Heading1"], fontName="Helvetica-Bold", fontSize=16,
        leading=19, textColor=NAVY, spaceAfter=4,
    )
    h2 = ParagraphStyle(
        "H2", parent=sample["Heading2"], fontName="Helvetica-Bold", fontSize=10.5,
        leading=13, textColor=BLUE, spaceBefore=7, spaceAfter=5,
    )
    h3 = ParagraphStyle(
        "H3", parent=sample["Heading3"], fontName="Helvetica-Bold", fontSize=8.8,
        leading=11, textColor=NAVY, spaceBefore=5, spaceAfter=3,
    )
    callout = ParagraphStyle(
        "Callout", parent=body, fontName="Helvetica-Bold", fontSize=8.2, leading=10.5,
        textColor=RED, leftIndent=8, rightIndent=8, borderColor=RED, borderWidth=0.7,
        borderPadding=7, backColor=colors.HexColor("#FFF5F5"), spaceBefore=4, spaceAfter=7,
    )
    req = ParagraphStyle("Requirement", parent=body, fontSize=7.7, leading=9.5, spaceAfter=0)
    tiny_center = ParagraphStyle("TinyCenter", parent=small, alignment=TA_CENTER, fontSize=6.5, leading=8)

    story = []

    # Page 173
    story.extend([
        paragraph("8.4  Station 12 feeder restoration and outage isolation", h1),
        paragraph("Functional design specification excerpt", ParagraphStyle(
            "Subtitle", parent=body, fontName="Helvetica-Bold", fontSize=10, leading=12, textColor=TEAL,
        )),
        Spacer(1, 5),
        make_table([
            ["Document ID", "RBMP-FDS-DA-004", "System", "Station 12 distribution automation"],
            ["Revision", "4", "Effective date", "2026-08-14"],
            ["Owner", "OT Systems Engineering", "Approval", "Operations / Protection Engineering"],
            ["Excerpt scope", "Sections 8.4-8.7", "Classification", "Internal training copy"],
        ], [0.92*inch, 1.55*inch, 0.92*inch, 3.79*inch], header=False, font_size=7.3,
        row_backgrounds=[(0, PALE), (2, PALE)]),
        Spacer(1, 8),
        paragraph(
            "Document authenticity notice. This four-page excerpt is an authored CS 6494 teaching artifact. "
            "Riverbend Municipal Power, its station, addresses, personnel, and control scheme are fictional. "
            "The layout imitates an internal engineering manual so students can practice source authority and "
            "requirements traceability; it does not reproduce any utility's proprietary documentation.",
            callout,
        ),
        paragraph("8.4.1 Purpose", h2),
        paragraph(
            "This section defines the close-permission behavior for main breaker B0 and branch switching devices "
            "S1 through S3 during planned maintenance and restoration. It specifies the operating properties to "
            "be preserved by the controller. Protection settings, field switching procedures, communications "
            "security, and personnel authorization remain governed by their owning documents.", body),
        OneLineDiagram(),
        Spacer(1, 5),
        paragraph("8.4.2 Operating context", h2),
        paragraph(
            "The normal training scenario declares S3 out of service while S1 and S2 remain required for service. "
            "B0 may be open while branch contacts retain their last position. Consequently, a zero source-current "
            "measurement does not establish that a later B0 close will be safe. The controller shall evaluate the "
            "state that would result from the requested operation.", body),
    ])

    story.append(PageBreak())

    # Page 174
    story.extend([
        paragraph("8.5  Required controller behavior", h1),
        paragraph("The words SHALL and SHALL NOT identify mandatory behavior in this excerpt.", small),
        make_table([
            ["ID", "Requirement", "Rationale / owner"],
            ["FDS-DA-401", paragraph("A close operation SHALL NOT result in any device declared out of service becoming energized.", req), paragraph("Primary safety property. Operations owns the approved outage declaration.", req)],
            ["FDS-DA-402", paragraph("The close-permission function SHALL evaluate the resulting contact topology: <b>ResultingPositions = ActualPositions OR TargetMask</b>.", req), paragraph("Covers upstream closes that energize an already-closed downstream branch.", req)],
            ["FDS-DA-403", paragraph("A close operation SHALL be denied while the independent trip latch is set.", req), paragraph("Protection state constrains restoration; it is not cleared by this function.", req)],
            ["FDS-DA-404", paragraph("A close decision SHALL fail closed when required position or outage-state evidence is stale, invalid, or from a different command generation.", req), paragraph("Freshness/versioning signal is an interface requirement. This excerpt does not define its transport.", req)],
            ["FDS-DA-405", paragraph("Present current MAY support diagnosis but SHALL NOT be used alone to infer the safety of a topology-changing close.", req), paragraph("Current before a close cannot prove which downstream section the close will energize.", req)],
            ["FDS-DA-410", paragraph("With the out-of-service branch isolated, the design SHALL permit a bounded restoration sequence that supplies all required healthy branches.", req), paragraph("Service property prevents a deny-all implementation from satisfying the design.", req)],
            ["FDS-DA-411", paragraph("A protocol acknowledgement or controller permit SHALL NOT be reported as actual device movement. Position feedback shall originate from the device/process boundary.", req), paragraph("Separates request, decision, actuation, and physical consequence.", req)],
        ], [0.88*inch, 3.95*inch, 2.35*inch], font_size=7.1,
        row_backgrounds=[(2, PALE_BLUE), (4, PALE), (6, PALE_BLUE)]),
        Spacer(1, 8),
        paragraph("8.5.1 Close-permission sequence", h2),
        make_table([
            ["Step", "Owning function", "Required behavior"],
            ["1", "Request adapter", "Validate command form and assign a nonzero request sequence. Do not actuate a device."],
            ["2", "State adapter", "Present current positions, target mask, approved out-of-service mask, trip state, and measurement context."],
            ["3", "Compiled controller", "Evaluate FDS-DA-401 through FDS-DA-405 for the same request generation; return permit or deny."],
            ["4", "Device adapter", "Apply only a current permit. Timeout, controller stop, or sequence mismatch shall fail closed."],
            ["5", "Process / feedback", "Derive actual contact position and electrical measurements independently of the requested value."],
        ], [0.43*inch, 1.45*inch, 5.30*inch], font_size=7.2,
        row_backgrounds=[(2, PALE), (4, PALE)]),
        Spacer(1, 8),
        paragraph(
            "Boundary note: This FDS establishes functional behavior. It does not establish requester identity, "
            "network authenticity, field isolation, relay coordination, or compliance with any named protocol or standard.", callout),
    ])

    story.append(PageBreak())

    # Page 175
    story.extend([
        paragraph("8.6  Point contract and source authority", h1),
        paragraph(
            "The following integration points are shown for the training implementation. Register locations are "
            "configuration details, not proof of physical state or authority.", body),
        make_table([
            ["Point", "Location", "Owner", "Meaning / limitation"],
            ["RequestSeq", "%MW0 / 1024", "Request adapter", "Nonzero command generation; binds one request to one decision."],
            ["ActualPositions", "%MW1 / 1025", "Device adapter", "Bit mask B0=01, S1=02, S2=04, S3=08. Requires independent freshness evidence."],
            ["TargetMask", "%MW2 / 1026", "Request adapter", "One requested close target; not an actual device position."],
            ["OutOfServiceMask", "%MW3 / 1027", "Outage record adapter", "Approved unavailable section mask. A local label alone is not authority."],
            ["TripLatched", "%MW4 / 1028", "Protection adapter", "Independent protection state; 0 clear, 1 latched."],
            ["PresentCurrent_dA", "%MW5 / 1029", "Measurement adapter", "Source current in deciamps. Observation only; not a topology guarantee."],
            ["CurrentLimit_dA", "%MW6 / 1030", "Configuration", "Teaching threshold. Does not replace FDS-DA-401/402."],
            ["DecisionCode", "%MW7 / 1031", "Compiled controller", "0 deny, 1 permit for DecisionSeq."],
            ["DecisionSeq", "%MW8 / 1032", "Compiled controller", "Request generation associated with current decision."],
            ["Heartbeat", "%MW9 / 1033", "Compiled controller", "Scan liveness only; not proof of correct logic or safe actuation."],
        ], [1.25*inch, 1.03*inch, 1.31*inch, 3.59*inch], font_size=6.85,
        row_backgrounds=[(2, PALE), (4, PALE), (6, PALE), (8, PALE), (10, PALE)]),
        Spacer(1, 8),
        paragraph("8.6.1 Source-use rules", h2),
        make_table([
            ["Source", "Authoritative for", "Cannot establish by itself"],
            ["This FDS excerpt", "Required functional behavior and ownership boundaries", "Actual field state, current implementation, or test result"],
            ["Approved outage record", "Which section is declared unavailable for the active generation", "Contact position, de-energization, or isolation completeness"],
            ["Controller source/build", "Implemented decision logic and artifact identity", "That the device moved or the process remained safe"],
            ["Device/process telemetry", "Reported contact and electrical consequence at a stated time", "Requester authority or correctness of controller logic"],
            ["Captured regression", "Observed behavior for the named build, scenario, and run", "Untested states or operation outside the stated assumptions"],
        ], [1.37*inch, 2.66*inch, 3.15*inch], font_size=7.0,
        row_backgrounds=[(2, PALE), (4, PALE)]),
        Spacer(1, 8),
        paragraph(
            "Traceability rule: Claims shall name the requirement, controller build, run identifier, evidence source, "
            "and assumptions. Unknown or unavailable evidence shall remain explicit; it shall not be inferred from a "
            "communication success or a plausible label.", callout),
    ])

    story.append(PageBreak())

    # Page 176
    story.extend([
        paragraph("8.7  Verification and acceptance excerpt", h1),
        paragraph(
            "Acceptance requires both a prohibited-transition test and a legitimate-service test against the same "
            "compiled controller build. Independent process evidence shall determine the physical result.", body),
        make_table([
            ["Test", "Initial state and request", "Required result", "Evidence retained"],
            ["AT-DA-17\nUpstream close", paragraph("B0 open; S3 contact closed; S3 declared OOS; source current 0 A. Request CLOSE B0.", req), paragraph("DENY. B0 remains open; S3 remains de-energized; no protection trip.", req), paragraph("Request/decision generation, build ID, actual contacts, bus voltage, branch current, trip state.", req)],
            ["AT-DA-18\nHealthy restoration", paragraph("B0 open; S1/S2/S3 open; S3 declared OOS. Request CLOSE S1, CLOSE S2, then CLOSE B0.", req), paragraph("PERMIT valid sequence. S1 and S2 are supplied; S3 remains isolated; no trip.", req), paragraph("Three requests/decisions, actual positions, sustained-service result, measurements.", req)],
            ["AT-DA-19\nRelocated outage", paragraph("B0 open; S2 declared OOS; S1 and S3 required. Perform bounded restoration.", req), paragraph("S1 and S3 may be supplied while S2 remains de-energized. No target-specific exception is acceptable.", req), paragraph("Scenario ID, outage mask, build ID, resulting topology, service and safety verdicts.", req)],
            ["DR-DA-20\nStale position review", paragraph("A previously safe contact report expires or physical state changes before actuation.", req), paragraph("Do not extend a prior permit. Revalidate at the final actuation boundary or fail closed.", req), paragraph("Freshness/version mechanism is not supplied by the current fixture; record this as a bounded claim limitation.", req)],
        ], [1.06*inch, 2.39*inch, 2.14*inch, 1.59*inch], font_size=6.9,
        row_backgrounds=[(2, PALE), (4, PALE)]),
        Spacer(1, 9),
        paragraph("8.7.1 Acceptance conditions", h2),
        paragraph("<b>a.</b> A controller that blocks every close fails FDS-DA-410 even if no unsafe energization occurs.<br/>"
                  "<b>b.</b> A controller that blocks only direct close commands to the OOS branch fails AT-DA-17.<br/>"
                  "<b>c.</b> A protective trip after energization does not satisfy FDS-DA-401; protection is an independent layer.<br/>"
                  "<b>d.</b> A request acknowledgement, decision code, or HMI echo does not satisfy actual-position evidence.<br/>"
                  "<b>e.</b> Results shall be labeled TESTED, REPLAYED, or PROPOSED according to how the evidence was produced.", body),
        paragraph("8.7.2 Revision note", h2),
        make_table([
            ["Rev", "Date", "Description", "Approved by"],
            ["3", "2026-07-29", "Separated protocol acceptance from device-position confirmation.", "OT Systems / Operations"],
            ["4", "2026-08-14", "Added resulting-topology requirement and stale-evidence design review.", "OT Systems / Protection"],
        ], [0.48*inch, 0.82*inch, 4.55*inch, 1.33*inch], font_size=7.1,
        row_backgrounds=[(2, PALE)]),
        Spacer(1, 10),
        paragraph(
            "END OF SUPPLIED EXCERPT. Referenced but not supplied: RBMP-OPS-SW-012 switching procedure; "
            "RBMP-PRT-012 protection settings; RBMP-SEC-006 remote-access standard; Station 12 as-built drawings. "
            "Students shall not invent facts from these absent sources.", callout),
        Spacer(1, 5),
        paragraph("Course provenance", h3),
        paragraph(
            "Prepared for CS 6494 as a fictional internal-documentation excerpt. Functional identifiers align with "
            "the Substation Recovery Lab, but the document makes no claim of standards conformance, vendor equivalence, "
            "or use at a real facility.", small),
        paragraph("Document identity: RBMP-FDS-DA-004, Rev 4, excerpt pages 173-176.", tiny_center),
    ])
    return story


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = BaseDocTemplate(
        str(OUTPUT),
        pagesize=letter,
        leftMargin=42,
        rightMargin=42,
        topMargin=58,
        bottomMargin=45,
        title="Riverbend Substation Functional Design Specification Excerpt",
        author="CS 6494 course staff",
        subject="Fictional training artifact for requirements and evidence analysis",
        creator="CS 6494 artifact builder",
    )
    frame = Frame(42, 45, letter[0] - 84, letter[1] - 103, id="body", showBoundary=0)
    doc.addPageTemplates([PageTemplate(id="technical", frames=[frame], onPage=header_footer)])
    doc.build(build_story())
    print(OUTPUT)


if __name__ == "__main__":
    main()
