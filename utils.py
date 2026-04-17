from datetime import datetime
import requests as http_requests


def auto_assign(country):
    ANZ = ['Australia', 'New Zealand']
    NA = ['United States', 'Canada']
    if country in ANZ:
        return 'Skye'
    elif country in NA:
        return 'Tony'
    return 'Unassigned'


def record_stage_change(lead, new_status):
    from models import LeadStageHistory
    from extensions import db

    # Close current open stage
    current = LeadStageHistory.query.filter_by(lead_id=lead.id, exited_at=None).first()
    if current:
        current.exited_at = datetime.utcnow()
        current.days_in_stage = (current.exited_at - current.entered_at).days

    # Open new stage
    new_history = LeadStageHistory(
        lead_id=lead.id,
        stage=new_status,
        entered_at=datetime.utcnow()
    )
    db.session.add(new_history)


def send_slack(app, message):
    webhook_url = app.config.get('SLACK_WEBHOOK_URL', '')
    if not webhook_url or not webhook_url.startswith('https://hooks.slack.com'):
        return
    try:
        http_requests.post(webhook_url, json={'text': message}, timeout=5)
    except Exception:
        pass
