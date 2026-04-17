from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from models import Lead, LeadNote, LeadStageHistory, LeadStatusFeedback, Contact, Company, Task, CalendarEvent, ActivityLog
from extensions import db
from utils import auto_assign, record_stage_change, send_slack
from status_config import (ALL_STATUSES, STATUS_COLORS, TERMINAL_STATUSES,
                            FEEDBACK_REQUIRED, VALID_TRANSITIONS, SOURCE_CHANNELS,
                            get_allowed_transitions)

leads_bp = Blueprint('leads', __name__)

ASSIGNEES = ['Skye', 'Tony', 'Unassigned']

COUNTRIES = [
    "Afghanistan","Albania","Algeria","Andorra","Angola","Argentina","Armenia","Australia",
    "Austria","Azerbaijan","Bahamas","Bahrain","Bangladesh","Belarus","Belgium","Belize",
    "Benin","Bhutan","Bolivia","Bosnia and Herzegovina","Botswana","Brazil","Brunei",
    "Bulgaria","Burkina Faso","Burundi","Cambodia","Cameroon","Canada","Cape Verde",
    "Central African Republic","Chad","Chile","China","Colombia","Comoros","Congo",
    "Costa Rica","Croatia","Cuba","Cyprus","Czech Republic","Denmark","Djibouti",
    "Dominican Republic","Ecuador","Egypt","El Salvador","Equatorial Guinea","Eritrea",
    "Estonia","Eswatini","Ethiopia","Fiji","Finland","France","Gabon","Gambia","Georgia",
    "Germany","Ghana","Greece","Guatemala","Guinea","Guinea-Bissau","Guyana","Haiti",
    "Honduras","Hungary","Iceland","India","Indonesia","Iran","Iraq","Ireland","Israel",
    "Italy","Jamaica","Japan","Jordan","Kazakhstan","Kenya","Kosovo","Kuwait","Kyrgyzstan",
    "Laos","Latvia","Lebanon","Lesotho","Liberia","Libya","Liechtenstein","Lithuania",
    "Luxembourg","Madagascar","Malawi","Malaysia","Maldives","Mali","Malta","Mauritania",
    "Mauritius","Mexico","Moldova","Monaco","Mongolia","Montenegro","Morocco","Mozambique",
    "Myanmar","Namibia","Nepal","Netherlands","New Zealand","Nicaragua","Niger","Nigeria",
    "North Korea","North Macedonia","Norway","Oman","Pakistan","Panama","Papua New Guinea",
    "Paraguay","Peru","Philippines","Poland","Portugal","Qatar","Romania","Russia","Rwanda",
    "Saudi Arabia","Senegal","Serbia","Sierra Leone","Singapore","Slovakia","Slovenia",
    "Somalia","South Africa","South Korea","South Sudan","Spain","Sri Lanka","Sudan",
    "Suriname","Sweden","Switzerland","Syria","Taiwan","Tajikistan","Tanzania","Thailand",
    "Togo","Trinidad and Tobago","Tunisia","Turkey","Turkmenistan","Uganda","Ukraine",
    "United Arab Emirates","United Kingdom","United States","Uruguay","Uzbekistan",
    "Venezuela","Vietnam","Yemen","Zambia","Zimbabwe"
]


def _template_ctx():
    """Common context variables for lead templates."""
    return dict(
        statuses=ALL_STATUSES,
        status_colors=STATUS_COLORS,
        terminal_statuses=list(TERMINAL_STATUSES),
        channels=SOURCE_CHANNELS,
        assignees=ASSIGNEES,
        countries=COUNTRIES,
    )


@leads_bp.route('/leads')
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '')
    assigned_filter = request.args.get('assigned_to', current_user.username)
    source_filter = request.args.get('source', '')
    country_filter = request.args.get('country', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    select_mode = request.args.get('select', '0') == '1'

    query = Lead.query
    if search:
        query = query.filter(db.or_(
            Lead.name.ilike(f'%{search}%'),
            Lead.company.ilike(f'%{search}%'),
            Lead.email.ilike(f'%{search}%'),
        ))
    if status_filter:
        query = query.filter_by(status=status_filter)
    if assigned_filter:
        query = query.filter_by(assigned_to=assigned_filter)
    if source_filter:
        query = query.filter_by(source_channel=source_filter)
    if country_filter:
        query = query.filter_by(country=country_filter)
    if date_from:
        try:
            query = query.filter(Lead.created_at >= datetime.strptime(date_from, '%Y-%m-%d'))
        except ValueError:
            pass
    if date_to:
        try:
            query = query.filter(Lead.created_at <= datetime.strptime(date_to, '%Y-%m-%d'))
        except ValueError:
            pass

    leads = query.order_by(Lead.created_at.desc()).paginate(page=page, per_page=25, error_out=False)

    funnel_data = [{'stage': s, 'count': Lead.query.filter_by(status=s).count()} for s in ALL_STATUSES]
    users = db.session.execute(db.select(db.distinct(Lead.assigned_to))).scalars().all()

    from models import Pipeline
    pipelines = Pipeline.query.order_by(Pipeline.name).all()

    ctx = _template_ctx()
    ctx.update(
        leads=leads,
        funnel_data=funnel_data,
        search=search,
        status_filter=status_filter,
        assigned_filter=assigned_filter,
        source_filter=source_filter,
        country_filter=country_filter,
        date_from=date_from,
        date_to=date_to,
        select_mode=select_mode,
        users=users,
        pipelines=pipelines,
    )
    return render_template('leads/index.html', **ctx)


@leads_bp.route('/leads/add', methods=['POST'])
@login_required
def add():
    name = request.form.get('name', '').strip()
    if not name:
        flash('Lead name is required.', 'error')
        return redirect(url_for('leads.index'))

    country = request.form.get('country', '')
    assigned_to = request.form.get('assigned_to') or auto_assign(country)

    lead = Lead(
        name=name,
        company=request.form.get('company', ''),
        country=country,
        email=request.form.get('email', ''),
        phone=request.form.get('phone', ''),
        message=request.form.get('message', ''),
        source_channel=request.form.get('source_channel', ''),
        source_url=request.form.get('source_url', ''),
        assigned_to=assigned_to,
        status='New Lead',
        created_by=current_user.username,
    )
    company_id = request.form.get('company_id')
    if company_id:
        lead.company_id = int(company_id)

    db.session.add(lead)
    db.session.flush()

    history = LeadStageHistory(lead_id=lead.id, stage='New Lead',
                               entered_at=lead.created_at or datetime.utcnow())
    db.session.add(history)

    log = ActivityLog(user=current_user.username, action='Created lead',
                      entity_type='lead', entity_id=lead.id, entity_name=lead.name)
    db.session.add(log)
    db.session.commit()

    send_slack(current_app._get_current_object(),
        f"New Lead Created\nName: {lead.name} | Company: {lead.company} | Country: {lead.country}\n"
        f"Source: {lead.source_channel} | Assigned To: {lead.assigned_to}"
    )

    flash(f'Lead "{name}" created successfully.', 'success')
    return redirect(url_for('leads.detail', lead_id=lead.id))


@leads_bp.route('/leads/import', methods=['POST'])
@login_required
def import_csv():
    from import_utils import read_spreadsheet, build_column_map, _get, LEAD_ALIASES
    from status_config import ALL_STATUSES
    file = request.files.get('csv_file')
    if not file or not file.filename:
        flash('Please upload a file.', 'error')
        return redirect(url_for('leads.index'))
    try:
        headers, rows = read_spreadsheet(file)
    except ValueError as e:
        flash(str(e), 'error')
        return redirect(url_for('leads.index'))

    col_map = build_column_map(headers, LEAD_ALIASES)
    created = 0
    skipped = 0

    for row in rows:
        name = _get(row, col_map, 'name')
        if not name:
            skipped += 1
            continue
        country = _get(row, col_map, 'country')
        assigned_to = _get(row, col_map, 'assigned_to') or auto_assign(country)
        status = _get(row, col_map, 'status', 'New Lead')
        if status not in ALL_STATUSES:
            status = 'New Lead'
        lead = Lead(
            name=name,
            company=_get(row, col_map, 'company'),
            country=country,
            email=_get(row, col_map, 'email'),
            phone=_get(row, col_map, 'phone'),
            message=_get(row, col_map, 'message'),
            source_channel=_get(row, col_map, 'source_channel'),
            source_url=_get(row, col_map, 'source_url'),
            assigned_to=assigned_to,
            status=status,
            created_by=current_user.username,
        )
        db.session.add(lead)
        db.session.flush()
        db.session.add(LeadStageHistory(lead_id=lead.id, stage=status,
                                        entered_at=lead.created_at or datetime.utcnow()))
        db.session.add(ActivityLog(user=current_user.username, action='Imported lead',
                                   entity_type='lead', entity_id=lead.id, entity_name=lead.name))
        created += 1

    db.session.commit()
    flash(f'Import complete: {created} lead(s) created, {skipped} row(s) skipped.', 'success')
    return redirect(url_for('leads.index'))


@leads_bp.route('/leads/<int:lead_id>')
@login_required
def detail(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    stage_history = lead.stage_history.order_by(LeadStageHistory.entered_at.asc()).all()
    notes = lead.notes.order_by(LeadNote.created_at.desc()).all()
    feedback_list = lead.feedback.order_by(LeadStatusFeedback.created_at.desc()).all()
    tasks = lead.tasks.order_by(Task.due_date.asc()).all()
    events = lead.events.order_by(CalendarEvent.start_datetime.asc()).all()
    activity = ActivityLog.query.filter_by(entity_type='lead', entity_id=lead_id).order_by(ActivityLog.created_at.desc()).limit(30).all()
    contacts_list = Contact.query.order_by(Contact.first_name).all()
    companies_list = Company.query.order_by(Company.name).all()

    now = datetime.utcnow()
    for h in stage_history:
        if h.exited_at is None:
            h.days_so_far = (now - h.entered_at).days

    allowed = get_allowed_transitions(lead.status)
    is_terminal = lead.status in TERMINAL_STATUSES

    ctx = _template_ctx()
    ctx.update(
        lead=lead,
        stage_history=stage_history,
        notes=notes,
        feedback_list=feedback_list,
        tasks=tasks,
        events=events,
        activity=activity,
        contacts_list=contacts_list,
        companies_list=companies_list,
        now=now,
        allowed_transitions=allowed,
        is_terminal=is_terminal,
    )
    return render_template('leads/detail.html', **ctx)


@leads_bp.route('/leads/<int:lead_id>/edit', methods=['POST'])
@login_required
def edit(lead_id):
    lead = Lead.query.get_or_404(lead_id)

    # Non-admin users cannot change source_channel/source_url if they didn't create the lead
    can_edit_source = (current_user.role == 'admin' or lead.created_by == current_user.username)

    lead.name = request.form.get('name', lead.name).strip()
    lead.company = request.form.get('company', lead.company)
    lead.country = request.form.get('country', lead.country)
    lead.email = request.form.get('email', lead.email)
    lead.phone = request.form.get('phone', lead.phone)
    lead.message = request.form.get('message', lead.message)
    if can_edit_source:
        lead.source_channel = request.form.get('source_channel', lead.source_channel)
        lead.source_url = request.form.get('source_url', lead.source_url)
    lead.updated_at = datetime.utcnow()

    new_assigned = request.form.get('assigned_to')
    if new_assigned and new_assigned != lead.assigned_to:
        log = ActivityLog(user=current_user.username,
                          action=f'Reassigned from {lead.assigned_to} to {new_assigned}',
                          entity_type='lead', entity_id=lead.id, entity_name=lead.name)
        db.session.add(log)
        lead.assigned_to = new_assigned

    company_id = request.form.get('company_id')
    lead.company_id = int(company_id) if company_id else None
    contact_id = request.form.get('contact_id')
    lead.contact_id = int(contact_id) if contact_id else None

    log = ActivityLog(user=current_user.username, action='Updated lead details',
                      entity_type='lead', entity_id=lead.id, entity_name=lead.name)
    db.session.add(log)
    db.session.commit()
    flash('Lead updated successfully.', 'success')
    return redirect(url_for('leads.detail', lead_id=lead.id))


@leads_bp.route('/leads/<int:lead_id>/status', methods=['POST'])
@login_required
def change_status(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    new_status = request.form.get('status')
    feedback_text = request.form.get('feedback_text', '').strip()

    if new_status not in ALL_STATUSES:
        return jsonify({'error': 'Invalid status'}), 400

    old_status = lead.status

    # Block terminal stages
    if old_status in TERMINAL_STATUSES:
        return jsonify({'error': 'terminal',
                        'message': f'This lead is {old_status} and cannot be changed.'}), 400

    # Validate allowed transition
    allowed = get_allowed_transitions(old_status)
    if new_status not in allowed:
        return jsonify({'error': 'invalid_transition',
                        'message': f'Cannot move from {old_status} to {new_status}.'}), 400

    if new_status == old_status:
        return jsonify({'status': 'no_change'})

    # Feedback required
    needs_feedback = new_status in FEEDBACK_REQUIRED or old_status in FEEDBACK_REQUIRED
    if needs_feedback and len(feedback_text) < 10:
        return jsonify({'error': 'feedback_required',
                        'message': 'Please provide a reason (min 10 characters).'}), 400

    if needs_feedback and feedback_text:
        fb = LeadStatusFeedback(lead_id=lead.id, from_status=old_status,
                                to_status=new_status, feedback_text=feedback_text)
        db.session.add(fb)

    record_stage_change(lead, new_status)
    lead.status = new_status
    lead.updated_at = datetime.utcnow()

    log = ActivityLog(user=current_user.username,
                      action=f'Status changed: {old_status} -> {new_status}',
                      entity_type='lead', entity_id=lead.id, entity_name=lead.name,
                      details=feedback_text or None)
    db.session.add(log)
    db.session.commit()

    app = current_app._get_current_object()
    if new_status == 'Close Won':
        send_slack(app, f"Lead Closed Won!\nName: {lead.name} | Company: {lead.company} | Assigned To: {lead.assigned_to}")
    elif new_status == 'Close Lost':
        send_slack(app, f"Lead Closed Lost\nName: {lead.name} | Company: {lead.company} | Reason: {feedback_text}")

    return jsonify({'status': 'ok', 'new_status': new_status})


@leads_bp.route('/leads/<int:lead_id>/assign', methods=['POST'])
@login_required
def assign(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    new_assigned = request.form.get('assigned_to')
    if new_assigned in ASSIGNEES:
        old = lead.assigned_to
        lead.assigned_to = new_assigned
        lead.updated_at = datetime.utcnow()
        log = ActivityLog(user=current_user.username,
                          action=f'Reassigned from {old} to {new_assigned}',
                          entity_type='lead', entity_id=lead.id, entity_name=lead.name)
        db.session.add(log)
        db.session.commit()
    return jsonify({'status': 'ok', 'assigned_to': lead.assigned_to})


@leads_bp.route('/leads/<int:lead_id>/note', methods=['POST'])
@login_required
def add_note(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    note_text = request.form.get('note_text', '').strip()
    if not note_text:
        flash('Note cannot be empty.', 'error')
        return redirect(url_for('leads.detail', lead_id=lead_id))
    note = LeadNote(lead_id=lead_id, note_text=note_text, created_by=current_user.username)
    db.session.add(note)
    log = ActivityLog(user=current_user.username, action='Added note',
                      entity_type='lead', entity_id=lead.id, entity_name=lead.name)
    db.session.add(log)
    db.session.commit()
    flash('Note added.', 'success')
    return redirect(url_for('leads.detail', lead_id=lead_id))


@leads_bp.route('/leads/<int:lead_id>/convert', methods=['POST'])
@login_required
def convert_to_contact(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    if lead.contact_id:
        flash('Lead already converted to contact.', 'info')
        return redirect(url_for('leads.detail', lead_id=lead_id))

    parts = lead.name.strip().split(' ', 1)
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else ''

    company_record = None
    if lead.company:
        company_record = Company.query.filter(Company.name.ilike(lead.company)).first()
        if not company_record:
            company_record = Company(name=lead.company, country=lead.country)
            db.session.add(company_record)
            db.session.flush()

    contact = Contact(
        first_name=first_name, last_name=last_name,
        email=lead.email, phone=lead.phone,
        company_id=company_record.id if company_record else None,
        country=lead.country, source='Converted from Lead',
    )
    db.session.add(contact)
    db.session.flush()

    lead.contact_id = contact.id
    if company_record and not lead.company_id:
        lead.company_id = company_record.id

    log = ActivityLog(user=current_user.username, action='Converted to contact',
                      entity_type='lead', entity_id=lead.id, entity_name=lead.name,
                      details=f'Created contact #{contact.id}')
    db.session.add(log)
    db.session.commit()
    flash('Lead converted to contact successfully.', 'success')
    return redirect(url_for('leads.detail', lead_id=lead_id))


@leads_bp.route('/leads/<int:lead_id>/delete', methods=['POST'])
@login_required
def delete(lead_id):
    if current_user.role != 'admin':
        flash('Only admins can delete leads.', 'error')
        return redirect(url_for('leads.index'))
    lead = Lead.query.get_or_404(lead_id)
    name = lead.name
    db.session.delete(lead)
    db.session.commit()
    flash(f'Lead "{name}" deleted.', 'success')
    return redirect(url_for('leads.index'))


@leads_bp.route('/leads/bulk-action', methods=['POST'])
@login_required
def bulk_action():
    """Bulk assign leads to pipeline or export them."""
    from models import Pipeline
    import csv, io
    from flask import Response

    ids = request.form.getlist('lead_ids')
    if not ids:
        flash('No leads selected.', 'error')
        return redirect(url_for('leads.index'))

    action = request.form.get('action', '')
    ids = [int(i) for i in ids]

    if action == 'export_csv':
        leads = Lead.query.filter(Lead.id.in_(ids)).all()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['ID','Name','Company','Country','Email','Phone',
                         'Source','Status','Assigned To','Created'])
        for l in leads:
            writer.writerow([l.id, l.name, l.company, l.country, l.email,
                             l.phone, l.source_channel, l.status, l.assigned_to,
                             l.created_at.strftime('%Y-%m-%d') if l.created_at else ''])
        output.seek(0)
        return Response(output.getvalue(), mimetype='text/csv',
                        headers={'Content-Disposition': 'attachment;filename=selected_leads.csv'})

    elif action == 'add_to_pipeline':
        pipeline_id = request.form.get('pipeline_id')
        if pipeline_id:
            from models import PipelineMemberStage
            pipeline = Pipeline.query.get_or_404(int(pipeline_id))
            leads = Lead.query.filter(Lead.id.in_(ids)).all()
            for l in leads:
                if l not in pipeline.leads:
                    pipeline.leads.append(l)
                    if not PipelineMemberStage.query.filter_by(pipeline_id=pipeline.id, member_type='lead', member_id=l.id).first():
                        db.session.add(PipelineMemberStage(pipeline_id=pipeline.id, member_type='lead', member_id=l.id))
            db.session.commit()
            flash(f'{len(leads)} lead(s) added to pipeline "{pipeline.name}".', 'success')
        return redirect(url_for('leads.index'))

    elif action == 'create_pipeline':
        pipeline_name = request.form.get('new_pipeline_name', '').strip()
        if not pipeline_name:
            flash('Pipeline name is required.', 'error')
            return redirect(url_for('leads.index'))
        from models import PipelineMemberStage
        pipeline = Pipeline(name=pipeline_name, owner=current_user.username)
        db.session.add(pipeline)
        db.session.flush()
        leads = Lead.query.filter(Lead.id.in_(ids)).all()
        for l in leads:
            pipeline.leads.append(l)
            db.session.add(PipelineMemberStage(pipeline_id=pipeline.id, member_type='lead', member_id=l.id))
        db.session.commit()
        flash(f'Pipeline "{pipeline_name}" created with {len(leads)} lead(s).', 'success')
        return redirect(url_for('pipelines.detail', pipeline_id=pipeline.id))

    flash('Unknown action.', 'error')
    return redirect(url_for('leads.index'))


@leads_bp.route('/search')
@login_required
def search():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify({'leads': [], 'contacts': [], 'companies': []})

    leads = Lead.query.filter(db.or_(
        Lead.name.ilike(f'%{q}%'), Lead.email.ilike(f'%{q}%'), Lead.company.ilike(f'%{q}%')
    )).limit(5).all()
    contacts = Contact.query.filter(db.or_(
        Contact.first_name.ilike(f'%{q}%'), Contact.last_name.ilike(f'%{q}%'),
        Contact.email.ilike(f'%{q}%')
    )).limit(5).all()
    companies = Company.query.filter(Company.name.ilike(f'%{q}%')).limit(5).all()

    return jsonify({
        'leads':     [{'id': l.id, 'name': l.name, 'company': l.company} for l in leads],
        'contacts':  [{'id': c.id, 'name': c.full_name, 'email': c.email} for c in contacts],
        'companies': [{'id': co.id, 'name': co.name} for co in companies],
    })
