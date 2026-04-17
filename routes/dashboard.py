from datetime import datetime, timedelta
from flask import Blueprint, render_template
from flask_login import login_required
from models import Lead, Contact, Company, Task, CalendarEvent
from extensions import db

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
@login_required
def index():
    # Top stats
    total_leads = Lead.query.count()
    skye_leads = Lead.query.filter_by(assigned_to='Skye').count()
    tony_leads = Lead.query.filter_by(assigned_to='Tony').count()
    unassigned_leads = Lead.query.filter_by(assigned_to='Unassigned').count()

    total_contacts = Contact.query.count()
    total_companies = Company.query.count()
    open_tasks = Task.query.filter(Task.status.in_(['Open', 'In Progress'])).count()

    # Events this week
    today = datetime.utcnow()
    week_end = today + timedelta(days=7)
    events_this_week = CalendarEvent.query.filter(
        CalendarEvent.start_datetime >= today,
        CalendarEvent.start_datetime <= week_end
    ).count()

    # Funnel data
    stages = ['New Lead', 'SAL', 'Out', 'Demo', 'Close Won', 'Close Lost']
    funnel_data = []
    for stage in stages:
        count = Lead.query.filter_by(status=stage).count()
        funnel_data.append({'stage': stage, 'count': count})

    # Recent leads
    recent_leads = Lead.query.order_by(Lead.created_at.desc()).limit(10).all()

    # Today's tasks
    today_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    todays_tasks = Task.query.filter(
        Task.status.in_(['Open', 'In Progress']),
        Task.due_date <= today_end
    ).order_by(Task.due_date.asc()).limit(10).all()

    return render_template('dashboard.html',
        total_leads=total_leads,
        skye_leads=skye_leads,
        tony_leads=tony_leads,
        unassigned_leads=unassigned_leads,
        total_contacts=total_contacts,
        total_companies=total_companies,
        open_tasks=open_tasks,
        events_this_week=events_this_week,
        funnel_data=funnel_data,
        recent_leads=recent_leads,
        todays_tasks=todays_tasks,
        today=today,
    )
