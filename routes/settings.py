import csv
import io
import os
from flask import Blueprint, render_template, redirect, url_for, flash, request, Response, current_app
from flask_login import login_required, current_user
from models import User, Lead, Contact, Company
from extensions import db

settings_bp = Blueprint('settings', __name__)


def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user.role != 'admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated


@settings_bp.route('/settings')
@login_required
def index():
    users = User.query.order_by(User.created_at).all() if current_user.role == 'admin' else []
    slack_url = current_app.config.get('SLACK_WEBHOOK_URL', '')
    return render_template('settings.html', users=users, slack_url=slack_url)


# ── Profile ────────────────────────────────────────────────

@settings_bp.route('/settings/profile', methods=['POST'])
@login_required
def update_profile():
    current_user.display_name = request.form.get('display_name', '').strip()
    current_user.email = request.form.get('email', '').strip()
    current_user.phone = request.form.get('phone', '').strip()
    db.session.commit()
    flash('Profile updated.', 'success')
    return redirect(url_for('settings.index'))


# ── Password ───────────────────────────────────────────────

@settings_bp.route('/settings/password', methods=['POST'])
@login_required
def change_password():
    current_password = request.form.get('current_password')
    new_password     = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    if not current_user.check_password(current_password):
        flash('Current password is incorrect.', 'error')
        return redirect(url_for('settings.index'))
    if new_password != confirm_password:
        flash('New passwords do not match.', 'error')
        return redirect(url_for('settings.index'))
    if len(new_password) < 6:
        flash('Password must be at least 6 characters.', 'error')
        return redirect(url_for('settings.index'))
    current_user.set_password(new_password)
    db.session.commit()
    flash('Password changed successfully.', 'success')
    return redirect(url_for('settings.index'))


# ── User management (admin) ────────────────────────────────

@settings_bp.route('/settings/users/add', methods=['POST'])
@login_required
@admin_required
def add_user():
    username     = request.form.get('username', '').strip()
    display_name = request.form.get('display_name', '').strip()
    email        = request.form.get('email', '').strip()
    password     = request.form.get('password', '')
    role         = request.form.get('role', 'viewer')

    if not username or not password:
        flash('Username and password are required.', 'error')
        return redirect(url_for('settings.index'))
    if User.query.filter_by(username=username).first():
        flash('Username already exists.', 'error')
        return redirect(url_for('settings.index'))

    user = User(username=username, role=role,
                display_name=display_name, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    flash(f'User "{username}" created.', 'success')
    return redirect(url_for('settings.index'))


@settings_bp.route('/settings/users/<int:user_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot deactivate yourself.', 'error')
        return redirect(url_for('settings.index'))
    user.is_active = not user.is_active
    db.session.commit()
    status = 'activated' if user.is_active else 'deactivated'
    flash(f'User "{user.username}" {status}.', 'success')
    return redirect(url_for('settings.index'))


@settings_bp.route('/settings/users/<int:user_id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    user.display_name = request.form.get('display_name', '').strip() or None
    user.email = request.form.get('email', '').strip() or None
    user.phone = request.form.get('phone', '').strip() or None
    if user.id != current_user.id:
        user.role = request.form.get('role', user.role)
        user.is_active = request.form.get('is_active', '1') == '1'
    db.session.commit()
    flash(f'User "{user.username}" updated.', 'success')
    return redirect(url_for('settings.index'))


@settings_bp.route('/settings/users/<int:user_id>/password', methods=['POST'])
@login_required
@admin_required
def reset_user_password(user_id):
    user = User.query.get_or_404(user_id)
    new_password = request.form.get('new_password', '')
    if len(new_password) < 6:
        flash('Password must be at least 6 characters.', 'error')
        return redirect(url_for('settings.index'))
    user.set_password(new_password)
    db.session.commit()
    flash(f'Password for "{user.username}" reset.', 'success')
    return redirect(url_for('settings.index'))


# ── Slack ──────────────────────────────────────────────────

@settings_bp.route('/settings/slack/test', methods=['POST'])
@login_required
@admin_required
def test_slack():
    from utils import send_slack
    send_slack(current_app._get_current_object(),
               'AgriChain CRM Slack integration is working!')
    flash('Slack test message sent.', 'success')
    return redirect(url_for('settings.index'))


@settings_bp.route('/settings/slack/save', methods=['POST'])
@login_required
@admin_required
def save_slack():
    webhook_url = request.form.get('slack_webhook_url', '').strip()
    env_path = os.path.join(current_app.root_path, '.env')
    lines = []
    found = False
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            lines = f.readlines()
        new_lines = []
        for line in lines:
            if line.startswith('SLACK_WEBHOOK_URL='):
                new_lines.append(f'SLACK_WEBHOOK_URL={webhook_url}\n')
                found = True
            else:
                new_lines.append(line)
        lines = new_lines
    if not found:
        lines.append(f'SLACK_WEBHOOK_URL={webhook_url}\n')
    with open(env_path, 'w') as f:
        f.writelines(lines)
    current_app.config['SLACK_WEBHOOK_URL'] = webhook_url
    flash('Slack webhook URL saved.', 'success')
    return redirect(url_for('settings.index'))


# ── Export ─────────────────────────────────────────────────

@settings_bp.route('/settings/export/leads')
@login_required
def export_leads():
    leads = Lead.query.order_by(Lead.created_at.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID','Name','Company','Country','Email','Phone',
                     'Source Channel','Source URL','Assigned To','Status',
                     'Created At','Updated At','Message'])
    for l in leads:
        writer.writerow([l.id, l.name, l.company, l.country, l.email, l.phone,
                         l.source_channel, l.source_url, l.assigned_to, l.status,
                         l.created_at.strftime('%Y-%m-%d %H:%M') if l.created_at else '',
                         l.updated_at.strftime('%Y-%m-%d %H:%M') if l.updated_at else '',
                         l.message])
    output.seek(0)
    return Response(output.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment;filename=leads_export.csv'})


@settings_bp.route('/settings/export/contacts')
@login_required
def export_contacts():
    contacts = Contact.query.order_by(Contact.created_at.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID','First Name','Last Name','Email','Phone',
                     'Company','Job Title','Country','Source','Created At'])
    for c in contacts:
        writer.writerow([c.id, c.first_name, c.last_name, c.email, c.phone,
                         c.company.name if c.company else '',
                         c.job_title, c.country, c.source,
                         c.created_at.strftime('%Y-%m-%d %H:%M') if c.created_at else ''])
    output.seek(0)
    return Response(output.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment;filename=contacts_export.csv'})


@settings_bp.route('/settings/export/companies')
@login_required
def export_companies():
    companies = Company.query.order_by(Company.created_at.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID','Name','Industry','Country','Website','Phone','Created At'])
    for co in companies:
        writer.writerow([co.id, co.name, co.industry, co.country, co.website, co.phone,
                         co.created_at.strftime('%Y-%m-%d %H:%M') if co.created_at else ''])
    output.seek(0)
    return Response(output.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment;filename=companies_export.csv'})
