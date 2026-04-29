from __future__ import annotations

import html
import json

import pandas as pd
import requests
import streamlit as st


# ── HTML 转义工具 ───────────────────────────────────────────────────────────
def escape_html(text: str) -> str:
    """转义 HTML 特殊字符，防止 XSS 注入"""
    return html.escape(str(text), quote=True)

# ── Config ────────────────────────────────────────────────────────────────────
API_BASE = "http://localhost:8000"
PRIORITY_EMOJI = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}
PRIORITY_COLOR_CSS = {"High": "#dc3545", "Medium": "#ffc107", "Low": "#28a745"}

st.set_page_config(
    page_title="AI 测试用例生成器",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Light mode (default) ── */
:root {
    --bg-base: #f0f2f6;
    --bg-card: #ffffff;
    --bg-sidebar: #1e2a3a;
    --text-primary: #1e2a3a;
    --text-secondary: #ffffff;
    --text-muted: #6c757d;
    --border-color: #dee2e6;
    --accent: #4a90d9;
    --accent-hover: #3a7fc8;
    --shadow: rgba(0,0,0,0.06);
    --shadow-hover: rgba(0,0,0,0.12);

    /* Priority */
    --p0-color: #dc3545;
    --p0-bg: #fde8e8;
    --p1-color: #d39e00;
    --p1-bg: #fef9e7;
    --p2-color: #28a745;
    --p2-bg: #e8f5e9;

    /* Tags */
    --tag-feature-bg: #e3edf7;
    --tag-feature-color: #2c5aa0;
    --tag-rule-bg: #fef9e7;
    --tag-rule-border: #f0b429;
    --tag-boundary-bg: #fdf2f2;
    --tag-question-bg: #f2f2f2;

    /* Upload */
    --upload-border: #c8d6e5;
    --upload-hover-border: #4a90d9;
}

/* ── Dark mode ── */
@media (prefers-color-scheme: dark) {
    :root {
        --bg-base: #0e1117;
        --bg-card: #1c1f2b;
        --text-primary: #e8eaf0;
        --text-muted: #9ca3af;
        --border-color: #2d3142;
        --shadow: rgba(0,0,0,0.3);
        --shadow-hover: rgba(0,0,0,0.5);

        --p0-bg: rgba(220, 53, 69, 0.15);
        --p1-bg: rgba(211, 158, 0, 0.15);
        --p2-bg: rgba(40, 167, 69, 0.15);

        --tag-feature-bg: rgba(44, 90, 160, 0.25);
        --tag-feature-color: #7eb8ff;
        --tag-rule-bg: rgba(240, 180, 41, 0.15);
        --tag-boundary-bg: rgba(220, 53, 69, 0.15);
        --tag-question-bg: rgba(134, 142, 150, 0.2);

        --upload-border: #2d3142;
        --upload-hover-border: #4a90d9;
    }
}

/* ── Base ── */
.stApp { background: var(--bg-base); }

/* Sidebar */
section[data-testid="stSidebar"] { background: var(--bg-sidebar); }
.sidebar-title { color: #ffffff; font-size: 1.1rem; font-weight: 700; margin-bottom: 0.5rem; }
.sidebar-stat { color: #a8c1d8; font-size: 0.85rem; }
.sidebar-stat strong { color: #ffffff; }

/* Cards */
.card, .analysis-section, .tc-card {
    background: var(--bg-card);
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1rem;
    box-shadow: 0 2px 8px var(--shadow);
    color: var(--text-primary);
    transition: transform 0.15s, box-shadow 0.15s;
}
.tc-card { border-left: 5px solid var(--border-color); }
.tc-card:hover { transform: translateY(-2px); box-shadow: 0 4px 16px var(--shadow-hover); }
.card-title, .section-header { font-size: 1rem; font-weight: 700; color: var(--text-primary);
    border-bottom: 2px solid var(--accent); padding-bottom: 0.5rem; margin-bottom: 1rem; }

/* Upload zone */
.upload-zone {
    border: 2px dashed var(--upload-border);
    border-radius: 12px;
    padding: 3rem 2rem;
    text-align: center;
    margin: 2rem 0;
    background: var(--bg-card);
    color: var(--text-primary);
    transition: all 0.2s;
}
.upload-zone:hover { border-color: var(--upload-hover-border); }

/* Analysis tags */
.feature-tag {
    display: inline-block;
    background: var(--tag-feature-bg);
    color: var(--tag-feature-color);
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.85rem;
    margin: 3px 3px 3px 0;
}
.rule-item {
    background: var(--tag-rule-bg);
    border-left: 3px solid var(--tag-rule-border);
    padding: 8px 12px;
    margin-bottom: 6px;
    border-radius: 0 6px 6px 0;
    font-size: 0.9rem;
    color: var(--text-primary);
}
.boundary-item {
    background: var(--tag-boundary-bg);
    border-left: 3px solid var(--p0-color);
    padding: 8px 12px;
    margin-bottom: 6px;
    border-radius: 0 6px 6px 0;
    font-size: 0.9rem;
    color: var(--text-primary);
}
.question-item {
    background: var(--tag-question-bg);
    border-left: 3px solid var(--text-muted);
    padding: 8px 12px;
    margin-bottom: 6px;
    border-radius: 0 6px 6px 0;
    font-size: 0.9rem;
    font-style: italic;
    color: var(--text-primary);
}

/* Priority cards */
.tc-p0 { border-left-color: var(--p0-color); }
.tc-p1 { border-left-color: var(--p1-color); }
.tc-p2 { border-left-color: var(--p2-color); }

/* Priority badges */
.badge { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 0.8rem; font-weight: 700; }
.badge-p0 { background: var(--p0-bg); color: var(--p0-color); }
.badge-p1 { background: var(--p1-bg); color: var(--p1-color); }
.badge-p2 { background: var(--p2-bg); color: var(--p2-color); }

/* Step number circle */
.step-number {
    display: inline-flex; align-items: center; justify-content: center;
    width: 28px; height: 28px; background: var(--accent); color: white;
    border-radius: 50%; font-weight: 700; font-size: 0.85rem; margin-right: 8px;
}

/* Buttons */
.stButton > button { border-radius: 8px; font-weight: 600; }
.stButton > button.primary { background: var(--accent); color: white; border: none; }
.stButton > button.primary:hover { background: var(--accent-hover); }

/* Expander */
.streamlit-expanderHeader { border-radius: 8px; }

/* Progress bar */
.stProgress > div > div { background: var(--accent); }

/* Metric */
.stMetric {
    background: var(--bg-card);
    border-radius: 10px;
    padding: 1rem;
    text-align: center;
    box-shadow: 0 2px 8px var(--shadow);
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] { gap: 8px; }
.stTabs [data-baseweb="tab"] {
    border-radius: 8px 8px 0 0;
    padding: 6px 16px;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)


# ── API helpers ────────────────────────────────────────────────────────────────

# ── API Key 管理 ───────────────────────────────────────────────────────────────
def _get_api_headers() -> dict:
    """获取 API 请求头，包含可选的 API Key"""
    api_key = st.session_state.get("api_key", "")
    if api_key:
        return {"X-API-Key": api_key}
    return {}


def _handle_error(exc: Exception, fallback_msg: str) -> None:
    """Show error message safely (handles malformed HTTP error responses)."""
    msg = fallback_msg
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        try:
            msg = exc.response.json().get("detail", fallback_msg)
        except Exception:
            msg = exc.response.text[:120] if exc.response.text else fallback_msg
    st.error(f"❌ {msg}")


def upload_document(file_bytes: bytes, filename: str) -> dict | None:
    try:
        r = requests.post(f"{API_BASE}/documents/upload", files={"file": (filename, file_bytes)}, headers=_get_api_headers(), timeout=300)
        r.raise_for_status()
        return r.json()
    except requests.HTTPError as exc:
        try:
            detail = exc.response.json().get("detail", "文档上传失败")
        except Exception:
            detail = exc.response.text[:120] if exc.response.text else "文档上传失败"
        st.error(f"❌ {detail}")
    except requests.ConnectionError:
        st.error("❌ 无法连接到后端服务，请确认已启动 `python main.py`")
    except Exception as exc:
        st.error(f"❌ 发生未知错误：{exc}")
    return None


def retry_analyze(document_id: str) -> dict | None:
    try:
        r = requests.post(f"{API_BASE}/documents/{document_id}/analyze", headers=_get_api_headers(), timeout=300)
        r.raise_for_status()
        return r.json()
    except requests.HTTPError as exc:
        try:
            detail = exc.response.json().get("detail", "分析重试失败")
        except Exception:
            detail = exc.response.text[:200] if exc.response.text else "分析重试失败"
        st.error(f"❌ 分析重试失败：{detail}")
    except requests.ConnectionError:
        st.error("❌ 无法连接到后端，请确认 `python main.py` 已启动")
    except Exception as exc:
        st.error(f"❌ 发生异常：{type(exc).__name__} — {exc}")
    return None


def fetch_analysis(document_id: str) -> dict | None:
    try:
        r = requests.get(f"{API_BASE}/documents/{document_id}/analysis", headers=_get_api_headers(), timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.HTTPError as exc:
        _handle_error(exc, "获取分析结果失败")
    except Exception as exc:
        st.error(f"❌ {exc}")
    return None


def generate_test_cases(document_id: str) -> dict | None:
    try:
        r = requests.post(f"{API_BASE}/documents/{document_id}/generate", headers=_get_api_headers(), timeout=1200)
        r.raise_for_status()
        return r.json()
    except requests.HTTPError as exc:
        _handle_error(exc, "测试用例生成失败")
    except requests.ConnectionError:
        st.error("❌ 连接断开，请重试")
    except Exception as exc:
        st.error(f"❌ {exc}")
    return None


def fetch_stats() -> dict:
    try:
        r = requests.get(f"{API_BASE}/knowledge-base/stats", headers=_get_api_headers(), timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {}


# ── Session init ─────────────────────────────────────────────────────────────
for key, default in [
    ("step", "upload"),       # upload | confirm | results
    ("document_id", None),
    ("analysis", None),
    ("test_cases", None),
    ("upload_result", None),
    ("api_key", ""),          # API 认证密钥
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="sidebar-title">🧪 AI 测试用例生成器</div>', unsafe_allow_html=True)
    st.markdown("基于 RAG 的智能测试用例生成平台", unsafe_allow_html=True)
    st.divider()

    # API 密钥配置
    st.session_state["api_key"] = st.text_input(
        "🔑 API 密钥",
        value=st.session_state.get("api_key", ""),
        type="password",
        help="留空则使用开发模式（无认证）",
    )
    st.divider()

    stats = fetch_stats()
    col_a, col_b = st.columns(2)
    with col_a:
        st.metric("📄 分析文档", stats.get("analyzed_documents", 0))
        st.metric("🧩 向量块", stats.get("requirement_chunk_vectors", 0))
    with col_b:
        st.metric("✅ 生成用例", stats.get("generated_test_cases", 0))
        st.metric("📊 分析条目", stats.get("requirement_analysis_vectors", 0))

    st.divider()

    if st.button("🔄 刷新状态", use_container_width=True):
        st.rerun()

    if st.session_state["step"] != "upload":
        if st.button("🗑️ 重新开始", use_container_width=True):
            st.session_state["step"] = "upload"
            st.session_state["document_id"] = None
            st.session_state["analysis"] = None
            st.session_state["test_cases"] = None
            st.session_state["upload_result"] = None
            st.rerun()


# ── STEP 1: Upload ────────────────────────────────────────────────────────────
if st.session_state["step"] == "upload":
    st.title("📋 需求文档分析与测试生成")

    col_intro, _ = st.columns([3, 1])
    with col_intro:
        st.markdown("""
        <div class="card">
        <b>使用方法：</b><br>
        1️⃣ 上传软件需求文档（PDF、DOCX、Markdown、TXT）<br>
        2️⃣ AI 自动解析需求，提取功能点、业务规则、边界条件<br>
        3️⃣ 确认分析结果后，一键生成完整测试用例<br>
        4️⃣ 导出 JSON 或 CSV 格式
        </div>
        """, unsafe_allow_html=True)

    st.markdown("### 📤 上传需求文档")
    uploaded_file = st.file_uploader(
        "拖拽或点击选择文件",
        type=["pdf", "docx", "md", "txt"],
        label_visibility="collapsed",
        help="支持 PDF、DOCX、Markdown、TXT 格式",
    )

    if uploaded_file is not None:
        st.info(f"已选择：**{uploaded_file.name}**（{uploaded_file.size / 1024:.1f} KB）")

        if st.button("🚀 开始分析文档", type="primary", use_container_width=True):
            progress_bar = st.progress(0, text="正在上传并分析...")
            progress_bar.progress(20, text="📤 上传文件 + AI 分析...")
            result = upload_document(uploaded_file.getvalue(), uploaded_file.name)
            progress_bar.progress(100)

            if result is not None:
                doc_id = result["document_id"]
                status = result.get("status", "")
                msg = result.get("message", "")
                is_dup = result.get("duplicate", False)

                st.session_state["upload_result"] = result
                st.session_state["document_id"] = doc_id

                if is_dup:
                    st.warning(f"⚠️ 检测到重复文档（ID: {doc_id}），已复用已有记录")
                    analysis = fetch_analysis(doc_id)
                    st.session_state["analysis"] = analysis
                    st.session_state["step"] = "confirm"
                    st.rerun()
                elif status == "analyzed":
                    analysis = fetch_analysis(doc_id)
                    st.session_state["analysis"] = analysis
                    st.session_state["step"] = "confirm"
                    st.rerun()
                elif status == "analysis_failed":
                    # 分析失败，但文档已存——用占位符进入确认页，提供重试按钮
                    st.warning(f"⚠️ 分析暂时失败：{msg or 'AI 服务不可用'}。文档已保存，可点击下方「重试分析」按钮")
                    st.session_state["analysis"] = None  # 无有效分析
                    st.session_state["step"] = "confirm"
                    st.rerun()
                else:
                    st.error(f"❌ 状态异常：{status} — {msg}")
                progress_bar.empty()
            else:
                progress_bar.empty()


# ── STEP 2: Confirm Analysis ─────────────────────────────────────────────────
elif st.session_state["step"] == "confirm":
    st.title("🔍 需求分析确认")

    doc_id = st.session_state["document_id"]
    result = st.session_state.get("upload_result") or {}
    artifact = st.session_state.get("analysis") or {}

    # 分析失败时：显示重试按钮
    if not artifact:
        st.warning("⚠️ 分析暂时失败，文档已保存。点击下方按钮重试分析")
        if st.button("🔄 重试分析", type="primary", use_container_width=True):
            progress_bar = st.progress(0, text="正在重新分析...")
            progress_bar.progress(30, text="AI 正在分析需求...")
            new_analysis = retry_analyze(doc_id)
            progress_bar.progress(100)
            if new_analysis is not None:
                st.session_state["analysis"] = new_analysis
                st.rerun()
            else:
                progress_bar.empty()
                st.error("❌ 重试失败，请稍后再次尝试")
        with st.container():
            st.markdown("""
            <div style="text-align:center; color:#888; margin:1rem 0;">
                或点击下方按钮重新上传文档
            </div>
            """, unsafe_allow_html=True)
            if st.button("📤 重新上传", use_container_width=True):
                st.session_state["step"] = "upload"
                st.session_state["document_id"] = None
                st.session_state["analysis"] = None
                st.session_state["test_cases"] = None
                st.session_state["upload_result"] = None
                st.rerun()
        st.stop()

    # 分析正常时
    st.info("💡 请确认 AI 对需求的理解是否准确，如有遗漏可重新上传。")

    if result.get("duplicate"):
        st.warning("⚠️ 检测到重复文档，已复用已有记录")

    # Tabs: Summary | Features | Rules | Boundaries | Questions
    tabs = st.tabs(["📝 摘要", "🛠️ 功能特性", "📏 业务规则", "🚧 边界条件", "❓ 待澄清"])

    with tabs[0]:
        summary = escape_html(artifact.get('summary', '（无）') or '（无）')
        st.markdown(f"""
        <div class="analysis-section">
            <div class="section-header">📝 需求概述</div>
            <p style="font-size:1rem; line-height:1.7;">{summary}</p>
        </div>
        """, unsafe_allow_html=True)

    with tabs[1]:
        features = [escape_html(f) for f in (artifact.get("features") or [])]
        if features:
            tags_html = "".join(f'<span class="feature-tag">• {f}</span>' for f in features)
            st.markdown(f"""
            <div class="analysis-section">
                <div class="section-header">🛠️ 识别到的功能点（共 {len(features)} 项）</div>
                {tags_html}
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown('<div class="analysis-section"><i>（未识别到功能点）</i></div>', unsafe_allow_html=True)

    with tabs[2]:
        rules = [escape_html(r) for r in (artifact.get("business_rules") or [])]
        if rules:
            rules_html = "".join(f'<div class="rule-item">• {r}</div>' for r in rules)
            st.markdown(f"""
            <div class="analysis-section">
                <div class="section-header">📏 业务规则（共 {len(rules)} 条）</div>
                {rules_html}
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown('<div class="analysis-section"><i>（未识别到业务规则）</i></div>', unsafe_allow_html=True)

    with tabs[3]:
        boundaries = [escape_html(b) for b in (artifact.get("boundary_conditions") or [])]
        if boundaries:
            bdry_html = "".join(f'<div class="boundary-item">• {b}</div>' for b in boundaries)
            st.markdown(f"""
            <div class="analysis-section">
                <div class="section-header">🚧 边界条件（共 {len(boundaries)} 项）</div>
                {bdry_html}
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown('<div class="analysis-section"><i>（未识别到边界条件）</i></div>', unsafe_allow_html=True)

    with tabs[4]:
        questions = [escape_html(q) for q in (artifact.get("open_questions") or [])]
        if questions:
            q_html = "".join(f'<div class="question-item">• {q}</div>' for q in questions)
            st.markdown(f"""
            <div class="analysis-section">
                <div class="section-header">❓ 待澄清问题（共 {len(questions)} 项）</div>
                {q_html}
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown('<div class="analysis-section"><i>（无待澄清问题）</i></div>', unsafe_allow_html=True)

        # 只有在有有效分析结果时才显示tabs和生成按钮
    if artifact and artifact.get("summary"):
        st.divider()
        col_gen, col_reupload = st.columns(2)
        with col_gen:
            if st.button("✅ 确认无误，生成测试用例", type="primary", use_container_width=True):
                with st.spinner("AI 正在生成测试用例，请耐心等待（预计 5-15 分钟）..."):
                    gen_result = generate_test_cases(doc_id)
                if gen_result is not None:
                    st.session_state["test_cases"] = gen_result
                    st.session_state["step"] = "results"
                    st.rerun()
                else:
                    st.error("生成失败，请重试")
        with col_reupload:
            if st.button("📤 重新上传", use_container_width=True):
                st.session_state["step"] = "upload"
                st.rerun()
    else:
        st.divider()
        if st.button("📤 重新上传", use_container_width=True):
            st.session_state["step"] = "upload"
            st.rerun()


# ── STEP 3: Results ──────────────────────────────────────────────────────────
elif st.session_state["step"] == "results":
    gen = st.session_state.get("test_cases") or {}
    test_cases = gen.get("test_cases") or []
    doc_id = st.session_state["document_id"]

    st.title("✅ 测试用例生成结果")

    # Summary metrics
    m_col1, m_col2, m_col3 = st.columns(3)
    m_col1.metric("📋 用例总数", len(test_cases))
    m_col2.metric("🔗 引用历史上下文", gen.get("retrieved_context_count", 0))
    high_count = sum(1 for tc in test_cases if tc.get("优先级") == "P0")
    med_count = sum(1 for tc in test_cases if tc.get("优先级") == "P1")
    low_count = sum(1 for tc in test_cases if tc.get("优先级") == "P2")
    m_col3.metric("🔴 P0/P1/P2", f"{high_count} / {med_count} / {low_count}")

    st.divider()

    # Export buttons
    df = pd.DataFrame([{
        "编号": tc.get("编号", ""),
        "标题": tc.get("标题", ""),
        "目录": tc.get("目录", ""),
        "负责人": tc.get("负责人", ""),
        "前置条件": "；".join(tc.get("前置条件", [])),
        "步骤描述": "；".join(tc.get("步骤描述", [])),
        "预期结果": "；".join(tc.get("预期结果", [])),
        "优先级": tc.get("优先级", ""),
        "类型": tc.get("类型", ""),
        "来源": "；".join(tc.get("来源", [])),
    } for tc in test_cases])

    e_col1, e_col2 = st.columns(2)
    with e_col1:
        st.download_button(
            "📥 下载 JSON",
            data=json.dumps(test_cases, ensure_ascii=False, indent=2),
            file_name="test_cases.json",
            mime="application/json",
            use_container_width=True,
        )
    with e_col2:
        st.download_button(
            "📥 下载 CSV",
            data=df.to_csv(index=False).encode("utf-8-sig"),
            file_name="test_cases.csv",
            mime="text/csv",
            use_container_width=True,
        )

    st.divider()

    # Group by priority
    for priority in ("P0", "P1", "P2"):
        group = [tc for tc in test_cases if tc.get("优先级") == priority]
        if not group:
            continue

        css_class = f"tc-{priority.lower()}"
        badge_html = f'<span class="badge badge-{priority.lower()}">{priority}</span>'

        st.markdown(f"### {badge_html} {priority}（{len(group)} 条）", unsafe_allow_html=True)

        for tc in group:
            tc_id = escape_html(tc.get("编号", "?"))
            title = escape_html(tc.get("标题", "无标题"))
            directory = escape_html(tc.get("目录", ""))
            owner = escape_html(tc.get("负责人", ""))
            test_type = escape_html(tc.get("类型", ""))
            preconditions = [escape_html(p) for p in (tc.get("前置条件") or [])]
            steps = [escape_html(s) for s in (tc.get("步骤描述") or [])]
            expected = [escape_html(e) for e in (tc.get("预期结果") or [])]
            source_refs = [escape_html(r) for r in (tc.get("来源") or [])]

            with st.container():
                meta_line = " | ".join(filter(None, [directory, f"类型:{test_type}", f"负责人:{owner}"]))
                st.markdown(f"""
                <div class="tc-card {css_class}">
                    <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:0.5rem;">
                        <div style="font-weight:700; font-size:1rem;">[{tc_id}] {title}</div>
                        {badge_html}
                    </div>
                    {f'<div style="font-size:0.8rem; color:#888; margin-bottom:0.75rem;">{escape_html(meta_line)}</div>' if meta_line else ''}
                </div>
                """, unsafe_allow_html=True)

                tab_a, tab_b, tab_c = st.tabs(["📋 步骤与结果", "🔗 来源", "📝 完整信息"])

                with tab_a:
                    if preconditions:
                        st.markdown("**前置条件：**")
                        for p in preconditions:
                            st.markdown(f"• {p}")
                        st.divider()
                    st.markdown("**步骤：**")
                    for i, step in enumerate(steps, 1):
                        st.markdown(f"{i}. {step}")
                    st.divider()
                    st.markdown("**预期结果：**")
                    for e in expected:
                        st.markdown(f"• {e}")

                with tab_b:
                    if source_refs:
                        for ref in source_refs:
                            st.markdown(f"- `{ref}`")
                    else:
                        st.markdown("（无来源追溯信息）")

                with tab_c:
                    cols = st.columns([1, 3])
                    with cols[0]:
                        st.markdown(f"**目录：**\n{directory}")
                        st.markdown(f"**负责人：**\n{owner}")
                        st.markdown(f"**类型：**\n{test_type}")
                    with cols[1]:
                        st.markdown(f"**前置条件：**\n" + "\n".join(f"- {p}" for p in preconditions) if preconditions else "**前置条件：**\n（无）")
                        st.markdown(f"**步骤：**\n" + "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1)) if steps else "**步骤：**\n（无）")
                        st.markdown(f"**预期结果：**\n" + "\n".join(f"- {e}" for e in expected) if expected else "**预期结果：**\n（无）")
