from agents import EvidenceAgent, StrategyAgent
from utils import average_scores, safe_clamp
from report import build_pdf_report, build_markdown_report


def test_evidence_separation():
    e = EvidenceAgent().build("I designed solar PV layouts.", "Experience with BESS is preferred.", "Engineer", "Energy")
    assert any("solar" in x.lower() for x in e["candidate_facts"])
    assert any("bess" in x.lower() for x in e["jd_requirements"])


def test_score_average():
    a = average_scores([{"technical": 80, "relevance": 60, "evidence": 70, "communication": 90, "structure": 80, "confidence": 70}])
    assert a["technical"] == 80


def test_clamp():
    assert len(safe_clamp("x" * 100, 10)) <= 50


def test_strategy_with_categories_and_time():
    plan = StrategyAgent().plan([], "Mixed", "30 Minutes", {}, categories=["Behavioral & Situational 🎭"], remaining_minutes=29.5, target_questions=8)
    assert plan["focus"]
    assert plan["categories"] == ["Behavioral & Situational 🎭"]
    assert plan["target_questions"] == 8


def test_ats_readiness_signals():
    e = EvidenceAgent().build(
        "John Doe\nEmail john@example.com\nExperience\nSkills\nPython Streamlit",
        "Experience with Python and Streamlit",
        "AI Engineer",
        "Energy",
        cv_filename="resume.pdf",
    )
    assert 0 <= e["ats_readiness"]["score"] <= 100
    assert e["ats_readiness"]["cv_filename"] == "resume.pdf"
    assert e["ats_readiness"]["keyword_match_score"] >= 50


def test_complete_report_builders():
    evidence = EvidenceAgent().build("Email test@example.com\nExperience in Python.", "Python required.", "AI Engineer")
    turns = [{
        "question": "Tell me about Python.",
        "category": "Technical & Role-Specific 💻",
        "answer": "I built Python applications.",
        "answer_mode": "text",
        "elapsed_seconds": 20,
        "feedback": {
            "scores": {"technical": 80, "relevance": 80, "evidence": 80, "communication": 80, "structure": 80, "confidence": 80},
            "overall": 80,
            "strengths": ["Clear example"],
            "missing_points": ["Add measurable impact"],
            "verification_notes": ["Grounded in supplied CV"],
            "practice_answer": "A stronger answer would use a concise structure.",
            "next_improvement": "Add measurable impact.",
        },
    }]
    md = build_markdown_report("AI Engineer", "Not specified", "Mixed", turns, evidence, company="Example", categories=["Technical & Role-Specific 💻"])
    pdf = build_pdf_report("AI Engineer", "Not specified", "Mixed", turns, evidence, company="Example", categories=["Technical & Role-Specific 💻"])
    assert "ATS-readiness estimate" in md
    assert pdf.startswith(b"%PDF")
