from datetime import datetime
from functools import wraps
from flask import Blueprint, request, jsonify, current_app
from werkzeug.security import check_password_hash
from models import Lead, Contact, Company, LeadNote, LeadStatusFeedback, LeadStageHistory, ActivityLog
from extensions import db
from utils import auto_assign, record_stage_change, send_slack

api_bp = Blueprint('api', __name__)

STATUSES = ['New Lead', 'SAL', 'Out', 'Demo', 'Close Won', 'Close Lost']
FEEDBACK_REQUIRED = ['Out', 'Close Lost']


def basic_auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        from models import User
        auth = request.authorization
        if not auth:
            return jsonify({'error': 'Authentication required'}), 401
        user = User.query.filter_by(username=auth.username, is_active=True).first()
        if not user or not user.check_password(auth.password):
            return jsonify({'error': 'Invalid credentials'}), 401
        return f(*args, **kwargs)
    return decorated


def lead_to_dict(lead):
    return {
        'id': lead.id,
        'name': lead.name,
        'company': lead.company,
        'country': lead.country,
        'email': lead.email,
        'phone': lead.phone,
        'message': lead.message,
        'source_channel': lead.source_channel,
        'source_url': lead.source_url,
        'assigned_to': lead.assigned_to,
        'status': lead.status,
        'created_at': lead.created_at.isoformat() if lead.created_at else None,
        'updated_at': lead.updated_at.isoformat() if lead.updated_at else None,
    }


def contact_to_dict(c):
    return {
        'id': c.id,
        'first_name': c.first_name,
        'last_name': c.last_name,
        'email': c.email,
        'phone': c.phone,
        'job_title': c.job_title,
        'country': c.country,
        'source': c.source,
        'company': c.company.name if c.company else None,
        'created_at': c.created_at.isoformat() if c.created_at else None,
    }


def company_to_dict(co):
    return {
        'id': co.id,
        'name': co.name,
        'industry': co.industry,
        'country': co.country,
        'website': co.website,
        'phone': co.phone,
        'created_at': co.created_at.isoformat() if co.created_at else None,
    }


def create_lead_from_data(data, username='api'):
    country = data.get('country', '')
    assigned_to = data.get('assigned_to') or auto_assign(country)

    lead = Lead(
        name=data.get('name', '').strip(),
        company=data.get('company', ''),
        country=country,
        email=data.get('email', ''),
        phone=data.get('phone', ''),
        message=data.get('message', ''),
        source_channel=data.get('source_channel', ''),
        source_url=data.get('source_url', ''),
        assigned_to=assigned_to,
        status='New Lead',
    )

    if not lead.name:
        return None, 'Name is required'

    db.session.add(lead)
    db.session.flush()

    history = LeadStageHistory(
        lead_id=lead.id,
        stage='New Lead',
        entered_at=lead.created_at or datetime.utcnow()
    )
    db.session.add(history)

    log = ActivityLog(user=username, action='Created lead via API',
                      entity_type='lead', entity_id=lead.id, entity_name=lead.name)
    db.session.add(log)
    db.session.commit()

    send_slack(current_app._get_current_object(),
        f"🆕 New Lead Created\nName: {lead.name} | Company: {lead.company} | Country: {lead.country}\n"
        f"Source: {lead.source_channel} | Assigned To: {lead.assigned_to}"
    )

    return lead, None


# ── Leads ──────────────────────────────────────────────────────────────────

@api_bp.route('/api/leads', methods=['POST'])
@basic_auth_required
def api_create_lead():
    data = request.get_json(force=True, silent=True) or {}
    lead, error = create_lead_from_data(data)
    if error:
        return jsonify({'error': error}), 400
    return jsonify(lead_to_dict(lead)), 201


@api_bp.route('/api/leads', methods=['GET'])
@basic_auth_required
def api_list_leads():
    query = Lead.query
    if request.args.get('status'):
        query = query.filter_by(status=request.args['status'])
    if request.args.get('assigned_to'):
        query = query.filter_by(assigned_to=request.args['assigned_to'])
    if request.args.get('source'):
        query = query.filter_by(source_channel=request.args['source'])
    leads = query.order_by(Lead.created_at.desc()).limit(200).all()
    return jsonify([lead_to_dict(l) for l in leads])


@api_bp.route('/api/leads/<int:lead_id>', methods=['GET'])
@basic_auth_required
def api_get_lead(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    return jsonify(lead_to_dict(lead))


@api_bp.route('/api/leads/<int:lead_id>', methods=['PATCH'])
@basic_auth_required
def api_update_lead(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    data = request.get_json(force=True, silent=True) or {}
    for field in ['name', 'company', 'country', 'email', 'phone', 'message',
                  'source_channel', 'source_url', 'assigned_to']:
        if field in data:
            setattr(lead, field, data[field])
    lead.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(lead_to_dict(lead))


@api_bp.route('/api/leads/<int:lead_id>/status', methods=['PATCH'])
@basic_auth_required
def api_change_status(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    data = request.get_json(force=True, silent=True) or {}
    new_status = data.get('status')
    feedback_text = data.get('feedback_text', '')

    if new_status not in STATUSES:
        return jsonify({'error': 'Invalid status'}), 400

    old_status = lead.status
    needs_feedback = new_status in FEEDBACK_REQUIRED or old_status in FEEDBACK_REQUIRED
    if needs_feedback and len(feedback_text) < 10:
        return jsonify({'error': 'feedback_required'}), 400

    if needs_feedback and feedback_text:
        fb = LeadStatusFeedback(lead_id=lead.id, from_status=old_status,
                                to_status=new_status, feedback_text=feedback_text)
        db.session.add(fb)

    record_stage_change(lead, new_status)
    lead.status = new_status
    lead.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(lead_to_dict(lead))


@api_bp.route('/api/leads/<int:lead_id>/notes', methods=['POST'])
@basic_auth_required
def api_add_note(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    data = request.get_json(force=True, silent=True) or {}
    note_text = data.get('note_text', '').strip()
    if not note_text:
        return jsonify({'error': 'note_text required'}), 400
    note = LeadNote(lead_id=lead.id, note_text=note_text, created_by='api')
    db.session.add(note)
    db.session.commit()
    return jsonify({'id': note.id, 'note_text': note.note_text, 'created_at': note.created_at.isoformat()}), 201


@api_bp.route('/api/leads/<int:lead_id>', methods=['DELETE'])
@basic_auth_required
def api_delete_lead(lead_id):
    from models import User
    auth = request.authorization
    user = User.query.filter_by(username=auth.username).first()
    if not user or user.role != 'admin':
        return jsonify({'error': 'Admin required'}), 403
    lead = Lead.query.get_or_404(lead_id)
    db.session.delete(lead)
    db.session.commit()
    return jsonify({'deleted': True})


# ── Contacts ────────────────────────────────────────────────────────────────

@api_bp.route('/api/contacts', methods=['POST'])
@basic_auth_required
def api_create_contact():
    data = request.get_json(force=True, silent=True) or {}
    from models import Contact
    contact = Contact(
        first_name=data.get('first_name', '').strip(),
        last_name=data.get('last_name', '').strip(),
        email=data.get('email', ''),
        phone=data.get('phone', ''),
        job_title=data.get('job_title', ''),
        country=data.get('country', ''),
        source='API',
    )
    if not contact.first_name or not contact.last_name:
        return jsonify({'error': 'first_name and last_name required'}), 400
    db.session.add(contact)
    db.session.commit()
    return jsonify(contact_to_dict(contact)), 201


@api_bp.route('/api/contacts', methods=['GET'])
@basic_auth_required
def api_list_contacts():
    from models import Contact
    contacts = Contact.query.order_by(Contact.created_at.desc()).limit(200).all()
    return jsonify([contact_to_dict(c) for c in contacts])


@api_bp.route('/api/contacts/<int:contact_id>', methods=['GET'])
@basic_auth_required
def api_get_contact(contact_id):
    from models import Contact
    contact = Contact.query.get_or_404(contact_id)
    return jsonify(contact_to_dict(contact))


@api_bp.route('/api/contacts/<int:contact_id>', methods=['PATCH'])
@basic_auth_required
def api_update_contact(contact_id):
    from models import Contact
    contact = Contact.query.get_or_404(contact_id)
    data = request.get_json(force=True, silent=True) or {}
    for field in ['first_name', 'last_name', 'email', 'phone', 'job_title', 'country']:
        if field in data:
            setattr(contact, field, data[field])
    contact.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(contact_to_dict(contact))


@api_bp.route('/api/contacts/<int:contact_id>', methods=['DELETE'])
@basic_auth_required
def api_delete_contact(contact_id):
    from models import User, Contact
    auth = request.authorization
    user = User.query.filter_by(username=auth.username).first()
    if not user or user.role != 'admin':
        return jsonify({'error': 'Admin required'}), 403
    contact = Contact.query.get_or_404(contact_id)
    db.session.delete(contact)
    db.session.commit()
    return jsonify({'deleted': True})


# ── Companies ───────────────────────────────────────────────────────────────

@api_bp.route('/api/companies', methods=['POST'])
@basic_auth_required
def api_create_company():
    data = request.get_json(force=True, silent=True) or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'name required'}), 400
    company = Company(name=name, industry=data.get('industry', ''),
                      country=data.get('country', ''), website=data.get('website', ''))
    db.session.add(company)
    db.session.commit()
    return jsonify(company_to_dict(company)), 201


@api_bp.route('/api/companies', methods=['GET'])
@basic_auth_required
def api_list_companies():
    companies = Company.query.order_by(Company.created_at.desc()).limit(200).all()
    return jsonify([company_to_dict(co) for co in companies])


@api_bp.route('/api/companies/<int:company_id>', methods=['GET'])
@basic_auth_required
def api_get_company(company_id):
    company = Company.query.get_or_404(company_id)
    return jsonify(company_to_dict(company))


@api_bp.route('/api/companies/<int:company_id>', methods=['PATCH'])
@basic_auth_required
def api_update_company(company_id):
    company = Company.query.get_or_404(company_id)
    data = request.get_json(force=True, silent=True) or {}
    for field in ['name', 'industry', 'country', 'website', 'phone', 'address', 'notes']:
        if field in data:
            setattr(company, field, data[field])
    company.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(company_to_dict(company))


# ── Webhook ─────────────────────────────────────────────────────────────────

@api_bp.route('/api/webhook/lead', methods=['POST'])
def api_webhook_lead():
    """Public webhook for marketing platform integrations."""
    # Optional: check a secret token in header
    data = request.get_json(force=True, silent=True) or request.form.to_dict()
    if not data.get('name'):
        return jsonify({'error': 'name required'}), 400

    lead, error = create_lead_from_data(data, username='webhook')
    if error:
        return jsonify({'error': error}), 400

    return jsonify(lead_to_dict(lead)), 201
