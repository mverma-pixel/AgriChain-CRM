from datetime import datetime, timedelta
from collections import OrderedDict
from flask import Blueprint, render_template, request
from flask_login import login_required
from models import Lead, Contact, Company, Task, CalendarEvent
from extensions import db
from ga_client import ga_is_configured, get_ga_users_by_country
import json

dashboard_bp = Blueprint('dashboard', __name__)

COUNTRY_MAP = OrderedDict([
    ('AU',  'Australia'),
    ('CA',  'Canada'),
    ('USA', 'United States'),
    ('NZ',  'New Zealand'),
])

# Distinct, professional palette — no orange
COUNTRY_COLORS = {
    'AU':  '#1565C0',  # Royal Blue
    'CA':  '#C62828',  # Canada Red
    'USA': '#2E7D32',  # Forest Green
    'NZ':  '#7B1FA2',  # Deep Purple
}

TF_CONFIG = {
    '7d':     {'days': 7,    'label': 'Last 7 Days',    'gran': 'day'},
    '30d':    {'days': 30,   'label': 'Last 30 Days',   'gran': 'day'},
    '3m':     {'days': 91,   'label': 'Last 3 Months',  'gran': 'week'},
    '6m':     {'days': 182,  'label': 'Last 6 Months',  'gran': 'week'},
    '12m':    {'days': 365,  'label': 'Last 12 Months', 'gran': 'month'},
    'all':    {'days': None, 'label': 'All Time',        'gran': 'month'},
    'custom': {'days': None, 'label': 'Custom Range',    'gran': 'day'},
}

STAGES = ['New Lead', 'SAL', 'Out', 'Demo', 'Close Won', 'Close Lost']
STAGE_COLORS = {
    'New Lead':   '#4A7FA5',
    'SAL':        '#6AAE20',
    'Out':        '#E53935',
    'Demo':       '#173347',
    'Close Won':  '#4CAF50',
    'Close Lost': '#F9A825',
}


@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
@login_required
def index():
    today = datetime.utcnow()

    timeframe = request.args.get('timeframe', '30d')
    if timeframe not in TF_CONFIG:
        timeframe = '30d'

    cfg = TF_CONFIG[timeframe]
    timeframe_label = cfg['label']
    custom_from = request.args.get('from', '')
    custom_to   = request.args.get('to', '')
    date_to = today

    if timeframe == 'custom':
        try:
            date_from = datetime.strptime(custom_from, '%Y-%m-%d')
            date_to   = datetime.strptime(custom_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            timeframe_label = f"{date_from.strftime('%d %b %Y')} – {date_to.strftime('%d %b %Y')}"
        except ValueError:
            timeframe, cfg = '30d', TF_CONFIG['30d']
            date_from = today - timedelta(days=30)
            timeframe_label = cfg['label']
    elif timeframe == 'all':
        first = Lead.query.order_by(Lead.created_at.asc()).first()
        date_from = first.created_at if first else (today - timedelta(days=365))
    else:
        date_from = today - timedelta(days=cfg['days'])

    gran = cfg['gran']
    if timeframe == 'custom':
        d = (date_to - date_from).days
        gran = 'day' if d <= 31 else ('week' if d <= 182 else 'month')

    # ── All-time secondary stats ──────────────────────────────
    total_contacts  = Contact.query.count()
    total_companies = Company.query.count()
    open_tasks      = Task.query.filter(Task.status.in_(['Open', 'In Progress'])).count()
    events_this_week = CalendarEvent.query.filter(
        CalendarEvent.start_datetime >= today,
        CalendarEvent.start_datetime <= today + timedelta(days=7),
    ).count()

    # ── Period query helper ───────────────────────────────────
    def pq():
        q = Lead.query.filter(Lead.created_at >= date_from)
        if timeframe == 'custom':
            q = q.filter(Lead.created_at <= date_to)
        return q

    # ── Period stats ──────────────────────────────────────────
    period_total  = pq().count()
    period_sals   = pq().filter_by(status='SAL').count()
    period_won    = pq().filter_by(status='Close Won').count()
    period_lost   = pq().filter_by(status='Close Lost').count()
    win_rate = (
        round((period_won / (period_won + period_lost)) * 100)
        if (period_won + period_lost) > 0 else None
    )
    lead_to_sal_pct = round((period_sals / period_total) * 100) if period_total > 0 else None

    # ── Country breakdown ─────────────────────────────────────
    country_totals = {
        code: pq().filter(Lead.country == name).count()
        for code, name in COUNTRY_MAP.items()
    }

    # ── Period funnel (timeframe-filtered) ───────────────────
    period_funnel = [
        {'stage': s, 'count': pq().filter_by(status=s).count(),
         'color': STAGE_COLORS[s]}
        for s in STAGES
    ]

    # ── Period leads list ─────────────────────────────────────
    period_leads = pq().order_by(Lead.created_at.desc()).limit(20).all()

    # ── Chart: try GA first, fall back to leads ───────────────
    ga_connected = ga_is_configured()
    chart_title  = 'Users Over Time'   # always show this label; GA badge shows connection status

    all_period_leads = pq().all()

    if ga_connected:
        ga_raw = get_ga_users_by_country(date_from, date_to)
        if ga_raw:
            time_labels, country_series = _build_ga_series(gran, date_from, date_to, ga_raw)
        else:
            ga_connected = False
            chart_title  = 'Leads Over Time'
            time_labels, country_series = _build_lead_series(gran, date_from, date_to, all_period_leads)
    else:
        time_labels, country_series = _build_lead_series(gran, date_from, date_to, all_period_leads)

    chart_labels      = json.dumps(time_labels)
    chart_series_json = json.dumps({
        code: {'data': country_series.get(code, [0] * len(time_labels)), 'color': COUNTRY_COLORS[code]}
        for code in COUNTRY_MAP
    })

    # ── Pie chart ─────────────────────────────────────────────
    pie_labels = json.dumps(list(COUNTRY_MAP.keys()))
    pie_values = json.dumps([country_totals[c] for c in COUNTRY_MAP])
    pie_colors = json.dumps([COUNTRY_COLORS[c] for c in COUNTRY_MAP])

    # ── Kanban pre-load ───────────────────────────────────────
    kanban_data = {
        code: {
            stage: [
                {'id': l.id, 'name': l.name, 'company': l.company or '', 'assigned_to': l.assigned_to}
                for l in all_period_leads if l.country == name and l.status == stage
            ]
            for stage in STAGES
        }
        for code, name in COUNTRY_MAP.items()
    }

    # ── Today's tasks ─────────────────────────────────────────
    today_start  = today.replace(hour=0, minute=0, second=0, microsecond=0)
    todays_tasks = Task.query.filter(
        Task.status.in_(['Open', 'In Progress']),
        Task.due_date <= today_start + timedelta(days=1),
    ).order_by(Task.due_date.asc()).limit(10).all()

    return render_template('dashboard.html',
        today=today,
        timeframe=timeframe,
        timeframe_label=timeframe_label,
        custom_from=custom_from,
        custom_to=custom_to,
        ga_connected=ga_connected,
        chart_title=chart_title,
        total_contacts=total_contacts,
        total_companies=total_companies,
        open_tasks=open_tasks,
        events_this_week=events_this_week,
        period_total=period_total,
        period_sals=period_sals,
        period_won=period_won,
        period_lost=period_lost,
        win_rate=win_rate,
        lead_to_sal_pct=lead_to_sal_pct,
        country_totals=country_totals,
        period_funnel=period_funnel,
        period_leads=period_leads,
        chart_labels=chart_labels,
        chart_series_json=chart_series_json,
        pie_labels=pie_labels,
        pie_values=pie_values,
        pie_colors=pie_colors,
        kanban_json=json.dumps(kanban_data),
        country_names_json=json.dumps(dict(COUNTRY_MAP)),
        stage_colors_json=json.dumps(STAGE_COLORS),
        todays_tasks=todays_tasks,
    )


# ── Time-series helpers ───────────────────────────────────────

def _buckets(gran, date_from, date_to):
    """Return an OrderedDict of label → {} for the given granularity."""
    series = OrderedDict()
    if gran == 'day':
        d, end = _to_date(date_from), _to_date(date_to)
        while d <= end:
            series[d.strftime('%d %b')] = {}
            d += timedelta(days=1)
    elif gran == 'week':
        d, end = _to_date(date_from), _to_date(date_to)
        while d <= end:
            series[d.strftime('%d %b')] = {}
            d += timedelta(weeks=1)
    else:  # month
        d = date_from.replace(day=1) if hasattr(date_from, 'replace') else date_from
        end = date_to
        while d <= end:
            k = d.strftime('%b %Y')
            series.setdefault(k, {})
            d = d.replace(month=d.month % 12 + 1, day=1,
                          year=d.year + (1 if d.month == 12 else 0))
    return series


def _build_lead_series(gran, date_from, date_to, leads):
    series = _buckets(gran, date_from, date_to)
    keys   = list(series.keys())
    start  = _to_date(date_from)

    for lead in leads:
        ld   = lead.created_at
        code = _CODES.get(lead.country)
        if not code:
            continue
        if gran == 'day':
            k = ld.strftime('%d %b')
        elif gran == 'week':
            idx = min((ld.date() - start).days // 7, len(keys) - 1)
            k   = keys[idx] if idx >= 0 else None
        else:
            k = ld.strftime('%b %Y')
        if k and k in series:
            series[k][code] = series[k].get(code, 0) + 1

    labels = list(series.keys())
    return labels, {c: [series[l].get(c, 0) for l in labels] for c in ('AU','CA','USA','NZ')}


def _build_ga_series(gran, date_from, date_to, ga_raw):
    """Convert {code: {YYYYMMDD: count}} to (labels, {code: [counts]})."""
    from datetime import datetime as _dt
    series = _buckets(gran, date_from, date_to)
    keys   = list(series.keys())
    start  = _to_date(date_from)

    for code, date_counts in ga_raw.items():
        for yyyymmdd, count in date_counts.items():
            d = _dt.strptime(yyyymmdd, '%Y%m%d')
            if gran == 'day':
                k = d.strftime('%d %b')
            elif gran == 'week':
                idx = min((d.date() - start).days // 7, len(keys) - 1)
                k   = keys[idx] if idx >= 0 else None
            else:
                k = d.strftime('%b %Y')
            if k and k in series:
                series[k][code] = series[k].get(code, 0) + count

    labels = list(series.keys())
    return labels, {c: [series[l].get(c, 0) for l in labels] for c in ('AU','CA','USA','NZ')}


def _to_date(dt):
    return dt.date() if hasattr(dt, 'date') else dt


_CODES = {
    'Australia':     'AU',
    'Canada':        'CA',
    'United States': 'USA',
    'New Zealand':   'NZ',
}
