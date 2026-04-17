from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db


# ── Pipeline association tables ────────────────────────────
pipeline_contacts = db.Table('pipeline_contacts',
    db.Column('pipeline_id', db.Integer, db.ForeignKey('pipelines.id'), primary_key=True),
    db.Column('contact_id',  db.Integer, db.ForeignKey('contacts.id'),  primary_key=True),
)

pipeline_companies = db.Table('pipeline_companies',
    db.Column('pipeline_id', db.Integer, db.ForeignKey('pipelines.id'), primary_key=True),
    db.Column('company_id',  db.Integer, db.ForeignKey('companies.id'), primary_key=True),
)

pipeline_leads = db.Table('pipeline_leads',
    db.Column('pipeline_id', db.Integer, db.ForeignKey('pipelines.id'), primary_key=True),
    db.Column('lead_id',     db.Integer, db.ForeignKey('leads.id'),     primary_key=True),
)


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='viewer')   # 'admin' or 'viewer'
    is_active = db.Column(db.Boolean, default=True)
    display_name = db.Column(db.String(120))
    email = db.Column(db.String(200))
    phone = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def name(self):
        return self.display_name or self.username

    def __repr__(self):
        return f'<User {self.username}>'


class Company(db.Model):
    __tablename__ = 'companies'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    industry = db.Column(db.String(100))
    country = db.Column(db.String(100))
    website = db.Column(db.String(200))
    phone = db.Column(db.String(50))
    address = db.Column(db.Text)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    contacts = db.relationship('Contact', back_populates='company', lazy='dynamic')
    leads = db.relationship('Lead', back_populates='company_rel', lazy='dynamic')
    company_notes = db.relationship('CompanyNote', back_populates='company', lazy='dynamic', cascade='all, delete-orphan')
    tasks = db.relationship('Task', back_populates='related_company', lazy='dynamic')

    def __repr__(self):
        return f'<Company {self.name}>'


class Contact(db.Model):
    __tablename__ = 'contacts'
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(200))
    phone = db.Column(db.String(50))
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True)
    job_title = db.Column(db.String(100))
    country = db.Column(db.String(100))
    address = db.Column(db.Text)
    notes = db.Column(db.Text)
    source = db.Column(db.String(50), default='Manual')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    company = db.relationship('Company', back_populates='contacts')
    leads = db.relationship('Lead', back_populates='contact_rel', lazy='dynamic')
    contact_notes = db.relationship('ContactNote', back_populates='contact', lazy='dynamic', cascade='all, delete-orphan')
    tasks = db.relationship('Task', back_populates='related_contact', lazy='dynamic')
    events = db.relationship('CalendarEvent', back_populates='related_contact', lazy='dynamic')

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'

    def __repr__(self):
        return f'<Contact {self.full_name}>'


class Lead(db.Model):
    __tablename__ = 'leads'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    company = db.Column(db.String(200))
    country = db.Column(db.String(100))
    email = db.Column(db.String(200))
    phone = db.Column(db.String(50))
    message = db.Column(db.Text)
    source_channel = db.Column(db.String(50))
    source_url = db.Column(db.String(500))
    assigned_to = db.Column(db.String(50), default='Unassigned')
    status = db.Column(db.String(50), default='New Lead')
    created_by = db.Column(db.String(80))   # username of creator
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True)

    contact_rel = db.relationship('Contact', back_populates='leads')
    company_rel = db.relationship('Company', back_populates='leads')
    stage_history = db.relationship('LeadStageHistory', back_populates='lead', lazy='dynamic', cascade='all, delete-orphan')
    notes = db.relationship('LeadNote', back_populates='lead', lazy='dynamic', cascade='all, delete-orphan')
    feedback = db.relationship('LeadStatusFeedback', back_populates='lead', lazy='dynamic', cascade='all, delete-orphan')
    tasks = db.relationship('Task', back_populates='related_lead', lazy='dynamic')
    events = db.relationship('CalendarEvent', back_populates='related_lead', lazy='dynamic')

    def get_days_in_current_stage(self):
        current = self.stage_history.filter_by(exited_at=None).first()
        if current:
            return (datetime.utcnow() - current.entered_at).days
        return 0

    def __repr__(self):
        return f'<Lead {self.name}>'


class LeadStageHistory(db.Model):
    __tablename__ = 'lead_stage_history'
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('leads.id'), nullable=False)
    stage = db.Column(db.String(50), nullable=False)
    entered_at = db.Column(db.DateTime, default=datetime.utcnow)
    exited_at = db.Column(db.DateTime, nullable=True)
    days_in_stage = db.Column(db.Integer, nullable=True)

    lead = db.relationship('Lead', back_populates='stage_history')


class LeadNote(db.Model):
    __tablename__ = 'lead_notes'
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('leads.id'), nullable=False)
    note_text = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    lead = db.relationship('Lead', back_populates='notes')


class LeadStatusFeedback(db.Model):
    __tablename__ = 'lead_status_feedback'
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('leads.id'), nullable=False)
    from_status = db.Column(db.String(50))
    to_status = db.Column(db.String(50))
    feedback_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    lead = db.relationship('Lead', back_populates='feedback')


class Task(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    due_date = db.Column(db.DateTime)
    assigned_to = db.Column(db.String(80))
    related_lead_id = db.Column(db.Integer, db.ForeignKey('leads.id'), nullable=True)
    related_contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=True)
    related_company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True)
    status = db.Column(db.String(50), default='Open')
    priority = db.Column(db.String(20), default='Medium')
    created_by = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    related_lead = db.relationship('Lead', back_populates='tasks')
    related_contact = db.relationship('Contact', back_populates='tasks')
    related_company = db.relationship('Company', back_populates='tasks')

    def __repr__(self):
        return f'<Task {self.title}>'


class CalendarEvent(db.Model):
    __tablename__ = 'calendar_events'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    start_datetime = db.Column(db.DateTime, nullable=False)
    end_datetime = db.Column(db.DateTime)
    event_type = db.Column(db.String(50), default='Other')
    related_lead_id = db.Column(db.Integer, db.ForeignKey('leads.id'), nullable=True)
    related_contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=True)
    created_by = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    related_lead = db.relationship('Lead', back_populates='events')
    related_contact = db.relationship('Contact', back_populates='events')


class ContactNote(db.Model):
    __tablename__ = 'contact_notes'
    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=False)
    note_text = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    contact = db.relationship('Contact', back_populates='contact_notes')


class CompanyNote(db.Model):
    __tablename__ = 'company_notes'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    note_text = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    company = db.relationship('Company', back_populates='company_notes')


class Pipeline(db.Model):
    __tablename__ = 'pipelines'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    owner = db.Column(db.String(80), nullable=False)   # username
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    contacts  = db.relationship('Contact',  secondary=pipeline_contacts,  lazy='dynamic',
                                backref=db.backref('pipelines', lazy='dynamic'))
    companies = db.relationship('Company',  secondary=pipeline_companies, lazy='dynamic',
                                backref=db.backref('pipelines', lazy='dynamic'))
    leads     = db.relationship('Lead',     secondary=pipeline_leads,     lazy='dynamic',
                                backref=db.backref('pipelines', lazy='dynamic'))

    @property
    def total_members(self):
        return self.contacts.count() + self.companies.count() + self.leads.count()

    def __repr__(self):
        return f'<Pipeline {self.name}>'


PIPELINE_STAGES = ['Prospect', 'Contacted', 'Qualified', 'Demo', 'Close Won', 'Close Lost']

class PipelineMemberStage(db.Model):
    __tablename__ = 'pipeline_member_stages'
    id = db.Column(db.Integer, primary_key=True)
    pipeline_id = db.Column(db.Integer, db.ForeignKey('pipelines.id', ondelete='CASCADE'), nullable=False)
    member_type = db.Column(db.String(20), nullable=False)   # 'contact', 'company', 'lead'
    member_id = db.Column(db.Integer, nullable=False)
    stage = db.Column(db.String(50), default='Prospect')
    __table_args__ = (db.UniqueConstraint('pipeline_id', 'member_type', 'member_id', name='uq_pipeline_member'),)


class ActivityLog(db.Model):
    __tablename__ = 'activity_log'
    id = db.Column(db.Integer, primary_key=True)
    user = db.Column(db.String(80))
    action = db.Column(db.String(200))
    entity_type = db.Column(db.String(50))
    entity_id = db.Column(db.Integer)
    entity_name = db.Column(db.String(200))
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
