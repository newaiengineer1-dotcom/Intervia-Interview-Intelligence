import re
from typing import Any


class EvidenceAgent:
    """Builds deterministic, source-separated CV/JD evidence and ATS-readiness signals."""

    STOP = {
        "and", "the", "with", "for", "from", "this", "that", "have", "will", "your", "you",
        "are", "our", "their", "into", "using", "years", "role", "work", "team", "job", "about",
        "preferred", "required", "requirements", "responsibilities", "experience", "candidate",
    }

    COMMON_HEADINGS = [
        "summary", "profile", "professional summary", "experience", "work experience",
        "employment", "education", "skills", "technical skills", "certifications",
        "projects", "achievements", "awards", "languages", "publications",
    ]

    def _sentences(self, text: str) -> list[str]:
        return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text or "") if len(s.strip()) > 20]

    def _terms(self, text: str) -> set[str]:
        return {
            x.lower()
            for x in re.findall(r"[A-Za-z][A-Za-z0-9+#.-]{2,}", text or "")
            if x.lower() not in self.STOP
        }

    def _ats_readiness(self, cv_text: str, jd_text: str, cv_filename: str = "") -> dict[str, Any]:
        text = cv_text or ""
        lower = text.lower()
        cv_terms = self._terms(text)
        jd_terms = self._terms(jd_text)
        required_terms = sorted(jd_terms - self.STOP)
        matched = sorted(cv_terms & jd_terms)
        missing = sorted(jd_terms - cv_terms)

        keyword_score = round(100 * len(matched) / max(1, len(required_terms)))
        keyword_score = min(100, keyword_score)

        heading_hits = [h for h in self.COMMON_HEADINGS if re.search(rf"\b{re.escape(h)}\b", lower)]
        heading_score = min(100, round(len(heading_hits) / 5 * 100))

        contact_signals = {
            "email": bool(re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)),
            "phone": bool(re.search(r"(?:\+?\d[\d\s().-]{7,}\d)", text)),
            "linkedin": "linkedin.com" in lower,
        }
        contact_score = round(sum(contact_signals.values()) / 3 * 100)

        bullet_lines = [line.strip() for line in text.splitlines() if re.match(r"^[•●▪◦\-*]\s+", line.strip())]
        bullet_ratio = len(bullet_lines) / max(1, len([x for x in text.splitlines() if x.strip()]))
        bullet_score = min(100, round(bullet_ratio * 400))

        quantified = len(re.findall(r"\b\d+(?:\.\d+)?\s*(?:%|years?|months?|MW|GW|MWh|GWh|kW|kWh|million|billion|people|projects?)\b", lower))
        quantified_score = min(100, quantified * 10)

        page_like_words = len(re.findall(r"\b\w+\b", text))
        length_score = 100 if 300 <= page_like_words <= 1800 else (75 if 180 <= page_like_words <= 2500 else 50)

        score = round(
            keyword_score * 0.45
            + heading_score * 0.15
            + contact_score * 0.10
            + bullet_score * 0.10
            + quantified_score * 0.10
            + length_score * 0.10
        )

        strengths = []
        improvements = []
        if keyword_score >= 70:
            strengths.append("Strong alignment between CV terminology and the supplied job description.")
        else:
            improvements.append("Add truthful, job-relevant keywords from the JD where they accurately describe your experience.")
        if len(heading_hits) >= 4:
            strengths.append("Clear conventional resume section structure detected.")
        else:
            improvements.append("Use conventional ATS-readable headings such as Summary, Experience, Education and Skills.")
        if contact_score >= 67:
            strengths.append("Basic contact information is detectable in extracted CV text.")
        else:
            improvements.append("Ensure email and phone details are present as selectable text near the top of the CV.")
        if quantified:
            strengths.append("Quantified achievements or project measures were detected.")
        else:
            improvements.append("Add measurable outcomes to relevant achievements where truthful.")
        if not bullet_lines:
            improvements.append("Use concise bullet points for responsibilities and achievements instead of dense paragraphs.")

        return {
            "score": score,
            "label": "ATS-ready signals detected" if score >= 75 else "ATS optimization recommended",
            "method": "Deterministic estimate using extracted CV text, JD keyword alignment and common ATS-readable structure signals.",
            "not_a_vendor_score": True,
            "keyword_match_score": keyword_score,
            "matched_keywords": matched[:80],
            "missing_keywords": missing[:80],
            "detected_headings": heading_hits,
            "contact_signals": contact_signals,
            "bullet_points_detected": len(bullet_lines),
            "quantified_achievement_signals": quantified,
            "estimated_word_count": page_like_words,
            "cv_filename": cv_filename or "Not provided",
            "strengths": strengths,
            "improvements": improvements,
        }

    def build(
        self,
        cv_text: str,
        jd_text: str,
        target_role: str,
        industry: str = "Not specified",
        cv_filename: str = "",
    ) -> dict[str, Any]:
        cv_sentences = self._sentences(cv_text)
        jd_sentences = self._sentences(jd_text)
        cv_terms = self._terms(cv_text)
        jd_terms = self._terms(jd_text)
        return {
            "target_role": target_role,
            "industry": industry,
            "candidate_facts": cv_sentences[:80],
            "jd_requirements": jd_sentences[:80],
            "candidate_terms": sorted(cv_terms)[:250],
            "jd_terms": sorted(jd_terms)[:250],
            "matches": sorted(cv_terms & jd_terms)[:80],
            "gaps": sorted(jd_terms - cv_terms)[:80],
            "ats_readiness": self._ats_readiness(cv_text, jd_text, cv_filename=cv_filename),
            "grounding_rule": "Candidate facts come only from the CV. JD requirements and research are never candidate facts.",
        }
