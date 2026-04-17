from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from models import Task, Lead, Contact, Company, ActivityLog, User
from extensions import db

tasks_bp = Blueprint('tasks', __name__)


@tasks_bp.route('/tasks')
@login_required
def index():
    tab = request.args.get('tab', 'all')
    status_filter = request.args.get('status', '')
    priority_filter = request.args.get('priority', '')
    assigned_filter = request.args.get('assigned_to', '')

    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start.replace(hour=23, minute=59, second=59)

    query = Task.query
    if tab == 'mine':
        query = query.filter_by(assigned_to=current_user.username)
    elif tab == 'overdue':
        query = query.filter(Task.due_date < today_start, Task.status.in_(['Open', 'In Progress']))
    elif tab == 'today':
        query = query.filter(Task.due_date >= today_start, Task.due_date <= today_end)
    elif tab == 'completed':
        query = query.filter_by(status='Completed')

    if status_filter:
        query = query.filter_by(status=status_filter)
    if priority_filter:
        query = query.filter_by(priority=priority_filter)
    if assigned_filter:
        query = query.filter_by(assigned_to=assigned_filter)

    tasks = query.order_by(Task.due_date.asc().nullslast(), Task.created_at.desc()).all()
    users = User.query.filter_by(is_active=True).all()
    leads = Lead.query.order_by(Lead.name).all()
    contacts = Contact.query.order_by(Contact.first_name).all()
    companies = Company.query.order_by(Company.name).all()

    return render_template('tasks.html',
        tasks=tasks,
        tab=tab,
        users=users,
        leads=leads,
        contacts=contacts,
        companies=companies,
        now=now,
        status_filter=status_filter,
        priority_filter=priority_filter,
        assigned_filter=assigned_filter,
    )


@tasks_bp.route('/tasks/add', methods=['POST'])
@login_required
def add():
    title = request.form.get('title', '').strip()
    if not title:
        flash('Task title is required.', 'error')
        return redirect(url_for('tasks.index'))

    due_date_str = request.form.get('due_date', '')
    due_date = None
    if due_date_str:
        try:
            due_date = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            try:
                due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
            except ValueError:
                pass

    task = Task(
        title=title,
        description=request.form.get('description', ''),
        due_date=due_date,
        assigned_to=request.form.get('assigned_to', current_user.username),
        priority=request.form.get('priority', 'Medium'),
        status='Open',
        created_by=current_user.username,
    )

    related_type = request.form.get('related_type', '')
    related_id_str = request.form.get('related_id', '')
    if related_id_str:
        rid = int(related_id_str)
        if related_type == 'lead':
            task.related_lead_id = rid
        elif related_type == 'contact':
            task.related_contact_id = rid
        elif related_type == 'company':
            task.related_company_id = rid

    db.session.add(task)
    db.session.commit()
    flash('Task created.', 'success')

    redirect_to = request.form.get('redirect_to', '')
    if redirect_to:
        return redirect(redirect_to)
    return redirect(url_for('tasks.index'))


@tasks_bp.route('/tasks/<int:task_id>/complete', methods=['POST'])
@login_required
def complete(task_id):
    task = Task.query.get_or_404(task_id)
    task.status = 'Completed'
    task.completed_at = datetime.utcnow()
    db.session.commit()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'status': 'ok'})

    flash('Task marked as completed.', 'success')
    redirect_to = request.form.get('redirect_to', '')
    return redirect(redirect_to or url_for('tasks.index'))


@tasks_bp.route('/tasks/<int:task_id>/edit', methods=['POST'])
@login_required
def edit(task_id):
    task = Task.query.get_or_404(task_id)
    task.title = request.form.get('title', task.title).strip()
    task.description = request.form.get('description', task.description)
    task.priority = request.form.get('priority', task.priority)
    task.status = request.form.get('status', task.status)
    task.assigned_to = request.form.get('assigned_to', task.assigned_to)

    due_date_str = request.form.get('due_date', '')
    if due_date_str:
        try:
            task.due_date = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            try:
                task.due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
            except ValueError:
                pass

    if task.status == 'Completed' and not task.completed_at:
        task.completed_at = datetime.utcnow()

    db.session.commit()
    flash('Task updated.', 'success')
    return redirect(url_for('tasks.index'))


@tasks_bp.route('/tasks/<int:task_id>/delete', methods=['POST'])
@login_required
def delete(task_id):
    task = Task.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    flash('Task deleted.', 'success')
    return redirect(url_for('tasks.index'))
