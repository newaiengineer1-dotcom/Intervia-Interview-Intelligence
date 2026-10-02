import html
import io
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from utils import average_scores


def _text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ", ".join(str(x) for x in value) if value else "—"
    if isinstance(value, dict):
        return "; ".join(f"{k}: {v}" for k, v in value.items()) if value else "—"
    return str(value)


def _safe(value) -> str:
    return escape(_text(value)).replace("\n", "<br/>") or "—"


def _overall(scores: dict) -> int:
    return round(sum(scores.values()) / len(scores)) if scores else 0


def build_markdown_report(
    target_role,
    industry,
    mode,
    turns,
    evidence,
    company="",
    duration_minutes=30,
    categories=None,
    question_mode="Text Questions",
    answer_mode="⌨️ Type Answers",
    use_research=False,
    camera_enabled=False,
    speech_language="English (US)",
    answer_length="Standard",
    company_track="",
    session_id="",
    started_at=None,
    groq_model="",
):
    scores = average_scores([t.get("feedback", {}).get("scores", {}) for t in turns])
    overall = _overall(scores)
    ats = (evidence or {}).get("ats_readiness", {})
    lines = [
        "# Intervia Interview Intelligence — Session Report",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"Session ID: {session_id or 'Not recorded'}",
        f"Target role: {target_role}",
        f"Company / employer: {company or 'Not specified'}",
        f"Mode: {mode}",
        f"Duration: {duration_minutes} minutes",
        f"Question format: {question_mode}",
        f"Answer format: {answer_mode}",
        f"Categories: {', '.join(categories or [])}",
        f"Question voice: {speech_language}",
        f"Practice-answer length: {answer_length}",
        f"Company / role analysis: {'Enabled' if use_research else 'Disabled'}",
        f"Camera presentation snapshot: {'Enabled' if camera_enabled else 'Disabled'}",
        f"Groq model: {groq_model or 'Automatic model discovery'}",
        "",
        "## Executive performance",
        f"Overall average: {overall}/100",
    ]
    for k, v in scores.items():
        lines.append(f"- {k.title()}: {v}/100")
    lines += [
        "",
        "## Candidate Evidence & ATS Readiness",
        f"ATS-readiness estimate: {ats.get('score', 0)}/100 — {ats.get('label', 'Not available')}",
        f"Method: {ats.get('method', 'Not available')}",
        f"CV file: {ats.get('cv_filename', 'Not provided')}",
        f"Keyword alignment: {ats.get('keyword_match_score', 0)}/100",
        f"Matched keywords: {', '.join(ats.get('matched_keywords', [])[:40]) or 'None detected'}",
        f"Missing / not detected keywords: {', '.join(ats.get('missing_keywords', [])[:40]) or 'None detected'}",
        f"Detected headings: {', '.join(ats.get('detected_headings', [])) or 'None detected'}",
        "",
        "## Evidence grounding",
        "Candidate evidence is sourced only from the CV. JD requirements and optional research/context are kept separate.",
        f"Candidate facts: {len((evidence or {}).get('candidate_facts', []))}",
        f"JD requirements: {len((evidence or {}).get('jd_requirements', []))}",
        f"Matched terms: {len((evidence or {}).get('matches', []))}",
        f"Gaps / unknowns: {len((evidence or {}).get('gaps', []))}",
    ]
    if company_track:
        lines += ["", "## Company-specific context supplied", company_track]
    if evidence and evidence.get("research"):
        lines += ["", "## Company / role analysis", _text(evidence.get("research"))]
    for i, turn in enumerate(turns, 1):
        fb = turn.get("feedback", {})
        lines += [
            "", f"## Question {i} — {turn.get('category', 'General')}",
            f"Question: {turn.get('question', '')}",
            f"Answer mode: {turn.get('answer_mode', 'text')}",
            "", "### Candidate answer", turn.get("answer", ""),
            "", "### Performance scores",
        ]
        for k, v in fb.get("scores", {}).items():
            lines.append(f"- {k.title()}: {v}/100")
        lines += [
            f"- Overall: {fb.get('overall', 0)}/100",
            "", "### Strengths", _text(fb.get("strengths", [])),
            "", "### Missing points / improvement areas", _text(fb.get("missing_points", [])),
            "", "### Verification notes", _text(fb.get("verification_notes", [])),
            "", "### Suggested better answer", fb.get("practice_answer", ""),
            "", "### Next improvement", fb.get("next_improvement", ""),
            "", "### Speech analytics", _text(fb.get("speech_metrics", {})),
            "", "### Presentation cues", _text(fb.get("presentation_cues", {})),
        ]
    return "\n".join(lines)


def _section_title(text, styles):
    return [Spacer(1, 7), Paragraph(_safe(text), styles["H2"]), HRFlowable(width="100%", thickness=0.7, color=colors.HexColor("#394A70")), Spacer(1, 6)]


def _kv_table(rows, styles):
    data = [[Paragraph(_safe(k), styles["Label"]), Paragraph(_safe(v), styles["Body"])] for k, v in rows]
    table = Table(data, colWidths=[48 * mm, 132 * mm], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EEF2FA")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#C9D3E6")),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D9E1EF")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


def _score_table(scores, styles):
    data = [[Paragraph("Dimension", styles["Label"]), Paragraph("Score", styles["Label"])]]
    for key, value in scores.items():
        data.append([Paragraph(_safe(key.title()), styles["Body"]), Paragraph(_safe(f"{value}/100"), styles["Body"])])
    table = Table(data, colWidths=[100 * mm, 40 * mm], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#182846")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#B9C7DE")),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D5DDEB")),
        ("ALIGN", (1, 1), (1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


def build_pdf_report(
    target_role,
    industry,
    mode,
    turns,
    evidence,
    company="",
    duration_minutes=30,
    categories=None,
    question_mode="Text Questions",
    answer_mode="⌨️ Type Answers",
    use_research=False,
    camera_enabled=False,
    speech_language="English (US)",
    answer_length="Standard",
    company_track="",
    session_id="",
    started_at=None,
    groq_model="",
    research=None,
    cv_filename="",
    jd_filename="",
):
    """Build a complete, professional session PDF containing configuration, evidence, ATS, coaching and recommendations."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, rightMargin=17 * mm, leftMargin=17 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title="Intervia Interview Intelligence — Session Report",
        author="Intervia Interview Intelligence",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Hero", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=24, leading=28, textColor=colors.HexColor("#13203A"), alignment=TA_LEFT, spaceAfter=8))
    styles.add(ParagraphStyle(name="Subtitle", parent=styles["BodyText"], fontSize=10, leading=14, textColor=colors.HexColor("#596A86"), spaceAfter=10))
    styles.add(ParagraphStyle(name="H2", parent=styles["Heading2"], fontSize=15, leading=18, textColor=colors.HexColor("#172B4D"), spaceBefore=8, spaceAfter=6))
    styles.add(ParagraphStyle(name="H3", parent=styles["Heading3"], fontSize=11, leading=14, textColor=colors.HexColor("#2B4268"), spaceBefore=6, spaceAfter=4))
    styles.add(ParagraphStyle(name="Body", parent=styles["BodyText"], fontSize=9.2, leading=13.5, textColor=colors.HexColor("#26354E"), spaceAfter=3))
    styles.add(ParagraphStyle(name="Label", parent=styles["BodyText"], fontSize=8.7, leading=12, textColor=colors.HexColor("#334B70"), fontName="Helvetica-Bold"))
    styles.add(ParagraphStyle(name="Score", parent=styles["BodyText"], fontSize=20, leading=24, textColor=colors.HexColor("#4C35A8"), fontName="Helvetica-Bold", alignment=TA_CENTER))
    styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontSize=7.8, leading=10.5, textColor=colors.HexColor("#6B7A93")))

    scores = average_scores([t.get("feedback", {}).get("scores", {}) for t in turns])
    overall = _overall(scores)
    ev = evidence or {}
    ats = ev.get("ats_readiness", {})
    story = []

    story.append(Paragraph("INTERVIA", styles["Subtitle"]))
    story.append(Paragraph("Interview Intelligence — Complete Session Report", styles["Hero"]))
    story.append(Paragraph("Professional session record · performance · evidence · ATS readiness · coaching · recommendations", styles["Subtitle"]))

    hero = Table([
        [Paragraph("OVERALL PERFORMANCE", styles["Label"]), Paragraph("ATS READINESS", styles["Label"]), Paragraph("QUESTIONS COMPLETED", styles["Label"])],
        [Paragraph(f"{overall}/100", styles["Score"]), Paragraph(f"{ats.get('score', 0)}/100", styles["Score"]), Paragraph(str(len(turns)), styles["Score"])],
    ], colWidths=[58 * mm, 58 * mm, 58 * mm])
    hero.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F5F7FC")),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#C4D0E3")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D7DFEC")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story += [hero, Spacer(1, 10)]

    story += _section_title("1. Session configuration", styles)
    story.append(_kv_table([
        ("Session ID", session_id or "Not recorded"),
        ("Target role", target_role),
        ("Company / employer", company or "Not specified"),
        ("Interview mode", mode),
        ("Interview categories", ", ".join(categories or []) or "Default categories"),
        ("Practice duration", f"{duration_minutes} minutes"),
        ("Question format", question_mode),
        ("Answer format", answer_mode),
        ("Question voice", speech_language),
        ("AI practice-answer length", answer_length),
        ("Company / role analysis", "Enabled" if use_research else "Disabled"),
        ("Camera presentation snapshot", "Enabled" if camera_enabled else "Disabled"),
        ("CV / Resume file", cv_filename or ats.get("cv_filename", "Not provided")),
        ("Job Description file", jd_filename or "Not provided / pasted text"),
        ("Groq model", groq_model or "Automatic model discovery"),
    ], styles))

    if company_track:
        story += _section_title("2. User-supplied company / role context", styles)
        story.append(Paragraph(_safe(company_track), styles["Body"]))

    story += _section_title("3. Candidate Evidence & ATS Readiness", styles)
    story.append(_kv_table([
        ("ATS-readiness estimate", f"{ats.get('score', 0)}/100 — {ats.get('label', 'Not available')}"),
        ("Keyword alignment", f"{ats.get('keyword_match_score', 0)}/100"),
        ("Detected headings", ", ".join(ats.get("detected_headings", [])) or "None detected"),
        ("Contact signals", _text(ats.get("contact_signals", {}))),
        ("Bullet points detected", ats.get("bullet_points_detected", 0)),
        ("Quantified achievement signals", ats.get("quantified_achievement_signals", 0)),
        ("Estimated extracted word count", ats.get("estimated_word_count", 0)),
    ], styles))
    story.append(Spacer(1, 6))
    story.append(Paragraph("ATS methodology note", styles["H3"]))
    story.append(Paragraph(_safe(ats.get("method", "ATS readiness was not calculated.")), styles["Body"]))
    story.append(Paragraph("This is a deterministic readiness estimate based on the supplied CV text and job description. It is not a vendor-specific ATS score and does not guarantee ranking by a particular recruitment system.", styles["Small"]))
    story.append(Paragraph("Matched keywords", styles["H3"]))
    story.append(Paragraph(_safe(ats.get("matched_keywords", [])), styles["Body"]))
    story.append(Paragraph("Missing / not detected keywords", styles["H3"]))
    story.append(Paragraph(_safe(ats.get("missing_keywords", [])), styles["Body"]))
    story.append(Paragraph("ATS strengths", styles["H3"]))
    story.append(Paragraph(_safe(ats.get("strengths", [])), styles["Body"]))
    story.append(Paragraph("ATS improvement recommendations", styles["H3"]))
    story.append(Paragraph(_safe(ats.get("improvements", [])), styles["Body"]))

    story += _section_title("4. Evidence grounding", styles)
    story.append(_kv_table([
        ("Candidate facts", len(ev.get("candidate_facts", []))),
        ("JD requirements", len(ev.get("jd_requirements", []))),
        ("Matched terms", len(ev.get("matches", []))),
        ("Gaps / unknowns", len(ev.get("gaps", []))),
        ("Grounding rule", ev.get("grounding_rule", "Candidate evidence is kept separate from JD and research context.")),
    ], styles))
    if ev.get("candidate_facts"):
        story.append(Paragraph("Candidate facts extracted from CV / Resume", styles["H3"]))
        story.append(Paragraph(_safe(ev.get("candidate_facts", [])), styles["Body"]))
    if ev.get("jd_requirements"):
        story.append(Paragraph("Job description requirements extracted", styles["H3"]))
        story.append(Paragraph(_safe(ev.get("jd_requirements", [])), styles["Body"]))
    if ev.get("matches"):
        story.append(Paragraph("Matched terms", styles["H3"]))
        story.append(Paragraph(_safe(ev.get("matches", [])), styles["Body"]))
    if ev.get("gaps"):
        story.append(Paragraph("JD gaps / unknowns", styles["H3"]))
        story.append(Paragraph(_safe(ev.get("gaps", [])), styles["Body"]))

    if research:
        story += _section_title("5. Company / role analysis", styles)
        story.append(Paragraph(_safe(research), styles["Body"]))
        story.append(Paragraph("Analysis is based on supplied role/JD/company context and should not be treated as independently verified current company facts unless separately sourced.", styles["Small"]))

    story += _section_title("6. Performance summary", styles)
    story.append(_score_table(scores, styles) if scores else Paragraph("No scored interview turns were completed.", styles["Body"]))
    if turns:
        category_scores = {}
        for turn in turns:
            category = turn.get("category", "General")
            category_scores.setdefault(category, []).append(turn.get("feedback", {}).get("overall", 0))
        story.append(Paragraph("Category readiness", styles["H3"]))
        story.append(_kv_table([(k, f"{round(sum(v)/len(v))}/100 across {len(v)} question(s)") for k, v in category_scores.items()], styles))

    story.append(PageBreak())
    story += _section_title("7. Question-by-question coaching record", styles)
    for i, turn in enumerate(turns, 1):
        fb = turn.get("feedback", {})
        block = [Paragraph(f"Question {i} · {_safe(turn.get('category', 'General'))}", styles["H2"])]
        block.append(_kv_table([
            ("Question", turn.get("question", "")),
            ("Answer mode", turn.get("answer_mode", "text")),
            ("Elapsed time", f"{turn.get('elapsed_seconds', 0)} seconds"),
        ], styles))
        block += [Spacer(1, 6), Paragraph("Candidate answer", styles["H3"]), Paragraph(_safe(turn.get("answer", "")), styles["Body"])]
        block += [Paragraph("Performance scores", styles["H3"]), _score_table(fb.get("scores", {}), styles)]
        block += [
            Paragraph(f"Overall: {fb.get('overall', 0)}/100", styles["Label"]),
            Paragraph("Strengths", styles["H3"]), Paragraph(_safe(fb.get("strengths", [])), styles["Body"]),
            Paragraph("Missing points / improvement areas", styles["H3"]), Paragraph(_safe(fb.get("missing_points", [])), styles["Body"]),
            Paragraph("Verification notes", styles["H3"]), Paragraph(_safe(fb.get("verification_notes", [])), styles["Body"]),
            Paragraph("Suggested better answer", styles["H3"]), Paragraph(_safe(fb.get("practice_answer", "")), styles["Body"]),
            Paragraph("Next improvement", styles["H3"]), Paragraph(_safe(fb.get("next_improvement", "")), styles["Body"]),
            Paragraph("Speech analytics", styles["H3"]), Paragraph(_safe(fb.get("speech_metrics", {})), styles["Body"]),
            Paragraph("Presentation cues", styles["H3"]), Paragraph(_safe(fb.get("presentation_cues", {})), styles["Body"]),
        ]
        story.append(KeepTogether(block))
        story.append(Spacer(1, 8))

    story += _section_title("8. Final recommendations", styles)
    if turns:
        strengths = []
        improvements = []
        for turn in turns:
            fb = turn.get("feedback", {})
            strengths.extend(fb.get("strengths", []) or [])
            improvements.extend(fb.get("missing_points", []) or [])
            if fb.get("next_improvement"):
                improvements.append(fb["next_improvement"])
        unique_strengths = list(dict.fromkeys(strengths))[:12]
        unique_improvements = list(dict.fromkeys(improvements))[:12]
        story.append(Paragraph("Observed strengths", styles["H3"]))
        story.append(Paragraph(_safe(unique_strengths), styles["Body"]))
        story.append(Paragraph("Priority improvement actions", styles["H3"]))
        story.append(Paragraph(_safe(unique_improvements), styles["Body"]))
        story.append(Paragraph("Recommended practice cycle", styles["H3"]))
        story.append(Paragraph("Review the lowest-scoring dimensions, revise the suggested better answers using only truthful experience, then repeat the weakest interview categories in a fresh session.", styles["Body"]))
    else:
        story.append(Paragraph("Complete an interview session to generate personalized performance recommendations.", styles["Body"]))

    story += _section_title("9. Report coverage & methodology", styles)
    story.append(Paragraph("This report is generated from the configuration and outputs available in the completed Intervia session. It includes the session design, candidate/JD evidence signals, ATS-readiness estimate, performance scores, coaching feedback, suggested answers, speech/presentation analytics when available, and recommendations.", styles["Body"]))
    story.append(Paragraph("The ATS score is a readiness estimate, not a guarantee from any specific applicant-tracking-system vendor. AI coaching is grounded in the supplied CV/JD/session evidence and should be reviewed for factual accuracy before reuse.", styles["Small"]))

    def footer(canvas, doc_obj):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D4DCE9"))
        canvas.line(17 * mm, 12 * mm, 193 * mm, 12 * mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#71809A"))
        canvas.drawString(17 * mm, 7.5 * mm, "Intervia Interview Intelligence · Confidential candidate practice report")
        canvas.drawRightString(193 * mm, 7.5 * mm, f"Page {doc_obj.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
