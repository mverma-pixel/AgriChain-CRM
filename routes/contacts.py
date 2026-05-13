from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from models import Contact, Company, ContactNote, Lead, Task, CalendarEvent, ActivityLog
from extensions import db

contacts_bp = Blueprint('contacts', __name__)

COUNTRIES = [
    "Afghanistan","Albania","Algeria","Andorra","Angola","Argentina","Armenia","Australia",
    "Austria","Azerbaijan","Bahamas","Bahrain","Bangladesh","Belarus","Belgium","Belize",
    "Benin","Bhutan","Bolivia","Bosnia and Herzegovina","Botswana","Brazil","Brunei",
    "Bulgaria","Burkina Faso","Burundi","Cambodia","Cameroon","Canada","Cape Verde",
    "Central African Republic","Chad","Chile","China","Colombia","Comoros","Congo",
    "Costa Rica","Croatia","Cuba","Cyprus","Czech Republic","Denmark","Djibouti",
    "Dominican Republic","Ecuador","Egypt","El Salvador","Eritrea","Estonia","Eswatini",
    "Ethiopia","Fiji","Finland","France","Gabon","Gambia","Georgia","Germany","Ghana",
    "Greece","Guatemala","Guinea","Guinea-Bissau","Guyana","Haiti","Honduras","Hungary",
    "Iceland","India","Indonesia","Iran","Iraq","Ireland","Israel","Italy","Jamaica",
    "Japan","Jordan","Kazakhstan","Kenya","Kosovo","Kuwait","Kyrgyzstan","Laos","Latvia",
    "Lebanon","Lesotho","Liberia","Libya","Liechtenstein","Lithuania","Luxembourg",
    "Madagascar","Malawi","Malaysia","Maldives","Mali","Malta","Mauritania","Mauritius",
    "Mexico","Moldova","Monaco","Mongolia","Montenegro","Morocco","Mozambique","Myanmar",
    "Namibia","Nepal","Netherlands","New Zealand","Nicaragua","Niger","Nigeria",
    "North Korea","North Macedonia","Norway","Oman","Pakistan","Panama","Papua New Guinea",
    "Paraguay","Peru","Philippines","Poland","Portugal","Qatar","Romania","Russia","Rwanda",
    "Saudi Arabia","Senegal","Serbia","Sierra Leone","Singapore","Slovakia","Slovenia",
    "Somalia","South Africa","South Korea","South Sudan","Spain","Sri Lanka","Sudan",
    "Suriname","Sweden","Switzerland","Syria","Taiwan","Tajikistan","Tanzania","Thailand",
    "Togo","Trinidad and Tobago","Tunisia","Turkey","Turkmenistan","Uganda","Ukraine",
    "United Arab Emirates","United Kingdom","United States","Uruguay","Uzbekistan",
    "Venezuela","Vietnam","Yemen","Zambia","Zimbabwe"
]


@contacts_bp.route('/contacts')
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    country_filter = request.args.get('country', '')
    source_filter = request.args.get('source', '')

    query = Contact.query
    if search:
        query = query.filter(
            db.or_(
                Contact.first_name.ilike(f'%{search}%'),
                Contact.last_name.ilike(f'%{search}%'),
                Contact.email.ilike(f'%{search}%'),
            )
        )
    if country_filter:
        query = query.filter_by(country=country_filter)
    if source_filter:
        query = query.filter_by(source=source_filter)

    contacts = query.order_by(Contact.created_at.desc()).paginate(page=page, per_page=25, error_out=False)
    companies = Company.query.order_by(Company.name).all()

    from models import Pipeline
    pipelines = Pipeline.query.order_by(Pipeline.name).all()

    return render_template('contacts/index.html',
        contacts=contacts,
        companies=companies,
        countries=COUNTRIES,
        search=search,
        country_filter=country_filter,
        source_filter=source_filter,
        pipelines=pipelines,
    )


@contacts_bp.route('/contacts/add', methods=['POST'])
@login_required
def add():
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    if not first_name or not last_name:
        flash('First and last name are required.', 'error')
        return redirect(url_for('contacts.index'))

    contact = Contact(
        first_name=first_name,
        last_name=last_name,
        email=request.form.get('email', ''),
        phone=request.form.get('phone', ''),
        job_title=request.form.get('job_title', ''),
        country=request.form.get('country', ''),
        address=request.form.get('address', ''),
        notes=request.form.get('notes', ''),
        source='Manual',
    )
    company_id = request.form.get('company_id')
    if company_id:
        contact.company_id = int(company_id)

    db.session.add(contact)
    db.session.flush()

    log = ActivityLog(user=current_user.username, action='Created contact',
                      entity_type='contact', entity_id=contact.id, entity_name=contact.full_name)
    db.session.add(log)
    db.session.commit()
    flash(f'Contact "{contact.full_name}" created.', 'success')
    return redirect(url_for('contacts.detail', contact_id=contact.id))


@contacts_bp.route('/contacts/import', methods=['POST'])
@login_required
def import_csv():
    from import_utils import read_spreadsheet, build_column_map, _get, CONTACT_ALIASES
    file = request.files.get('csv_file')
    if not file or not file.filename:
        flash('Please upload a file.', 'error')
        return redirect(url_for('contacts.index'))
    try:
        headers, rows = read_spreadsheet(file)
    except ValueError as e:
        flash(str(e), 'error')
        return redirect(url_for('contacts.index'))

    col_map = build_column_map(headers, CONTACT_ALIASES)
    created = 0
    skipped = 0

    for row in rows:
        first_name = _get(row, col_map, 'first_name')
        last_name  = _get(row, col_map, 'last_name')
        full_name  = _get(row, col_map, 'full_name')
        if not first_name and full_name:
            parts = full_name.split(' ', 1)
            first_name = parts[0]
            last_name  = parts[1] if len(parts) > 1 else ''
        if not first_name:
            skipped += 1
            continue

        company_id = None
        company_name = _get(row, col_map, 'company')
        if company_name:
            co = Company.query.filter(Company.name.ilike(company_name)).first()
            if not co:
                co = Company(name=company_name, country=_get(row, col_map, 'country'))
                db.session.add(co)
                db.session.flush()
            company_id = co.id

        contact = Contact(
            first_name=first_name,
            last_name=last_name,
            email=_get(row, col_map, 'email'),
            phone=_get(row, col_map, 'phone'),
            job_title=_get(row, col_map, 'job_title'),
            country=_get(row, col_map, 'country'),
            company_id=company_id,
            source='CSV Import',
        )
        db.session.add(contact)
        db.session.flush()
        db.session.add(ActivityLog(user=current_user.username, action='Imported contact',
                                   entity_type='contact', entity_id=contact.id,
                                   entity_name=contact.full_name))
        created += 1

    db.session.commit()
    flash(f'Import complete: {created} contact(s) created, {skipped} row(s) skipped.', 'success')
    return redirect(url_for('contacts.index'))


@contacts_bp.route('/contacts/<int:contact_id>')
@login_required
def detail(contact_id):
    contact = Contact.query.get_or_404(contact_id)
    notes = contact.contact_notes.order_by(ContactNote.created_at.desc()).all()
    related_leads = contact.leads.order_by(Lead.created_at.desc()).all()
    tasks = contact.tasks.order_by(Task.due_date.asc()).all()
    events = contact.events.order_by(CalendarEvent.start_datetime.asc()).all()
    activity = ActivityLog.query.filter_by(entity_type='contact', entity_id=contact_id).order_by(ActivityLog.created_at.desc()).limit(20).all()
    companies = Company.query.order_by(Company.name).all()

    return render_template('contacts/detail.html',
        contact=contact,
        notes=notes,
        related_leads=related_leads,
        tasks=tasks,
        events=events,
        activity=activity,
        companies=companies,
        countries=COUNTRIES,
    )


@contacts_bp.route('/contacts/<int:contact_id>/edit', methods=['POST'])
@login_required
def edit(contact_id):
    contact = Contact.query.get_or_404(contact_id)
    contact.first_name = request.form.get('first_name', contact.first_name).strip()
    contact.last_name = request.form.get('last_name', contact.last_name).strip()
    contact.email = request.form.get('email', contact.email)
    contact.phone = request.form.get('phone', contact.phone)
    contact.job_title = request.form.get('job_title', contact.job_title)
    contact.country = request.form.get('country', contact.country)
    contact.address = request.form.get('address', contact.address)
    contact.notes = request.form.get('notes', contact.notes)
    contact.updated_at = datetime.utcnow()

    company_id = request.form.get('company_id')
    contact.company_id = int(company_id) if company_id else None

    log = ActivityLog(user=current_user.username, action='Updated contact',
                      entity_type='contact', entity_id=contact.id, entity_name=contact.full_name)
    db.session.add(log)
    db.session.commit()
    flash('Contact updated.', 'success')
    return redirect(url_for('contacts.detail', contact_id=contact_id))


@contacts_bp.route('/contacts/<int:contact_id>/note', methods=['POST'])
@login_required
def add_note(contact_id):
    contact = Contact.query.get_or_404(contact_id)
    note_text = request.form.get('note_text', '').strip()
    if not note_text:
        flash('Note cannot be empty.', 'error')
        return redirect(url_for('contacts.detail', contact_id=contact_id))
    note = ContactNote(contact_id=contact_id, note_text=note_text, created_by=current_user.username)
    db.session.add(note)
    log = ActivityLog(user=current_user.username, action='Added note',
                      entity_type='contact', entity_id=contact.id, entity_name=contact.full_name)
    db.session.add(log)
    db.session.commit()
    flash('Note added.', 'success')
    return redirect(url_for('contacts.detail', contact_id=contact_id))


@contacts_bp.route('/contacts/<int:contact_id>/delete', methods=['POST'])
@login_required
def delete(contact_id):
    if current_user.role != 'admin':
        flash('Only admins can delete contacts.', 'error')
        return redirect(url_for('contacts.index'))
    contact = Contact.query.get_or_404(contact_id)
    name = contact.full_name
    db.session.delete(contact)
    db.session.commit()
    flash(f'Contact "{name}" deleted.', 'success')
    return redirect(url_for('contacts.index'))


@contacts_bp.route('/contacts/bulk-action', methods=['POST'])
@login_required
def bulk_action():
    from models import Pipeline
    import csv, io
    from flask import Response

    ids = request.form.getlist('contact_ids')
    if not ids:
        flash('No contacts selected.', 'error')
        return redirect(url_for('contacts.index'))

    action = request.form.get('action', '')
    ids = [int(i) for i in ids]

    if action == 'export_csv':
        contacts = Contact.query.filter(Contact.id.in_(ids)).all()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['ID','First Name','Last Name','Email','Phone','Company','Country','Job Title','Source'])
        for c in contacts:
            writer.writerow([c.id, c.first_name, c.last_name, c.email or '', c.phone or '',
                             c.company.name if c.company else '', c.country or '', c.job_title or '', c.source or ''])
        output.seek(0)
        return Response(output.getvalue(), mimetype='text/csv',
                        headers={'Content-Disposition': 'attachment;filename=selected_contacts.csv'})

    elif action == 'add_to_pipeline':
        pipeline_id = request.form.get('pipeline_id')
        if pipeline_id:
            from models import Pipeline, PipelineMemberStage
            pipeline = Pipeline.query.get_or_404(int(pipeline_id))
            contacts = Contact.query.filter(Contact.id.in_(ids)).all()
            for c in contacts:
                if c not in pipeline.contacts:
                    pipeline.contacts.append(c)
                    if not PipelineMemberStage.query.filter_by(pipeline_id=pipeline.id, member_type='contact', member_id=c.id).first():
                        db.session.add(PipelineMemberStage(pipeline_id=pipeline.id, member_type='contact', member_id=c.id))
            db.session.commit()
            flash(f'{len(contacts)} contact(s) added to pipeline "{pipeline.name}".', 'success')
        return redirect(url_for('contacts.index'))

    elif action == 'create_pipeline':
        pipeline_name = request.form.get('new_pipeline_name', '').strip()
        if not pipeline_name:
            flash('Pipeline name is required.', 'error')
            return redirect(url_for('contacts.index'))
        from models import Pipeline, PipelineMemberStage
        pipeline = Pipeline(name=pipeline_name, owner=current_user.username)
        db.session.add(pipeline)
        db.session.flush()
        contacts = Contact.query.filter(Contact.id.in_(ids)).all()
        for c in contacts:
            pipeline.contacts.append(c)
            db.session.add(PipelineMemberStage(pipeline_id=pipeline.id, member_type='contact', member_id=c.id))
        db.session.commit()
        flash(f'Pipeline "{pipeline_name}" created with {len(contacts)} contact(s).', 'success')
        return redirect(url_for('pipelines.detail', pipeline_id=pipeline.id))

    elif action == 'delete':
        if current_user.role != 'admin':
            flash('Only admins can delete contacts.', 'error')
            return redirect(url_for('contacts.index'))
        contacts = Contact.query.filter(Contact.id.in_(ids)).all()
        count = len(contacts)
        for c in contacts:
            db.session.delete(c)
        db.session.commit()
        flash(f'{count} contact(s) deleted.', 'success')
        return redirect(url_for('contacts.index'))

    flash('Unknown action.', 'error')
    return redirect(url_for('contacts.index'))


@contacts_bp.route('/contacts/search')
@login_required
def search():
    q = request.args.get('q', '').strip()
    if len(q) < 1:
        return jsonify([])
    contacts = Contact.query.filter(
        db.or_(
            Contact.first_name.ilike(f'%{q}%'),
            Contact.last_name.ilike(f'%{q}%'),
            Contact.email.ilike(f'%{q}%'),
        )
    ).limit(10).all()
    return jsonify([{'id': c.id, 'name': c.full_name, 'email': c.email} for c in contacts])
