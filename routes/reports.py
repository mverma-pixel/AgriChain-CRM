from datetime import datetime, timedelta
from flask import Blueprint, render_template, request
from flask_login import login_required
from models import Lead, Contact, Company, LeadStageHistory, ActivityLog
from extensions import db
from sqlalchemy import func

reports_bp = Blueprint('reports', __name__)

STAGES = ['New Lead', 'Pending', 'SAL', 'Out', 'Demo', 'Close Won', 'Close Lost']
CHANNELS = ['Homepage', 'About', 'Feature', 'User', 'Blog', 'Google Ads', 'Chatbot']
ASSIGNEES = ['Skye', 'Tony', 'Unassigned']


@reports_bp.route('/reports')
@login_required
def index():
    # --- Lead Funnel ---
    total_leads = Lead.query.count() or 1
    funnel = []
    for stage in STAGES:
        count = Lead.query.filter_by(status=stage).count()
        # Average days in stage from history
        avg_days_query = db.session.query(func.avg(LeadStageHistory.days_in_stage)).filter_by(stage=stage).scalar()
        avg_days = round(avg_days_query, 1) if avg_days_query else 0
        funnel.append({
            'stage': stage,
            'count': count,
            'pct': round(count / total_leads * 100, 1),
            'avg_days': avg_days,
        })

    # --- Source Performance ---
    source_data = []
    for channel in CHANNELS:
        total = Lead.query.filter_by(source_channel=channel).count()
        if total == 0:
            continue
        sal = Lead.query.filter_by(source_channel=channel, status='SAL').count()
        demo = Lead.query.filter_by(source_channel=channel, status='Demo').count()
        won = Lead.query.filter_by(source_channel=channel, status='Close Won').count()
        lost = Lead.query.filter_by(source_channel=channel, status='Close Lost').count()
        conv_rate = round(won / total * 100, 1) if total else 0
        source_data.append({
            'channel': channel, 'total': total, 'sal': sal, 'demo': demo,
            'won': won, 'lost': lost, 'conv_rate': conv_rate,
        })

    # --- Team Performance ---
    team_data = []
    for assignee in ASSIGNEES:
        total = Lead.query.filter_by(assigned_to=assignee).count()
        if total == 0:
            continue
        sal = Lead.query.filter_by(assigned_to=assignee, status='SAL').count()
        demo = Lead.query.filter_by(assigned_to=assignee, status='Demo').count()
        won = Lead.query.filter_by(assigned_to=assignee, status='Close Won').count()
        lost = Lead.query.filter_by(assigned_to=assignee, status='Close Lost').count()
        win_rate = round(won / (won + lost) * 100, 1) if (won + lost) > 0 else 0

        # Avg days to close
        closed_leads = Lead.query.filter_by(assigned_to=assignee, status='Close Won').all()
        if closed_leads:
            total_days = sum((l.updated_at - l.created_at).days for l in closed_leads)
            avg_days_close = round(total_days / len(closed_leads), 1)
        else:
            avg_days_close = 0

        team_data.append({
            'manager': assignee, 'total': total, 'sal': sal, 'demo': demo,
            'won': won, 'lost': lost, 'win_rate': win_rate, 'avg_days_close': avg_days_close,
        })

    # --- Activity Report ---
    date_from_str = request.args.get('date_from', '')
    date_to_str = request.args.get('date_to', '')
    user_filter = request.args.get('user_filter', '')
    action_filter = request.args.get('action_filter', '')

    activity_query = ActivityLog.query
    if date_from_str:
        try:
            activity_query = activity_query.filter(
                ActivityLog.created_at >= datetime.strptime(date_from_str, '%Y-%m-%d')
            )
        except ValueError:
            pass
    if date_to_str:
        try:
            activity_query = activity_query.filter(
                ActivityLog.created_at <= datetime.strptime(date_to_str, '%Y-%m-%d') + timedelta(days=1)
            )
        except ValueError:
            pass
    if user_filter:
        activity_query = activity_query.filter_by(user=user_filter)
    if action_filter:
        activity_query = activity_query.filter(ActivityLog.action.ilike(f'%{action_filter}%'))

    activity_logs = activity_query.order_by(ActivityLog.created_at.desc()).limit(100).all()

    # --- Funnel Leak Analysis ---
    leak_data = []
    ordered = ['New Lead', 'SAL', 'Demo', 'Close Won']
    for i, stage in enumerate(ordered):
        entered = LeadStageHistory.query.filter_by(stage=stage).count()
        if i < len(ordered) - 1:
            next_stage = ordered[i + 1]
            # Leads that have a history entry for next stage
            progressed = db.session.query(func.count(func.distinct(LeadStageHistory.lead_id))).filter_by(stage=next_stage).scalar() or 0
        else:
            progressed = entered
        dropped = max(entered - progressed, 0)
        drop_rate = round(dropped / entered * 100, 1) if entered > 0 else 0
        leak_data.append({
            'stage': stage, 'entered': entered, 'progressed': progressed,
            'dropped': dropped, 'drop_rate': drop_rate,
        })

    # Get unique users for filter
    users = db.session.query(ActivityLog.user).distinct().all()
    users = [u[0] for u in users if u[0]]

    return render_template('reports.html',
        funnel=funnel,
        source_data=source_data,
        team_data=team_data,
        activity_logs=activity_logs,
        leak_data=leak_data,
        users=users,
        date_from_str=date_from_str,
        date_to_str=date_to_str,
        user_filter=user_filter,
        action_filter=action_filter,
    )


@reports_bp.route('/reports/board')
@login_required
def board():
    from status_config import ALL_STATUSES, STATUS_COLORS
    view = request.args.get('view', 'funnel')
    filter_val = request.args.get('filter', '')
    search = request.args.get('search', '').strip()

    query = Lead.query
    if view == 'source' and filter_val:
        query = query.filter_by(source_channel=filter_val)
        board_title = f'Source: {filter_val}'
    elif view == 'team' and filter_val:
        query = query.filter_by(assigned_to=filter_val)
        board_title = f'Team: {filter_val}'
    elif view == 'stage' and filter_val:
        query = query.filter_by(status=filter_val)
        board_title = f'Stage: {filter_val}'
    else:
        board_title = 'All Leads'

    if search:
        query = query.filter(db.or_(
            Lead.name.ilike(f'%{search}%'),
            Lead.company.ilike(f'%{search}%'),
        ))

    all_leads = query.order_by(Lead.created_at.desc()).all()

    # Group leads by status
    columns = []
    for stage in ALL_STATUSES:
        stage_leads = [l for l in all_leads if l.status == stage]
        columns.append({
            'stage': stage,
            'color': STATUS_COLORS.get(stage, '#999'),
            'leads': stage_leads,
            'count': len(stage_leads),
        })

    return render_template('reports_board.html',
        columns=columns,
        board_title=board_title,
        view=view,
        filter_val=filter_val,
        search=search,
        total=len(all_leads),
    )
