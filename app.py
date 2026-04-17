from flask import Flask, render_template
from flask_wtf.csrf import CSRFProtect
from apscheduler.schedulers.background import BackgroundScheduler
from config import Config
from extensions import db, login_manager
import atexit

csrf = CSRFProtect()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # ── Blueprints ─────────────────────────────────────────
    from routes.auth      import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.leads     import leads_bp
    from routes.contacts  import contacts_bp
    from routes.companies import companies_bp
    from routes.pipelines import pipelines_bp
    from routes.calendar  import calendar_bp
    from routes.tasks     import tasks_bp
    from routes.reports   import reports_bp
    from routes.settings  import settings_bp
    from routes.api       import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(leads_bp)
    app.register_blueprint(contacts_bp)
    app.register_blueprint(companies_bp)
    app.register_blueprint(pipelines_bp)
    app.register_blueprint(calendar_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(api_bp)

    csrf.exempt(api_bp)

    @app.route('/help')
    def help_page():
        return render_template('help.html')

    with app.app_context():
        db.create_all()

    return app


# ── Scheduled jobs ─────────────────────────────────────────

def run_breach_check(app):
    from datetime import datetime, timedelta
    from models import Lead
    from utils import send_slack

    with app.app_context():
        threshold = app.config.get('BREACH_DAYS_THRESHOLD', 7)
        cutoff = datetime.utcnow() - timedelta(days=threshold)
        breached = Lead.query.filter(
            Lead.status.notin_(['Close Won', 'Close Lost']),
            Lead.updated_at < cutoff,
        ).all()
        host = app.config.get('HOST', 'localhost:5001')
        for lead in breached:
            days_since = (datetime.utcnow() - lead.updated_at).days
            msg = (f"Lead Breach Alert\n"
                   f"Lead: {lead.name} | Company: {lead.company}\n"
                   f"Country: {lead.country} | Status: {lead.status}\n"
                   f"Assigned To: {lead.assigned_to}\n"
                   f"Days since last update: {days_since}\n"
                   f"View lead: http://{host}/leads/{lead.id}")
            send_slack(app, msg)


def run_auto_pending(app):
    """Auto-advance leads stuck in 'New Lead' for AUTO_PENDING_DAYS to 'Pending'."""
    from datetime import datetime, timedelta
    from models import Lead, LeadStageHistory, ActivityLog
    from utils import record_stage_change
    from status_config import AUTO_PENDING_DAYS

    with app.app_context():
        cutoff = datetime.utcnow() - timedelta(days=AUTO_PENDING_DAYS)
        stale = Lead.query.filter(
            Lead.status == 'New Lead',
            Lead.updated_at < cutoff,
        ).all()
        for lead in stale:
            record_stage_change(lead, 'Pending')
            lead.status = 'Pending'
            lead.updated_at = datetime.utcnow()
            log = ActivityLog(
                user='system',
                action='Auto-advanced to Pending (3 days in New Lead)',
                entity_type='lead', entity_id=lead.id, entity_name=lead.name,
            )
            db.session.add(log)
        if stale:
            db.session.commit()


app = create_app()

if __name__ == '__main__':
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=run_breach_check, args=[app],
                      trigger='cron', hour=9, minute=0, id='breach_check')
    scheduler.add_job(func=run_auto_pending, args=[app],
                      trigger='interval', hours=6, id='auto_pending')
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown())
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=5001)
