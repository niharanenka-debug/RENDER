import hashlib
import html
import json
import re
import time

import streamlit as st

from core.config import (
    ANALYSIS_DEPTHS,
    DB_PATH,
    DIFFICULTIES,
    LOCAL_DEMO,
    MODEL,
    QUESTION_COUNTS,
    SUMMARY_STYLES,
)
from core.db import Database
from core.extraction import content_hash, extract_file, extract_url
from core.ai import AIError, GeminiService
from core.logic import mistake_from_question, score_questions
from core.validation import QuizPayload


st.set_page_config(
    page_title="prep-Nerd.ai | Your study space",
    page_icon="📘",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Microsoft Fluent-inspired system: Segoe UI, neutral surfaces, restrained Azure
# blue, visible focus rings, and high-contrast form controls.
st.markdown(
    """
    <style>
    :root{
      --bg:#070812; --panel:rgba(17,19,34,.72); --panel2:rgba(24,27,48,.72);
      --line:rgba(255,255,255,.09); --text:#f6f7fb; --muted:#a6abc0;
      --brand:#8b7cff; --brand2:#5ee7ff; --good:#62e6a7; --danger:#ff718c;
      --shadow:0 24px 80px rgba(0,0,0,.32);
    }
    html,body,[class*="css"],button,input,textarea,select{
      font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif!important;
    }
    .stApp{
      color:var(--text);
      background:
        radial-gradient(700px 420px at 8% -5%,rgba(139,124,255,.22),transparent 65%),
        radial-gradient(650px 430px at 96% 4%,rgba(94,231,255,.13),transparent 62%),
        radial-gradient(600px 500px at 52% 100%,rgba(139,124,255,.08),transparent 68%),
        var(--bg);
      min-height:100vh;
    }
    .stApp:before{
      content:"";position:fixed;inset:0;pointer-events:none;opacity:.35;
      background-image:linear-gradient(rgba(255,255,255,.018) 1px,transparent 1px),
                       linear-gradient(90deg,rgba(255,255,255,.018) 1px,transparent 1px);
      background-size:42px 42px;mask-image:linear-gradient(to bottom,#000,transparent 82%);
    }
    [data-testid="stHeader"]{background:rgba(7,8,18,.48);backdrop-filter:blur(20px);z-index:5}
    [data-testid="stMainBlockContainer"]{max-width:1450px;padding:1.15rem 2rem 5rem}
    h1,h2,h3,h4{color:var(--text)!important;letter-spacing:-.045em}
    h1{font-size:clamp(2.1rem,4vw,4.25rem)!important;line-height:.98!important;font-weight:800!important}
    h2{font-size:2rem!important;font-weight:780!important}
    h3{font-size:1.18rem!important;font-weight:720!important}
    p,label,.stMarkdown{color:var(--text)}
    .stCaption,.stCaption p{color:var(--muted)!important}

    /* New app shell */
    [data-testid="stSidebar"]{
      background:rgba(8,9,19,.78);border-right:1px solid var(--line);
      backdrop-filter:blur(28px);-webkit-backdrop-filter:blur(28px);
    }
    [data-testid="stSidebar"]>div:first-child{padding:1rem .75rem}
    [data-testid="stSidebar"] [data-testid="stRadio"] label{
      color:#9da2ba;border:1px solid transparent;border-radius:14px;
      padding:.72rem .82rem;margin:.18rem 0;font-weight:650;
      transition:transform .22s ease,background .22s ease,border-color .22s ease,color .22s ease;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] label:hover{
      transform:translateX(4px);background:rgba(255,255,255,.045);border-color:var(--line);color:#fff;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] [aria-checked="true"]+div{
      color:#fff!important;font-weight:750;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] [aria-checked="true"]~*{color:#fff!important}
    [data-testid="stSidebar"] hr{border-color:var(--line)}
    [data-testid="stSidebar"] .stSelectbox>div>div{background:rgba(255,255,255,.045)!important;color:#fff!important}

    .app-topbar{
      display:flex;align-items:center;justify-content:space-between;gap:1rem;
      padding:.65rem .8rem;margin:0 0 1.2rem;border:1px solid var(--line);
      background:rgba(15,17,31,.58);border-radius:18px;backdrop-filter:blur(22px);
      box-shadow:0 12px 40px rgba(0,0,0,.16);animation:rise .5s ease both;
    }
    .brand-lockup{display:flex;align-items:center;gap:.7rem;margin:0}
    .brand-mark{
      width:38px;height:38px;border-radius:12px;display:grid;place-items:center;color:#fff;
      font-weight:900;background:linear-gradient(135deg,var(--brand),#5b4bdb);
      box-shadow:0 10px 30px rgba(139,124,255,.28);
    }
    .brand-name{font-weight:800;letter-spacing:-.03em;color:#fff}
    .brand-tag{font-size:.68rem;color:#7f859e;margin-top:1px}
    .top-status{
      border:1px solid rgba(98,230,167,.18);background:rgba(98,230,167,.07);
      color:#9af0c5;border-radius:999px;padding:.38rem .65rem;font-size:.72rem;font-weight:700;
    }

    /* Hero / dashboard */
    .hero-new{
      position:relative;overflow:hidden;border:1px solid var(--line);border-radius:30px;
      padding:3.1rem 3rem;margin-bottom:1.2rem;
      background:
        linear-gradient(135deg,rgba(139,124,255,.17),rgba(94,231,255,.07) 52%,rgba(255,255,255,.025)),
        rgba(14,16,30,.72);
      box-shadow:var(--shadow);animation:rise .6s ease both;
    }
    .hero-new:before{
      content:"";position:absolute;width:430px;height:430px;right:-130px;top:-220px;border-radius:50%;
      border:1px solid rgba(139,124,255,.22);box-shadow:0 0 0 40px rgba(139,124,255,.035),0 0 0 90px rgba(94,231,255,.025);
    }
    .hero-kicker{font-size:.72rem;letter-spacing:.16em;text-transform:uppercase;color:#a9a0ff;font-weight:800}
    .hero-new h1{max-width:850px;margin:.7rem 0 1rem}
    .hero-new p{max-width:700px;color:#aeb3c7;font-size:1rem;line-height:1.7;margin:0}
    .hero-pills{display:flex;gap:.5rem;flex-wrap:wrap;margin-top:1.5rem}
    .hero-pill{border:1px solid var(--line);background:rgba(255,255,255,.045);border-radius:999px;padding:.45rem .7rem;color:#c9cde0;font-size:.73rem}

    .section-heading{display:flex;align-items:center;justify-content:space-between;gap:1rem;margin:1.7rem 0 .8rem}
    .section-heading h3{margin:0}.section-note{color:var(--muted);font-size:.76rem}
    .module-intro{color:var(--muted)!important;margin-top:-.25rem;margin-bottom:1.1rem}

    .quick-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:.85rem;margin-top:.7rem}
    .quick-card{
      min-height:175px;padding:1.2rem;border:1px solid var(--line);border-radius:22px;
      background:linear-gradient(145deg,rgba(255,255,255,.065),rgba(255,255,255,.025));
      backdrop-filter:blur(18px);box-shadow:0 12px 45px rgba(0,0,0,.12);
      transition:transform .3s cubic-bezier(.2,.8,.2,1),border-color .3s,box-shadow .3s;
    }
    .quick-card:hover{transform:translateY(-7px);border-color:rgba(139,124,255,.34);box-shadow:0 22px 55px rgba(0,0,0,.2)}
    .quick-icon{
      width:42px;height:42px;border-radius:14px;display:grid;place-items:center;
      background:linear-gradient(135deg,rgba(139,124,255,.2),rgba(94,231,255,.1));
      color:#c3bcff;font-weight:850;margin-bottom:1rem
    }
    .quick-card h4{margin:0 0 .4rem;font-size:1rem}
    .quick-card p{margin:0;color:var(--muted);font-size:.8rem;line-height:1.5}

    /* Glass components */
    [data-testid="stMetric"],[data-testid="stExpander"],[data-testid="stFileUploader"] section,
    [data-testid="stChatMessage"],.source-list,.empty-state,.source-panel,.workspace-panel{
      background:var(--panel)!important;border:1px solid var(--line)!important;
      border-radius:20px!important;box-shadow:0 12px 45px rgba(0,0,0,.12)!important;
      backdrop-filter:blur(22px);-webkit-backdrop-filter:blur(22px);
    }
    [data-testid="stMetric"]{padding:1rem 1.05rem;transition:transform .25s ease,border-color .25s ease}
    [data-testid="stMetric"]:hover{transform:translateY(-4px);border-color:rgba(139,124,255,.3)!important}
    [data-testid="stMetricLabel"] p{color:var(--muted)!important;font-size:.76rem;font-weight:650}
    [data-testid="stMetricValue"]{color:#fff!important;font-size:1.9rem;font-weight:800}

    .stButton>button,.stDownloadButton>button,[data-testid="stFormSubmitButton"] button{
      min-height:2.7rem;border-radius:13px!important;border:1px solid var(--line)!important;
      background:rgba(255,255,255,.055)!important;color:#f4f5fb!important;font-weight:700!important;
      transition:transform .2s cubic-bezier(.2,.8,.2,1),box-shadow .2s,background .2s,border-color .2s!important;
    }
    .stButton>button:hover,.stDownloadButton>button:hover,[data-testid="stFormSubmitButton"] button:hover{
      transform:translateY(-2px);background:rgba(255,255,255,.09)!important;
      border-color:rgba(139,124,255,.4)!important;box-shadow:0 10px 28px rgba(0,0,0,.2)!important;
    }
    .stButton>button:active{transform:scale(.975)}
    .stButton>button[kind="primary"],[data-testid="stFormSubmitButton"] button[kind="primary"]{
      background:linear-gradient(135deg,var(--brand),#6654e8)!important;border-color:transparent!important;
      box-shadow:0 12px 35px rgba(139,124,255,.2)!important;color:#fff!important;
    }
    .stButton>button[kind="primary"]:hover{background:linear-gradient(135deg,#9b8eff,#715ef4)!important}

    .stTextInput input,.stTextArea textarea,.stNumberInput input,[data-testid="stChatInput"] textarea{
      color:#f7f8fc!important;background:rgba(255,255,255,.045)!important;
      -webkit-text-fill-color:#f7f8fc!important;border:1px solid var(--line)!important;border-radius:13px!important;
    }
    .stTextInput input::placeholder,.stTextArea textarea::placeholder,[data-testid="stChatInput"] textarea::placeholder{
      color:#777e98!important;-webkit-text-fill-color:#777e98!important
    }
    [data-baseweb="select"]>div{background:rgba(255,255,255,.045)!important;border-color:var(--line)!important;border-radius:13px!important;color:#fff!important}
    [data-baseweb="popover"]{background:#15182a!important;border:1px solid var(--line)!important}
    [data-baseweb="popover"] [role="option"]{color:#fff!important}
    [data-testid="stTabs"] [data-baseweb="tab-list"]{gap:.35rem;border-bottom:1px solid var(--line)}
    [data-testid="stTabs"] [data-baseweb="tab"]{color:#858ba5;font-weight:700;padding:.75rem .9rem}
    [data-testid="stTabs"] [aria-selected="true"]{color:#c6c0ff!important;border-bottom-color:var(--brand)!important}
    [data-testid="stFileUploader"] section{padding:1rem}
    [data-testid="stProgressBar"]>div>div{background:linear-gradient(90deg,var(--brand),var(--brand2))}
    [data-testid="stChatMessage"]{padding:.85rem 1rem}
    hr{border-color:var(--line)!important}

    .source-panel{padding:1.15rem 1.2rem;margin:.7rem 0 1rem}
    .source-panel-head{display:flex;justify-content:space-between;align-items:center;gap:1rem;margin-bottom:.7rem}
    .source-panel-title{font-size:1rem;font-weight:800;color:#fff}
    .source-panel-sub{font-size:.74rem;color:var(--muted)}
    .source-banner{
      display:flex;gap:.65rem;align-items:center;background:rgba(98,230,167,.07);
      border:1px solid rgba(98,230,167,.2);border-radius:14px;padding:.75rem .9rem;
      color:#a4efc7;font-size:.82rem;margin:.4rem 0 .8rem
    }
    .source-list{padding:.35rem 1rem}
    .source-row{display:flex;justify-content:space-between;gap:1rem;padding:.85rem .1rem;border-bottom:1px solid var(--line)}
    .source-row:last-child{border-bottom:0}.source-title{color:#fff;font-weight:700}.source-meta{color:var(--muted);font-size:.75rem}
    .empty-state{text-align:center;padding:1.8rem;color:var(--muted)}
    .auth-panel{max-width:700px;margin:8vh auto;background:var(--panel);border:1px solid var(--line);border-radius:26px;padding:2.3rem;box-shadow:var(--shadow)}
    @keyframes rise{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:translateY(0)}}
    @media(max-width:900px){.quick-grid{grid-template-columns:1fr 1fr}}
    @media(max-width:700px){
      [data-testid="stMainBlockContainer"]{padding:.7rem .8rem 3rem}
      .hero-new{padding:2rem 1.35rem;border-radius:23px}.hero-new h1{font-size:2.35rem!important}
    }
    @media(prefers-reduced-motion:reduce){
      *,*::before,*::after{animation-duration:.01ms!important;transition-duration:.01ms!important}
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def authenticated_user_id():
    """Return a stable opaque owner key, or show a safe sign-in/setup page."""
    if LOCAL_DEMO:
        return "local"
    user = getattr(st, "user", None)
    if user and bool(getattr(user, "is_logged_in", False)):
        subject = getattr(user, "sub", None) or getattr(user, "email", None)
        if subject:
            return hashlib.sha256(str(subject).encode("utf-8")).hexdigest()
    st.markdown(
        '<div class="auth-panel"><div class="brand-lockup"><div class="brand-mark">P</div><div><div class="brand-name">prep-Nerd.ai</div><div class="brand-tag">A focused workspace for learning</div></div></div>',
        unsafe_allow_html=True,
    )
    st.title("Sign in to your study space")
    st.write("Your sources, chats, study notes, progress, and mistakes are kept in a separate account workspace.")
    if hasattr(st, "login"):
        if st.button("Continue with Google", type="primary"):
            try:
                st.login()
            except Exception as exc:
                st.error(f"Google sign-in is not configured for this Streamlit app: {exc}")
                st.info("If another Streamlit app already signs in with Google, reuse its client_id and client_secret in this app's private Secrets. Streamlit app secrets are not shared automatically. The existing Google client must also allow this app's /oauth2callback URL; a new client is not required if you can reuse the old one.")
    else:
        st.error("This Streamlit version does not support OIDC sign-in. Install the project requirements and configure Google OAuth.")
    st.caption("This app runs on Streamlit Community Cloud; Manus Website Builder login is separate and is not inherited here. Setup and credential reuse steps are in README.md. For a one-person local preview only, set PREP_NERD_LOCAL_DEMO=true.")
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()


USER_ID = authenticated_user_id()
db = Database(DB_PATH)

for key, default in {
    "answers": {}, "exam": None, "source": "", "source_id": None,
    "module": "Dashboard", "chat": [], "chat_artifact_id": None, "chat_source_id": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

MODULES = [
    "Dashboard",
    "Universal Summarizer",
    "Notes Generator",
    "Chat with Material",
    "Mock Exam",
    "Mistake Notebook",
]

if st.session_state.module not in MODULES:
    st.session_state.module = "Dashboard"
if st.session_state.get("nav_module") not in MODULES:
    st.session_state.nav_module = st.session_state.module


def go_to(target):
    st.session_state.module = target
    st.session_state.nav_module = target
    st.session_state["_nav_pulse"] = time.time()

# New persistent app shell: compact navigation rail + contextual workspace header.
with st.sidebar:
    st.markdown(
        '<div class="brand-lockup"><div class="brand-mark">P</div><div><div class="brand-name">prep-Nerd.ai</div><div class="brand-tag">AI study workspace</div></div></div>',
        unsafe_allow_html=True,
    )
    st.markdown("### Workspace")
    nav_labels = {
        "Dashboard": "⌂  Home",
        "Universal Summarizer": "✦  Summarize",
        "Notes Generator": "▤  Notes",
        "Chat with Material": "◌  Study chat",
        "Mock Exam": "◉  Mock exam",
        "Mistake Notebook": "↗  Mistakes",
    }
    
    selected_module = st.radio(
        "Navigate",
        MODULES,
        index=MODULES.index(st.session_state.module),
        format_func=lambda name: nav_labels[name],
        label_visibility="collapsed",
        key="nav_module",
    )
    module = selected_module
    st.session_state.module = module
    st.divider()
    st.markdown("**Study engine**")
    depth = st.selectbox("Analysis depth", ANALYSIS_DEPTHS, index=2, key="analysis_depth")
    st.caption(f"Model · {MODEL}")
    st.markdown(
        '<div style="margin-top:.8rem;padding:.85rem;border:1px solid rgba(255,255,255,.08);border-radius:14px;background:rgba(255,255,255,.035);color:#8e94ad;font-size:.75rem;line-height:1.55">Create notes from a topic, summarize material, take a mock exam, and ask questions without leaving your workspace.</div>',
        unsafe_allow_html=True,
    )
    st.divider()
    identity = "Local demo" if LOCAL_DEMO else (getattr(st.user, "email", None) or "Signed in")
    st.caption(f"●  {identity}")
    if not LOCAL_DEMO and hasattr(st, "logout") and st.button("Sign out", use_container_width=True):
        st.logout()

st.markdown(
    f'<div class="app-topbar"><div class="brand-lockup"><div class="brand-mark">P</div><div><div class="brand-name">{html.escape(module)}</div><div class="brand-tag">prep-Nerd.ai · focused study mode</div></div></div><div class="top-status">● Workspace ready</div></div>',
    unsafe_allow_html=True,
)


def section_title(title, subtitle=None):
    st.markdown(
        f'<div style="animation:rise .45s ease both"><div class="hero-kicker">Study workspace</div><h2 style="margin:.35rem 0 .35rem">{html.escape(title)}</h2></div>',
        unsafe_allow_html=True,
    )
    if subtitle:
        st.markdown(f'<p class="module-intro">{html.escape(subtitle)}</p>', unsafe_allow_html=True)


def source_box(scope="default"):
    safe_scope = re.sub(r"[^a-zA-Z0-9_-]", "_", scope)
    st.markdown(
        '<div class="source-panel"><div class="source-panel-head"><div><div class="source-panel-title">Build your study source</div><div class="source-panel-sub">One source powers every study tool</div></div><div class="hero-pill">STEP 1 · SOURCE</div></div>',
        unsafe_allow_html=True,
    )
    saved_sources = db.sources(user_id=USER_ID)
    if saved_sources:
        with st.expander("Use an existing source", expanded=False):
            saved_source_id = st.selectbox(
                "Saved sources", [item["id"] for item in saved_sources],
                format_func=lambda value: next((item["title"] for item in saved_sources if item["id"] == value), "Saved source"),
                key=f"saved_source_{safe_scope}",
            )
            if st.button("Load source →", key=f"load_source_{safe_scope}", use_container_width=True):
                source = next(item for item in saved_sources if item["id"] == saved_source_id)
                st.session_state.source = source["content"]
                st.session_state.source_id = source["id"]
                st.rerun()

    tab1, tab2, tab3 = st.tabs(["01 · Paste", "02 · Upload", "03 · URL"])
    with tab1:
        topic = st.text_input("Topic", key=f"topic_{safe_scope}", placeholder="e.g. Operating systems, SQL joins, cell division")
        pasted = st.text_area("Study material", key=f"pasted_{safe_scope}", height=145, placeholder="Paste notes, textbook content, lecture transcript, or your own material…")
    with tab2:
        uploaded = st.file_uploader("Drop your file here", key=f"upload_{safe_scope}", type=["txt", "pdf", "md", "markdown", "pptx", "docx"], help="TXT · PDF · Markdown · PPTX · DOCX · up to 20 MB")
    with tab3:
        url = st.text_input("Public webpage or YouTube URL", key=f"url_{safe_scope}", placeholder="https://…")

    if st.button("Create study source  →", type="primary", key=f"process_source_{safe_scope}", use_container_width=True):
        try:
            if uploaded:
                text = extract_file(uploaded)
                title, ref, kind = uploaded.name, uploaded.name, "file"
            elif url.strip():
                text, ref = extract_url(url.strip())
                title, kind = ref, "url"
            elif pasted.strip() or topic.strip():
                text = pasted.strip() or topic.strip()
                title, ref, kind = topic.strip() or "Pasted notes", "", "text"
            else:
                st.warning("Add a topic, paste material, upload a file, or enter a URL.")
                return st.session_state.get("source", "")
            if len(text.strip()) < 10:
                st.warning("This source is too short. Add more material and try again.")
                return st.session_state.get("source", "")
            source_id = db.add_source(title, kind, text, ref, user_id=USER_ID)
            st.session_state.source = text
            st.session_state.source_id = source_id
            st.success(f"Ready · {len(text):,} characters loaded")
            return text
        except Exception as exc:
            st.error(str(exc))
    current_source = st.session_state.get("source", "")
    if current_source:
        st.markdown(
            f'<div class="source-banner"><span>✓</span><span><strong>Source ready.</strong> {len(current_source):,} characters available to this tool.</span></div>',
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)
    return current_source


def ai():
    return GeminiService()


def ai_text(task, content):
    try:
        with st.spinner("Working through your material…"):
            return ai().analyze(task, content, depth)
    except AIError as exc:
        st.error(str(exc))
        return None


def notes_generator():
    section_title(
        "Notes Generator",
        "Enter a topic and choose the style of notes you want. Your notes are saved to your workspace.",
    )

    topic = st.text_input(
        "Topic name",
        placeholder="e.g. Photosynthesis, SQL joins, or World War I",
        key="notes_topic",
    )

    style_choice = st.selectbox(
        "Preferred notes style",
        [
            "Structured study notes",
            "Concise revision notes",
            "Detailed lecture notes",
            "Exam-focused notes",
            "Beginner-friendly notes",
            "Cornell notes",
            "Mind-map-style outline",
            "Custom instructions",
        ],
        key="notes_style_choice",
    )

    if style_choice == "Custom instructions":
        custom_style = st.text_input(
            "Describe the notes style you prefer",
            placeholder="e.g. Use question-and-answer format with examples",
            key="notes_custom_style",
        )
        preferred_style = custom_style.strip()
    else:
        preferred_style = style_choice

    if st.button(
        "Generate notes",
        type="primary",
        disabled=not bool(topic.strip()) or not bool(preferred_style),
        key="generate_topic_notes",
    ):
        prompt = f"""
You are a careful and helpful study tutor. Create clear, accurate study notes
about the topic below, using general knowledge.

Follow the requested notes style. Organize the notes with useful headings.
Include key ideas, definitions, explanations, and examples where appropriate.
For broad topics, organize the material into manageable sections. Do not claim
the notes are based on a supplied document or cite sources you have not checked.

Topic: {topic.strip()}

Preferred notes style: {preferred_style}
"""
        try:
            with st.spinner("Preparing your notes…"):
                output = ai().generate(prompt)

            artifact_id = db.save(
                "notes",
                topic.strip(),
                {
                    "topic": topic.strip(),
                    "style": preferred_style,
                    "text": output,
                },
                user_id=USER_ID,
            )
            st.session_state["notes_output"] = output
            st.session_state["notes_output_id"] = artifact_id
            st.session_state["notes_output_title"] = topic.strip()
            st.rerun()
        except AIError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Could not save your notes: {exc}")

    output = st.session_state.get("notes_output")
    if output:
        st.markdown("### Your notes")
        st.markdown(output)
        filename = re.sub(
            r"[^A-Za-z0-9._-]+",
            "_",
            st.session_state.get("notes_output_title", "study-notes"),
        ).strip("._") or "study-notes"
        st.download_button(
            "Download notes as text",
            output,
            file_name=f"{filename}.txt",
            mime="text/plain",
            key="download_topic_notes",
        )

    saved_notes = db.artifacts("notes", user_id=USER_ID)
    if saved_notes:
        with st.expander("Previously generated notes"):
            selected_id = st.selectbox(
                "Saved note sets",
                [item["id"] for item in saved_notes],
                format_func=lambda value: next(
                    (item["title"] for item in saved_notes if item["id"] == value),
                    "Saved notes",
                ),
                key="saved_notes_picker",
            )
            if st.button("Load saved notes", key="load_saved_notes"):
                selected = next(
                    item for item in saved_notes if item["id"] == selected_id
                )
                payload = selected.get("payload", {})
                st.session_state["notes_output"] = payload.get("text", "")
                st.session_state["notes_output_id"] = selected["id"]
                st.session_state["notes_output_title"] = selected["title"]
                st.rerun()


def dashboard():
    sources = db.sources(user_id=USER_ID)
    notes_count = len(db.artifacts("notes", user_id=USER_ID))
    mistakes_count = sum(item["status"] != "Reviewed" for item in db.mistakes(user_id=USER_ID))

    st.markdown(
        '<div class="hero-new"><div class="hero-kicker">PERSONAL LEARNING OS</div><h1>Study less randomly.<br>Learn with a system.</h1><p>Bring your material into one workspace, then move through the shortest useful path: understand → make notes → practice → fix.</p><div class="hero-pills"><span class="hero-pill">AI summaries</span><span class="hero-pill">Topic notes</span><span class="hero-pill">Mock exams</span><span class="hero-pill">Mistake tracking</span></div></div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section-heading"><h3>Today at a glance</h3><span class="section-note">Your current workspace</span></div>', unsafe_allow_html=True)
    cols = st.columns(3)
    for col, (label, value) in zip(cols, [("Sources", len(sources)), ("Note sets", notes_count), ("Open mistakes", mistakes_count)]):
        with col:
            st.metric(label, value)

    st.markdown('<div class="section-heading"><h3>Choose your next move</h3><span class="section-note">Designed as a learning flow, not a menu</span></div>', unsafe_allow_html=True)
    tools = [
        ("✦", "Understand", "Universal Summarizer", "Turn dense material into a clean explanation, outline, or revision summary."),
        ("▤", "Create", "Notes Generator", "Create and save study notes from a topic in your preferred style."),
        ("◌", "Ask", "Chat with Material", "Ask questions and get answers grounded in the material you loaded."),
        ("◉", "Practice", "Mock Exam", "Generate a timed exam and expose the topics you actually struggle with."),
        ("↗", "Fix", "Mistake Notebook", "Review missed questions instead of repeatedly studying what you already know."),
    ]
    for start_i in range(0, len(tools), 3):
        cols = st.columns(3)
        for col, (icon, stage, title, description) in zip(cols, tools[start_i:start_i+3]):
            with col:
                st.markdown(
                    f'<div class="quick-card"><div class="quick-icon">{icon}</div><div style="font-size:.68rem;color:#858ba5;font-weight:800;letter-spacing:.12em;text-transform:uppercase">{stage}</div><h4>{title}</h4><p>{description}</p></div>',
                    unsafe_allow_html=True,
                )
                st.button(f"Open {title}  →", key=f"open_{title}", on_click=go_to, args=(title,), use_container_width=True)

    st.markdown('<div class="section-heading"><h3>Recent material</h3><span class="section-note">Your saved sources</span></div>', unsafe_allow_html=True)
    if sources:
        rows=[]
        for source in sources[:6]:
            title=html.escape(str(source.get("title","Untitled source")))
            kind=html.escape(str(source.get("kind","source")).title())
            created=html.escape(str(source.get("created_at","")))
            rows.append(f'<div class="source-row"><span class="source-title">{title}</span><span class="source-meta">{kind} · {created}</span></div>')
        st.markdown('<div class="source-list">'+''.join(rows)+'</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="empty-state"><strong>No study source yet.</strong><br>Open any tool and create one. It will become reusable across your workspace.</div>', unsafe_allow_html=True)


def mock_exam():
    section_title("Mock Exam", "Practice under a timer, then review your answers and mistakes.")
    content = source_box("mock-exam")
    col1, col2 = st.columns(2)
    with col1:
        count = st.selectbox("Number of questions", QUESTION_COUNTS, index=0, key="exam_question_count")
    with col2:
        difficulty = st.selectbox("Difficulty", DIFFICULTIES, index=1, key="exam_difficulty")
    minutes = st.slider("Time limit", 5, 90, 20, format="%d minutes", key="exam_time_limit")
    st.caption("Your answers are kept as you move through the exam. Correct answers and explanations appear after submission.")

    if st.button("Generate mock exam", type="primary", disabled=not bool(content), key="generate_mock_exam"):
        prompt = (
            f'Create exactly {count} unique multiple-choice questions at {difficulty} difficulty. '
            f'Return ONLY JSON: {{"questions":[{{"question":str,"options":{{"A":str,"B":str,"C":str,"D":str}},'
            f'"correct_answer":"A|B|C|D","explanation":str,"hint":str,"topic":str,"difficulty":str}}]}}. Source: {content}'
        )
        try:
            parsed = QuizPayload.model_validate(ai().json(prompt)).model_dump()
            st.session_state.exam = {
                "questions": parsed["questions"],
                "started": time.time(),
                "limit": minutes * 60,
                "submitted": False,
                "results_saved": False,
            }
            st.session_state.answers = {}
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    state = st.session_state.exam
    if not state:
        return

    questions = state["questions"]
    submitted = state.get("submitted", False)
    if not submitted:
        remaining = max(0, int(state["limit"] - (time.time() - state["started"])))
        st.progress(len(st.session_state.answers) / max(1, len(questions)))
        st.markdown(f"**Time remaining** · {remaining // 60:02d}:{remaining % 60:02d}")
        if remaining <= 0:
            submitted = True
            state["submitted"] = True
            st.warning("Time expired. Your exam has been submitted.")

    for index, question in enumerate(questions):
        st.markdown(f"#### {index + 1}. {question['question']}")
        choice = st.radio(
            "Choose one answer",
            list(question["options"]),
            format_func=lambda key, options=question["options"]: f"{key}. {options[key]}",
            key=f"exam_{index}",
            index=None,
            disabled=submitted,
            label_visibility="collapsed",
        )
        if choice:
            st.session_state.answers[index] = choice
        if submitted:
            st.markdown(
                f"**Correct answer: {question['correct_answer']}** · {question['explanation']}"
            )
        st.divider()

    if st.button("Submit exam", disabled=submitted, key="submit_mock_exam"):
        state["submitted"] = True
        st.rerun()

    if submitted:
        result = score_questions(questions, st.session_state.answers)
        st.success(
            f"Your score: **{result['correct']} / {result['total']}** · "
            f"{result['percentage']}% · {result['unanswered']} unanswered"
        )
        if not state.get("results_saved"):
            db.save("exam_results", "Mock Exam", result, user_id=USER_ID)
            for index, question in enumerate(questions):
                if st.session_state.answers.get(index) != question["correct_answer"]:
                    db.add_mistake(
                        mistake_from_question(question, st.session_state.answers.get(index)),
                        user_id=USER_ID,
                    )
            state["results_saved"] = True
        if st.button("Start a new mock exam", key="new_mock_exam"):
            st.session_state.answers = {}
            st.session_state.exam = None
            st.rerun()


def text_module(kind, label, task):
    description = "Choose a source and a format; your draft is saved to your account so you can copy or download it." if kind == "summary" else "Turn a source into organized revision notes with the details that matter most."
    section_title(label, description)
    content = source_box(kind)
    saved_drafts = db.artifacts(kind, user_id=USER_ID)
    if saved_drafts:
        with st.expander("Open a saved draft", expanded=False):
            saved_draft_id = st.selectbox(
                "Saved drafts", [item["id"] for item in saved_drafts],
                format_func=lambda value: next((item["title"] for item in saved_drafts if item["id"] == value), "Saved draft"),
                key=f"saved_draft_{kind}",
            )
            if st.button("Load selected draft", key=f"load_draft_{kind}"):
                selected_draft = next(item for item in saved_drafts if item["id"] == saved_draft_id)
                payload = selected_draft.get("payload", {})
                if isinstance(payload, dict) and payload.get("text"):
                    st.session_state[f"output_{kind}"] = payload["text"]
                    st.session_state[f"output_id_{kind}"] = selected_draft["id"]
                    st.session_state[f"edit_output_{kind}"] = payload["text"]
                    st.rerun()
    styles = SUMMARY_STYLES if kind == "summary" else ["Concise revision notes", "Detailed study notes"]
    style = st.selectbox("Output style", styles, key=f"style_{kind}")
    if st.button(f"Generate {label.lower()}", type="primary", disabled=not bool(content), key=f"generate_{kind}"):
        output = ai_text(
            f"{task}. Style: {style}. Use headings, definitions, key concepts, examples, comparisons, formulas where relevant, revision points, and possible exam questions.",
            content,
        )
        if output:
            artifact_id = db.save(kind, label, {"text": output, "style": style, "source_hash": content_hash(content)}, user_id=USER_ID)
            st.session_state[f"output_{kind}"] = output
            st.session_state[f"output_id_{kind}"] = artifact_id
            st.session_state[f"edit_output_{kind}"] = output
            st.rerun()
    output = st.session_state.get(f"output_{kind}")
    if output:
        st.markdown('<div class="section-heading"><h3>Your draft</h3><span class="section-note">Edit and save your changes</span></div>', unsafe_allow_html=True)
        edited = st.text_area("Generated content", output, height=430, key=f"edit_output_{kind}", label_visibility="collapsed")
        c1, c2 = st.columns([1, 3])
        if c1.button("Save changes", key=f"save_output_{kind}"):
            artifact_id = st.session_state.get(f"output_id_{kind}")
            payload = {"text": edited, "style": style, "source_hash": content_hash(content) if content else ""}
            if artifact_id and db.update_artifact(artifact_id, payload, user_id=USER_ID):
                st.session_state[f"output_{kind}"] = edited
                st.success("Draft saved to your account.")
            else:
                st.error("This draft could not be updated. Generate it again and retry.")
        c2.download_button("Download as text", edited, file_name=f"{kind}.txt", mime="text/plain", key=f"download_{kind}")


def mistakes():
    section_title("Mistake Notebook", "A practical, searchable list of questions worth another look.")
    items = db.mistakes(user_id=USER_ID)
    search = st.text_input("Search by question or topic", placeholder="Try a keyword…", key="mistake_search")
    if not items:
        st.markdown('<div class="empty-state"><strong>Your notebook is clear.</strong><br>Missed answers from completed quizzes and exams will appear here.</div>', unsafe_allow_html=True)
        return
    shown = 0
    for item in items:
        payload = item["payload"]
        haystack = f"{payload.get('question', '')} {payload.get('topic', '')}".lower()
        if search and search.lower() not in haystack:
            continue
        shown += 1
        with st.expander(f"{payload.get('topic', 'Review')} · {item.get('status', 'To review')} · {payload.get('question', '')}"):
            st.markdown(f"**Your answer:** {payload.get('selected_answer') or 'Unanswered'}  ·  **Correct:** {payload.get('correct_answer', '—')}")
            st.caption(payload.get("explanation", ""))
            if item.get("status") != "Reviewed" and st.button("Mark as reviewed", key=f"mark_{item['id']}"):
                db.update_mistake(item["id"], "Reviewed", user_id=USER_ID)
                st.rerun()
    if not shown:
        st.info("No mistakes match that search.")


def chat():
    section_title("Chat with Material", "Ask naturally. Answers use relevant passages from your notes and keep extra context clearly labeled.")
    content = source_box("chat")
    if not content:
        st.info("Add study material above to start a grounded conversation.")
        return
    source_id = st.session_state.get("source_id")
    if source_id != st.session_state.get("chat_source_id"):
        stored = next((item for item in db.artifacts("chat", user_id=USER_ID) if item.get("title") == f"chat:{source_id}"), None)
        payload = stored.get("payload", {}) if stored else {}
        st.session_state.chat = payload.get("messages", []) if isinstance(payload, dict) else []
        st.session_state.chat_artifact_id = stored.get("id") if stored else None
        st.session_state.chat_source_id = source_id
    question = st.chat_input("Ask about a concept, synonym, example, or follow-up…")
    if question:
        history = list(st.session_state.get("chat", []))
        history.append({"role": "user", "content": question})
        ai_history = [(item.get("role", "user"), item.get("content", "")) for item in st.session_state.chat]
        try:
            with st.spinner("Finding relevant passages and composing an answer…"):
                answer = ai().answer_question(question, content, history=ai_history)
            history.append({"role": "assistant", "content": answer})
            st.session_state.chat = history
            payload = {"source_id": source_id, "messages": history}
            artifact_id = st.session_state.get("chat_artifact_id")
            if artifact_id and db.update_artifact(artifact_id, payload, user_id=USER_ID):
                pass
            else:
                st.session_state.chat_artifact_id = db.save("chat", f"chat:{source_id}", payload, user_id=USER_ID)
        except AIError as exc:
            st.error(str(exc))
    for message in st.session_state.get("chat", []):
        with st.chat_message(message.get("role", "assistant")):
            st.write(message.get("content", ""))
    if st.session_state.get("chat") and st.button("Clear conversation", key="clear_chat"):
        st.session_state.chat = []
        artifact_id = st.session_state.get("chat_artifact_id")
        if artifact_id:
            db.update_artifact(artifact_id, {"source_id": source_id, "messages": []}, user_id=USER_ID)
        st.rerun()


if module == "Dashboard":
    dashboard()
elif module == "Mock Exam":
    mock_exam()
elif module == "Universal Summarizer":
    text_module("summary", "Universal Summarizer", "Summarize the source")
elif module == "Notes Generator":
    notes_generator()
elif module == "Mistake Notebook":
    mistakes()
elif module == "Chat with Material":
    chat()
