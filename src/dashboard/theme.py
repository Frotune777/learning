"""
File: src/dashboard/theme.py
Purpose: Professional ultra-modern institutional dark theme for Sharegenius.
Uses modern fonts (Inter), sleek glassmorphism, tailored CSS variables,
and custom card/badge designs.
"""

CSS_THEME = """
<style>
/* Import Inter and JetBrains Mono fonts */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

/* Hide Streamlit default sidebar and unwanted header elements */
[data-testid="stSidebar"], section[data-testid="stSidebar"] {
    display: none !important;
}
[data-testid="collapsedControl"] {
    display: none !important;
}
header[data-testid="stHeader"] {
    background: transparent !important;
}

/* Global Font and Canvas Setup */
html, body, [class*="css"], [class*="st-"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    color: #e2e8f0;
}
code, pre, .mono {
    font-family: 'JetBrains Mono', monospace !important;
}

.stApp {
    background: radial-gradient(circle at 15% 15%, #131722 0%, #0c0e14 100%) !important;
}

/* Top App Brand Bar */
.top-brand-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 14px 28px;
    background: rgba(22, 27, 40, 0.75);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 16px;
    margin-bottom: 18px;
    box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
}
.brand-title {
    font-size: 1.45rem;
    font-weight: 800;
    letter-spacing: -0.02em;
    background: linear-gradient(135deg, #ffffff 0%, #94a3b8 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    display: flex;
    align-items: center;
    gap: 10px;
}
.brand-badge {
    background: linear-gradient(135deg, rgba(59, 130, 246, 0.2) 0%, rgba(147, 51, 234, 0.2) 100%);
    border: 1px solid rgba(147, 51, 234, 0.4);
    color: #a855f7;
    font-size: 0.72rem;
    font-weight: 700;
    padding: 3px 10px;
    border-radius: 9999px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* Glassmorphism Metric Cards */
.pro-card {
    background: rgba(22, 27, 40, 0.6);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 14px;
    padding: 18px 22px;
    transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}
.pro-card:hover {
    transform: translateY(-2px);
    border-color: rgba(59, 130, 246, 0.35);
    box-shadow: 0 10px 24px -10px rgba(59, 130, 246, 0.3);
}
.pro-card-title {
    font-size: 0.78rem;
    font-weight: 600;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 6px;
}
.pro-card-value {
    font-size: 1.85rem;
    font-weight: 800;
    color: #f8fafc;
    line-height: 1.1;
    font-feature-settings: "tnum";
}
.pro-card-sub {
    font-size: 0.8rem;
    color: #64748b;
    margin-top: 6px;
}

/* Badges */
.badge-bull {
    background: rgba(16, 185, 129, 0.15);
    color: #10b981;
    border: 1px solid rgba(16, 185, 129, 0.35);
    padding: 3px 9px;
    border-radius: 6px;
    font-weight: 600;
    font-size: 0.75rem;
}
.badge-bear {
    background: rgba(239, 68, 68, 0.15);
    color: #ef4444;
    border: 1px solid rgba(239, 68, 68, 0.35);
    padding: 3px 9px;
    border-radius: 6px;
    font-weight: 600;
    font-size: 0.75rem;
}
.badge-neutral {
    background: rgba(148, 163, 184, 0.15);
    color: #94a3b8;
    border: 1px solid rgba(148, 163, 184, 0.3);
    padding: 3px 9px;
    border-radius: 6px;
    font-weight: 600;
    font-size: 0.75rem;
}

/* Button & Input Styling */
.stButton > button {
    border-radius: 10px !important;
    font-weight: 600 !important;
    letter-spacing: -0.01em !important;
    transition: all 0.2s ease !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
}
.stButton > button:hover {
    border-color: #3b82f6 !important;
    box-shadow: 0 4px 14px rgba(59, 130, 246, 0.35) !important;
}
div[data-baseweb="select"] > div {
    border-radius: 10px !important;
    border-color: rgba(255, 255, 255, 0.12) !important;
}

/* Section Header Dividers */
.section-hdr {
    display: flex;
    align-items: center;
    gap: 12px;
    margin: 24px 0 14px 0;
}
.section-hdr h3 {
    font-size: 1.2rem;
    font-weight: 700;
    color: #f1f5f9;
    margin: 0;
}
.section-hdr .line {
    flex-grow: 1;
    height: 1px;
    background: rgba(255, 255, 255, 0.08);
}
</style>
"""

NAV_STYLES = {
    "container": {
        "padding": "6px",
        "background-color": "rgba(22, 27, 40, 0.85)",
        "backdrop-filter": "blur(14px)",
        "-webkit-backdrop-filter": "blur(14px)",
        "border": "1px solid rgba(255, 255, 255, 0.08)",
        "border-radius": "14px",
        "margin-bottom": "24px",
        "box-shadow": "0 4px 20px rgba(0,0,0,0.3)",
    },
    "icon": {
        "color": "#94a3b8",
        "font-size": "15px",
    },
    "nav-link": {
        "font-size": "13.5px",
        "font-weight": "600",
        "color": "#94a3b8",
        "text-align": "center",
        "margin": "2px 4px",
        "padding": "10px 14px",
        "border-radius": "9px",
        "--hover-color": "rgba(255, 255, 255, 0.06)",
        "transition": "all 0.2s ease",
    },
    "nav-link-selected": {
        "background": "linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)",
        "color": "#ffffff",
        "font-weight": "700",
        "box-shadow": "0 4px 12px rgba(37, 99, 235, 0.4)",
    },
}
