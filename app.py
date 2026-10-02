```python
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


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Intervia — Interview Intelligence",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# INTERVIEW CONFIGURATION
# ============================================================

CATEGORIES = [
    "Behavioral & Situational 🎭",
    "Technical & Role-Specific 💻",
    "HR & Screening Basics 🤝",
    "Leadership & Management 👔",
    "Case & Analytical Interviews 📊",
    "Competency & Skill-Based 🧠",
    "Reverse Interviewing — Questions for the Employer 🔍",
]

DURATIONS = {
    "30 Minutes": 30,
    "60 Minutes": 60,
    "120 Minutes": 120,
    "180 Minutes": 180,
}

TARGET_QUESTIONS = {
    30: 8,
    60: 15,
    120: 28,
    180: 40,
}


# ============================================================
# PREMIUM UI
# ============================================================

st.markdown(
    """
    <style>

    :root {
        --bg:#050914;
        --panel:#0b1224;
        --panel-2:#0f1930;
        --line:#243454;
        --muted:#a9b7d0;
        --text:#f4f7ff;
        --accent:#8b6cff;
        --accent-2:#45d6ff;
        --good:#7cf2b4;
        --warn:#ffd27a;
        --danger:#ff8c9d;
    }

    .stApp {
        background:
            radial-gradient(
                circle at 78% -8%,
                rgba(139,108,255,.25),
                transparent 30%
            ),
            radial-gradient(
                circle at 8% 18%,
                rgba(69,214,255,.10),
                transparent 24%
            ),
            linear-gradient(
                180deg,
                #050914 0%,
                #07101f 100%
            );
    }

    [data-testid="stSidebar"] {
        background:rgba(5,9,20,.97);
        border-right:1px solid var(--line);
    }

    [data-testid="stSidebar"] * {
        color:var(--text);
    }

    .hero {
        padding:34px 38px;
        border:1px solid rgba(139,108,255,.30);
        border-radius:26px;
        background:
            linear-gradient(
                135deg,
                rgba(139,108,255,.18),
                rgba(12,20,39,.94) 55%,
                rgba(69,214,255,.08)
            );
        box-shadow:0 24px 70px rgba(0,0,0,.34);
        margin-bottom:22px;
    }

    .eyebrow {
        color:#b9aaff;
        font-size:11px;
        font-weight:900;
        letter-spacing:.18em;
        text-transform:uppercase;
    }

    .hero h1 {
        color:var(--text);
        margin:8px 0 10px;
        font-size:42px;
        line-height:1.08;
        letter-spacing:-.03em;
    }

    .muted,
    .small {
        color:var(--muted)!important;
    }

    .card,
    .cockpit {
        padding:20px;
        border:1px solid var(--line);
        border-radius:20px;
        background:
            linear-gradient(
                180deg,
                rgba(15,25,48,.94),
                rgba(9,17,33,.94)
            );
        box-shadow:0 14px 40px rgba(0,0,0,.18);
        margin-bottom:14px;
    }

    .agent {
        display:flex;
        justify-content:space-between;
        gap:16px;
        align-items:center;
        padding:13px 0;
        border-bottom:1px solid rgba(36,52,84,.72);
        color:var(--text);
    }

    .agent:last-child {
        border-bottom:0;
    }

    .agent-name {
        font-weight:750;
    }

    .status {
        font-size:10px;
        font-weight:900;
        letter-spacing:.10em;
        padding:5px 9px;
        border-radius:999px;
        border:1px solid rgba(124,242,180,.28);
        color:var(--good);
        background:rgba(124,242,180,.08);
    }

    .status.active {
        color:#bcaeff;
        border-color:rgba(139,108,255,.35);
        background:rgba(139,108,255,.10);
    }

    .status.waiting {
        color:var(--warn);
        border-color:rgba(255,210,122,.30);
        background:rgba(255,210,122,.08);
    }

    .status.optional {
        color:#9db0cc;
        border-color:rgba(157,176,204,.25);
        background:rgba(157,176,204,.07);
    }

    .question {
        font-size:26px;
        line-height:1.38;
        font-weight:760;
        color:var(--text);
        padding:26px;
        border:1px solid rgba(139,108,255,.26);
        border-left:5px solid var(--accent);
        background:
            linear-gradient(
                135deg,
                #0b1429,
                #0b1222
            );
        border-radius:18px;
        box-shadow:0 16px 42px rgba(0,0,0,.20);
    }

    .category {
        display:inline-block;
        padding:7px 11px;
        border:1px solid #3b4f78;
        border-radius:999px;
        color:#e0e7f6;
        font-size:12px;
        background:#111c35;
        margin-bottom:10px;
    }

    .mode-box {
        padding:16px;
        border:1px solid #2b4068;
        border-radius:16px;
        background:#091326;
    }

    .cockpit-title {
        color:#f4f7ff;
        font-size:13px;
        font-weight:900;
        letter-spacing:.08em;
        text-transform:uppercase;
        margin-bottom:7px;
    }

    div[data-testid="stButton"] > button {
        border-radius:12px;
        min-height:44px;
        font-weight:800;
        border:1px solid #34476f;
    }

    div[data-testid="stButton"] > button[kind="primary"] {
        box-shadow:0 10px 30px rgba(139,108,255,.22);
    }

    div[data-baseweb="tab-list"] {
        gap:6px;
        background:rgba(11,18,36,.75);
        padding:6px;
        border:1px solid var(--line);
        border-radius:14px;
    }

    button[data-baseweb="tab"] {
        color:#cbd6ea!important;
        border-radius:10px;
    }

    button[data-baseweb="tab"][aria-selected="true"] {
        color:#fff!important;
        background:
            linear-gradient(
                90deg,
                rgba(139,108,255,.22),
                rgba(69,214,255,.10)
            );
    }

    label,
    [data-testid="stWidgetLabel"] p {
        color:#eaf0fc!important;
        font-weight:650!important;
    }

    input,
    textarea {
        color:#f4f7ff!important;
    }

    .footer {
        margin-top:30px;
        padding:18px 20px;
        border-top:1px solid var(--line);
        color:#94a4bf;
        text-align:center;
    }

    .main .block-container {
        max-width:1480px;
        padding-top:1.6rem;
        padding-bottom:3rem;
    }

    .hero {
        position:relative;
        overflow:hidden;
        min-height:220px;
        display:flex;
        flex-direction:column;
        justify-content:center;
    }

    .hero:after {
        content:"";
        position:absolute;
        width:340px;
        height:340px;
        right:-120px;
        top:-150px;
        border-radius:50%;
        background:
            radial-gradient(
                circle,
                rgba(69,214,255,.20),
                transparent 68%
            );
        pointer-events:none;
    }

    .hero h1 {
        font-size:clamp(34px,4vw,56px);
        max-width:900px;
    }

    .hero .muted {
        max-width:920px;
        font-size:15px;
        line-height:1.65;
    }

    .ats-banner {
        display:flex;
        align-items:center;
        justify-content:space-between;
        gap:24px;
        margin:12px 0 18px;
        padding:20px 24px;
        border-radius:20px;
        border:1px solid rgba(69,214,255,.28);
        background:
            linear-gradient(
                100deg,
                rgba(69,214,255,.09),
                rgba(139,108,255,.13),
                rgba(12,20,39,.96)
            );
        box-shadow:0 18px 50px rgba(0,0,0,.22);
    }

    .ats-score {
        font-size:38px;
        line-height:1;
        font-weight:900;
        color:#ffffff;
        margin-top:6px;
    }

    .ats-score span {
        font-size:15px;
        color:#9fb0cc;
        margin-left:3px;
    }

    .stMetric {
        background:
            linear-gradient(
                145deg,
                rgba(15,25,48,.96),
                rgba(8,15,29,.96)
            );
        border:1px solid rgba(71,91,133,.42);
        padding:8px 10px;
        border-radius:16px;
        box-shadow:0 12px 30px rgba(0,0,0,.16);
    }

    [data-testid=stFileUploader] {
        background:rgba(12,21,40,.72);
        border:1px dashed #3b4f78;
        border-radius:16px;
        padding:8px;
    }

    textarea,
    input {
        border-radius:12px!important;
    }

    div[data-testid=stButton] > button:hover {
        transform:translateY(-1px);
        border-color:#6e83b0;
        box-shadow:0 12px 32px rgba(69,214,255,.10);
    }

    div[data-testid=stButton] > button[kind=primary] {
        background:
            linear-gradient(
                100deg,
                #7157e8,
                #4f7cff
            )!important;
        color:white!important;
        border:1px solid rgba(164,148,255,.65)!important;
    }

    .question {
        box-shadow:0 22px 60px rgba(0,0,0,.30);
        background:
            linear-gradient(
                135deg,
                rgba(19,32,61,.98),
                rgba(8,16,31,.98)
            );
    }

    .card {
        backdrop-filter:blur(14px);
    }

    .section-kicker {
        color:#7edfff;
        font-size:10px;
        font-weight:900;
        letter-spacing:.16em;
        text-transform:uppercase;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SPEECH CONTROLS
# ============================================================

def render_speech_controls(
    text: str,
    key: str,
    title: str,
    language: str,
    autoplay: bool = False,
):
    """Browser-native question playback."""

    payload = json.dumps(text or "", ensure_ascii=False)
    lang_payload = json.dumps(language or "en-US")

    safe_key = re.sub(
        r"[^A-Za-z0-9_]",
        "_",
        key,
    )

    auto_delay = 350 if autoplay else 999999

    components.html(
        f"""
        <div style="font-family:Arial,sans-serif;padding:8px 0;">

          <div style="
              color:#91a2c0;
              font-size:12px;
              font-weight:700;
              margin-bottom:7px;
          ">
              🔊 {escape(title)}
          </div>

          <button
              id="play_{safe_key}"
              style="
                  border:1px solid #33466f;
                  background:#151f3b;
                  color:#fff;
                  border-radius:10px;
                  padding:9px 14px;
                  cursor:pointer;
                  margin-right:6px;
              ">
              ▶ Play
          </button>

          <button
              id="stop_{safe_key}"
              style="
                  border:1px solid #33466f;
                  background:#0d1830;
                  color:#c9d4ea;
                  border-radius:10px;
                  padding:9px 14px;
                  cursor:pointer;
              ">
              ■ Stop
          </button>

          <span
              id="status_{safe_key}"
              style="
                  color:#91a2c0;
                  font-size:12px;
                  margin-left:8px;
              ">
          </span>

        </div>

        <script>

        const text_{safe_key} = {payload};
        const lang_{safe_key} = {lang_payload};

        const play_{safe_key} =
            document.getElementById("play_{safe_key}");

        const stop_{safe_key} =
            document.getElementById("stop_{safe_key}");

        const status_{safe_key} =
            document.getElementById("status_{safe_key}");

        let utterance_{safe_key} = null;

        function stopSpeech_{safe_key}(label="Stopped") {{

            if ("speechSynthesis" in window) {{
                window.speechSynthesis.cancel();
            }}

            utterance_{safe_key} = null;

            status_{safe_key}.textContent = label;
        }}

        function speak_{safe_key}() {{

            if (!("speechSynthesis" in window)) {{

                status_{safe_key}.textContent =
                    "Browser speech is not supported.";

                return;
            }}

            stopSpeech_{safe_key}("");

            utterance_{safe_key} =
                new SpeechSynthesisUtterance(
                    text_{safe_key}
                );

            utterance_{safe_key}.lang =
                lang_{safe_key};

            utterance_{safe_key}.rate = 0.96;
            utterance_{safe_key}.pitch = 1.0;

            utterance_{safe_key}.onstart = () => {{
                status_{safe_key}.textContent = "Speaking…";
            }};

            utterance_{safe_key}.onend = () => {{

                utterance_{safe_key} = null;

                status_{safe_key}.textContent =
                    "Question finished";
            }};

            utterance_{safe_key}.onerror = () => {{

                utterance_{safe_key} = null;

                status_{safe_key}.textContent =
                    "Speech playback failed";
            }};

            window.speechSynthesis.speak(
                utterance_{safe_key}
            );
        }}

        play_{safe_key}.onclick =
            speak_{safe_key};

        stop_{safe_key}.onclick =
            () => stopSpeech_{safe_key}();

        window.addEventListener(
            "beforeunload",
            () => stopSpeech_{safe_key}("")
        );

        setTimeout(
            () => {{
                if ({str(autoplay).lower()}) {{
                    speak_{safe_key}();
                }}
            }},
            {auto_delay}
        );

        </script>
        """,
        height=78,
        scrolling=False,
    )


# ============================================================
# TIMER
# ============================================================

def render_timer(
    started_at: float,
    duration_minutes: int,
):
    remaining = max(
        0,
        int(
            duration_minutes * 60
            - (time.time() - started_at)
        ),
    )

    components.html(
        f"""
        <div style="
            padding:8px 0;
            text-align:right;
            font-family:Arial,sans-serif;
        ">

            <span style="
                color:#91a2c0;
                font-size:12px;
            ">
                SESSION TIME REMAINING
            </span>

            <div
                id="timer"
                style="
                    font-size:24px;
                    font-weight:800;
                    color:#e8edff;
                ">
                --:--
            </div>

        </div>

        <script>

        let remaining = {remaining};

        const el =
            document.getElementById("timer");

        function tick() {{

            const m =
                Math.floor(
                    Math.max(0, remaining) / 60
                );

            const s =
                Math.max(0, remaining) % 60;

            el.textContent =
                String(m).padStart(2, "0")
                + ":"
                + String(s).padStart(2, "0");

            if (remaining <= 0) {{
                el.textContent = "00:00 — TIME";
            }}

            remaining -= 1;
        }}

        tick();

        setInterval(
            tick,
            1000
        );

        </script>
        """,
        height=70,
        scrolling=False,
    )


# ============================================================
# SESSION HELPERS
# ============================================================

def duration_state(
    started_at: float,
    duration_minutes: int,
):
    elapsed = max(
        0.0,
        time.time() - started_at,
    )

    remaining = max(
        0.0,
        duration_minutes * 60 - elapsed,
    )

    return (
        elapsed,
        remaining,
        remaining <= 0,
    )


def question_target(
    duration_minutes: int,
    elapsed_seconds: float,
    completed: int,
) -> int:

    base = TARGET_QUESTIONS[
        duration_minutes
    ]

    if elapsed_seconds <= 0:
        return base

    avg_turn = (
        elapsed_seconds
        / max(1, completed)
    )

    projected = int(
        (duration_minutes * 60)
        / max(avg_turn, 120)
    )

    return max(
        3,
        min(
            base * 2,
            max(base, projected),
        ),
    )


def speech_metrics(
    text: str,
    estimated_seconds: float | None = None,
):

    words = re.findall(
        r"\b[\w']+\b",
        text or "",
    )

    filler_list = [
        "um",
        "uh",
        "erm",
        "like",
        "you know",
        "basically",
        "actually",
        "sort of",
        "kind of",
    ]

    lowered = (
        text or ""
    ).lower()

    fillers = sum(
        len(
            re.findall(
                r"\b"
                + re.escape(f)
                + r"\b",
                lowered,
            )
        )
        for f in filler_list
    )

    words_count = len(words)

    if estimated_seconds:
        seconds = estimated_seconds
    elif words_count:
        seconds = max(
            10,
            words_count / 2.3,
        )
    else:
        seconds = 0

    wpm = (
        round(
            words_count
            / (seconds / 60),
            1,
        )
        if seconds
        else 0
    )

    return {
        "words": words_count,
        "filler_words": fillers,
        "estimated_seconds": round(
            seconds,
            1,
        ),
        "words_per_minute": wpm,
    }


# ============================================================
# DATABASE
# ============================================================

init_db()


# ============================================================
# SESSION STATE
# ============================================================

DEFAULT_SESSION_STATE = {
    "session_id": None,
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
    "groq_model": "",
    "reset_notice": False,
    "cv_filename": "",
    "jd_filename": "",
}


for key, default in DEFAULT_SESSION_STATE.items():

    if key not in st.session_state:

        if key == "session_id":
            st.session_state[key] = (
                uuid.uuid4().hex
            )

        elif isinstance(default, list):
            st.session_state[key] = default[:]

        else:
            st.session_state[key] = default


# ============================================================
# RESET SESSION
# ============================================================

def reset_interview_session():

    dynamic_prefixes = (
        "answer_input_",
        "answer_audio_",
        "camera_",
        "question_",
    )

    for key in list(
        st.session_state.keys()
    ):

        if (
            key
            in {
                "cv",
                "jd",
                "target_role_input",
                "company_input",
                "mode_input",
                "categories_input",
                "duration_input",
                "question_mode_input",
                "answer_mode_input",
                "research_input",
                "camera_enabled_input",
                "speech_language_input",
                "answer_length_input",
                "company_track_input",
                "jd_text_input",
                "confirm_reset_input",
            }
            or key.startswith(dynamic_prefixes)
        ):
            del st.session_state[key]

    for key, default in DEFAULT_SESSION_STATE.items():

        if key == "session_id":

            st.session_state[key] = (
                uuid.uuid4().hex
            )

        elif isinstance(default, list):

            st.session_state[key] = default[:]

        elif key == "reset_notice":

            st.session_state[key] = True

        else:

            st.session_state[key] = default


# ============================================================
# GROQ SECRET
# ============================================================

def configured_secret(
    name: str,
    default: str = "",
) -> str:

    try:
        value = st.secrets.get(
            name,
            "",
        )

    except Exception:
        value = ""

    return str(
        value
        or os.getenv(
            name,
            default,
        )
        or ""
    ).strip()


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown("## 🎯 Intervia")
    st.caption(
        "Evidence-Grounded Interview Intelligence"
    )

    api_key = st.text_input(
        "Groq API key",
        type="password",
        value=configured_secret(
            "GROQ_API_KEY"
        ),
        key="api_key_input",
        help=(
            "Enter your Groq API key here. "
            "For Streamlit Cloud, you can also store "
            "GROQ_API_KEY in Secrets."
        ),
    )

    target_role = st.text_input(
        "Target role",
        value="Senior Renewable Energy Engineer",
        disabled=st.session_state.started,
        key="target_role_input",
    )

    company = st.text_input(
        "Company / employer (optional)",
        value=st.session_state.company,
        disabled=st.session_state.started,
        key="company_input",
    )

    st.markdown("### Interview Design")

    setup_tab, new_tab = st.tabs(
        [
            "Interview categories and Interview mode",
            "New Interview Session",
        ]
    )

    with setup_tab:

        mode = st.selectbox(
            "Interview mode",
            [
                "Mixed",
                "Technical",
                "Behavioral",
                "Case / Situational",
                "HR / Screening",
                "Leadership",
            ],
            disabled=st.session_state.started,
            help=(
                "Controls the interviewer's primary "
                "question style."
            ),
            key="mode_input",
        )

        categories = st.multiselect(
            "Interview categories",
            CATEGORIES,
            default=st.session_state.categories,
            disabled=st.session_state.started,
            help=(
                "Select one or more categories. "
                "The adaptive strategy agent balances "
                "them as the session progresses."
            ),
            key="categories_input",
        )

    with new_tab:

        st.markdown(
            "**Start clean, keep your Groq key.**"
        )

        st.caption(
            "This resets the active interview, "
            "evidence pack, uploaded files, answers, "
            "coaching, timer and adaptive question. "
            "Your API key and deployment remain untouched."
        )

        if (
            st.session_state.started
            or st.session_state.turns
            or st.session_state.evidence
        ):

            st.markdown(
                """
                <div class="card">
                    <b>Active session detected</b><br>
                    <span class="small">
                        A reset will create a fresh session ID
                        and return the interview design
                        to its defaults.
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        else:

            st.markdown(
                """
                <div class="card">
                    <b>Ready for a new session</b><br>
                    <span class="small">
                        No active interview is currently running.
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        confirm_reset = st.checkbox(
            "I understand that the current interview session will be cleared.",
            key="confirm_reset_input",
        )

        if st.button(
            "↻ Reset & Start New Interview",
            type="primary",
            use_container_width=True,
            disabled=not confirm_reset,
            key="reset_sidebar_button",
        ):

            reset_interview_session()
            st.rerun()

    duration_label = st.selectbox(
        "Practice session duration",
        list(DURATIONS.keys()),
        index=(
            0
            if st.session_state.session_duration == 30
            else list(
                DURATIONS.values()
            ).index(
                st.session_state.session_duration
            )
        ),
        disabled=st.session_state.started,
        key="duration_input",
    )

    duration_minutes = DURATIONS[
        duration_label
    ]

    question_mode = st.radio(
        "Question format",
        [
            "Text Questions",
            "Audio Questions",
        ],
        index=(
            0
            if st.session_state.question_mode
            == "Text Questions"
            else 1
        ),
        disabled=st.session_state.started,
        horizontal=True,
        help=(
            "Text Questions shows the question on screen. "
            "Audio Questions also reads it aloud."
        ),
        key="question_mode_input",
    )

    answer_mode = st.radio(
        "Answer format",
        [
            "⌨️ Type Answers",
            "🎙️ Speak Answers",
        ],
        index=(
            0
            if st.session_state.answer_mode.startswith("⌨")
            else 1
        ),
        disabled=st.session_state.started,
        horizontal=True,
        help=(
            "Type Answers uses a text box. "
            "Speak Answers records your microphone "
            "response and sends it to Groq Whisper."
        ),
        key="answer_mode_input",
    )

    use_research = st.checkbox(
        "Company / role analysis",
        value=False,
        disabled=st.session_state.started,
        help=(
            "Optional AI analysis of the supplied role, "
            "JD and company context."
        ),
        key="research_input",
    )

    camera_enabled = st.checkbox(
        "Camera presentation snapshot",
        value=st.session_state.camera_enabled,
        disabled=st.session_state.started,
        help=(
            "Optional snapshot analysis of observable "
            "framing/posture cues."
        ),
        key="camera_enabled_input",
    )

    speech_language = st.selectbox(
        "Question voice",
        [
            "English (US)",
            "English (UK)",
        ],
        index=0,
        disabled=st.session_state.started,
        key="speech_language_input",
    )

    speech_locale = (
        "en-US"
        if speech_language == "English (US)"
        else "en-GB"
    )

    answer_length = st.selectbox(
        "AI practice-answer length",
        [
            "Short",
            "Standard",
            "Detailed",
        ],
        disabled=st.session_state.started,
        key="answer_length_input",
    )

    st.divider()

    st.caption(
        "Tip: choose your modalities once here. "
        "Intervia keeps them fixed for the complete session."
    )

    st.caption(
        "Production: keep secrets in Streamlit Secrets, "
        "not GitHub."
    )

    if not st.session_state.started:

        st.session_state.session_duration = (
            duration_minutes
        )

        st.session_state.question_mode = (
            question_mode
        )

        st.session_state.answer_mode = (
            answer_mode
        )

        st.session_state.categories = (
            categories or CATEGORIES[:]
        )

        st.session_state.company = company

        st.session_state.company_track = ""

        st.session_state.camera_enabled = (
            camera_enabled
        )


# ============================================================
# HERO
# ============================================================

st.markdown(
    """
    <div class="hero">

        <div class="eyebrow">
            Adaptive Interview Intelligence
        </div>

        <h1>
            Practice against the job —
            with text or voice, on your schedule.
        </h1>

        <div class="muted">
            Choose question and answer modalities once,
            select a session length and interview categories,
            then Intervia automatically adapts the Q&A pace
            to the remaining time.
        </div>

    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SESSION STATUS
# ============================================================

status_col, reset_col = st.columns(
    [4, 1]
)

with status_col:

    if st.session_state.get(
        "reset_notice"
    ):

        st.success(
            "✨ New interview session is ready. "
            "Your previous session state has been cleared."
        )

        st.session_state.reset_notice = False

    elif st.session_state.started:

        st.info(
            "Interview session active · use "
            "**New Interview Session** when you want "
            "a clean reset."
        )

    else:

        st.caption(
            "Session workspace ready · your API key "
            "is preserved when you start a new interview."
        )


with reset_col:

    if st.button(
        "↻ New Interview",
        use_container_width=True,
        key="reset_dashboard_button",
        help=(
            "Clear the current interview and "
            "return to a fresh session."
        ),
    ):

        reset_interview_session()
        st.rerun()


if not st.session_state.started:

    st.info(
        "Before starting: configure "
        "**Interview categories and Interview mode**, "
        "choose **Text or Audio Questions**, "
        "**Type or Speak Answers**, and select "
        "your practice session duration."
    )


# ============================================================
# EVIDENCE PACK AREA
# ============================================================

left, right = st.columns(
    [1.35, 1]
)

with left:

    st.markdown(
        "### 1. Build the evidence pack"
    )

    cv_file = st.file_uploader(
        "CV / Resume",
        type=[
            "pdf",
            "docx",
            "txt",
        ],
        key="cv",
    )

    jd_file = st.file_uploader(
        "Job Description",
        type=[
            "pdf",
            "docx",
            "txt",
        ],
        key="jd",
    )

    jd_text = st.text_area(
        "Or paste the job description",
        height=150,
        placeholder=(
            "Paste the JD here if you do not have a file."
        ),
        key="jd_text_input",
    )

    company_track = st.text_area(
        "Optional company-specific question context",
        height=90,
        placeholder=(
            "Paste publicly sourced interview themes/questions "
            "or a company-specific question bank here."
        ),
        disabled=st.session_state.started,
        key="company_track_input",
    )

    if st.button(
        "Build evidence pack",
        type="primary",
        use_container_width=True,
        disabled=st.session_state.started,
    ):

        # ----------------------------------------------------
        # VALIDATION
        # ----------------------------------------------------

        if not api_key:

            st.error(
                "Enter a Groq API key first."
            )

        elif not cv_file:

            st.error(
                "Upload a CV / Resume."
            )

        elif not (
            jd_file
            or jd_text.strip()
        ):

            st.error(
                "Upload or paste the Job Description."
            )

        else:

            # ------------------------------------------------
            # STORE FILE INFORMATION
            # ------------------------------------------------

            st.session_state.company_track = (
                company_track
            )

            st.session_state.cv_filename = (
                getattr(
                    cv_file,
                    "name",
                    "CV / Resume",
                )
            )

            st.session_state.jd_filename = (
                getattr(
                    jd_file,
                    "name",
                    "Pasted Job Description",
                )
                if jd_file
                else "Pasted Job Description"
            )

            # ------------------------------------------------
            # EXTRACT DOCUMENT TEXT
            # ------------------------------------------------

            cv_text = extract_uploaded_text(
                cv_file
            )

            final_jd = (
                extract_uploaded_text(jd_file)
                if jd_file
                else jd_text
            )

            # ------------------------------------------------
            # BUILD EVIDENCE
            # ------------------------------------------------

            st.session_state.evidence = (
                EvidenceAgent().build(
                    cv_text=safe_clamp(
                        cv_text,
                        14000,
                    ),
                    jd_text=safe_clamp(
                        final_jd,
                        12000,
                    ),
                    target_role=target_role,
                    industry=(
                        "Not specified — grounded "
                        "in CV/JD and role context"
                    ),
                    cv_filename=(
                        st.session_state.cv_filename
                    ),
                )
            )

            st.session_state.research = None
            st.session_state.turns = []
            st.session_state.question = None
            st.session_state.started = False
            st.session_state.started_at = None

            # ------------------------------------------------
            # OPTIONAL COMPANY / ROLE RESEARCH
            # ------------------------------------------------

            if use_research:

                try:

                    gateway = GroqGateway(
                        api_key
                    )

                    st.session_state.research = (
                        ResearchAgent(
                            gateway
                        ).run(
                            target_role,
                            (
                                "Not specified — grounded "
                                "in CV/JD and role context"
                            ),
                            safe_clamp(
                                final_jd,
                                6000,
                            ),
                            company=company,
                            company_track=company_track,
                        )
                    )

                except Exception:

                    st.session_state.research = None

                    st.warning(
                        "Company / role analysis is temporarily "
                        "unavailable. The interview will continue "
                        "using the CV and Job Description."
                    )

            st.success(
                "Evidence pack created. Candidate evidence, "
                "JD requirements and role analysis remain separate."
            )


# ============================================================
# AGENT COCKPIT
# ============================================================

with right:

    st.markdown(
        "### Agent cockpit"
    )

    agent_statuses = [
        (
            "Evidence Intelligence",
            "READY"
            if st.session_state.evidence
            else "WAITING",
        ),
        (
            "Career & Market Research",
            "READY"
            if st.session_state.research
            else (
                "OPTIONAL"
                if not use_research
                else "WAITING"
            ),
        ),
        (
            "Interview Strategy",
            "ACTIVE"
            if st.session_state.started
            else "READY",
        ),
        (
            "AI Interviewer",
            "ACTIVE"
            if st.session_state.question
            else "READY",
        ),
        (
            "Performance Coach",
            "READY",
        ),
    ]

    for name, status in agent_statuses:

        st.markdown(
            f"""
            <div class="agent">
                <span>{escape(name)}</span>
                <span class="status">
                    {escape(status)}
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        "### Session design"
    )

    model_label = (
        st.session_state.get(
            "groq_model"
        )
        or "Automatic model discovery"
    )

    st.markdown(
        f"""
        <div class="card">

            <b>
                {escape(duration_label)}
            </b>

            <br>

            <span class="small">
                Mode: {escape(mode)}
                · Categories:
                {len(categories or CATEGORIES)}
            </span>

            <br>

            <span class="small">
                Questions:
                {escape(question_mode)}
                · Answers:
                {escape(answer_mode)}
            </span>

            <br>

            <span class="small">
                Groq model:
                {escape(model_label)}
            </span>

            <br>

            <span class="small">
                Target pacing:
                approximately
                {TARGET_QUESTIONS[duration_minutes]}
                core questions,
                automatically adjusted for answer speed
                and remaining time.
            </span>

        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# EVIDENCE INTELLIGENCE
# ============================================================

if st.session_state.evidence:

    ev = st.session_state.evidence

    ats = ev.get(
        "ats_readiness",
        {},
    )

    st.markdown(
        "### Candidate Evidence Intelligence"
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "ATS Readiness",
        f"{ats.get('score', 0)}/100",
    )

    c2.metric(
        "JD Keyword Match",
        f"{ats.get('keyword_match_score', 0)}/100",
    )

    c3.metric(
        "Candidate Facts",
        len(
            ev.get(
                "candidate_facts",
                [],
            )
        ),
    )

    c4.metric(
        "Skill Gaps",
        len(
            ev.get(
                "gaps",
                [],
            )
        ),
    )

    st.markdown(
        f"""
        <div class="ats-banner">

            <div>

                <span class="eyebrow">
                    ATS RESUME CHECK
                </span>

                <div class="ats-score">
                    {ats.get('score', 0)}
                    <span>/100</span>
                </div>

            </div>

            <div>

                <b>
                    {escape(
                        ats.get(
                            "label",
                            "ATS readiness estimate",
                        )
                    )}
                </b>

                <div class="small">
                    {escape(
                        ats.get(
                            "method",
                            "Deterministic CV/JD readiness estimate.",
                        )
                    )}
                </div>

            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )

    ev_left, ev_right = st.columns(2)

    with ev_left:

        st.markdown(
            "**ATS strengths**"
        )

        for item in ats.get(
            "strengths",
            [],
        )[:6]:

            st.markdown(
                f"• {escape(item)}"
            )

        st.markdown(
            "**Detected headings**"
        )

        st.caption(
            ", ".join(
                ats.get(
                    "detected_headings",
                    [],
                )
            )
            or "No conventional headings detected"
        )

    with ev_right:

        st.markdown(
            "**ATS improvement recommendations**"
        )

        for item in ats.get(
            "improvements",
            [],
        )[:6]:

            st.markdown(
                f"• {escape(item)}"
            )

        st.markdown(
            "**Missing / not detected JD keywords**"
        )

        st.caption(
            ", ".join(
                ats.get(
                    "missing_keywords",
                    [],
                )[:30]
            )
            or "No major keyword gaps detected"
        )

    with st.expander(
        "View complete grounding data"
    ):

        st.write(
            "**Candidate evidence**",
            ev.get(
                "candidate_facts",
                [],
            ),
        )

        st.write(
            "**JD requirements**",
            ev.get(
                "jd_requirements",
                [],
            ),
        )

        st.write(
            "**Matched skills / terms**",
            ev.get(
                "matches",
                [],
            ),
        )

        st.write(
            "**Gaps / unknowns**",
            ev.get(
                "gaps",
                [],
            ),
        )

        st.write(
            "**ATS matched keywords**",
            ats.get(
                "matched_keywords",
                [],
            ),
        )

    # ========================================================
    # START INTERVIEW
    # ========================================================

    if not st.session_state.started:

        if st.button(
            "🚀 Start complete adaptive interview",
            type="primary",
            use_container_width=True,
        ):

            if not categories:

                st.error(
                    "Select at least one interview category."
                )

            elif not api_key:

                st.error(
                    "Groq API key is required."
                )

            else:

                try:

                    gateway = GroqGateway(
                        api_key
                    )

                    st.session_state.groq_model = (
                        gateway.selected_model()
                    )

                    strategy = StrategyAgent()

                    interviewer = InterviewerAgent(
                        gateway
                    )

                    now = time.time()

                    st.session_state.started_at = now

                    elapsed, remaining, _ = (
                        duration_state(
                            now,
                            duration_minutes,
                        )
                    )

                    target_count = question_target(
                        duration_minutes,
                        elapsed,
                        0,
                    )

                    plan = strategy.plan(
                        [],
                        mode,
                        duration_label,
                        ev,
                        categories=categories,
                        remaining_minutes=round(
                            remaining / 60,
                            1,
                        ),
                        target_questions=target_count,
                    )

                    q = interviewer.ask_question(
                        ev,
                        st.session_state.research,
                        plan,
                        target_role,
                        (
                            "Not specified — grounded "
                            "in CV/JD and role context"
                        ),
                        mode,
                        company=company,
                    )

                    st.session_state.question = q
                    st.session_state.started = True
                    st.session_state.session_duration = (
                        duration_minutes
                    )
                    st.session_state.question_mode = (
                        question_mode
                    )
                    st.session_state.answer_mode = (
                        answer_mode
                    )
                    st.session_state.categories = (
                        categories
                    )
                    st.session_state.company = (
                        company
                    )
                    st.session_state.camera_enabled = (
                        camera_enabled
                    )

                    st.rerun()

                except Exception:

                    st.error(
                        "❌ The adaptive interview could not "
                        "generate Question 1."
                    )

                    st.info(
                        "Check your Groq API key and model access, "
                        "then try again."
                    )


# ============================================================
# LIVE INTERVIEW
# ============================================================

if (
    st.session_state.started
    and st.session_state.question
):

    st.markdown("---")

    st.markdown(
        "### 2. Live interview studio"
    )

    elapsed, remaining, expired = (
        duration_state(
            st.session_state.started_at,
            st.session_state.session_duration,
        )
    )

    turn_no = (
        len(
            st.session_state.turns
        )
        + 1
    )

    target_count = question_target(
        st.session_state.session_duration,
        elapsed,
        len(
            st.session_state.turns
        ),
    )

    progress = min(
        1.0,
        len(
            st.session_state.turns
        )
        / max(
            1,
            target_count,
        ),
    )

    top1, top2, top3 = st.columns(
        [1.6, 1, 1]
    )

    with top1:

        st.progress(
            progress,
            text=(
                f"Question {turn_no} · "
                f"adaptive target {target_count}"
            ),
        )

    with top2:

        st.metric(
            "Elapsed",
            f"{int(elapsed // 60):02d}:"
            f"{int(elapsed % 60):02d}",
        )

    with top3:

        render_timer(
            st.session_state.started_at,
            st.session_state.session_duration,
        )

    if expired:

        st.warning(
            "⏱️ Your selected practice session time "
            "has ended. Your report is ready below."
        )

        st.session_state.question = None

    else:

        if isinstance(
            st.session_state.question,
            dict,
        ):

            q_obj = (
                st.session_state.question
            )

        else:

            q_obj = {
                "category": "General",
                "question": str(
                    st.session_state.question
                ),
            }

        question_text = (
            q_obj.get(
                "question",
                "",
            )
            .strip()
        )

        category = q_obj.get(
            "category",
            "General",
        )

        st.markdown(
            f"""
            <span class="category">
                {escape(category)}
            </span>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            f"""
            <div class="question">
                {escape(question_text)}
            </div>
            """,
            unsafe_allow_html=True,
        )

        render_speech_controls(
            question_text,
            f"question_{turn_no}",
            "Generated interview question",
            speech_locale,
            autoplay=(
                st.session_state.question_mode
                == "Audio Questions"
            ),
        )

        if (
            st.session_state.question_mode
            == "Audio Questions"
        ):

            st.caption(
                "Audio mode: the question is spoken "
                "automatically when available."
            )

        st.markdown(
            "#### Your answer"
        )

        st.caption(
            f"Answer mode locked for this session: "
            f"**{st.session_state.answer_mode}**"
        )

        answer = ""
        voice_transcript = ""
        audio = None

        # ----------------------------------------------------
        # TEXT ANSWER
        # ----------------------------------------------------

        if (
            st.session_state.answer_mode
            == "⌨️ Type Answers"
        ):

            answer = st.text_area(
                "Type your answer",
                key=f"answer_input_{turn_no}",
                height=190,
                placeholder=(
                    "Answer as if you were "
                    "in the real interview."
                ),
            )

        # ----------------------------------------------------
        # VOICE ANSWER
        # ----------------------------------------------------

        else:

            audio = st.audio_input(
                "🎙️ Record your answer",
                sample_rate=16000,
                key=f"answer_audio_{turn_no}",
            )

            st.caption(
                "Speak naturally. Submit the recording "
                "when you finish; Whisper will transcribe "
                "it before coaching."
            )

        # ----------------------------------------------------
        # CAMERA
        # ----------------------------------------------------

        camera = None

        if st.session_state.camera_enabled:

            camera = st.camera_input(
                "Optional camera snapshot for presentation-cue feedback",
                key=f"camera_{turn_no}",
            )

            st.caption(
                "MVP camera analysis is a snapshot, "
                "not continuous video. It evaluates "
                "only observable framing/posture/camera cues."
            )

        # ----------------------------------------------------
        # SUBMIT ANSWER
        # ----------------------------------------------------

        submit = st.button(
            "Submit answer & get coaching",
            type="primary",
            use_container_width=True,
        )

        if submit:

            elapsed_now, remaining_now, expired_now = (
                duration_state(
                    st.session_state.started_at,
                    st.session_state.session_duration,
                )
            )

            if expired_now:

                st.warning(
                    "The session time has ended. "
                    "Finish with the report below."
                )

                st.session_state.question = None
                st.rerun()

            elif not api_key:

                st.error(
                    "Groq API key is required."
                )

            else:

                gateway = GroqGateway(
                    api_key
                )

                # ------------------------------------------------
                # VOICE TRANSCRIPTION
                # ------------------------------------------------

                if (
                    st.session_state.answer_mode
                    == "🎙️ Speak Answers"
                    and audio is not None
                ):

                    try:

                        voice_transcript = (
                            gateway.transcribe(
                                audio.getvalue(),
                                getattr(
                                    audio,
                                    "name",
                                    "answer.wav",
                                ),
                            )
                            .strip()
                        )

                        answer = (
                            voice_transcript
                        )

                    except Exception:

                        st.error(
                            "Voice transcription failed. "
                            "Please record again or use text."
                        )

                else:

                    answer = (
                        answer or ""
                    ).strip()

                # ------------------------------------------------
                # ANSWER VALIDATION
                # ------------------------------------------------

                if not answer:

                    st.error(
                        "Provide an answer before submitting."
                    )

                else:

                    # --------------------------------------------
                    # COACHING
                    # --------------------------------------------

                    try:

                        coach = CoachAgent(
                            gateway
                        )

                        result = coach.evaluate(
                            question=question_text,
                            answer=answer,
                            evidence=(
                                st.session_state.evidence
                            ),
                            target_role=target_role,
                            mode=mode,
                            answer_length=answer_length,
                        )

                    except Exception:

                        st.error(
                            "❌ Coaching could not be generated."
                        )

                        st.info(
                            "Check your Groq API key, "
                            "model access and current API limits."
                        )

                        st.stop()

                    # --------------------------------------------
                    # SPEECH METRICS
                    # --------------------------------------------

                    if voice_transcript:

                        metrics = speech_metrics(
                            answer
                        )

                    else:

                        metrics = {
                            "words": len(
                                answer.split()
                            ),
                            "filler_words": None,
                            "estimated_seconds": None,
                            "words_per_minute": None,
                        }

                    # --------------------------------------------
                    # CAMERA ANALYSIS
                    # --------------------------------------------

                    camera_feedback = None

                    if camera is not None:

                        try:

                            camera_feedback = (
                                gateway.analyze_camera(
                                    camera.getvalue(),
                                    getattr(
                                        camera,
                                        "type",
                                        "image/jpeg",
                                    ),
                                )
                            )

                        except Exception:

                            camera_feedback = {
                                "available": False,
                                "message": (
                                    "Camera analysis is "
                                    "unavailable for this snapshot."
                                ),
                            }

                    result["speech_metrics"] = metrics

                    result["presentation_cues"] = (
                        camera_feedback
                    )

                    # --------------------------------------------
                    # SAVE TURN
                    # --------------------------------------------

                    st.session_state.turns.append(
                        {
                            "question": question_text,
                            "category": category,
                            "answer": answer,
                            "answer_mode": (
                                "voice"
                                if voice_transcript
                                else "text"
                            ),
                            "voice_transcript": (
                                voice_transcript
                            ),
                            "feedback": result,
                            "timestamp": (
                                datetime.now()
                                .isoformat(
                                    timespec="seconds"
                                )
                            ),
                            "elapsed_seconds": round(
                                elapsed_now,
                                1,
                            ),
                        }
                    )

                    save_session(
                        st.session_state.session_id,
                        target_role,
                        (
                            "Not specified — grounded "
                            "in CV/JD and role context"
                        ),
                        st.session_state.turns,
                    )

                    # --------------------------------------------
                    # NEXT QUESTION
                    # --------------------------------------------

                    elapsed_after, remaining_after, expired_after = (
                        duration_state(
                            st.session_state.started_at,
                            st.session_state.session_duration,
                        )
                    )

                    if expired_after:

                        st.session_state.question = None

                    else:

                        strategy = StrategyAgent()

                        target_count = question_target(
                            st.session_state.session_duration,
                            elapsed_after,
                            len(
                                st.session_state.turns
                            ),
                        )

                        plan = strategy.plan(
                            st.session_state.turns,
                            mode,
                            duration_label,
                            st.session_state.evidence,
                            categories=(
                                st.session_state.categories
                            ),
                            remaining_minutes=round(
                                remaining_after / 60,
                                1,
                            ),
                            target_questions=target_count,
                        )

                        interviewer = InterviewerAgent(
                            gateway
                        )

                        # IMPORTANT:
                        # try/except is correctly indented here.

                        try:

                            st.session_state.question = (
                                interviewer.ask_question(
                                    st.session_state.evidence,
                                    st.session_state.research,
                                    plan,
                                    target_role,
                                    (
                                        "Not specified — grounded "
                                        "in CV/JD and role context"
                                    ),
                                    mode,
                                    company=company,
                                )
                            )

                        except Exception:

                            st.error(
                                "❌ The next adaptive question "
                                "could not be generated."
                            )

                            st.info(
                                "Your completed answer has been "
                                "saved. Check Groq availability "
                                "and try again."
                            )

                    st.rerun()


# ============================================================
# LATEST COACHING
# ============================================================

if (
    st.session_state.started
    and st.session_state.turns
):

    latest = (
        st.session_state.turns[-1]
        .get(
            "feedback",
            {},
        )
    )

    st.markdown(
        "### Latest coaching"
    )

    cols = st.columns(6)

    score_keys = [
        "technical",
        "relevance",
        "evidence",
        "communication",
        "structure",
        "confidence",
    ]

    score_labels = [
        "Technical",
        "Relevance",
        "Evidence",
        "Communication",
        "Structure",
        "Confidence",
    ]

    for col, key, label in zip(
        cols,
        score_keys,
        score_labels,
    ):

        col.metric(
            label,
            latest.get(
                "scores",
                {},
            ).get(
                key,
                0,
            ),
        )

    st.metric(
        "Overall",
        latest.get(
            "overall",
            0,
        ),
    )

    st.markdown(
        '<div class="card">',
        unsafe_allow_html=True,
    )

    st.write(
        "**Strengths**",
        latest.get(
            "strengths",
            [],
        ),
    )

    st.write(
        "**Missing / improve**",
        latest.get(
            "missing_points",
            [],
        ),
    )

    st.write(
        "**Verification notes**",
        latest.get(
            "verification_notes",
            [],
        ),
    )

    st.write(
        "**Practice answer**",
        latest.get(
            "practice_answer",
            "",
        ),
    )

    st.write(
        "**Next improvement**",
        latest.get(
            "next_improvement",
            "",
        ),
    )

    sm = latest.get(
        "speech_metrics",
        {},
    )

    if sm:

        st.write(
            "**Speech analytics**",
            sm,
        )

    if latest.get(
        "presentation_cues"
    ):

        st.write(
            "**Presentation cues**",
            latest[
                "presentation_cues"
            ],
        )

    st.markdown(
        "</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# CATEGORY READINESS
# ============================================================

if st.session_state.turns:

    st.markdown(
        "### Category readiness"
    )

    category_scores = defaultdict(
        list
    )

    for turn in st.session_state.turns:

        category_scores[
            turn.get(
                "category",
                "General",
            )
        ].append(
            turn.get(
                "feedback",
                {},
            ).get(
                "overall",
                0,
            )
        )

    readiness_cols = st.columns(
        min(
            4,
            max(
                1,
                len(category_scores),
            ),
        )
    )

    for idx, (
        cat,
        vals,
    ) in enumerate(
        category_scores.items()
    ):

        readiness_cols[
            idx % len(readiness_cols)
        ].metric(
            cat.split(" ")[0],
            round(
                sum(vals)
                / len(vals)
            ),
        )


# ============================================================
# SESSION REPORT
# ============================================================

if (
    st.session_state.turns
    and st.session_state.evidence
):

    st.markdown(
        "### 3. Session report"
    )

    report_kwargs = dict(
        target_role=target_role,
        industry=(
            "Not specified — grounded "
            "in CV/JD and role context"
        ),
        mode=mode,
        turns=st.session_state.turns,
        evidence=st.session_state.evidence,
        company=company,
        duration_minutes=duration_minutes,
        categories=st.session_state.categories,
        question_mode=question_mode,
        answer_mode=answer_mode,
        use_research=use_research,
        camera_enabled=camera_enabled,
        speech_language=speech_language,
        answer_length=answer_length,
        company_track=(
            st.session_state.company_track
        ),
        session_id=(
            st.session_state.session_id
        ),
        started_at=(
            st.session_state.started_at
        ),
        groq_model=(
            st.session_state.get(
                "groq_model",
                "",
            )
        ),
        research=(
            st.session_state.research
        ),
        cv_filename=(
            st.session_state.get(
                "cv_filename",
                "",
            )
        ),
        jd_filename=(
            st.session_state.get(
                "jd_filename",
                "",
            )
        ),
    )

    try:

        md = build_markdown_report(
            **report_kwargs
        )

        pdf = build_pdf_report(
            **report_kwargs
        )

        st.download_button(
            "Download Markdown report",
            md,
            file_name="intervia_report.md",
            mime="text/markdown",
        )

        st.download_button(
            "Download PDF report",
            pdf,
            file_name="intervia_report.pdf",
            mime="application/pdf",
        )

    except Exception:

        st.warning(
            "The interview is complete, but the "
            "downloadable report could not be generated."
        )


# ============================================================
# FOOTER
# ============================================================

st.markdown(
    """
    <div class="footer">
        Intervia Interview Intelligence ·
        Premium modular interview workspace ·
        Start a new session anytime without changing
        your deployment or Groq secret.
    </div>
    """,
    unsafe_allow_html=True,
)
```
