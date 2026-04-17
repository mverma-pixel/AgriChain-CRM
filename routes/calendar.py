from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from models import CalendarEvent, Lead, Contact
from extensions import db

calendar_bp = Blueprint('calendar', __name__)

EVENT_TYPES = ['Call', 'Meeting', 'Demo', 'Follow-up', 'Other']


@calendar_bp.route('/calendar')
@login_required
def index():
    leads = Lead.query.order_by(Lead.name).all()
    contacts = Contact.query.order_by(Contact.first_name).all()
    return render_template('calendar.html',
        event_types=EVENT_TYPES,
        leads=leads,
        contacts=contacts,
    )


@calendar_bp.route('/calendar/events')
@login_required
def events_json():
    year = request.args.get('year', datetime.utcnow().year, type=int)
    month = request.args.get('month', datetime.utcnow().month, type=int)

    # Get events for the month (+/- buffer)
    from calendar import monthrange
    _, last_day = monthrange(year, month)
    start = datetime(year, month, 1)
    end = datetime(year, month, last_day, 23, 59, 59)

    events = CalendarEvent.query.filter(
        CalendarEvent.start_datetime >= start,
        CalendarEvent.start_datetime <= end,
    ).all()

    result = []
    for e in events:
        result.append({
            'id': e.id,
            'title': e.title,
            'description': e.description or '',
            'event_type': e.event_type,
            'start': e.start_datetime.isoformat(),
            'end': e.end_datetime.isoformat() if e.end_datetime else None,
            'related_lead_id': e.related_lead_id,
            'related_contact_id': e.related_contact_id,
        })
    return jsonify(result)


@calendar_bp.route('/calendar/day')
@login_required
def day_events():
    date_str = request.args.get('date', '')
    try:
        day = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        return jsonify([])

    day_end = day.replace(hour=23, minute=59, second=59)
    events = CalendarEvent.query.filter(
        CalendarEvent.start_datetime >= day,
        CalendarEvent.start_datetime <= day_end,
    ).order_by(CalendarEvent.start_datetime).all()

    result = []
    for e in events:
        result.append({
            'id': e.id,
            'title': e.title,
            'description': e.description or '',
            'event_type': e.event_type,
            'start': e.start_datetime.strftime('%H:%M'),
            'end': e.end_datetime.strftime('%H:%M') if e.end_datetime else '',
            'related_lead': e.related_lead.name if e.related_lead else None,
            'related_contact': e.related_contact.full_name if e.related_contact else None,
        })
    return jsonify(result)


@calendar_bp.route('/calendar/add', methods=['POST'])
@login_required
def add():
    title = request.form.get('title', '').strip()
    if not title:
        flash('Event title is required.', 'error')
        return redirect(url_for('calendar.index'))

    start_str = request.form.get('start_datetime', '')
    end_str = request.form.get('end_datetime', '')

    start_dt = None
    end_dt = None
    try:
        start_dt = datetime.strptime(start_str, '%Y-%m-%dT%H:%M')
    except ValueError:
        flash('Invalid start date/time.', 'error')
        return redirect(url_for('calendar.index'))

    if end_str:
        try:
            end_dt = datetime.strptime(end_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            pass

    event = CalendarEvent(
        title=title,
        description=request.form.get('description', ''),
        event_type=request.form.get('event_type', 'Other'),
        start_datetime=start_dt,
        end_datetime=end_dt,
        created_by=current_user.username,
    )

    lead_id = request.form.get('related_lead_id')
    contact_id = request.form.get('related_contact_id')
    if lead_id:
        event.related_lead_id = int(lead_id)
    if contact_id:
        event.related_contact_id = int(contact_id)

    db.session.add(event)
    db.session.commit()
    flash('Event created.', 'success')
    return redirect(url_for('calendar.index'))


@calendar_bp.route('/calendar/<int:event_id>/edit', methods=['POST'])
@login_required
def edit(event_id):
    event = CalendarEvent.query.get_or_404(event_id)
    event.title = request.form.get('title', event.title).strip()
    event.description = request.form.get('description', event.description)
    event.event_type = request.form.get('event_type', event.event_type)

    start_str = request.form.get('start_datetime', '')
    end_str = request.form.get('end_datetime', '')
    if start_str:
        try:
            event.start_datetime = datetime.strptime(start_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            pass
    if end_str:
        try:
            event.end_datetime = datetime.strptime(end_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            pass

    lead_id = request.form.get('related_lead_id')
    contact_id = request.form.get('related_contact_id')
    event.related_lead_id = int(lead_id) if lead_id else None
    event.related_contact_id = int(contact_id) if contact_id else None

    db.session.commit()
    flash('Event updated.', 'success')
    return redirect(url_for('calendar.index'))


@calendar_bp.route('/calendar/<int:event_id>/delete', methods=['POST'])
@login_required
def delete(event_id):
    event = CalendarEvent.query.get_or_404(event_id)
    db.session.delete(event)
    db.session.commit()
    flash('Event deleted.', 'success')
    return redirect(url_for('calendar.index'))
