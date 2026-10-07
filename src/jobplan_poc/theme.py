"""Static presentation tokens; no record or user text enters the style block."""

import streamlit as st


TOKENS = {
    "brand-deep": "#0B3B3C", "brand-primary": "#1B7F5A", "brand-hover": "#14694A",
    "mint": "#E8F4EF", "surface": "#FFFFFF", "canvas": "#F6F8F7",
    "text": "#14292B", "text-secondary": "#44595B", "text-muted": "#5F7173",
    "border": "#D3DEDB", "border-control": "#6F8582",
    "attention-bg": "#FFF4DB", "attention-text": "#6B4700", "attention-icon": "#8A5300",
    "info-bg": "#E8F0F8", "info-text": "#1D4E89",
    "error-bg": "#FDECEA", "error-text": "#A4262C",
}
CSS = ":root {" + "".join(f"--{key}:{value};" for key, value in TOKENS.items()) + "}\n" + """
[data-testid="stMainBlockContainer"] {padding-top: 32px; padding-bottom: 40px; max-width: 1280px;}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {color: var(--text-muted); font-size: 13px;}
[data-testid="stCaptionContainer"] {opacity: 1;}
[data-testid="stDialog"] h3 {font-size: 18px; font-weight: 600;}
[data-testid="stText"] {font-family: inherit; line-height: 1.5;}
[data-testid="stButton"] button, [data-testid="stDownloadButton"] button {min-height: 40px;}
[data-testid="stTextInputRootElement"],
[data-testid="stSelectbox"] [role="group"] {min-height: 44px;}
[data-testid="stSelectbox"] input[role="combobox"] {min-height: 42px;}
[data-testid="stMain"] button:focus-visible,
[data-testid="stMain"] input:focus-visible,
[data-testid="stMain"] summary:focus-visible,
[data-testid="stMain"] [role="combobox"]:focus-visible,
[data-testid="stDialog"] button:focus-visible,
[data-testid="stDialog"] summary:focus-visible {
    outline: 3px solid var(--brand-primary); outline-offset: 2px;
}
[data-testid="stSelectbox"] [role="group"]:focus-within,
[data-testid="stMain"] [data-testid="stTextInput"]:focus-within {
    outline: 3px solid var(--brand-primary); outline-offset: 2px; border-radius: 8px;
}
[data-testid="stBaseButton-primary"]:hover {background: var(--brand-hover); color: var(--surface);}
div[class*="st-key-plan-card-"] {background: var(--surface); border-radius: 8px; gap: 8px; border-color: var(--border);}
div[class*="st-key-plan-card-"]:hover {background: var(--mint);}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"],
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {color: var(--surface);}
[data-testid="stSidebar"] [data-testid="stRadio"] label {
    min-height: 44px; padding: 8px; border-radius: 8px; border-left: 3px solid transparent;
}
[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {
    background: var(--mint); border-left-color: var(--brand-primary); color: var(--text);
}
[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) p {color: var(--text);}
[data-testid="stSidebar"] [data-testid="stRadio"] label:focus-within {
    outline: 3px solid var(--surface); outline-offset: 2px;
}
[data-testid="stSidebar"] button:focus-visible {outline: 3px solid var(--surface); outline-offset: 2px;}
@media (max-width: 700px) {
    [data-testid="stMainBlockContainer"] {padding-left: 16px; padding-right: 16px;}
}
"""


def apply_theme() -> None:
    st.markdown("<style>" + CSS + "</style>", unsafe_allow_html=True)
