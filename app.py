import json
import os
import re
import time
import uuid
from collections import defaultdict
from datetime import datetime
from html import escape

import streamlit as st
import streamlit.components.v1 as components

from agents import (
    CoachAgent,
    EvidenceAgent,
    GroqGateway,
    InterviewerAgent,
    ResearchAgent,
    StrategyAgent,
)
from db import init_db, save_session
from report import build_markdown_report, build_pdf_report
from utils import extract_uploaded_text, safe_clamp

st.set_page_config(
    page_title="Intervia — Interview Intelligence",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

CATEGORIES = [
    "Behavioral & Situational 🎭",
    "Technical & Role-Specific 💻",
    "HR & Screening Basics 🤝",
    "Leadership & Management 👔",
    "Case & Analytical Interviews 📊",
    "Competency & Skill-Based 🧠",
    "Reverse Interviewing — Questions for the Employer 🔍",
]
DURATIONS = {"30 Minutes": 30, "60 Minutes": 60, "120 Minutes": 120, "180 Minutes": 180}
TARGET_QUESTIONS = {30: 8, 60: 15, 120: 28, 180: 40}

st.markdown(
    """
    <style>
    :root { --bg:#07101f; --panel:#0d1830; --line:#203052; --muted:#91a2c0; --accent:#7c5cff; --good:#9df2c1; }
    .stApp { background: radial-gradient(circle at 70% 0%, #17204a 0%, var(--bg) 45%); }
    [data-testid="stSidebar"] { background:#081225; border-right:1px solid var(--line); }
    .hero { padding:26px 30px; border:1px solid var(--line); border-radius:22px; background:linear-gradient(135deg,rgba(124,92,255,.20),rgba(13,24,48,.92)); box-shadow:0 18px 50px rgba(0,0,0,.25); }
    .eyebrow { color:#a99bff; font-size:12px; font-weight:800; letter-spacing:.14em; text-transform:uppercase; }
    .hero h1 { margin:6px 0; font-size:38px; }
    .muted { color:var(--muted); }
    .card { padding:18px; border:1px solid var(--line); border-radius:18px; background:rgba(13,24,48,.78); margin-bottom:12px; }
    .agent { display:flex; justify-content:space-between; padding:10px 0; border-bottom:1px solid #182641; }
    .agent:last-child { border-bottom:0; }
    .status { color:var(--good); font-size:12px; font-weight:700; }
    .question { font-size:25px; line-height:1.35; font-weight:700; padding:22px; border-left:4px solid var(--accent); background:#0a1428; border-radius:14px; }
    .category { display:inline-block; padding:6px 10px; border:1px solid #33466f; border-radius:999px; color:#c9d4ea; font-size:12px; background:#111d38; }
    .timer { font-size:20px; font-weight:800; color:#e8edff; }
    .small { font-size:12px; color:var(--muted); }
    .mode-box { padding:12px; border:1px solid #263a61; border-radius:14px; background:#0b152a; }
    .cockpit { padding:18px; border:1px solid var(--line); border-radius:18px; background:rgba(13,24,48,.78); }
    .cockpit-title { font-size:13px; font-weight:800; letter-spacing:.08em; text-transform:uppercase; color:#a99bff; margin-bottom:10px; }
    .agent-name { color:#d8e2f4; font-weight:700; }
    .status.ready { color:#9df2c1; }
    .status.active { color:#9ad7ff; }
    .status.waiting { color:#ffd58a; }
    .status.optional { color:#91a2c0; }
    .footer { margin-top:28px; padding:20px 0 8px; border-top:1px solid var(--line); color:#91a2c0; }
    </style>
    """,
    unsafe_allow_html=True,
)


def render_speech_controls(text: str, key: str, title: str, language: str, autoplay: bool = False):
    """Browser-native question playback. It automatically ends/cancels when the utterance ends."""
    payload = json.dumps(text or "", ensure_ascii=False)
    lang_payload = json.dumps(language or "en-US")
    safe_key = re.sub(r"[^A-Za-z0-9_]", "_", key)
    auto_delay = 350 if autoplay else 999999
    components.html(
        f"""
        <div style="font-family:Arial,sans-serif;padding:8px 0;">
          <div style="color:#91a2c0;font-size:12px;font-weight:700;margin-bottom:7px;">🔊 {escape(title)}</div>
          <button id="play_{safe_key}" style="border:1px solid #33466f;background:#151f3b;color:#fff;border-radius:10px;padding:9px 14px;cursor:pointer;margin-right:6px;">▶ Play</button>
          <button id="stop_{safe_key}" style="border:1px solid #33466f;background:#0d1830;color:#c9d4ea;border-radius:10px;padding:9px 14px;cursor:pointer;">■ Stop</button>
          <span id="status_{safe_key}" style="color:#91a2c0;font-size:12px;margin-left:8px;"></span>
        </div>
        <script>
        const text_{safe_key} = {payload};
        const lang_{safe_key} = {lang_payload};
        const play_{safe_key} = document.getElementById('play_{safe_key}');
        const stop_{safe_key} = document.getElementById('stop_{safe_key}');
        const status_{safe_key} = document.getElementById('status_{safe_key}');
        let utterance_{safe_key} = null;
        function stopSpeech_{safe_key}(label='Stopped') {{
          if ('speechSynthesis' in window) window.speechSynthesis.cancel();
          utterance_{safe_key} = null;
          status_{safe_key}.textContent = label;
        }}
        function speak_{safe_key}() {{
          if (!('speechSynthesis' in window)) {{ status_{safe_key}.textContent='Browser speech is not supported.'; return; }}
          stopSpeech_{safe_key}('');
          utterance_{safe_key} = new SpeechSynthesisUtterance(text_{safe_key});
          utterance_{safe_key}.lang = lang_{safe_key};
          utterance_{safe_key}.rate = 0.96;
          utterance_{safe_key}.pitch = 1.0;
          utterance_{safe_key}.onstart = () => status_{safe_key}.textContent='Speaking…';
          utterance_{safe_key}.onend = () => {{ utterance_{safe_key}=null; status_{safe_key}.textContent='Question finished'; }};
          utterance_{safe_key}.onerror = () => {{ utterance_{safe_key}=null; status_{safe_key}.textContent='Speech playback failed'; }};
          window.speechSynthesis.speak(utterance_{safe_key});
        }}
        play_{safe_key}.onclick = speak_{safe_key};
        stop_{safe_key}.onclick = () => stopSpeech_{safe_key}();
        window.addEventListener('beforeunload', () => stopSpeech_{safe_key}(''));
        setTimeout(() => {{ if ({str(autoplay).lower()}) speak_{safe_key}(); }}, {auto_delay});
        </script>
        """,
        height=78,
        scrolling=False,
    )


def render_timer(started_at: float, duration_minutes: int):
    remaining = max(0, int(duration_minutes * 60 - (time.time() - started_at)))
    components.html(
        f"""
        <div style="padding:8px 0;text-align:right;font-family:Arial,sans-serif;">
          <span style="color:#91a2c0;font-size:12px;">SESSION TIME REMAINING</span>
          <div id="timer" style="font-size:24px;font-weight:800;color:#e8edff;">--:--</div>
        </div>
        <script>
        let remaining = {remaining};
        const el = document.getElementById('timer');
        function tick() {{
          const m = Math.floor(Math.max(0, remaining) / 60);
          const s = Math.max(0, remaining) % 60;
          el.textContent = String(m).padStart(2,'0') + ':' + String(s).padStart(2,'0');
          if (remaining <= 0) el.textContent = '00:00 — TIME';
          remaining -= 1;
        }}
        tick(); setInterval(tick, 1000);
        </script>
        """,
        height=70,
        scrolling=False,
    )


def duration_state(started_at: float, duration_minutes: int):
    elapsed = max(0.0, time.time() - started_at)
    remaining = max(0.0, duration_minutes * 60 - elapsed)
    return elapsed, remaining, remaining <= 0


def question_target(duration_minutes: int, elapsed_seconds: float, completed: int) -> int:
    base = TARGET_QUESTIONS[duration_minutes]
    if elapsed_seconds <= 0:
        return base
    # Faster answers allow more questions; slower answers naturally reduce the target.
    avg_turn = elapsed_seconds / max(1, completed)
    projected = int((duration_minutes * 60) / max(avg_turn, 120))
    return max(3, min(base * 2, max(base, projected)))


def speech_metrics(text: str, estimated_seconds: float | None = None):
    words = re.findall(r"\b[\w']+\b", text or "")
    filler_list = ["um", "uh", "erm", "like", "you know", "basically", "actually", "sort of", "kind of"]
    lowered = (text or "").lower()
    fillers = sum(len(re.findall(r"\b" + re.escape(f) + r"\b", lowered)) for f in filler_list)
    words_count = len(words)
    seconds = estimated_seconds or max(10, words_count / 2.3) if words_count else 0
    wpm = round(words_count / (seconds / 60), 1) if seconds else 0
    return {"words": words_count, "filler_words": fillers, "estimated_seconds": round(seconds, 1), "words_per_minute": wpm}


init_db()

for key, default in {
    "session_id": str(uuid.uuid4()),
    "evidence": None,
    "research": None,
    "turns": [],
    "question": None,
    "started": False,
    "started_at": None,
    "session_duration": 30,
    "question_mode": "Text Questions",
    "answer_mode": "⌨️ Type Answers",
    "categories": CATEGORIES[:],
    "company": "",
    "company_track": "",
    "camera_enabled": False,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

def configured_secret(name: str, default: str = "") -> str:
    """Read Streamlit Cloud secrets first, then local environment variables."""
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    return str(value or os.getenv(name, default) or "").strip()


with st.sidebar:
    st.markdown("## 🎯 Intervia")
    st.caption("Evidence-Grounded Interview Intelligence")
    api_key = st.text_input("Groq API key", type="password", value=configured_secret("GROQ_API_KEY"))
    target_role = st.text_input("Target role", value="Senior Renewable Energy Engineer", disabled=st.session_state.started)
    company = st.text_input("Company / employer (optional)", value=st.session_state.company, disabled=st.session_state.started)

    st.markdown("### Interview Setup")
    setup_tab, = st.tabs(["Interview categories and Interview mode"])
    with setup_tab:
        mode = st.selectbox(
            "Interview mode",
            ["Mixed", "Technical", "Behavioral", "Case / Situational", "HR / Screening", "Leadership"],
            disabled=st.session_state.started,
            help="Controls the interviewer's primary question style. Categories below provide the specific areas to test."
        )
        categories = st.multiselect(
            "Interview categories",
            CATEGORIES,
            default=st.session_state.categories,
            disabled=st.session_state.started,
            help="Select one or more categories. The adaptive strategy agent balances them as the session progresses."
        )

    duration_label = st.selectbox("Practice session duration", list(DURATIONS.keys()), index=0 if st.session_state.session_duration == 30 else list(DURATIONS.values()).index(st.session_state.session_duration), disabled=st.session_state.started)
    duration_minutes = DURATIONS[duration_label]

    question_mode = st.radio(
        "Question format",
        ["Text Questions", "Audio Questions"],
        index=0 if st.session_state.question_mode == "Text Questions" else 1,
        disabled=st.session_state.started,
        horizontal=True,
        help="Text Questions shows the question on screen. Audio Questions also reads it aloud using the browser's built-in speech synthesis."
    )
    answer_mode = st.radio(
        "Answer format",
        ["⌨️ Type Answers", "🎙️ Speak Answers"],
        index=0 if st.session_state.answer_mode.startswith("⌨") else 1,
        disabled=st.session_state.started,
        horizontal=True,
        help="Type Answers uses a text box. Speak Answers records your microphone response and sends it to Groq Whisper for transcription."
    )
    use_research = st.checkbox("Company / role web research", value=False, disabled=st.session_state.started)
    camera_enabled = st.checkbox("Camera presentation snapshot", value=st.session_state.camera_enabled, disabled=st.session_state.started, help="Optional snapshot analysis of observable framing/posture cues. It does not infer emotions or personality.")
    speech_language = st.selectbox("Question voice", ["English (US)", "English (UK)"], index=0, disabled=st.session_state.started)
    speech_locale = "en-US" if speech_language == "English (US)" else "en-GB"
    answer_length = st.selectbox("AI practice-answer length", ["Short", "Standard", "Detailed"], disabled=st.session_state.started)
    st.divider()
    st.caption("Tip: for a realistic session, choose the modalities once here. Intervia keeps them fixed for the complete session.")
    st.caption("Production: keep secrets in Streamlit Secrets, not GitHub.")

    if not st.session_state.started:
        st.session_state.session_duration = duration_minutes
        st.session_state.question_mode = question_mode
        st.session_state.answer_mode = answer_mode
        st.session_state.categories = categories or CATEGORIES[:]
        st.session_state.company = company
        st.session_state.company_track = ""
        st.session_state.camera_enabled = camera_enabled

st.markdown(
    """
    <div class="hero">
      <div class="eyebrow">Adaptive Interview Intelligence</div>
      <h1>Practice against the job — with text or voice, on your schedule.</h1>
      <div class="muted">Choose question and answer modalities once, select a session length and interview categories, then Intervia automatically adapts the Q&A pace to the remaining time.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

if not st.session_state.started:
    st.info("Before starting: configure **Interview categories and Interview mode**, choose **Text or Audio Questions**, **Type or Speak Answers**, and select your practice session duration.")

left, right = st.columns([1.35, 1])
with left:
    st.markdown("### 1. Build the evidence pack")
    cv_file = st.file_uploader("CV / Resume", type=["pdf", "docx", "txt"], key="cv")
    jd_file = st.file_uploader("Job Description", type=["pdf", "docx", "txt"], key="jd")
    jd_text = st.text_area("Or paste the job description", height=150, placeholder="Paste the JD here if you do not have a file.")
    company_track = st.text_area("Optional company-specific question context", height=90, placeholder="Paste publicly sourced interview themes/questions or a company-specific question bank here. Keep it factual and non-confidential.", disabled=st.session_state.started)

    if st.button("Build evidence pack", type="primary", use_container_width=True, disabled=st.session_state.started):
        if not api_key:
            st.error("Enter a Groq API key first.")
        elif not cv_file:
            st.error("Upload a CV / Resume.")
        elif not (jd_file or jd_text.strip()):
            st.error("Upload or paste the Job Description.")
        else:
            st.session_state.company_track = company_track
            cv_text = extract_uploaded_text(cv_file)
            final_jd = extract_uploaded_text(jd_file) if jd_file else jd_text
            st.session_state.evidence = EvidenceAgent().build(
                cv_text=safe_clamp(cv_text, 14000),
                jd_text=safe_clamp(final_jd, 12000),
                target_role=target_role,
                industry="Not specified — grounded in CV/JD and role context",
            )
            st.session_state.research = None
            st.session_state.turns = []
            st.session_state.question = None
            st.session_state.started = False
            st.session_state.started_at = None
            # Optional company research is intentionally disabled in this stable build.
            # This keeps the evidence-pack path independent of the research agent.
            st.session_state.research = None
            st.success("Evidence pack created. Candidate evidence, JD requirements and external research remain separate.")

with right:
    st.markdown(
        """
        <div class="cockpit">
            <div class="cockpit-title">Agent Cockpit</div>

            <div class="agent">
                <span class="agent-name">Evidence Intelligence</span>
                <span class="status {evidence_status_class}">{evidence_status}</span>
            </div>

            <div class="agent">
                <span class="agent-name">Career &amp; Market Research</span>
                <span class="status {research_status_class}">{research_status}</span>
            </div>

            <div class="agent">
                <span class="agent-name">Interview Strategy</span>
                <span class="status {strategy_status_class}">{strategy_status}</span>
            </div>

            <div class="agent">
                <span class="agent-name">AI Interviewer</span>
                <span class="status {interviewer_status_class}">{interviewer_status}</span>
            </div>

            <div class="agent">
                <span class="agent-name">Performance Coach</span>
                <span class="status ready">READY</span>
            </div>

            <div style="height:18px;"></div>

            <div class="cockpit-title">Session Design</div>

            <b>Interview Mode</b><br>
            <span class="small">{mode_value}</span>

            <br><br>

            <b>Interview Categories</b><br>
            <span class="small">{category_count} selected</span>

            <br><br>

            <b>Duration</b><br>
            <span class="small">{duration_value}</span>

            <br><br>

            <b>Question Format</b><br>
            <span class="small">{question_format}</span>

            <br><br>

            <b>Answer Format</b><br>
            <span class="small">{answer_format}</span>
        </div>
        """.format(
            evidence_status_class="ready" if st.session_state.evidence else "waiting",
            evidence_status="READY" if st.session_state.evidence else "WAITING",
            research_status_class=("ready" if st.session_state.research else ("optional" if not use_research else "waiting")),
            research_status=("READY" if st.session_state.research else ("OPTIONAL" if not use_research else "WAITING")),
            strategy_status_class="active" if st.session_state.started else "ready",
            strategy_status="ACTIVE" if st.session_state.started else "READY",
            interviewer_status_class="active" if st.session_state.question else "ready",
            interviewer_status="ACTIVE" if st.session_state.question else "READY",
            mode_value=escape(mode),
            category_count=len(categories or CATEGORIES),
            duration_value=escape(duration_label),
            question_format=escape(question_mode),
            answer_format=escape(answer_mode),
        ),
        unsafe_allow_html=True,
    )

if st.session_state.evidence:
    ev = st.session_state.evidence
    st.markdown("### Evidence snapshot")
    c1, c2, c3 = st.columns(3)
    c1.metric("Candidate facts", len(ev.get("candidate_facts", [])))
    c2.metric("JD requirements", len(ev.get("jd_requirements", [])))
    c3.metric("Skill gaps", len(ev.get("gaps", [])))
    with st.expander("View grounding data"):
        st.write("**Candidate evidence**", ev.get("candidate_facts", []))
        st.write("**JD requirements**", ev.get("jd_requirements", []))
        st.write("**Matched skills**", ev.get("matches", []))
        st.write("**Gaps / unknowns**", ev.get("gaps", []))

    if not st.session_state.started:
        if st.button("🚀 Start complete adaptive interview", type="primary", use_container_width=True):
            if not categories:
                st.error("Select at least one interview category.")
            elif not api_key:
                st.error("Groq API key is required.")
            else:
                gateway = GroqGateway(api_key)
                strategy = StrategyAgent()
                interviewer = InterviewerAgent(gateway)
                now = time.time()
                st.session_state.started_at = now
                elapsed, remaining, _ = duration_state(now, duration_minutes)
                target_count = question_target(duration_minutes, elapsed, 0)
                plan = strategy.plan([], mode, duration_label, ev, categories=categories, remaining_minutes=round(remaining/60, 1), target_questions=target_count)
                try:
                    q = interviewer.ask_question(
                        ev,
                        st.session_state.research,
                        plan,
                        target_role,
                        "Not specified — grounded in CV/JD and role context",
                        mode,
                        company=company,
                    )
                except Exception as exc:
                    st.error("❌ The adaptive interview could not generate Question 1.")
                    st.code(str(exc), language="text")
                    st.info(
                        "The app now keeps the session stopped instead of crashing. "
                        "If this is a 403, enable at least one accessible Groq model in your Groq project. "
                        "If it is a 429, wait for the rate-limit window or use a shorter session."
                    )
                else:
                    st.session_state.question = q
                    st.session_state.started = True
                    st.session_state.session_duration = duration_minutes
                    st.session_state.question_mode = question_mode
                    st.session_state.answer_mode = answer_mode
                    st.session_state.categories = categories
                    st.session_state.company = company
                    st.session_state.camera_enabled = camera_enabled
                    st.rerun()

if st.session_state.started and st.session_state.question:
    st.markdown("---")
    st.markdown("### 2. Live interview studio")
    elapsed, remaining, expired = duration_state(st.session_state.started_at, st.session_state.session_duration)
    turn_no = len(st.session_state.turns) + 1
    target_count = question_target(st.session_state.session_duration, elapsed, len(st.session_state.turns))
    progress = min(1.0, len(st.session_state.turns) / max(1, target_count))
    top1, top2, top3 = st.columns([1.6, 1, 1])
    with top1:
        st.progress(progress, text=f"Question {turn_no} · adaptive target {target_count}")
    with top2:
        st.metric("Elapsed", f"{int(elapsed//60):02d}:{int(elapsed%60):02d}")
    with top3:
        render_timer(st.session_state.started_at, st.session_state.session_duration)

    if expired:
        st.warning("⏱️ Your selected practice session time has ended. Your report is ready below.")
        st.session_state.question = None
    else:
        q_obj = st.session_state.question if isinstance(st.session_state.question, dict) else {"category": "General", "question": str(st.session_state.question)}
        question_text = q_obj["question"].strip()
        category = q_obj.get("category", "General")
        st.markdown(f"<span class='category'>{escape(category)}</span>", unsafe_allow_html=True)
        st.markdown(f'<div class="question">{escape(question_text)}</div>', unsafe_allow_html=True)
        render_speech_controls(
            question_text,
            f"question_{turn_no}",
            "Generated interview question",
            speech_locale,
            autoplay=(st.session_state.question_mode == "Audio Questions"),
        )
        if st.session_state.question_mode == "Audio Questions":
            st.caption("Audio mode: the question is spoken automatically when available; playback stops automatically when the question finishes. Browser autoplay restrictions may require pressing Play once.")

        st.markdown("#### Your answer")
        st.caption(f"Answer mode locked for this session: **{st.session_state.answer_mode}**")
        answer = ""
        voice_transcript = ""
        audio = None
        if st.session_state.answer_mode == "⌨️ Type Answers":
            answer = st.text_area("Type your answer", key=f"answer_input_{turn_no}", height=190, placeholder="Answer as if you were in the real interview.")
        else:
            audio = st.audio_input("🎙️ Record your answer", sample_rate=16000, key=f"answer_audio_{turn_no}")
            st.caption("Speak naturally. Submit the recording when you finish; Whisper will transcribe it before coaching.")

        camera = None
        if st.session_state.camera_enabled:
            camera = st.camera_input("Optional camera snapshot for presentation-cue feedback", key=f"camera_{turn_no}")
            st.caption("MVP camera analysis is a snapshot, not continuous video. It evaluates only observable framing/posture/camera cues; it does not infer emotions, personality, health or mental state.")

        submit = st.button("Submit answer & get coaching", type="primary", use_container_width=True)
        if submit:
            elapsed_now, remaining_now, expired_now = duration_state(st.session_state.started_at, st.session_state.session_duration)
            if expired_now:
                st.warning("The session time has ended. Finish with the report below.")
                st.session_state.question = None
                st.rerun()
            elif not api_key:
                st.error("Groq API key is required.")
            else:
                gateway = GroqGateway(api_key)
                if st.session_state.answer_mode == "🎙️ Speak Answers" and audio is not None:
                    try:
                        voice_transcript = gateway.transcribe(audio.getvalue(), getattr(audio, "name", "answer.wav")).strip()
                        answer = voice_transcript
                    except Exception as exc:
                        st.error(f"Voice transcription failed. Please record again or use text. {exc}")
                else:
                    answer = (answer or "").strip()

                if not answer:
                    st.error("Provide an answer before submitting.")
                else:
                    coach = CoachAgent(gateway)
                    result = coach.evaluate(
                        question=question_text,
                        answer=answer,
                        evidence=st.session_state.evidence,
                        target_role=target_role,
                        mode=mode,
                        answer_length=answer_length,
                    )
                    metrics = speech_metrics(answer) if voice_transcript else {"words": len(answer.split()), "filler_words": None, "estimated_seconds": None, "words_per_minute": None}
                    camera_feedback = None
                    if camera is not None:
                        try:
                            camera_feedback = gateway.analyze_camera(camera.getvalue(), getattr(camera, "type", "image/jpeg"))
                        except Exception as exc:
                            camera_feedback = {"available": False, "error": str(exc)}
                    result["speech_metrics"] = metrics
                    result["presentation_cues"] = camera_feedback
                    st.session_state.turns.append({
                        "question": question_text,
                        "category": category,
                        "answer": answer,
                        "answer_mode": "voice" if voice_transcript else "text",
                        "voice_transcript": voice_transcript,
                        "feedback": result,
                        "timestamp": datetime.utcnow().isoformat(timespec="seconds"),
                        "elapsed_seconds": round(elapsed_now, 1),
                    })
                    save_session(st.session_state.session_id, target_role, "Not specified — grounded in CV/JD and role context", st.session_state.turns)

                    # Generate next question only if time remains.
                    elapsed_after, remaining_after, expired_after = duration_state(st.session_state.started_at, st.session_state.session_duration)
                    if expired_after:
                        st.session_state.question = None
                    else:
                        strategy = StrategyAgent()
                        target_count = question_target(st.session_state.session_duration, elapsed_after, len(st.session_state.turns))
                        plan = strategy.plan(
                            st.session_state.turns,
                            mode,
                            duration_label,
                            st.session_state.evidence,
                            categories=st.session_state.categories,
                            remaining_minutes=round(remaining_after / 60, 1),
                            target_questions=target_count,
                        )
                        interviewer = InterviewerAgent(gateway)
                        try:
                            st.session_state.question = interviewer.ask_question(
                                st.session_state.evidence,
                                st.session_state.research,
                                plan,
                                target_role,
                                "Not specified — grounded in CV/JD and role context",
                                mode,
                                company=company,
                            )
                        except Exception as exc:
                            st.error("❌ The next adaptive question could not be generated.")
                            st.code(str(exc), language="text")
                            st.info("Your completed answer is saved. Fix the Groq access/rate-limit issue and continue the session.")
                    st.rerun()

    if st.session_state.turns:
        latest = st.session_state.turns[-1]["feedback"]
        st.markdown("### Latest coaching")
        cols = st.columns(6)
        for col, key, label in zip(cols, ["technical", "relevance", "evidence", "communication", "structure", "confidence"], ["Technical", "Relevance", "Evidence", "Communication", "Structure", "Confidence"]):
            col.metric(label, latest.get("scores", {}).get(key, 0))
        st.metric("Overall", latest.get("overall", 0))
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.write("**Strengths**", latest.get("strengths", []))
        st.write("**Missing / improve**", latest.get("missing_points", []))
        st.write("**Verification notes**", latest.get("verification_notes", []))
        st.write("**Practice answer**", latest.get("practice_answer", ""))
        st.write("**Next improvement**", latest.get("next_improvement", ""))
        sm = latest.get("speech_metrics", {})
        if sm:
            st.write("**Speech analytics**", sm)
        if latest.get("presentation_cues"):
            st.write("**Presentation cues**", latest["presentation_cues"])
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("### Category readiness")
        category_scores = defaultdict(list)
        for t in st.session_state.turns:
            category_scores[t.get("category", "General")].append(t.get("feedback", {}).get("overall", 0))
        readiness_cols = st.columns(min(4, max(1, len(category_scores))))
        for idx, (cat, vals) in enumerate(category_scores.items()):
            readiness_cols[idx % len(readiness_cols)].metric(cat.split(" ")[0], round(sum(vals)/len(vals)))

        st.markdown("### 3. Session report")
        md = build_markdown_report(
            target_role=target_role,
            industry="Not specified — grounded in CV/JD and role context",
            mode=mode,
            turns=st.session_state.turns,
            evidence=st.session_state.evidence,
        )
        pdf = build_pdf_report(
            target_role=target_role,
            industry="Not specified — grounded in CV/JD and role context",
            mode=mode,
            turns=st.session_state.turns,
            evidence=st.session_state.evidence,
        )
        st.download_button("Download Markdown report", md, file_name="intervia_report.md", mime="text/markdown")
        st.download_button("Download PDF report", pdf, file_name="intervia_report.pdf", mime="application/pdf")


# ============================================================
# FOOTER
# ============================================================
st.markdown(
    """
    <div class="footer">
        <div style="color:#d8e2f4;font-weight:800;font-size:15px;">
            Intervia — Interview Intelligence
        </div>
        <div style="margin-top:6px;font-size:12px;">
            AI-assisted interview practice powered by Groq.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
