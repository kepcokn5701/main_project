# ==============================================================
#  AI 활용 고객경험관리시스템 조사결과 분석 웹 대시보드  v2.0
#  Professional Corporate Edition
#  실행법: python -m streamlit run cs_dashboard.py
# ==============================================================

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from collections import Counter
import io, re, os

# ── 선택적 라이브러리 ──────────────────────────────────────────
try:
    from konlpy.tag import Okt
    KONLPY_AVAILABLE = True
except Exception:
    KONLPY_AVAILABLE = False

try:
    from wordcloud import WordCloud
    WORDCLOUD_AVAILABLE = True
except Exception:
    WORDCLOUD_AVAILABLE = False

try:
    from transformers import pipeline as hf_pipeline
    TRANSFORMERS_AVAILABLE = True
except Exception:
    TRANSFORMERS_AVAILABLE = False

try:
    from keybert import KeyBERT
    KEYBERT_AVAILABLE = True
except Exception:
    KEYBERT_AVAILABLE = False

# ══════════════════════════════════════════════════════════════
#  0. 한글 폰트 (워드클라우드·matplotlib용)
# ══════════════════════════════════════════════════════════════
FONT_PATH = None
FONT_PROP = None
for _c in [
    "C:/Windows/Fonts/malgun.ttf",
    "C:/Windows/Fonts/NanumGothic.ttf",
    "C:/Windows/Fonts/gulim.ttc",
    "/System/Library/Fonts/AppleGothic.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
]:
    if os.path.exists(_c):
        FONT_PATH = _c
        FONT_PROP = fm.FontProperties(fname=_c)
        plt.rcParams["font.family"] = FONT_PROP.get_name()
        break
plt.rcParams["axes.unicode_minus"] = False

# ══════════════════════════════════════════════════════════════
#  1. 디자인 상수 (Corporate Blue Palette)
# ══════════════════════════════════════════════════════════════
C = dict(
    navy   = "#1a3a6c",
    blue   = "#0055a5",
    sky    = "#2196f3",
    light  = "#e3f2fd",
    gold   = "#f0a500",
    teal   = "#00897b",
    red    = "#c62828",
    orange = "#e65100",
    green  = "#2e7d32",
    gray   = "#546e7a",
    white  = "#ffffff",
    bg     = "#f4f7fc",
)

PIE_COLORS   = ["#1a3a6c","#0055a5","#2196f3","#42a5f5","#90caf9",
                "#64b5f6","#1565c0","#0288d1","#0097a7","#00897b"]
BAR_COLORS   = px.colors.sequential.Blues[3:]
MIXED_COLORS = ["#1a3a6c","#f0a500","#2196f3","#00897b","#c62828",
                "#7b1fa2","#e65100","#558b2f","#0288d1","#ad1457"]
PLOTLY_TPL   = "plotly_white"

NEGATIVE_KEYWORDS = [
    "불만","불편","민원","항의","화남","짜증","느림","느려","오류","오작동",
    "불량","고장","재방문","지연","오래","기다림","실망","최악","별로",
    "안됨","문제","취소","환불","비싸다","비싸","과다","과금","폭탄",
    "불친절","무시","황당","어이없","답답","이해불가","납득불가","부당",
    "잘못","실수","착오","불합리","불공정","차별","반복","또다시","여전히",
    "아직도","힘듭니다","어렵습니다","불쾌","무성의","소홀","방치","지체",
    "정전","단전","누전","위험","안전","사고",
]

_STOP = {
    # 조사·어미·보조
    "이","가","은","는","을","를","의","에","에서","으로","로","와","과","하",
    "것","수","있","없","않","못","더","또","그","저","있다","없다","됩니다",
    "합니다","했다","하는","하여","해서","입니다","이다","이고","이며","같은",
    "같이","너무","매우","정말","아주","조금","많이","항상","계속","때문",
    "경우","부분","관련","대한","위한","통해","에게","주세요","바랍니다",
    "부탁","감사","좋겠","드립니다","했습니다","있습니다","없습니다","이고",
    "이나","이라","해주세요","요청","드립니다","하겠습니다","하셨으면",
    # CS / 전력 서비스 도메인 불용어
    "관리","시스템","문의","확인","처리","접수","신청","등록","변경","조회",
    "이용","서비스","고객","전화","상담","안내","답변","진행","완료","내용",
    "한국전력","한전","전력","전기","사용","사용량","검침","수도","가스",
    "홈페이지","인터넷","방문","센터","지사","지점","담당","담당자","직원",
    "설문","조사","응답","결과","평가","만족","점수","항목","기타","해당",
}

# ══════════════════════════════════════════════════════════════
#  2. 유틸리티 함수
# ══════════════════════════════════════════════════════════════
def _extract_nouns_konlpy(texts):
    """KoNLPy Okt로 명사만 추출 (조사·어미 완전 제거)"""
    okt = Okt()
    words = []
    for t in texts:
        if not t or str(t).strip() in ("", "nan"):
            continue
        nouns = okt.nouns(str(t))
        words.extend([n for n in nouns if n not in _STOP and len(n) >= 2])
    return words


def extract_keywords(texts, top_n=60):
    valid = [str(t) for t in texts if t and str(t).strip() not in ("", "nan")]
    if not valid:
        return []

    # ── 방법 1: KeyBERT + KoNLPy (최고 품질 — 문맥 반영 키워드) ──
    if KEYBERT_AVAILABLE and KONLPY_AVAILABLE:
        try:
            nouns = _extract_nouns_konlpy(valid)
            noun_freq = Counter(nouns)
            if noun_freq:
                noun_doc = " ".join(nouns)
                kw_model = KeyBERT("paraphrase-multilingual-MiniLM-L12-v2")
                candidates = list(noun_freq.keys())
                kw_results = kw_model.extract_keywords(
                    noun_doc,
                    candidates=candidates,
                    top_n=min(top_n, len(candidates)),
                    use_mmr=True,
                    diversity=0.5,
                )
                result = []
                for kw, _score in kw_results:
                    if kw in noun_freq and kw not in _STOP and len(kw) >= 2:
                        result.append((kw, noun_freq[kw]))
                result.sort(key=lambda x: x[1], reverse=True)
                if len(result) >= 5:
                    return result[:top_n]
        except Exception:
            pass

    # ── 방법 2: KoNLPy 명사 추출 (양호 — 조사·어미 제거) ─────────
    if KONLPY_AVAILABLE:
        try:
            nouns = _extract_nouns_konlpy(valid)
            if nouns:
                return Counter(nouns).most_common(top_n)
        except Exception:
            pass

    # ── 방법 3: 정규식 기반 한글 2자 이상 (최소 품질) ─────────────
    words = []
    for t in valid:
        found = re.findall(r"[가-힣]{2,}", t)
        words.extend([w for w in found if w not in _STOP])
    return Counter(words).most_common(top_n)


def check_negative(text):
    if not text or str(text).strip() in ("", "nan"):
        return False, []
    s = str(text)
    found = [kw for kw in NEGATIVE_KEYWORDS if kw in s]
    return bool(found), found


# ── 감성 분석 (HuggingFace + 임계값 + 부정 키워드 오버라이드) ────
POSITIVE_THRESHOLD = 0.85   # 긍정 확률 85% 이상만 '긍정' 분류


@st.cache_resource
def _load_sentiment_model():
    """HuggingFace 한국어 감성분석 모델 로드 (세션 간 캐시)"""
    if not TRANSFORMERS_AVAILABLE:
        return None
    try:
        return hf_pipeline(
            "text-classification",
            model="snunlp/KR-FinBert-SC",
            truncation=True,
            max_length=512,
        )
    except Exception:
        return None


def classify_sentiment_single(text, pipe=None):
    """
    단일 텍스트 감성 분류 (3단계):
      1) 부정 키워드 포함 시 → 무조건 'negative'
      2) HuggingFace 모델 결과 + 임계값 적용
      3) 모델 미사용 시 키워드 기반 판정
    """
    if not text or str(text).strip() in ("", "nan"):
        return "neutral"
    s = str(text)
    # 1) 부정 키워드 강제 분류
    has_neg, _ = check_negative(s)
    if has_neg:
        return "negative"
    # 2) HuggingFace 모델 + 임계값
    if pipe is not None:
        try:
            result = pipe(s[:512])[0]
            label = result["label"].lower()
            score = result["score"]
            if "positive" in label or "긍정" in label:
                return "positive" if score >= POSITIVE_THRESHOLD else "neutral"
            elif "negative" in label or "부정" in label:
                return "negative"
            else:
                return "neutral"
        except Exception:
            pass
    # 3) 폴백: 부정 키워드 없으면 긍정 추정
    return "positive"


@st.cache_data(show_spinner="AI 감성 분석 중… (최초 1회만 소요)")
def batch_classify_sentiment(texts_tuple):
    """VOC 텍스트 배치 감성 분석 (결과 캐시)"""
    texts = list(texts_tuple)
    results = ["neutral"] * len(texts)
    pipe = _load_sentiment_model()

    # 1차: 부정 키워드 필터 (빠름)
    needs_model = []
    for i, t in enumerate(texts):
        has_neg, _ = check_negative(t)
        if has_neg:
            results[i] = "negative"
        elif t and str(t).strip() not in ("", "nan"):
            needs_model.append(i)

    # 2차: HuggingFace 모델 배치 추론
    if pipe and needs_model:
        try:
            model_texts = [str(texts[i])[:512] for i in needs_model]
            model_results = pipe(model_texts, batch_size=32)
            for idx, mr in zip(needs_model, model_results):
                label = mr["label"].lower()
                score = mr["score"]
                if "positive" in label or "긍정" in label:
                    results[idx] = "positive" if score >= POSITIVE_THRESHOLD else "neutral"
                elif "negative" in label or "부정" in label:
                    results[idx] = "negative"
                else:
                    results[idx] = "neutral"
        except Exception:
            for idx in needs_model:
                results[idx] = "positive"
    elif not pipe:
        for idx in needs_model:
            results[idx] = "positive"

    return results


def make_wordcloud_image(kw_list):
    """WordCloud → PIL Image"""
    if not WORDCLOUD_AVAILABLE or not kw_list:
        return None
    freq = {k: v for k, v in kw_list}
    kwargs = dict(
        width=1200, height=500, background_color="white",
        max_words=120, colormap="Blues", prefer_horizontal=0.7,
    )
    if FONT_PATH:
        kwargs["font_path"] = FONT_PATH
    try:
        wc = WordCloud(**kwargs)
        wc.generate_from_frequencies(freq)
        return wc.to_image()
    except Exception:
        return None


def df_to_excel_bytes(df):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="잠재민원고객")
    return buf.getvalue()


def score_color(val, med):
    return C["red"] if val < med else C["green"]


def is_negative_voc(text):
    h, _ = check_negative(text)
    return h


# ══════════════════════════════════════════════════════════════
#  3. 페이지 설정 & 전역 CSS
# ══════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="CS 분석 대시보드",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(f"""
<style>
  /* ── 전체 배경 ── */
  .stApp {{ background-color: {C['bg']}; }}

  /* ── 헤더 배너 ── */
  .dash-header {{
    background: linear-gradient(120deg, {C['navy']} 0%, {C['blue']} 55%, {C['sky']} 100%);
    padding: 2rem 2.5rem;
    border-radius: 16px;
    color: white;
    margin-bottom: 1.5rem;
    box-shadow: 0 4px 20px rgba(0,0,0,0.18);
  }}
  .dash-header h1 {{ font-size:1.9rem; font-weight:800; margin:0; letter-spacing:-0.5px; }}
  .dash-header p  {{ font-size:0.95rem; margin:0.4rem 0 0 0; opacity:0.85; }}
  .dash-badge {{
    display:inline-block; background:rgba(255,255,255,0.18);
    border:1px solid rgba(255,255,255,0.35); border-radius:20px;
    padding:0.2rem 0.8rem; font-size:0.78rem; margin-top:0.7rem; margin-right:0.4rem;
  }}

  /* ── Metric 카드 ── */
  [data-testid="stMetric"] {{
    background: {C['white']};
    border-radius: 14px;
    padding: 1.1rem 1.2rem 0.9rem 1.2rem;
    box-shadow: 0 2px 12px rgba(0,85,165,0.10);
    border-top: 4px solid {C['blue']};
    transition: transform 0.15s;
  }}
  [data-testid="stMetric"]:hover {{ transform: translateY(-2px); }}
  [data-testid="stMetricLabel"]  {{ font-size:0.82rem !important; color:{C['gray']} !important; font-weight:600; }}
  [data-testid="stMetricValue"]  {{ font-size:1.75rem !important; font-weight:800 !important; color:{C['navy']} !important; }}
  [data-testid="stMetricDelta"]  {{ font-size:0.82rem !important; }}

  /* ── 탭 ── */
  .stTabs [data-baseweb="tab-list"] {{
    gap: 6px; background:{C['bg']};
    border-bottom: 2px solid #dde4ef; padding-bottom:0;
  }}
  .stTabs [data-baseweb="tab"] {{
    font-size:0.95rem; font-weight:700; padding:0.6rem 1.4rem;
    border-radius:8px 8px 0 0; color:{C['gray']};
    background:transparent;
  }}
  .stTabs [aria-selected="true"] {{
    color:{C['navy']} !important; background:{C['white']} !important;
    border-bottom:3px solid {C['blue']} !important;
    box-shadow: 0 -2px 8px rgba(0,85,165,0.08);
  }}

  /* ── 섹션 헤더 ── */
  .sec-head {{
    font-size:1.1rem; font-weight:800; color:{C['navy']};
    border-left:5px solid {C['blue']}; padding:0.2rem 0 0.2rem 0.8rem;
    margin: 1.4rem 0 1rem 0;
  }}

  /* ── 카드 박스 ── */
  .card {{
    background:{C['white']}; border-radius:14px;
    padding:1.3rem 1.5rem;
    box-shadow:0 2px 12px rgba(0,85,165,0.09);
    margin-bottom:1rem;
  }}
  .card-red {{
    background:#fff5f5; border-radius:14px; padding:1.3rem 1.5rem;
    box-shadow:0 2px 12px rgba(198,40,40,0.10);
    border-left:5px solid {C['red']}; margin-bottom:1rem;
  }}
  .card-gold {{
    background:#fffbf0; border-radius:14px; padding:1.3rem 1.5rem;
    box-shadow:0 2px 12px rgba(240,165,0,0.12);
    border-left:5px solid {C['gold']}; margin-bottom:1rem;
  }}
  .card-teal {{
    background:#f0faf8; border-radius:14px; padding:1.3rem 1.5rem;
    box-shadow:0 2px 12px rgba(0,137,123,0.10);
    border-left:5px solid {C['teal']}; margin-bottom:1rem;
  }}
  .card-blue {{
    background:{C['light']}; border-radius:14px; padding:1.3rem 1.5rem;
    box-shadow:0 2px 12px rgba(0,85,165,0.09);
    border-left:5px solid {C['sky']}; margin-bottom:1rem;
  }}

  /* ── 사이드바 ── */
  [data-testid="stSidebar"] {{
    background: linear-gradient(180deg, {C['navy']} 0%, #1e4d8c 100%) !important;
  }}
  [data-testid="stSidebar"] * {{ color: white !important; }}
  [data-testid="stSidebar"] .stSelectbox label,
  [data-testid="stSidebar"] .stMultiSelect label,
  [data-testid="stSidebar"] .stSlider label {{ font-size:0.82rem !important; }}
  [data-testid="stSidebar"] [data-testid="stFileUploader"] {{
    background:rgba(255,255,255,0.08) !important;
    border:1px dashed rgba(255,255,255,0.4) !important;
    border-radius:10px;
  }}
  [data-testid="stSidebar"] hr {{ border-color:rgba(255,255,255,0.2) !important; }}

  /* ── 다운로드 버튼 ── */
  .stDownloadButton > button {{
    background: linear-gradient(90deg, {C['navy']}, {C['blue']}) !important;
    color: white !important; font-weight:700 !important;
    border-radius: 10px !important; border:none !important;
    padding: 0.65rem 1.5rem !important; font-size:0.95rem !important;
    box-shadow: 0 3px 10px rgba(0,85,165,0.3) !important;
    transition: opacity 0.2s !important;
  }}
  .stDownloadButton > button:hover {{ opacity:0.88 !important; }}

  /* ── 데이터프레임 헤더 ── */
  [data-testid="stDataFrame"] th {{
    background: {C['navy']} !important; color:white !important;
  }}

  /* ── expander ── */
  .stExpander {{ border-radius:10px !important; border:1px solid #dde4ef !important; }}

  /* ── 필터 칩 ── */
  .filter-chip {{
    display:inline-block; background:{C['light']}; color:{C['navy']};
    border:1px solid {C['sky']}; border-radius:20px;
    padding:0.15rem 0.7rem; font-size:0.78rem; margin:0.15rem;
  }}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
#  4. 사이드바
# ══════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("### ⚡ CS 분석 대시보드")
    st.markdown("<hr>", unsafe_allow_html=True)

    st.markdown("#### 📂 데이터 업로드")
    uploaded_file = st.file_uploader(
        "엑셀 파일을 여기에 드래그하세요",
        type=["xlsx", "xls"],
        label_visibility="collapsed",
    )

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("#### ⚙️ 시스템 상태")
    st.markdown(
        f"{'✅ KoNLPy (고정밀)' if KONLPY_AVAILABLE else '🟡 기본 분석 모드'}  \n"
        f"{'✅ HuggingFace 감성분석' if TRANSFORMERS_AVAILABLE else '🟡 키워드 기반 감성분석'}  \n"
        f"{'✅ KeyBERT 키워드' if KEYBERT_AVAILABLE else '🟡 빈도 기반 키워드'}  \n"
        f"{'✅ WordCloud' if WORDCLOUD_AVAILABLE else '🟡 WordCloud 미설치'}  \n"
        f"{'✅ 한글 폰트' if FONT_PATH else '🟡 기본 폰트'}"
    )

    if not KONLPY_AVAILABLE:
        st.caption("pip install konlpy 로 고정밀 분석 가능")
    if not TRANSFORMERS_AVAILABLE:
        st.caption("pip install transformers torch 로 AI 감성분석 활성화")
    if not KEYBERT_AVAILABLE:
        st.caption("pip install keybert 로 문맥 키워드 추출 활성화")
    if not WORDCLOUD_AVAILABLE:
        st.caption("pip install wordcloud 로 워드클라우드 활성화")

    st.markdown("<hr>", unsafe_allow_html=True)
    st.caption("© 2025 CS 분석 시스템 v2.0")

# ══════════════════════════════════════════════════════════════
#  5. 헤더 배너 (항상 표시)
# ══════════════════════════════════════════════════════════════
st.markdown("""
<div class="dash-header">
  <h1>⚡ AI 활용 고객경험관리시스템 조사결과 분석</h1>
  <p>전력산업 CS 데이터 기반 · AI 키워드 분석 · 잠재 민원 사전케어 · 임원 보고용 대시보드</p>
  <span class="dash-badge">📊 다차원 통계</span>
  <span class="dash-badge">☁️ VOC 키워드 AI 분석</span>
  <span class="dash-badge">🎯 잠재 민원 사전케어</span>
  <span class="dash-badge">📥 원클릭 엑셀 다운로드</span>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
#  6. 업로드 전 안내
# ══════════════════════════════════════════════════════════════
if uploaded_file is None:
    c_l, c_r = st.columns([1, 1])
    with c_l:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### 📋 사용 방법")
        st.markdown("""
1. **왼쪽 사이드바**에서 엑셀 파일(.xlsx)을 업로드하세요.
2. 컬럼 매핑 설정을 완료하세요.
3. 사이드바 필터로 원하는 데이터 범위를 선택하세요.
4. 각 **탭**을 클릭하며 분석 결과를 확인하세요.
        """)
        st.markdown('</div>', unsafe_allow_html=True)
    with c_r:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### 📌 권장 엑셀 컬럼 구성")
        st.markdown("""
| 컬럼명 예시 | 내용 |
|---|---|
| 고객번호 | 고객 식별 ID |
| 고객명 | 이름 |
| 연락처 | 전화번호 |
| 연령대 | 10대~70대 이상 |
| 계약종 | 주택용/일반용/산업용 |
| 업무구분 | 요금·설치·정전 등 |
| 만족도점수 | 숫자 (1~5 또는 1~10) |
| 주관식답변 | VOC 텍스트 |
        """)
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# ══════════════════════════════════════════════════════════════
#  7. 데이터 로드 & 정제
# ══════════════════════════════════════════════════════════════
@st.cache_data(show_spinner=False)
def load_data(raw_bytes):
    try:
        df = pd.read_excel(io.BytesIO(raw_bytes), engine="openpyxl")
    except Exception:
        df = pd.read_excel(io.BytesIO(raw_bytes))
    orig = len(df)
    df.dropna(how="all", inplace=True)
    df.dropna(axis=1, how="all", inplace=True)
    df.drop_duplicates(inplace=True)
    df.columns = [str(c).strip() for c in df.columns]
    return df, orig

with st.spinner("데이터를 불러오는 중…"):
    df_raw, orig_len = load_data(uploaded_file.read())

# ══════════════════════════════════════════════════════════════
#  8. 사이드바 — 컬럼 매핑
# ══════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("#### 🔗 컬럼 매핑")
    _none = "(선택 안 함)"
    _opts = [_none] + list(df_raw.columns)

    with st.expander("컬럼 매핑 펼치기", expanded=True):
        col_id       = st.selectbox("🔢 고객번호",      _opts, key="m_id")
        col_name     = st.selectbox("👤 고객이름",      _opts, key="m_name")
        col_contact  = st.selectbox("📞 연락처",        _opts, key="m_con")
        col_age      = st.selectbox("👥 연령대",        _opts, key="m_age")
        col_contract = st.selectbox("📋 계약종",        _opts, key="m_cont")
        col_business = st.selectbox("🏢 업무구분",      _opts, key="m_biz")
        col_score    = st.selectbox("⭐ 만족도 점수",   _opts, key="m_sc")
        col_voc      = st.selectbox("💬 주관식답변(VOC)",_opts, key="m_voc")

M = {
    "id":       col_id       if col_id       != _none else None,
    "name":     col_name     if col_name     != _none else None,
    "contact":  col_contact  if col_contact  != _none else None,
    "age":      col_age      if col_age      != _none else None,
    "contract": col_contract if col_contract != _none else None,
    "business": col_business if col_business != _none else None,
    "score":    col_score    if col_score    != _none else None,
    "voc":      col_voc      if col_voc      != _none else None,
}

# ══════════════════════════════════════════════════════════════
#  9. 사이드바 — 필터
# ══════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("#### 🔍 데이터 필터")

    df_f = df_raw.copy()

    if M["age"]:
        age_opts = sorted(df_raw[M["age"]].dropna().astype(str).unique().tolist())
        sel_age  = st.multiselect("연령대", age_opts, default=age_opts, key="f_age")
        if sel_age:
            df_f = df_f[df_f[M["age"]].astype(str).isin(sel_age)]

    if M["contract"]:
        cont_opts = sorted(df_raw[M["contract"]].dropna().astype(str).unique().tolist())
        sel_cont  = st.multiselect("계약종", cont_opts, default=cont_opts, key="f_cont")
        if sel_cont:
            df_f = df_f[df_f[M["contract"]].astype(str).isin(sel_cont)]

    if M["business"]:
        biz_opts = sorted(df_raw[M["business"]].dropna().astype(str).unique().tolist())
        sel_biz  = st.multiselect("업무구분", biz_opts, default=biz_opts, key="f_biz")
        if sel_biz:
            df_f = df_f[df_f[M["business"]].astype(str).isin(sel_biz)]

    if M["score"]:
        sc_s = pd.to_numeric(df_raw[M["score"]], errors="coerce").dropna()
        if not sc_s.empty:
            s_min, s_max = float(sc_s.min()), float(sc_s.max())
            sc_rng = st.slider("만족도 점수 범위",
                               min_value=s_min, max_value=s_max,
                               value=(s_min, s_max), step=0.1, key="f_sc")
            df_f[M["score"]] = pd.to_numeric(df_f[M["score"]], errors="coerce")
            df_f = df_f[df_f[M["score"]].between(sc_rng[0], sc_rng[1])]

    st.caption(f"필터 적용 결과: **{len(df_f):,}건** / 전체 {len(df_raw):,}건")

# ══════════════════════════════════════════════════════════════
#  10. KPI 메트릭 행
# ══════════════════════════════════════════════════════════════
st.markdown('<p class="sec-head">📌 핵심 요약 지표</p>', unsafe_allow_html=True)

# 사전 계산
avg_score_val = None
if M["score"]:
    sc_num = pd.to_numeric(df_f[M["score"]], errors="coerce")
    avg_score_val = sc_num.mean()

voc_texts_all = []
voc_sentiments = []
pos_cnt = neg_cnt = neu_cnt = 0
_row_sentiments = ["neutral"] * len(df_f)
if M["voc"]:
    raw_voc = df_f[M["voc"]].astype(str).str.strip()
    all_texts = raw_voc.tolist()
    voc_texts_all = [t for t in all_texts if t and t != "nan"]
    if voc_texts_all:
        voc_sentiments = batch_classify_sentiment(tuple(voc_texts_all))
        vi = 0
        for i, t in enumerate(all_texts):
            if t and t != "nan" and vi < len(voc_sentiments):
                _row_sentiments[i] = voc_sentiments[vi]
                vi += 1
        for sent in voc_sentiments:
            if sent == "negative":
                neg_cnt += 1
            elif sent == "positive":
                pos_cnt += 1
            else:
                neu_cnt += 1
    voc_response_rate = len(voc_texts_all) / max(len(df_f), 1) * 100
else:
    voc_response_rate = 0.0

neg_ratio = neg_cnt / max(len(voc_texts_all), 1) * 100

m1, m2, m3, m4, m5 = st.columns(5)
with m1:
    st.metric("📋 분석 건수",
              f"{len(df_f):,}건",
              delta=f"필터 전 {len(df_raw):,}건" if len(df_f) != len(df_raw) else None)
with m2:
    if avg_score_val is not None and not np.isnan(avg_score_val):
        bench = 4.0
        delta_v = avg_score_val - bench
        st.metric("⭐ 평균 만족도",
                  f"{avg_score_val:.2f}점",
                  delta=f"{delta_v:+.2f} vs 기준({bench}점)",
                  delta_color="normal")
    else:
        st.metric("⭐ 평균 만족도", "컬럼 미선택")
with m3:
    if M["voc"]:
        st.metric("💬 VOC 응답률", f"{voc_response_rate:.1f}%",
                  delta=f"총 {len(voc_texts_all):,}건")
    else:
        st.metric("💬 VOC 응답률", "미선택")
with m4:
    if M["voc"]:
        st.metric("😊 긍정 VOC 비율", f"{100 - neg_ratio:.1f}%",
                  delta=f"긍정 {pos_cnt:,}건")
    else:
        st.metric("😊 긍정 VOC 비율", "미선택")
with m5:
    if M["voc"]:
        st.metric("🚨 잠재 민원 고객",
                  f"{neg_cnt:,}명",
                  delta=f"전체의 {neg_ratio:.1f}%",
                  delta_color="inverse")
    else:
        st.metric("🚨 잠재 민원 고객", "미선택")

st.markdown("<br>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
#  11. 탭 구성
# ══════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4 = st.tabs([
    "📊  종합 현황 통계",
    "📈  다차원 교차 분석",
    "☁️  VOC 키워드 분석",
    "🎯  CS 인사이트 & 사전케어",
])

# ─────────────────────────────────────────────────────────────
#  TAB 1  종합 현황 통계
# ─────────────────────────────────────────────────────────────
with tab1:

    # ── 게이지 + 히스토그램 ──────────────────────────────────
    if M["score"] and avg_score_val is not None and not np.isnan(avg_score_val):
        sc_num = pd.to_numeric(df_f[M["score"]], errors="coerce").dropna()
        sc_min, sc_max = float(sc_num.min()), float(sc_num.max())

        g_col, h_col = st.columns([1, 2])

        with g_col:
            st.markdown('<p class="sec-head">🎯 평균 만족도 게이지</p>', unsafe_allow_html=True)
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=round(avg_score_val, 2),
                number={"suffix": "점", "font": {"size": 36, "color": C["navy"]}},
                delta={"reference": 4.0, "increasing": {"color": C["green"]},
                       "decreasing": {"color": C["red"]}},
                gauge={
                    "axis": {"range": [sc_min, sc_max],
                             "tickfont": {"size": 11}, "tickcolor": C["gray"]},
                    "bar": {"color": C["blue"], "thickness": 0.28},
                    "bgcolor": "white",
                    "borderwidth": 0,
                    "steps": [
                        {"range": [sc_min, sc_min + (sc_max - sc_min) * 0.4], "color": "#ffcdd2"},
                        {"range": [sc_min + (sc_max - sc_min) * 0.4,
                                   sc_min + (sc_max - sc_min) * 0.7], "color": "#fff9c4"},
                        {"range": [sc_min + (sc_max - sc_min) * 0.7, sc_max], "color": "#c8e6c9"},
                    ],
                    "threshold": {"line": {"color": C["red"], "width": 3},
                                  "thickness": 0.78, "value": 4.0},
                },
                title={"text": "평균 만족도 점수<br><span style='font-size:0.8em;color:gray'>"
                               "빨간 선 = 목표 4.0점</span>",
                       "font": {"size": 14, "color": C["navy"]}},
            ))
            fig_gauge.update_layout(
                height=280, margin=dict(t=60, b=20, l=30, r=30),
                paper_bgcolor="white", plot_bgcolor="white",
            )
            st.plotly_chart(fig_gauge, use_container_width=True)

        with h_col:
            st.markdown('<p class="sec-head">📊 만족도 점수 분포</p>', unsafe_allow_html=True)
            fig_hist = px.histogram(
                sc_num, nbins=min(30, int(sc_max - sc_min + 1) * 5),
                color_discrete_sequence=[C["sky"]],
                labels={"value": "만족도 점수", "count": "응답 수"},
                template=PLOTLY_TPL,
            )
            fig_hist.add_vline(
                x=avg_score_val, line_color=C["gold"], line_width=2.5, line_dash="dash",
                annotation_text=f"평균 {avg_score_val:.2f}",
                annotation_font_color=C["gold"], annotation_font_size=13,
            )
            fig_hist.update_layout(
                height=280, margin=dict(t=30, b=30, l=50, r=20),
                showlegend=False,
                xaxis_title="만족도 점수", yaxis_title="응답 수",
            )
            fig_hist.update_traces(marker_line_width=0)
            st.plotly_chart(fig_hist, use_container_width=True)

        st.markdown("---")

    # ── 분포 파이 차트 3종 ──────────────────────────────────
    has_pie = any([M["age"], M["contract"], M["business"]])
    if has_pie:
        st.markdown('<p class="sec-head">🍩 응답 분포 현황</p>', unsafe_allow_html=True)
        pie_cols = [c for c in [M["age"], M["contract"], M["business"]] if c]
        pc_list  = st.columns(len(pie_cols))

        titles_map = {M["age"]: "연령대", M["contract"]: "계약종", M["business"]: "업무구분"}
        for idx, col_nm in enumerate(pie_cols):
            counts = df_f[col_nm].dropna().astype(str).value_counts()
            fig_pie = px.pie(
                names=counts.index, values=counts.values,
                color_discrete_sequence=PIE_COLORS,
                hole=0.42,
                title=f"{titles_map.get(col_nm, col_nm)} 분포",
                template=PLOTLY_TPL,
            )
            fig_pie.update_traces(
                textposition="outside", textinfo="percent+label",
                textfont_size=12,
                marker=dict(line=dict(color="#ffffff", width=2)),
            )
            fig_pie.update_layout(
                height=360, margin=dict(t=50, b=20, l=20, r=20),
                showlegend=False,
                title_font=dict(size=15, color=C["navy"]),
            )
            with pc_list[idx]:
                st.plotly_chart(fig_pie, use_container_width=True)

        st.markdown("---")

    # ── 데이터 품질 ─────────────────────────────────────────
    st.markdown('<p class="sec-head">🔍 데이터 품질 현황</p>', unsafe_allow_html=True)
    q_df = pd.DataFrame({
        "컬럼명":   df_f.columns,
        "유효 건수": df_f.count().values,
        "결측 건수": df_f.isnull().sum().values,
        "결측률(%)": (df_f.isnull().sum().values / max(len(df_f), 1) * 100).round(1),
    })
    fig_q = px.bar(
        q_df, x="컬럼명", y="결측률(%)",
        color="결측률(%)",
        color_continuous_scale=["#c8e6c9", "#fff9c4", "#ffcdd2"],
        template=PLOTLY_TPL,
        title="컬럼별 결측률 (%)",
        text="결측률(%)",
    )
    fig_q.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig_q.update_layout(
        height=320, margin=dict(t=50, b=80, l=60, r=20),
        xaxis_tickangle=-35,
        coloraxis_showscale=False,
        title_font=dict(size=15, color=C["navy"]),
    )
    st.plotly_chart(fig_q, use_container_width=True)

    with st.expander("📄 원본 데이터 미리보기 (상위 30건)"):
        st.dataframe(df_f.head(30), use_container_width=True)


# ─────────────────────────────────────────────────────────────
#  TAB 2  다차원 교차 분석
# ─────────────────────────────────────────────────────────────
with tab2:

    def avg_score_bar(group_col, title_str, orientation="h", top_n=20):
        """그룹별 평균 만족도 막대 차트 (Plotly)"""
        if not M["score"]:
            st.info("만족도 점수 컬럼을 선택하면 표시됩니다.")
            return
        tmp = df_f[[group_col, M["score"]]].copy()
        tmp[M["score"]] = pd.to_numeric(tmp[M["score"]], errors="coerce")
        grp = tmp.groupby(group_col)[M["score"]].mean().sort_values().reset_index()
        grp.columns = ["항목", "평균만족도"]
        grp = grp.tail(top_n)
        med = grp["평균만족도"].median()
        grp["색상"] = grp["평균만족도"].apply(
            lambda v: "⬆ 우수" if v >= med else "⬇ 주의"
        )
        color_map = {"⬆ 우수": C["teal"], "⬇ 주의": C["red"]}

        if orientation == "h":
            fig = px.bar(
                grp, x="평균만족도", y="항목", color="색상",
                color_discrete_map=color_map, orientation="h",
                text="평균만족도", template=PLOTLY_TPL, title=title_str,
            )
            fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
            fig.update_layout(
                height=max(300, len(grp) * 30 + 60),
                margin=dict(t=50, b=20, l=10, r=80),
                legend_title_text="",
                title_font=dict(size=14, color=C["navy"]),
                showlegend=True,
            )
            fig.add_vline(x=med, line_color=C["gray"], line_dash="dot", line_width=1.5,
                          annotation_text=f"중앙값 {med:.2f}",
                          annotation_font_size=11, annotation_font_color=C["gray"])
        else:
            grp_s = grp.sort_values("평균만족도", ascending=False)
            fig = px.bar(
                grp_s, x="항목", y="평균만족도", color="색상",
                color_discrete_map=color_map,
                text="평균만족도", template=PLOTLY_TPL, title=title_str,
            )
            fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
            fig.update_layout(
                height=380, margin=dict(t=50, b=80, l=60, r=20),
                xaxis_tickangle=-30, legend_title_text="",
                title_font=dict(size=14, color=C["navy"]),
            )
        st.plotly_chart(fig, use_container_width=True)

    # ── 연령대 분석 ─────────────────────────────────────────
    if M["age"]:
        st.markdown('<p class="sec-head">👥 연령대별 분석</p>', unsafe_allow_html=True)
        a_left, a_right = st.columns(2)
        age_cnt = df_f[M["age"]].dropna().astype(str).value_counts().reset_index()
        age_cnt.columns = ["연령대", "건수"]
        with a_left:
            fig_ab = px.bar(
                age_cnt, x="연령대", y="건수",
                color="건수", color_continuous_scale="Blues",
                text="건수", template=PLOTLY_TPL,
                title="연령대별 응답 수",
            )
            fig_ab.update_traces(texttemplate="%{text:,}", textposition="outside")
            fig_ab.update_layout(
                height=340, margin=dict(t=50, b=50, l=60, r=20),
                coloraxis_showscale=False,
                title_font=dict(size=14, color=C["navy"]),
            )
            st.plotly_chart(fig_ab, use_container_width=True)
        with a_right:
            avg_score_bar(M["age"], "연령대별 평균 만족도 (낮은 순)", "h")
        st.markdown("---")

    # ── 계약종 분석 ─────────────────────────────────────────
    if M["contract"]:
        st.markdown('<p class="sec-head">📋 계약종별 분석</p>', unsafe_allow_html=True)
        co_l, co_r = st.columns(2)
        cont_cnt = df_f[M["contract"]].dropna().astype(str).value_counts().reset_index()
        cont_cnt.columns = ["계약종", "건수"]
        with co_l:
            fig_cb = px.bar(
                cont_cnt, x="계약종", y="건수",
                color_discrete_sequence=[C["blue"]],
                text="건수", template=PLOTLY_TPL, title="계약종별 응답 수",
            )
            fig_cb.update_traces(texttemplate="%{text:,}", textposition="outside")
            fig_cb.update_layout(
                height=340, margin=dict(t=50, b=50, l=60, r=20),
                title_font=dict(size=14, color=C["navy"]),
            )
            st.plotly_chart(fig_cb, use_container_width=True)
        with co_r:
            avg_score_bar(M["contract"], "계약종별 평균 만족도", "h")
        st.markdown("---")

    # ── 업무별 분석 ─────────────────────────────────────────
    if M["business"]:
        st.markdown('<p class="sec-head">🏢 업무별 분석</p>', unsafe_allow_html=True)
        biz_cnt = df_f[M["business"]].dropna().astype(str).value_counts().head(20).reset_index()
        biz_cnt.columns = ["업무", "건수"]
        fig_biz = px.bar(
            biz_cnt, x="업무", y="건수",
            color="건수", color_continuous_scale="Blues",
            text="건수", template=PLOTLY_TPL, title="업무별 응답 수 (상위 20개)",
        )
        fig_biz.update_traces(texttemplate="%{text:,}", textposition="outside")
        fig_biz.update_layout(
            height=360, margin=dict(t=50, b=100, l=60, r=20),
            xaxis_tickangle=-35, coloraxis_showscale=False,
            title_font=dict(size=14, color=C["navy"]),
        )
        st.plotly_chart(fig_biz, use_container_width=True)

        avg_score_bar(M["business"], "업무별 평균 만족도 (낮은 순·빨간색=주의)", "h", top_n=20)
        st.markdown("---")

    # ── 교차 분석: 연령대 × 계약종 ─────────────────────────
    if M["age"] and M["contract"]:
        st.markdown('<p class="sec-head">🔀 연령대 × 계약종 교차 분석</p>', unsafe_allow_html=True)
        cross = pd.crosstab(df_f[M["age"]], df_f[M["contract"]]).reset_index()
        cross_melt = cross.melt(id_vars=M["age"], var_name="계약종", value_name="건수")
        fig_cross = px.bar(
            cross_melt, x=M["age"], y="건수", color="계약종",
            barmode="group", template=PLOTLY_TPL,
            color_discrete_sequence=MIXED_COLORS,
            title="연령대 × 계약종 교차 분석",
        )
        fig_cross.update_layout(
            height=380, margin=dict(t=50, b=60, l=60, r=20),
            xaxis_tickangle=-20,
            title_font=dict(size=14, color=C["navy"]),
        )
        st.plotly_chart(fig_cross, use_container_width=True)

        with st.expander("교차 집계표 보기"):
            st.dataframe(
                pd.crosstab(df_f[M["age"]], df_f[M["contract"]]),
                use_container_width=True,
            )
        st.markdown("---")

    # ── 히트맵: 업무 × 연령대 평균 만족도 ──────────────────
    if M["business"] and M["age"] and M["score"]:
        st.markdown('<p class="sec-head">🌡️ 업무 × 연령대 평균 만족도 히트맵</p>',
                    unsafe_allow_html=True)
        tmp_h = df_f[[M["business"], M["age"], M["score"]]].copy()
        tmp_h[M["score"]] = pd.to_numeric(tmp_h[M["score"]], errors="coerce")
        pivot = tmp_h.pivot_table(
            values=M["score"], index=M["business"], columns=M["age"], aggfunc="mean"
        ).round(2)

        if not pivot.empty:
            fig_hm = px.imshow(
                pivot, color_continuous_scale="RdYlGn",
                text_auto=".2f", aspect="auto", template=PLOTLY_TPL,
                title="업무 × 연령대 평균 만족도 (초록=높음 / 빨간=낮음)",
            )
            fig_hm.update_layout(
                height=max(400, len(pivot.index) * 28 + 100),
                margin=dict(t=60, b=60, l=120, r=60),
                title_font=dict(size=14, color=C["navy"]),
                coloraxis_colorbar_title="만족도",
            )
            st.plotly_chart(fig_hm, use_container_width=True)


# ─────────────────────────────────────────────────────────────
#  TAB 3  VOC 키워드 분석
# ─────────────────────────────────────────────────────────────
with tab3:

    if not M["voc"]:
        st.warning("주관식 답변(VOC) 컬럼을 사이드바에서 먼저 선택해주세요.")
    else:
        voc_raw = df_f[M["voc"]].astype(str).str.strip()
        voc_list = [t for t in voc_raw.tolist() if t and t != "nan"]
        n_voc = len(voc_list)

        _analysis_mode = (
            "KeyBERT + KoNLPy" if (KEYBERT_AVAILABLE and KONLPY_AVAILABLE)
            else "KoNLPy 고정밀" if KONLPY_AVAILABLE
            else "정규식 기본"
        )
        st.markdown(
            f'<p class="sec-head">☁️ VOC 키워드 AI 분석 — '
            f'{_analysis_mode} 모드 ({n_voc:,}건 분석 대상)</p>',
            unsafe_allow_html=True,
        )

        if n_voc == 0:
            st.info("VOC 텍스트가 없습니다. 컬럼을 확인하세요.")
        else:
            with st.spinner("AI가 키워드를 추출 중입니다… 잠시 기다려주세요."):
                all_kws = extract_keywords(voc_list, top_n=60)

            if not all_kws:
                st.warning("키워드를 추출하지 못했습니다.")
            else:
                # ── 워드클라우드 + 키워드 표 ────────────────────
                wc_col, kw_col = st.columns([3, 2])

                with wc_col:
                    st.markdown('<div class="card">', unsafe_allow_html=True)
                    st.markdown("**☁️ 전체 VOC 워드클라우드**")
                    if WORDCLOUD_AVAILABLE:
                        img = make_wordcloud_image(all_kws)
                        if img:
                            st.image(img, use_container_width=True)
                        else:
                            st.error("워드클라우드 생성 실패. 한글 폰트를 확인하세요.")
                    else:
                        st.warning("`pip install wordcloud` 후 재시작하세요.")
                    st.markdown('</div>', unsafe_allow_html=True)

                with kw_col:
                    st.markdown('<div class="card">', unsafe_allow_html=True)
                    st.markdown("**🔑 키워드 빈도 Top 25**")
                    kw_df = pd.DataFrame(all_kws[:25], columns=["키워드", "언급 횟수"])
                    kw_df["비율(%)"] = (kw_df["언급 횟수"] / kw_df["언급 횟수"].sum() * 100).round(1)
                    kw_df["유형"] = kw_df["키워드"].apply(
                        lambda x: "⚠️ 부정" if any(n in x for n in NEGATIVE_KEYWORDS) else "✅ 일반"
                    )
                    st.dataframe(kw_df, use_container_width=True, height=440,
                                 hide_index=True)
                    st.markdown('</div>', unsafe_allow_html=True)

                st.markdown("---")

                # ── 키워드 빈도 막대 차트 ────────────────────────
                st.markdown('<p class="sec-head">📊 상위 30개 키워드 빈도 차트</p>',
                            unsafe_allow_html=True)
                top30 = all_kws[:30]
                kw_names = [k[0] for k in top30]
                kw_vals  = [k[1] for k in top30]
                kw_types = [
                    "부정 키워드" if any(n in kw for n in NEGATIVE_KEYWORDS) else "일반 키워드"
                    for kw in kw_names
                ]
                kw_chart_df = pd.DataFrame({
                    "키워드": kw_names, "언급 횟수": kw_vals, "유형": kw_types
                })
                fig_kw = px.bar(
                    kw_chart_df, x="키워드", y="언급 횟수", color="유형",
                    color_discrete_map={"부정 키워드": C["red"], "일반 키워드": C["sky"]},
                    text="언급 횟수", template=PLOTLY_TPL,
                    title="상위 30개 키워드 빈도  ·  빨간색 = 부정적 키워드",
                )
                fig_kw.update_traces(texttemplate="%{text}", textposition="outside")
                fig_kw.update_layout(
                    height=400, margin=dict(t=50, b=90, l=60, r=20),
                    xaxis_tickangle=-35,
                    legend_title_text="",
                    title_font=dict(size=14, color=C["navy"]),
                )
                st.plotly_chart(fig_kw, use_container_width=True)
                st.markdown("---")

                # ── 업무별 VOC 분석 ──────────────────────────────
                if M["business"]:
                    st.markdown('<p class="sec-head">🏢 업무별 VOC 키워드 분석</p>',
                                unsafe_allow_html=True)
                    biz_sel = st.selectbox(
                        "분석할 업무를 선택하세요",
                        df_f[M["business"]].dropna().astype(str).unique(),
                        key="voc_biz_sel",
                    )
                    biz_voc = [
                        t for t in df_f.loc[
                            df_f[M["business"]].astype(str) == biz_sel, M["voc"]
                        ].astype(str).str.strip().tolist()
                        if t and t != "nan"
                    ]
                    if biz_voc:
                        with st.spinner(f"[{biz_sel}] 분석 중…"):
                            biz_kws = extract_keywords(biz_voc, top_n=30)
                        bwc_c, bkw_c = st.columns([3, 2])
                        with bwc_c:
                            st.markdown(f'<div class="card-blue"><b>[{biz_sel}] 워드클라우드</b>',
                                        unsafe_allow_html=True)
                            if WORDCLOUD_AVAILABLE and biz_kws:
                                bimg = make_wordcloud_image(biz_kws)
                                if bimg:
                                    st.image(bimg, use_container_width=True)
                            st.markdown('</div>', unsafe_allow_html=True)
                        with bkw_c:
                            st.markdown(f'<div class="card"><b>[{biz_sel}] Top 15 키워드</b>',
                                        unsafe_allow_html=True)
                            if biz_kws:
                                bkdf = pd.DataFrame(biz_kws[:15], columns=["키워드","언급 횟수"])
                                st.dataframe(bkdf, use_container_width=True,
                                             height=320, hide_index=True)
                            st.markdown('</div>', unsafe_allow_html=True)
                    else:
                        st.info("해당 업무의 VOC 데이터가 없습니다.")

                st.markdown("---")

                # ── 연령대별 VOC 분석 ────────────────────────────
                if M["age"]:
                    st.markdown('<p class="sec-head">👥 연령대별 VOC 키워드 분석</p>',
                                unsafe_allow_html=True)
                    age_sel = st.selectbox(
                        "분석할 연령대를 선택하세요",
                        df_f[M["age"]].dropna().astype(str).unique(),
                        key="voc_age_sel",
                    )
                    age_voc = [
                        t for t in df_f.loc[
                            df_f[M["age"]].astype(str) == age_sel, M["voc"]
                        ].astype(str).str.strip().tolist()
                        if t and t != "nan"
                    ]
                    if age_voc:
                        with st.spinner(f"[{age_sel}] 분석 중…"):
                            age_kws = extract_keywords(age_voc, top_n=30)
                        awc_c, akw_c = st.columns([3, 2])
                        with awc_c:
                            st.markdown(f'<div class="card-blue"><b>[{age_sel}] 워드클라우드</b>',
                                        unsafe_allow_html=True)
                            if WORDCLOUD_AVAILABLE and age_kws:
                                aimg = make_wordcloud_image(age_kws)
                                if aimg:
                                    st.image(aimg, use_container_width=True)
                            st.markdown('</div>', unsafe_allow_html=True)
                        with akw_c:
                            st.markdown(f'<div class="card"><b>[{age_sel}] Top 15 키워드</b>',
                                        unsafe_allow_html=True)
                            if age_kws:
                                akdf = pd.DataFrame(age_kws[:15], columns=["키워드","언급 횟수"])
                                st.dataframe(akdf, use_container_width=True,
                                             height=320, hide_index=True)
                            st.markdown('</div>', unsafe_allow_html=True)
                    else:
                        st.info("해당 연령대의 VOC 데이터가 없습니다.")


# ─────────────────────────────────────────────────────────────
#  TAB 4  CS 인사이트 & 잠재 민원 사전케어
# ─────────────────────────────────────────────────────────────
with tab4:

    # ── AI CS 인사이트 ───────────────────────────────────────
    st.markdown('<p class="sec-head">💡 AI CS 활동 방향 인사이트</p>', unsafe_allow_html=True)

    INSIGHT_RULES = [
        (["요금","비용","청구","과금","납부","고지"],
         "💳 요금·청구 관련 문의 집중 → 청구서 사전 안내 강화 및 비용 상담 전담 채널 확충 권장"),
        (["설치","공사","계량","계기","시공"],
         "🔧 설치·공사 관련 문의 집중 → 시공 일정 사전 통보, AS 프로세스 개선 권장"),
        (["정전","단전","고장","누전","장애"],
         "⚡ 정전·장애 민원 발생 → 긴급복구 안내 강화, 사전 예방 점검 확대 권장"),
        (["직원","친절","응대","상담","담당자"],
         "👤 직원 응대 언급 多 → 고객응대 매뉴얼 재정비, CS 친절 교육 강화 권장"),
        (["앱","홈페이지","사이트","온라인","인터넷","모바일"],
         "📱 디지털 채널 관련 언급 → 앱·웹 UX 개선 및 디지털 이용 가이드 제공 권장"),
        (["대기","기다림","오래","느림","지연"],
         "⏱ 대기·지연 관련 불만 → 처리 속도 개선 및 처리 현황 실시간 안내 강화 권장"),
        (["안전","위험","누전","화재"],
         "🦺 안전 관련 민원 → 즉시 현장 대응 및 안전 점검 프로세스 강화 필요"),
    ]

    def build_insight(cat, kws_top, cat_label):
        kw_text = " ".join([k for k, _ in kws_top[:8]])
        neg_found = [kw for kw in NEGATIVE_KEYWORDS if kw in kw_text]
        lines = [f"**[{cat_label}: {cat}]**"]
        lines.append(f"주요 키워드: " + " ".join([f"`{k}`" for k, _ in kws_top[:7]]))
        if neg_found:
            lines.append(f"⚠️ 부정 키워드 감지: **{', '.join(neg_found[:4])}** → 즉시 케어 필요")
        for rule_kws, rule_msg in INSIGHT_RULES:
            if any(rk in kw_text for rk in rule_kws):
                lines.append(rule_msg)
        return "\n\n".join(lines)

    if not M["voc"]:
        st.warning("VOC 컬럼을 선택해야 인사이트를 생성할 수 있습니다.")
    else:
        in_l, in_r = st.columns(2)
        col_toggle = [in_l, in_r]
        idx = 0

        if M["business"]:
            with st.spinner("업무별 VOC 분석 중…"):
                for biz in df_f[M["business"]].dropna().value_counts().head(8).index:
                    texts_b = [
                        t for t in df_f.loc[
                            df_f[M["business"]].astype(str) == str(biz), M["voc"]
                        ].astype(str).str.strip().tolist()
                        if t and t != "nan"
                    ]
                    if not texts_b:
                        continue
                    kws_b = extract_keywords(texts_b, top_n=10)
                    insight_txt = build_insight(str(biz), kws_b, "업무")
                    card_cls = "card-red" if any(
                        nk in " ".join([k for k, _ in kws_b[:5]])
                        for nk in NEGATIVE_KEYWORDS
                    ) else "card-blue"
                    with col_toggle[idx % 2]:
                        st.markdown(
                            f'<div class="{card_cls}">{insight_txt}</div>',
                            unsafe_allow_html=True,
                        )
                    idx += 1

        if M["age"]:
            with st.spinner("연령대별 VOC 분석 중…"):
                for age in df_f[M["age"]].dropna().value_counts().head(6).index:
                    texts_a = [
                        t for t in df_f.loc[
                            df_f[M["age"]].astype(str) == str(age), M["voc"]
                        ].astype(str).str.strip().tolist()
                        if t and t != "nan"
                    ]
                    if not texts_a:
                        continue
                    kws_a = extract_keywords(texts_a, top_n=10)
                    insight_txt = build_insight(str(age), kws_a, "연령대")
                    card_cls = "card-gold"
                    with col_toggle[idx % 2]:
                        st.markdown(
                            f'<div class="{card_cls}">{insight_txt}</div>',
                            unsafe_allow_html=True,
                        )
                    idx += 1

    st.markdown("---")

    # ── 잠재 민원고객 사전케어 리스트 ───────────────────────
    st.markdown('<p class="sec-head">🚨 잠재적 민원고객 사전케어 리스트 (AI 자동 추출)</p>',
                unsafe_allow_html=True)

    st.markdown("""
<div class="card-red">
<b>📌 추출 기준</b> — 부정적 키워드(불만, 불편, 오류, 지연, 고장 등)가 VOC에 포함된 고객을 AI가 자동으로 식별합니다.<br>
해당 고객에게 <b>72시간 이내</b> 선제적으로 연락하여 민원 발생을 사전에 차단하세요.
</div>
    """, unsafe_allow_html=True)

    if not M["voc"]:
        st.warning("VOC 컬럼을 선택해야 리스트를 추출할 수 있습니다.")
    else:
        with st.spinner("AI 감성 분석 기반 잠재 민원고객 추출 중…"):
            neg_res  = df_f[M["voc"]].apply(check_negative)
            neg_kw_s = neg_res.apply(lambda x: ", ".join(x[1]) if x[1] else "")
            neg_mask = pd.Series(_row_sentiments, index=df_f.index) == "negative"

        df_neg = df_f[neg_mask].copy()
        df_neg["감지된_부정키워드"] = neg_kw_s[neg_mask].values
        neg_n = len(df_neg)
        neg_r = neg_n / max(len(df_f), 1) * 100

        # 케어 지표 3종
        nc1, nc2, nc3 = st.columns(3)
        with nc1:
            st.metric("🚨 잠재 민원고객 수", f"{neg_n:,}명")
        with nc2:
            st.metric("📊 전체 대비 비율",   f"{neg_r:.1f}%",
                      delta=f"긍정 {100 - neg_r:.1f}%",
                      delta_color="normal")
        with nc3:
            if M["score"] and neg_n > 0:
                neg_avg_s = pd.to_numeric(df_neg[M["score"]], errors="coerce").mean()
                all_avg_s = pd.to_numeric(df_f[M["score"]], errors="coerce").mean()
                st.metric("⭐ 잠재민원고객 평균 만족도",
                          f"{neg_avg_s:.2f}점",
                          delta=f"{neg_avg_s - all_avg_s:+.2f} vs 전체 평균",
                          delta_color="inverse")

        if neg_n > 0:
            st.markdown("<br>", unsafe_allow_html=True)

            # 부정 키워드 분포 도넛 차트
            all_neg_flat = []
            for kws in df_neg["감지된_부정키워드"]:
                all_neg_flat.extend([k.strip() for k in kws.split(",") if k.strip()])
            neg_kw_cnt = Counter(all_neg_flat).most_common(12)

            if neg_kw_cnt:
                nkw_df = pd.DataFrame(neg_kw_cnt, columns=["부정키워드", "감지횟수"])
                nk_l, nk_r = st.columns([3, 2])
                with nk_l:
                    fig_neg = px.bar(
                        nkw_df, x="부정키워드", y="감지횟수",
                        color_discrete_sequence=[C["red"]],
                        text="감지횟수", template=PLOTLY_TPL,
                        title="자주 감지된 부정 키워드 Top 12",
                    )
                    fig_neg.update_traces(texttemplate="%{text}", textposition="outside")
                    fig_neg.update_layout(
                        height=340, margin=dict(t=50, b=70, l=60, r=20),
                        xaxis_tickangle=-25,
                        title_font=dict(size=14, color=C["navy"]),
                    )
                    st.plotly_chart(fig_neg, use_container_width=True)
                with nk_r:
                    fig_don = px.pie(
                        nkw_df.head(8), names="부정키워드", values="감지횟수",
                        hole=0.5, color_discrete_sequence=px.colors.sequential.Reds[::-1],
                        title="부정 키워드 비중",
                        template=PLOTLY_TPL,
                    )
                    fig_don.update_traces(
                        textinfo="percent+label", textfont_size=11,
                        marker=dict(line=dict(color="white", width=2)),
                    )
                    fig_don.update_layout(
                        height=340, margin=dict(t=50, b=20, l=20, r=20),
                        showlegend=False,
                        title_font=dict(size=14, color=C["navy"]),
                    )
                    st.plotly_chart(fig_don, use_container_width=True)

            # ── 리스트 테이블 ────────────────────────────────
            display_cols = []
            for key in ["id", "name", "contact", "age", "contract", "business", "score", "voc"]:
                if M[key] and M[key] in df_neg.columns:
                    display_cols.append(M[key])
            display_cols.append("감지된_부정키워드")

            df_disp = df_neg[display_cols].reset_index(drop=True)

            st.markdown(
                f'<p class="sec-head">📋 잠재 민원고객 리스트 — 총 <span style="color:{C["red"]}">'
                f'{neg_n:,}명</span></p>',
                unsafe_allow_html=True,
            )
            st.dataframe(df_disp, use_container_width=True, height=440, hide_index=True)

            excel_bytes = df_to_excel_bytes(df_disp)
            st.download_button(
                label="📥  잠재 민원고객 리스트 엑셀 다운로드 (.xlsx)",
                data=excel_bytes,
                file_name="잠재민원고객_사전케어리스트.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

            st.markdown("""
<div class="card-red">
<b>⚠️ 사전케어 행동 가이드</b><br><br>
✅ <b>72시간 이내</b> — 담당자가 직접 전화·문자로 능동 연락<br>
✅ <b>경청 우선</b> — 고객 불만을 끝까지 듣고 공감 후 해결책 제시<br>
✅ <b>CRM 기록 필수</b> — 접촉 일시, 처리 내용, 결과를 반드시 시스템에 기록<br>
✅ <b>패턴 분석</b> — 동일 유형 불만이 반복되면 서비스 프로세스 자체를 개선하세요
</div>
            """, unsafe_allow_html=True)

        else:
            st.markdown("""
<div class="card-teal">
🎉 <b>부정적 VOC가 감지된 잠재 민원고객이 없습니다!</b><br>
현재 고객 만족 수준이 양호합니다. 지속적인 모니터링을 유지하세요.
</div>
            """, unsafe_allow_html=True)

    # ── Plotly 추가: 긍정/부정 비율 시각화 ─────────────────
    if M["voc"] and voc_texts_all:
        st.markdown("---")
        st.markdown('<p class="sec-head">📊 VOC 긍정 / 부정 비율 요약</p>',
                    unsafe_allow_html=True)
        ratio_l, ratio_r = st.columns([1, 2])
        with ratio_l:
            fig_ratio = go.Figure(go.Indicator(
                mode="gauge+number",
                value=round(100 - neg_ratio, 1),
                number={"suffix": "%", "font": {"size": 42, "color": C["teal"]}},
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar":  {"color": C["teal"], "thickness": 0.25},
                    "steps": [
                        {"range": [0,  40], "color": "#ffcdd2"},
                        {"range": [40, 70], "color": "#fff9c4"},
                        {"range": [70, 100], "color": "#c8e6c9"},
                    ],
                },
                title={"text": "긍정 VOC 비율", "font": {"size": 15, "color": C["navy"]}},
            ))
            fig_ratio.update_layout(
                height=260, margin=dict(t=60, b=20, l=30, r=30),
                paper_bgcolor="white",
            )
            st.plotly_chart(fig_ratio, use_container_width=True)

        with ratio_r:
            fig_pn = px.pie(
                names=["긍정 VOC", "부정 VOC(잠재 민원)"],
                values=[pos_cnt, neg_cnt],
                color_discrete_sequence=[C["teal"], C["red"]],
                hole=0.55,
                template=PLOTLY_TPL,
                title="긍정 / 부정 VOC 비율",
            )
            fig_pn.update_traces(
                textinfo="percent+label", textfont_size=14,
                marker=dict(line=dict(color="white", width=3)),
            )
            fig_pn.update_layout(
                height=260, margin=dict(t=50, b=10, l=20, r=20),
                showlegend=True,
                title_font=dict(size=14, color=C["navy"]),
            )
            st.plotly_chart(fig_pn, use_container_width=True)
