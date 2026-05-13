from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from models import Company, CompanyNote, Contact, Lead, Task, ActivityLog
from extensions import db

companies_bp = Blueprint('companies', __name__)

COUNTRIES = [
    "Afghanistan","Albania","Algeria","Andorra","Angola","Argentina","Armenia","Australia",
    "Austria","Azerbaijan","Bahamas","Bahrain","Bangladesh","Belarus","Belgium","Belize",
    "Benin","Bhutan","Bolivia","Bosnia and Herzegovina","Botswana","Brazil","Brunei",
    "Bulgaria","Burkina Faso","Burundi","Cambodia","Cameroon","Canada","Cape Verde",
    "Central African Republic","Chad","Chile","China","Colombia","Comoros","Congo",
    "Costa Rica","Croatia","Cuba","Cyprus","Czech Republic","Denmark","Djibouti",
    "Dominican Republic","Ecuador","Egypt","El Salvador","Eritrea","Estonia","Eswatini",
    "Ethiopia","Fiji","Finland","France","Gabon","Gambia","Georgia","Germany","Ghana",
    "Greece","Guatemala","Guinea","Guyana","Haiti","Honduras","Hungary","Iceland",
    "India","Indonesia","Iran","Iraq","Ireland","Israel","Italy","Jamaica","Japan",
    "Jordan","Kazakhstan","Kenya","Kosovo","Kuwait","Kyrgyzstan","Laos","Latvia",
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

INDUSTRIES = [
    'Agriculture', 'Technology', 'Manufacturing', 'Finance', 'Healthcare',
    'Education', 'Retail', 'Transportation', 'Energy', 'Mining',
    'Food & Beverage', 'Logistics', 'Consulting', 'Media', 'Other'
]


@companies_bp.route('/companies')
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    country_filter = request.args.get('country', '')

    query = Company.query
    if search:
        query = query.filter(
            db.or_(
                Company.name.ilike(f'%{search}%'),
                Company.country.ilike(f'%{search}%'),
                Company.industry.ilike(f'%{search}%'),
            )
        )
    if country_filter:
        query = query.filter_by(country=country_filter)

    companies = query.order_by(Company.created_at.desc()).paginate(page=page, per_page=25, error_out=False)

    from models import Pipeline
    pipelines = Pipeline.query.order_by(Pipeline.name).all()

    return render_template('companies/index.html',
        companies=companies,
        countries=COUNTRIES,
        industries=INDUSTRIES,
        search=search,
        country_filter=country_filter,
        pipelines=pipelines,
    )


@companies_bp.route('/companies/add', methods=['POST'])
@login_required
def add():
    name = request.form.get('name', '').strip()
    if not name:
        flash('Company name is required.', 'error')
        return redirect(url_for('companies.index'))

    company = Company(
        name=name,
        industry=request.form.get('industry', ''),
        country=request.form.get('country', ''),
        website=request.form.get('website', ''),
        phone=request.form.get('phone', ''),
        address=request.form.get('address', ''),
        notes=request.form.get('notes', ''),
    )
    db.session.add(company)
    db.session.flush()

    log = ActivityLog(user=current_user.username, action='Created company',
                      entity_type='company', entity_id=company.id, entity_name=company.name)
    db.session.add(log)
    db.session.commit()
    flash(f'Company "{name}" created.', 'success')
    return redirect(url_for('companies.detail', company_id=company.id))


@companies_bp.route('/companies/import', methods=['POST'])
@login_required
def import_csv():
    from import_utils import read_spreadsheet, build_column_map, _get, COMPANY_ALIASES
    file = request.files.get('csv_file')
    if not file or not file.filename:
        flash('Please upload a file.', 'error')
        return redirect(url_for('companies.index'))
    try:
        headers, rows = read_spreadsheet(file)
    except ValueError as e:
        flash(str(e), 'error')
        return redirect(url_for('companies.index'))

    col_map = build_column_map(headers, COMPANY_ALIASES)
    created = 0
    skipped = 0

    for row in rows:
        name = _get(row, col_map, 'name')
        if not name:
            skipped += 1
            continue
        if Company.query.filter(Company.name.ilike(name)).first():
            skipped += 1
            continue
        company = Company(
            name=name,
            industry=_get(row, col_map, 'industry'),
            country=_get(row, col_map, 'country'),
            website=_get(row, col_map, 'website'),
            phone=_get(row, col_map, 'phone'),
            address=_get(row, col_map, 'address'),
            notes=_get(row, col_map, 'notes'),
        )
        db.session.add(company)
        db.session.flush()
        db.session.add(ActivityLog(user=current_user.username, action='Imported company',
                                   entity_type='company', entity_id=company.id,
                                   entity_name=company.name))
        created += 1

    db.session.commit()
    flash(f'Import complete: {created} company(ies) created, {skipped} row(s) skipped.', 'success')
    return redirect(url_for('companies.index'))


@companies_bp.route('/companies/<int:company_id>')
@login_required
def detail(company_id):
    company = Company.query.get_or_404(company_id)
    company_contacts = company.contacts.order_by(Contact.first_name).all()
    company_leads = company.leads.order_by(Lead.created_at.desc()).all()
    notes = company.company_notes.order_by(CompanyNote.created_at.desc()).all()
    tasks = company.tasks.order_by(Task.due_date.asc()).all()
    activity = ActivityLog.query.filter_by(entity_type='company', entity_id=company_id).order_by(ActivityLog.created_at.desc()).limit(20).all()

    return render_template('companies/detail.html',
        company=company,
        company_contacts=company_contacts,
        company_leads=company_leads,
        notes=notes,
        tasks=tasks,
        activity=activity,
        countries=COUNTRIES,
        industries=INDUSTRIES,
    )


@companies_bp.route('/companies/<int:company_id>/edit', methods=['POST'])
@login_required
def edit(company_id):
    company = Company.query.get_or_404(company_id)
    company.name = request.form.get('name', company.name).strip()
    company.industry = request.form.get('industry', company.industry)
    company.country = request.form.get('country', company.country)
    company.website = request.form.get('website', company.website)
    company.phone = request.form.get('phone', company.phone)
    company.address = request.form.get('address', company.address)
    company.notes = request.form.get('notes', company.notes)
    company.updated_at = datetime.utcnow()

    log = ActivityLog(user=current_user.username, action='Updated company',
                      entity_type='company', entity_id=company.id, entity_name=company.name)
    db.session.add(log)
    db.session.commit()
    flash('Company updated.', 'success')
    return redirect(url_for('companies.detail', company_id=company_id))


@companies_bp.route('/companies/<int:company_id>/note', methods=['POST'])
@login_required
def add_note(company_id):
    company = Company.query.get_or_404(company_id)
    note_text = request.form.get('note_text', '').strip()
    if not note_text:
        flash('Note cannot be empty.', 'error')
        return redirect(url_for('companies.detail', company_id=company_id))
    note = CompanyNote(company_id=company_id, note_text=note_text, created_by=current_user.username)
    db.session.add(note)
    db.session.commit()
    flash('Note added.', 'success')
    return redirect(url_for('companies.detail', company_id=company_id))


@companies_bp.route('/companies/<int:company_id>/delete', methods=['POST'])
@login_required
def delete(company_id):
    if current_user.role != 'admin':
        flash('Only admins can delete companies.', 'error')
        return redirect(url_for('companies.index'))
    company = Company.query.get_or_404(company_id)
    name = company.name
    db.session.delete(company)
    db.session.commit()
    flash(f'Company "{name}" deleted.', 'success')
    return redirect(url_for('companies.index'))


@companies_bp.route('/companies/bulk-action', methods=['POST'])
@login_required
def bulk_action():
    from models import Pipeline
    import csv, io
    from flask import Response

    ids = request.form.getlist('company_ids')
    if not ids:
        flash('No companies selected.', 'error')
        return redirect(url_for('companies.index'))

    action = request.form.get('action', '')
    ids = [int(i) for i in ids]

    if action == 'export_csv':
        companies = Company.query.filter(Company.id.in_(ids)).all()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['ID','Name','Industry','Country','Website','Phone'])
        for co in companies:
            writer.writerow([co.id, co.name, co.industry or '', co.country or '',
                             co.website or '', co.phone or ''])
        output.seek(0)
        return Response(output.getvalue(), mimetype='text/csv',
                        headers={'Content-Disposition': 'attachment;filename=selected_companies.csv'})

    elif action == 'add_to_pipeline':
        pipeline_id = request.form.get('pipeline_id')
        if pipeline_id:
            from models import Pipeline, PipelineMemberStage
            pipeline = Pipeline.query.get_or_404(int(pipeline_id))
            companies = Company.query.filter(Company.id.in_(ids)).all()
            for co in companies:
                if co not in pipeline.companies:
                    pipeline.companies.append(co)
                    if not PipelineMemberStage.query.filter_by(pipeline_id=pipeline.id, member_type='company', member_id=co.id).first():
                        db.session.add(PipelineMemberStage(pipeline_id=pipeline.id, member_type='company', member_id=co.id))
            db.session.commit()
            flash(f'{len(companies)} company(ies) added to pipeline "{pipeline.name}".', 'success')
        return redirect(url_for('companies.index'))

    elif action == 'create_pipeline':
        pipeline_name = request.form.get('new_pipeline_name', '').strip()
        if not pipeline_name:
            flash('Pipeline name is required.', 'error')
            return redirect(url_for('companies.index'))
        from models import Pipeline, PipelineMemberStage
        pipeline = Pipeline(name=pipeline_name, owner=current_user.username)
        db.session.add(pipeline)
        db.session.flush()
        companies = Company.query.filter(Company.id.in_(ids)).all()
        for co in companies:
            pipeline.companies.append(co)
            db.session.add(PipelineMemberStage(pipeline_id=pipeline.id, member_type='company', member_id=co.id))
        db.session.commit()
        flash(f'Pipeline "{pipeline_name}" created with {len(companies)} company(ies).', 'success')
        return redirect(url_for('pipelines.detail', pipeline_id=pipeline.id))

    elif action == 'delete':
        if current_user.role != 'admin':
            flash('Only admins can delete companies.', 'error')
            return redirect(url_for('companies.index'))
        companies = Company.query.filter(Company.id.in_(ids)).all()
        count = len(companies)
        for co in companies:
            db.session.delete(co)
        db.session.commit()
        flash(f'{count} company(ies) deleted.', 'success')
        return redirect(url_for('companies.index'))

    flash('Unknown action.', 'error')
    return redirect(url_for('companies.index'))


@companies_bp.route('/companies/search')
@login_required
def search():
    q = request.args.get('q', '').strip()
    if len(q) < 1:
        return jsonify([])
    companies = Company.query.filter(Company.name.ilike(f'%{q}%')).limit(10).all()
    return jsonify([{'id': c.id, 'name': c.name} for c in companies])
