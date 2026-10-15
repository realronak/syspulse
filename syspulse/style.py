"""
SysPulse UI Stylesheet
Clean, modern dark styling tailored for Wayland, Hyprland, and laptop screens.
"""

CSS_TEXT = """
/* Main Application Window */
window {
    background-color: #0f1015;
    color: #e2e8f0;
    font-family: system-ui, -apple-system, "Segoe UI", Roboto, "Cantarell", sans-serif;
}

/* Sidebar Navigation */
.sidebar {
    background-color: #14151e;
    border-right: 1px solid #1f2230;
    padding: 12px 8px;
}

.sidebar-title {
    font-weight: 800;
    font-size: 16px;
    color: #38bdf8;
    margin-bottom: 16px;
    padding: 0 10px;
}

.nav-button {
    background: transparent;
    border: none;
    border-radius: 6px;
    color: #94a3b8;
    font-weight: 500;
    font-size: 13px;
    padding: 8px 12px;
    margin-bottom: 4px;
    transition: background 150ms ease, color 150ms ease;
}

.nav-button:hover {
    background-color: #1e2232;
    color: #f8fafc;
}

.nav-button.active {
    background-color: #252b40;
    color: #38bdf8;
    font-weight: 700;
}

/* Header Bar & Status */
.header-bar {
    background-color: #14151e;
    border-bottom: 1px solid #1f2230;
    padding: 10px 18px;
}

.status-pill {
    background-color: #1a1e2d;
    border: 1px solid #272d42;
    border-radius: 14px;
    padding: 4px 10px;
    font-size: 11px;
    color: #94a3b8;
}

.status-pill-val {
    color: #38bdf8;
    font-weight: 600;
}

/* Cards */
.metric-card {
    background-color: #151722;
    border: 1px solid #212536;
    border-radius: 8px;
    padding: 14px 16px;
}

.metric-card-title {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #64748b;
}

.metric-card-val {
    font-size: 24px;
    font-weight: 800;
    color: #f1f5f9;
    margin: 4px 0;
}

.metric-card-sub {
    font-size: 11px;
    color: #94a3b8;
}

/* Progress Bars */
progressbar trough {
    background-color: #1d2130;
    border-radius: 4px;
    min-height: 6px;
}

progressbar progress {
    background-color: #38bdf8;
    border-radius: 4px;
}

progressbar.green progress {
    background-color: #10b981;
}

progressbar.orange progress {
    background-color: #f59e0b;
}

progressbar.red progress {
    background-color: #ef4444;
}

progressbar.purple progress {
    background-color: #8b5cf6;
}

/* Action Buttons */
.btn-action {
    background-color: #1e2232;
    border: 1px solid #2b324a;
    border-radius: 6px;
    color: #e2e8f0;
    font-weight: 600;
    font-size: 12px;
    padding: 6px 14px;
}

.btn-action:hover {
    background-color: #272d42;
    color: #ffffff;
}

.btn-danger {
    background-color: #451a1a;
    border: 1px solid #7f1d1d;
    color: #fca5a5;
}

.btn-danger:hover {
    background-color: #7f1d1d;
    color: #ffffff;
}

.btn-primary {
    background-color: #0369a1;
    border: 1px solid #0284c7;
    color: #ffffff;
}

.btn-primary:hover {
    background-color: #0284c7;
}

/* Tables / ColumnView */
columnview {
    background-color: #12141c;
    border: 1px solid #1f2230;
    border-radius: 6px;
}

columnview header > button {
    background-color: #161925;
    color: #94a3b8;
    font-weight: 600;
    font-size: 11px;
    border: none;
    border-bottom: 1px solid #222638;
    padding: 8px 10px;
}

columnview row {
    padding: 4px 8px;
    border-bottom: 1px solid #181b26;
    color: #cbd5e1;
}

columnview row:selected {
    background-color: #1e2a47;
    color: #38bdf8;
}

/* Search Entry */
searchentry {
    background-color: #161925;
    border: 1px solid #222638;
    border-radius: 6px;
    color: #f1f5f9;
    padding: 4px 10px;
}

searchentry:focus-within {
    border-color: #38bdf8;
}

/* Dropdown */
dropdown button {
    background-color: #161925;
    border: 1px solid #222638;
    border-radius: 6px;
    color: #cbd5e1;
    padding: 6px 12px;
}
"""

CSS_DATA = CSS_TEXT.encode("utf-8")
