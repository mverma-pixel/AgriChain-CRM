"""
Centralised lead status + source configuration.
Import from here everywhere status/source logic is needed.
"""

# ── Statuses ───────────────────────────────────────────────
ALL_STATUSES = ['New Lead', 'Pending', 'SAL', 'Out', 'Demo', 'Close Won', 'Close Lost']

STATUS_COLORS = {
    'New Lead':   '#4A7FA5',
    'Pending':    '#D97706',   # mustard / amber
    'SAL':        '#A8D86E',
    'Out':        '#E53935',
    'Demo':       '#173347',
    'Close Won':  '#6AAE20',
    'Close Lost': '#F9A825',
}

# Terminal — no further transitions allowed
TERMINAL_STATUSES = {'Close Won', 'Close Lost'}

# Entry or exit requires written feedback
FEEDBACK_REQUIRED = {'Out', 'Close Lost'}

# Allowed next statuses from each stage
VALID_TRANSITIONS = {
    'New Lead': ['Pending', 'SAL', 'Out'],
    'Pending':  ['SAL', 'Out'],
    'SAL':      ['Demo', 'Close Won', 'Close Lost'],   # SAL constraint
    'Out':      ['New Lead', 'Pending', 'SAL'],
    'Demo':     ['Close Won', 'Close Lost', 'SAL'],
    # Close Won / Close Lost → terminal (empty)
}

# Days in New Lead before auto-advancing to Pending
AUTO_PENDING_DAYS = 3

# ── Source channels ────────────────────────────────────────
SOURCE_CHANNELS = [
    'Homepage', 'About', 'Feature', 'User',
    'Blog', 'Google Ads', 'Chatbot', 'Call', 'Email',
]


def get_allowed_transitions(current_status):
    """Return allowed next statuses. Empty list if terminal."""
    if current_status in TERMINAL_STATUSES:
        return []
    return VALID_TRANSITIONS.get(current_status,
           [s for s in ALL_STATUSES if s != current_status and s not in TERMINAL_STATUSES])
