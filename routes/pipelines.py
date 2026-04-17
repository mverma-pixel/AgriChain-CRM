import csv
import io
from datetime import datetime
from flask import (Blueprint, render_template, redirect, url_for, flash,
                   request, jsonify, Response)
from flask_login import login_required, current_user
from models import Pipeline, Contact, Company, Lead, ActivityLog, PipelineMemberStage, PIPELINE_STAGES
from extensions import db
from sqlalchemy import func

pipelines_bp = Blueprint('pipelines', __name__)

STAGE_COLORS = {
    'Prospect':  '#64B5F6',
    'Contacted': '#4DB6AC',
    'Qualified': '#FFB74D',
    'Demo':      '#9575CD',
    'Close Won': '#4CAF50',
    'Close Lost':'#EF5350',
}


def _ensure_stage(pipeline_id, member_type, member_id):
    """Create a PipelineMemberStage record if one doesn't exist."""
    if not PipelineMemberStage.query.filter_by(
        pipeline_id=pipeline_id, member_type=member_type, member_id=member_id
    ).first():
        db.session.add(PipelineMemberStage(
            pipeline_id=pipeline_id, member_type=member_type, member_id=member_id
        ))


def _build_bar_data(stage_dist):
    total = sum(stage_dist.values())
    bars = []
    for s in PIPELINE_STAGES:
        cnt = stage_dist.get(s, 0)
        if cnt > 0:
            bars.append({
                'stage': s,
                'color': STAGE_COLORS[s],
                'count': cnt,
                'pct':   round(cnt / total * 100, 1) if total > 0 else 0,
            })
    return bars


@pipelines_bp.route('/pipelines')
@login_required
def index():
    pipelines = Pipeline.query.order_by(Pipeline.created_at.desc()).all()

    # Stage distribution per pipeline
    stage_rows = db.session.query(
        PipelineMemberStage.pipeline_id,
        PipelineMemberStage.stage,
        func.count(PipelineMemberStage.id).label('cnt')
    ).group_by(PipelineMemberStage.pipeline_id, PipelineMemberStage.stage).all()

    raw_stage_data = {}
    for row in stage_rows:
        raw_stage_data.setdefault(row.pipeline_id, {})[row.stage] = row.cnt

    pipeline_bar_data = {
        p.id: _build_bar_data(raw_stage_data.get(p.id, {}))
        for p in pipelines
    }

    return render_template('pipelines/index.html',
        pipelines=pipelines,
        pipeline_bar_data=pipeline_bar_data,
        pipeline_stages=PIPELINE_STAGES,
        stage_colors=STAGE_COLORS,
    )


@pipelines_bp.route('/pipelines/add', methods=['POST'])
@login_required
def add():
    name = request.form.get('name', '').strip()
    if not name:
        flash('Pipeline name is required.', 'error')
        return redirect(url_for('pipelines.index'))

    pipeline = Pipeline(
        name=name,
        description=request.form.get('description', ''),
        owner=current_user.username,
    )
    db.session.add(pipeline)
    db.session.flush()

    for cid in request.form.getlist('contact_ids'):
        c = Contact.query.get(int(cid))
        if c:
            pipeline.contacts.append(c)
            _ensure_stage(pipeline.id, 'contact', int(cid))
    for coid in request.form.getlist('company_ids'):
        co = Company.query.get(int(coid))
        if co:
            pipeline.companies.append(co)
            _ensure_stage(pipeline.id, 'company', int(coid))
    for lid in request.form.getlist('lead_ids'):
        l = Lead.query.get(int(lid))
        if l:
            pipeline.leads.append(l)
            _ensure_stage(pipeline.id, 'lead', int(lid))

    db.session.commit()
    flash(f'Pipeline "{name}" created.', 'success')
    return redirect(url_for('pipelines.detail', pipeline_id=pipeline.id))


@pipelines_bp.route('/pipelines/<int:pipeline_id>')
@login_required
def detail(pipeline_id):
    pipeline  = Pipeline.query.get_or_404(pipeline_id)
    contacts  = pipeline.contacts.all()
    companies = pipeline.companies.all()
    leads     = pipeline.leads.all()

    stage_records = PipelineMemberStage.query.filter_by(pipeline_id=pipeline_id).all()
    stage_map = {(r.member_type, r.member_id): r.stage for r in stage_records}

    stage_dist = {s: 0 for s in PIPELINE_STAGES}
    for stage in stage_map.values():
        if stage in stage_dist:
            stage_dist[stage] += 1
    bar_data = _build_bar_data(stage_dist)

    all_contacts  = Contact.query.order_by(Contact.first_name).all()
    all_companies = Company.query.order_by(Company.name).all()
    all_leads     = Lead.query.order_by(Lead.name).all()

    return render_template('pipelines/detail.html',
        pipeline=pipeline,
        contacts=contacts, companies=companies, leads=leads,
        all_contacts=all_contacts, all_companies=all_companies, all_leads=all_leads,
        stage_map=stage_map,
        bar_data=bar_data,
        pipeline_stages=PIPELINE_STAGES,
        stage_colors=STAGE_COLORS,
    )


@pipelines_bp.route('/pipelines/<int:pipeline_id>/edit', methods=['POST'])
@login_required
def edit(pipeline_id):
    pipeline = Pipeline.query.get_or_404(pipeline_id)
    pipeline.name = request.form.get('name', pipeline.name).strip()
    pipeline.description = request.form.get('description', pipeline.description)
    pipeline.updated_at = datetime.utcnow()
    db.session.commit()
    flash('Pipeline updated.', 'success')
    return redirect(url_for('pipelines.detail', pipeline_id=pipeline_id))


@pipelines_bp.route('/pipelines/<int:pipeline_id>/delete', methods=['POST'])
@login_required
def delete(pipeline_id):
    pipeline = Pipeline.query.get_or_404(pipeline_id)
    name = pipeline.name
    db.session.delete(pipeline)
    db.session.commit()
    flash(f'Pipeline "{name}" deleted.', 'success')
    return redirect(url_for('pipelines.index'))


@pipelines_bp.route('/pipelines/<int:pipeline_id>/add-members', methods=['POST'])
@login_required
def add_members(pipeline_id):
    pipeline = Pipeline.query.get_or_404(pipeline_id)
    added = 0
    for cid in request.form.getlist('contact_ids'):
        cid = int(cid)
        c = Contact.query.get(cid)
        if c and c not in pipeline.contacts:
            pipeline.contacts.append(c)
            _ensure_stage(pipeline_id, 'contact', cid)
            added += 1
    for coid in request.form.getlist('company_ids'):
        coid = int(coid)
        co = Company.query.get(coid)
        if co and co not in pipeline.companies:
            pipeline.companies.append(co)
            _ensure_stage(pipeline_id, 'company', coid)
            added += 1
    for lid in request.form.getlist('lead_ids'):
        lid = int(lid)
        l = Lead.query.get(lid)
        if l and l not in pipeline.leads:
            pipeline.leads.append(l)
            _ensure_stage(pipeline_id, 'lead', lid)
            added += 1
    db.session.commit()
    flash(f'{added} member(s) added to pipeline.', 'success')
    return redirect(url_for('pipelines.detail', pipeline_id=pipeline_id))


@pipelines_bp.route('/pipelines/<int:pipeline_id>/remove-member', methods=['POST'])
@login_required
def remove_member(pipeline_id):
    pipeline    = Pipeline.query.get_or_404(pipeline_id)
    member_type = request.form.get('type')
    member_id   = int(request.form.get('id', 0))

    if member_type == 'contact':
        c = Contact.query.get(member_id)
        if c and c in pipeline.contacts:
            pipeline.contacts.remove(c)
    elif member_type == 'company':
        co = Company.query.get(member_id)
        if co and co in pipeline.companies:
            pipeline.companies.remove(co)
    elif member_type == 'lead':
        l = Lead.query.get(member_id)
        if l and l in pipeline.leads:
            pipeline.leads.remove(l)

    PipelineMemberStage.query.filter_by(
        pipeline_id=pipeline_id, member_type=member_type, member_id=member_id
    ).delete()
    db.session.commit()
    return redirect(url_for('pipelines.detail', pipeline_id=pipeline_id))


@pipelines_bp.route('/pipelines/<int:pipeline_id>/update-stage', methods=['POST'])
@login_required
def update_stage(pipeline_id):
    member_type = request.form.get('type')
    member_id   = int(request.form.get('id', 0))
    stage       = request.form.get('stage', 'Prospect')
    if stage not in PIPELINE_STAGES:
        stage = 'Prospect'

    pms = PipelineMemberStage.query.filter_by(
        pipeline_id=pipeline_id, member_type=member_type, member_id=member_id
    ).first()
    if pms:
        pms.stage = stage
    else:
        db.session.add(PipelineMemberStage(
            pipeline_id=pipeline_id, member_type=member_type,
            member_id=member_id, stage=stage
        ))
    db.session.commit()
    return redirect(url_for('pipelines.detail', pipeline_id=pipeline_id))


@pipelines_bp.route('/pipelines/<int:pipeline_id>/import', methods=['POST'])
@login_required
def import_csv(pipeline_id):
    pipeline = Pipeline.query.get_or_404(pipeline_id)
    file = request.files.get('csv_file')
    if not file or not file.filename.endswith('.csv'):
        flash('Please upload a valid CSV file.', 'error')
        return redirect(url_for('pipelines.detail', pipeline_id=pipeline_id))

    stream = io.StringIO(file.stream.read().decode('utf-8-sig'))
    reader = csv.DictReader(stream)
    created_contacts = 0
    created_companies = 0

    for row in reader:
        row = {k.strip().lower(): (v or '').strip() for k, v in row.items()}

        company_name = row.get('company') or row.get('company name') or row.get('organisation') or ''
        company_record = None
        if company_name:
            company_record = Company.query.filter(Company.name.ilike(company_name)).first()
            if not company_record:
                company_record = Company(
                    name=company_name,
                    industry=row.get('industry', ''),
                    country=row.get('country', ''),
                    website=row.get('website', ''),
                    phone=row.get('company phone', ''),
                )
                db.session.add(company_record)
                db.session.flush()
                created_companies += 1
            if company_record not in pipeline.companies:
                pipeline.companies.append(company_record)
                _ensure_stage(pipeline_id, 'company', company_record.id)

        first_name = row.get('first name') or row.get('firstname') or ''
        last_name  = row.get('last name')  or row.get('lastname')  or ''
        full_name  = row.get('name') or row.get('full name') or ''
        if not first_name and full_name:
            parts = full_name.split(' ', 1)
            first_name = parts[0]
            last_name  = parts[1] if len(parts) > 1 else ''

        if first_name:
            existing = Contact.query.filter(
                Contact.first_name.ilike(first_name),
                Contact.last_name.ilike(last_name or '%'),
            ).first()
            if not existing:
                contact = Contact(
                    first_name=first_name,
                    last_name=last_name or '',
                    email=row.get('email', ''),
                    phone=row.get('phone', ''),
                    job_title=row.get('job title') or row.get('title', ''),
                    country=row.get('country', ''),
                    company_id=company_record.id if company_record else None,
                    source='Pipeline Import',
                )
                db.session.add(contact)
                db.session.flush()
                created_contacts += 1
            else:
                contact = existing
            if contact not in pipeline.contacts:
                pipeline.contacts.append(contact)
                _ensure_stage(pipeline_id, 'contact', contact.id)

    db.session.commit()
    flash(f'Import complete: {created_contacts} contact(s) and {created_companies} company(ies) created.', 'success')
    return redirect(url_for('pipelines.detail', pipeline_id=pipeline_id))


@pipelines_bp.route('/pipelines/<int:pipeline_id>/export')
@login_required
def export_csv(pipeline_id):
    pipeline = Pipeline.query.get_or_404(pipeline_id)

    stage_records = PipelineMemberStage.query.filter_by(pipeline_id=pipeline_id).all()
    stage_map = {(r.member_type, r.member_id): r.stage for r in stage_records}

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Type', 'Name', 'Email', 'Phone', 'Company', 'Country',
                     'Source/Status', 'Pipeline Stage'])

    for c in pipeline.contacts.all():
        writer.writerow(['Contact', c.full_name, c.email or '', c.phone or '',
                         c.company.name if c.company else '', c.country or '',
                         c.source or '', stage_map.get(('contact', c.id), 'Prospect')])
    for co in pipeline.companies.all():
        writer.writerow(['Company', co.name, '', co.phone or '', '',
                         co.country or '', co.industry or '',
                         stage_map.get(('company', co.id), 'Prospect')])
    for l in pipeline.leads.all():
        writer.writerow(['Lead', l.name, l.email or '', l.phone or '',
                         l.company or '', l.country or '', l.status,
                         stage_map.get(('lead', l.id), 'Prospect')])

    output.seek(0)
    filename = pipeline.name.replace(' ', '_').lower() + '_pipeline.csv'
    return Response(output.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': f'attachment;filename={filename}'})
