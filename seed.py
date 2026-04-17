"""
Seed the AgriChain CRM database with sample data.
Run: python seed.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, timedelta
from app import create_app
from extensions import db
from models import (
    User, Lead, LeadStageHistory, LeadNote, LeadStatusFeedback,
    Contact, Company, Task, CalendarEvent, ActivityLog
)

app = create_app()

def seed():
    with app.app_context():
        db.drop_all()
        db.create_all()
        print("Database reset. Seeding...")

        # ── Users ──────────────────────────────────────────────
        admin = User(username='admin', role='admin')
        admin.set_password('admin123')
        viewer = User(username='viewer', role='viewer')
        viewer.set_password('viewer123')
        db.session.add_all([admin, viewer])
        db.session.flush()

        # ── Companies ──────────────────────────────────────────
        companies = [
            Company(name='FarmCo', industry='Agriculture', country='Australia',
                    website='https://farmco.com.au', phone='+61299990001',
                    notes='Major grain producer in NSW'),
            Company(name='GrainPro', industry='Agriculture', country='United States',
                    website='https://grainpro.com', phone='+14155551200',
                    notes='Largest US grain cooperative'),
            Company(name='HarvestNZ', industry='Agriculture', country='New Zealand',
                    website='https://harvestnz.co.nz', phone='+6498880001',
                    notes='NZ-based crop management company'),
            Company(name='AgroCorp', industry='Agriculture', country='United Kingdom',
                    website='https://agrocorp.co.uk', phone='+441614440001',
                    notes='EU-focused agricultural tech company'),
            Company(name='PampasGrain', industry='Agriculture', country='Argentina',
                    website='https://pampasgrain.com.ar', phone='+541122220001',
                    notes='South American grain exporter'),
        ]
        db.session.add_all(companies)
        db.session.flush()
        farmco, grainpro, harvestnz, agrocorp, pampasgrain = companies

        # ── Leads ──────────────────────────────────────────────
        now = datetime.utcnow()

        leads_data = [
            # AU/NZ → Skye
            dict(name='James Wilson', company='FarmCo', country='Australia',
                 email='james@farmco.com.au', phone='+61412000001',
                 message='Interested in grain tracking and compliance features.',
                 source_channel='Homepage', source_url='https://agrichain.com/',
                 assigned_to='Skye', status='Close Won', company_id=farmco.id,
                 created_at=now - timedelta(days=60)),
            dict(name='Emma Thompson', company='HarvestNZ', country='New Zealand',
                 email='emma@harvestnz.co.nz', phone='+6421000001',
                 message='Looking for digital grain management solution.',
                 source_channel='Feature', source_url='https://agrichain.com/features/grain-tracking',
                 assigned_to='Skye', status='Demo', company_id=harvestnz.id,
                 created_at=now - timedelta(days=22)),
            dict(name='Liam Chen', company='SunCrop AU', country='Australia',
                 email='liam@suncrop.com.au', phone='+61413000002',
                 message='Need to track paddock performance.',
                 source_channel='Blog', source_url='https://agrichain.com/blog/farm-management',
                 assigned_to='Skye', status='SAL',
                 created_at=now - timedelta(days=14)),
            dict(name='Sophie Martin', company='KiwiAg', country='New Zealand',
                 email='sophie@kiwi-ag.co.nz', phone='+6422000002',
                 message='Interested in API integration.',
                 source_channel='User', source_url='https://agrichain.com/users/testimonials',
                 assigned_to='Skye', status='Close Lost',
                 created_at=now - timedelta(days=45)),
            dict(name='Noah Walker', company='OzFarm', country='Australia',
                 email='noah@ozfarm.com.au', phone='+61414000003',
                 message='Evaluating AgriChain for 3 farms.',
                 source_channel='Google Ads', source_url='https://agrichain.com/lp/grain',
                 assigned_to='Skye', status='Pending',
                 created_at=now - timedelta(days=5)),
            # US/Canada → Tony
            dict(name='Olivia Johnson', company='GrainPro', country='United States',
                 email='olivia@grainpro.com', phone='+14155551001',
                 message='Large-scale corn tracking requirement.',
                 source_channel='Homepage', source_url='https://agrichain.com/',
                 assigned_to='Tony', status='Demo', company_id=grainpro.id,
                 created_at=now - timedelta(days=18)),
            dict(name='William Brown', company='Prairie Fields', country='Canada',
                 email='william@prairiefields.ca', phone='+14163000001',
                 message='Want to connect with our ERP.',
                 source_channel='Chatbot', source_url='https://agrichain.com/',
                 assigned_to='Tony', status='SAL',
                 created_at=now - timedelta(days=9)),
            dict(name='Ava Davis', company='MidWest Grain Co', country='United States',
                 email='ava@midwestgrain.com', phone='+13125551002',
                 message='Looking for compliance management.',
                 source_channel='About', source_url='https://agrichain.com/about',
                 assigned_to='Tony', status='Close Won',
                 created_at=now - timedelta(days=55)),
            dict(name='Mason Taylor', company='RanchPro', country='United States',
                 email='mason@ranchpro.com', phone='+14085551003',
                 message='Interested in livestock + grain modules.',
                 source_channel='Google Ads', source_url='https://agrichain.com/lp/livestock',
                 assigned_to='Tony', status='Out',
                 created_at=now - timedelta(days=30)),
            dict(name='Isabella Harris', company='Saskatchewan Farms', country='Canada',
                 email='isabella@saskfarms.ca', phone='+13069000001',
                 message='Trial of the software for 30 days.',
                 source_channel='Blog', source_url='https://agrichain.com/blog/case-study',
                 assigned_to='Tony', status='New Lead',
                 created_at=now - timedelta(days=2)),
            # Unassigned / Other countries
            dict(name='Ethan Clark', company='AgroCorp', country='United Kingdom',
                 email='ethan@agrocorp.co.uk', phone='+447700000001',
                 message='EU expansion. Need multi-country support.',
                 source_channel='Feature', source_url='https://agrichain.com/features/compliance',
                 assigned_to='Unassigned', status='Pending', company_id=agrocorp.id,
                 created_at=now - timedelta(days=5)),
            dict(name='Charlotte Lewis', company='PampasGrain', country='Argentina',
                 email='charlotte@pampasgrain.com.ar', phone='+541133000001',
                 message='Spanish-language support needed.',
                 source_channel='Homepage', source_url='https://agrichain.com/',
                 assigned_to='Unassigned', status='SAL', company_id=pampasgrain.id,
                 created_at=now - timedelta(days=12)),
            dict(name='Henry Scott', company='IndiaGrain Ltd', country='India',
                 email='henry@indiagrain.in', phone='+919900000001',
                 message='Looking for wholesale grain management.',
                 source_channel='Chatbot', source_url='https://agrichain.com/',
                 assigned_to='Unassigned', status='New Lead',
                 created_at=now - timedelta(days=1)),
            dict(name='Amelia White', company='Kenya Farms', country='Kenya',
                 email='amelia@kenyafarms.co.ke', phone='+254700000001',
                 message='Interested in cooperative management.',
                 source_channel='User', source_url='https://agrichain.com/users',
                 assigned_to='Unassigned', status='Pending',
                 created_at=now - timedelta(days=7)),
            dict(name='Lucas Anderson', company='BrazilCrop', country='Brazil',
                 email='lucas@brazilcrop.com.br', phone='+5511900000001',
                 message='Large soybean operation seeking tracking.',
                 source_channel='Google Ads', source_url='https://agrichain.com/lp/soy',
                 assigned_to='Unassigned', status='Out',
                 created_at=now - timedelta(days=35)),
            dict(name='Mia Jackson', company='EuroAg', country='Germany',
                 email='mia@euroag.de', phone='+4915100000001',
                 message='GDPR compliance requirement.',
                 source_channel='About', source_url='https://agrichain.com/about',
                 assigned_to='Unassigned', status='Pending',
                 created_at=now - timedelta(days=4)),
            dict(name='Alexander Young', company='FarmTech JP', country='Japan',
                 email='alex@farmtechjp.co.jp', phone='+819000000001',
                 message='Rice paddock management software.',
                 source_channel='Blog', source_url='https://agrichain.com/blog/rice',
                 assigned_to='Unassigned', status='Pending',
                 created_at=now - timedelta(days=6)),
            dict(name='Emily King', company='SkyFarm', country='Australia',
                 email='emily@skyfarm.com.au', phone='+61415000004',
                 message='Drone + AgriChain integration interest.',
                 source_channel='Feature', source_url='https://agrichain.com/features/drone',
                 assigned_to='Skye', status='Pending',
                 created_at=now - timedelta(days=8)),
            dict(name='Daniel Green', company='CanadaWheat', country='Canada',
                 email='daniel@canadawheat.ca', phone='+14167000001',
                 message='Wheat cooperative management.',
                 source_channel='Homepage', source_url='https://agrichain.com/',
                 assigned_to='Tony', status='Pending',
                 created_at=now - timedelta(days=10)),
            dict(name='Chloe Baker', company='SouthAfrican Grain', country='South Africa',
                 email='chloe@sagrain.co.za', phone='+27800000001',
                 message='Interested in export compliance tracking.',
                 source_channel='Chatbot', source_url='https://agrichain.com/',
                 assigned_to='Unassigned', status='New Lead',
                 created_at=now - timedelta(days=0)),
            # Additional leads
            dict(name='Raj Patel', company='Punjab AgriTech', country='India',
                 email='raj@punjabagritch.in', phone='+919800000002',
                 message='Large wheat cooperative, seeking compliance tools.',
                 source_channel='Call', source_url='',
                 assigned_to='Unassigned', status='SAL',
                 created_at=now - timedelta(days=20)),
            dict(name='Fatima Al-Hassan', company='Gulf Farms', country='United Arab Emirates',
                 email='fatima@gulffarms.ae', phone='+971501000001',
                 message='Interested in multi-farm management.',
                 source_channel='Email', source_url='',
                 assigned_to='Unassigned', status='Demo',
                 created_at=now - timedelta(days=25)),
            dict(name='Carlos Mendez', company='MexiCrop', country='Mexico',
                 email='carlos@mexicrop.mx', phone='+5215500000001',
                 message='Avocado & grain tracking.',
                 source_channel='Homepage', source_url='https://agrichain.com/',
                 assigned_to='Unassigned', status='Pending',
                 created_at=now - timedelta(days=5)),
            dict(name='Yuki Tanaka', company='Tokyo Farm Systems', country='Japan',
                 email='yuki@tokyofarm.jp', phone='+819100000001',
                 message='Rice + vegetable tracking, needs Japanese UI.',
                 source_channel='Blog', source_url='https://agrichain.com/blog',
                 assigned_to='Unassigned', status='New Lead',
                 created_at=now - timedelta(days=1)),
        ]

        lead_objs = []
        for d in leads_data:
            l = Lead(**d)
            db.session.add(l)
            lead_objs.append(l)
        db.session.flush()

        # ── Stage Histories ─────────────────────────────────────
        def add_history(lead, stages):
            """stages = [(stage_name, entered_days_ago, exited_days_ago)]"""
            for stage, entered_ago, exited_ago in stages:
                entered = now - timedelta(days=entered_ago)
                exited = (now - timedelta(days=exited_ago)) if exited_ago is not None else None
                days = (exited - entered).days if exited else None
                h = LeadStageHistory(lead_id=lead.id, stage=stage,
                                     entered_at=entered, exited_at=exited, days_in_stage=days)
                db.session.add(h)

        # Lead 0: James Wilson — Close Won
        add_history(lead_objs[0], [
            ('New Lead', 60, 55),
            ('SAL', 55, 45),
            ('Demo', 45, 35),
            ('Close Won', 35, None),
        ])
        # Lead 1: Emma Thompson — Demo
        add_history(lead_objs[1], [
            ('New Lead', 22, 18),
            ('SAL', 18, 12),
            ('Demo', 12, None),
        ])
        # Lead 2: Liam Chen — SAL
        add_history(lead_objs[2], [
            ('New Lead', 14, 10),
            ('SAL', 10, None),
        ])
        # Lead 3: Sophie Martin — Close Lost
        add_history(lead_objs[3], [
            ('New Lead', 45, 40),
            ('SAL', 40, 30),
            ('Out', 30, 25),
            ('SAL', 25, 15),
            ('Demo', 15, 10),
            ('Close Lost', 10, None),
        ])
        # Lead 4: Noah Walker — Pending (was New Lead, aged out)
        add_history(lead_objs[4], [
            ('New Lead', 5, 3),
            ('Pending', 3, None),
        ])
        # Lead 5: Olivia Johnson — Demo
        add_history(lead_objs[5], [
            ('New Lead', 18, 14),
            ('SAL', 14, 7),
            ('Demo', 7, None),
        ])
        # Lead 6: William Brown — SAL (simple entry)
        add_history(lead_objs[6], [
            ('New Lead', 9, 6),
            ('SAL', 6, None),
        ])
        # Lead 7: Ava Davis — Close Won
        add_history(lead_objs[7], [
            ('New Lead', 55, 50),
            ('SAL', 50, 40),
            ('Demo', 40, 30),
            ('Close Won', 30, None),
        ])
        # Lead 8: Mason Taylor — Out (simple entry)
        add_history(lead_objs[8], [
            ('New Lead', 30, 25),
            ('SAL', 25, 15),
            ('Out', 15, None),
        ])
        # Lead 9: Isabella Harris — New Lead (just arrived)
        add_history(lead_objs[9], [
            ('New Lead', 2, None),
        ])
        # Lead 10: Ethan Clark — Pending
        add_history(lead_objs[10], [
            ('New Lead', 5, 3),
            ('Pending', 3, None),
        ])
        # Lead 11: Charlotte Lewis — SAL
        add_history(lead_objs[11], [
            ('New Lead', 12, 8),
            ('SAL', 8, None),
        ])
        # Lead 12: Henry Scott — New Lead (just arrived)
        add_history(lead_objs[12], [
            ('New Lead', 1, None),
        ])
        # Lead 13: Amelia White — Pending
        add_history(lead_objs[13], [
            ('New Lead', 7, 3),
            ('Pending', 3, None),
        ])
        # Lead 14: Lucas Anderson — Out
        add_history(lead_objs[14], [
            ('New Lead', 35, 30),
            ('SAL', 30, 20),
            ('Out', 20, None),
        ])
        # Lead 15: Mia Jackson — Pending
        add_history(lead_objs[15], [
            ('New Lead', 4, 3),
            ('Pending', 3, None),
        ])
        # Lead 16: Alexander Young — Pending
        add_history(lead_objs[16], [
            ('New Lead', 6, 3),
            ('Pending', 3, None),
        ])
        # Lead 17: Emily King — Pending
        add_history(lead_objs[17], [
            ('New Lead', 8, 3),
            ('Pending', 3, None),
        ])
        # Lead 18: Daniel Green — Pending
        add_history(lead_objs[18], [
            ('New Lead', 10, 3),
            ('Pending', 3, None),
        ])
        # Lead 19: Chloe Baker — New Lead (just arrived)
        add_history(lead_objs[19], [
            ('New Lead', 0, None),
        ])
        # Lead 20: Raj Patel — SAL
        add_history(lead_objs[20], [
            ('New Lead', 20, 17),
            ('Pending', 17, 14),
            ('SAL', 14, None),
        ])
        # Lead 21: Fatima Al-Hassan — Demo
        add_history(lead_objs[21], [
            ('New Lead', 25, 22),
            ('Pending', 22, 18),
            ('SAL', 18, 10),
            ('Demo', 10, None),
        ])
        # Lead 22: Carlos Mendez — Pending
        add_history(lead_objs[22], [
            ('New Lead', 5, 3),
            ('Pending', 3, None),
        ])
        # Lead 23: Yuki Tanaka — New Lead (just arrived)
        add_history(lead_objs[23], [
            ('New Lead', 1, None),
        ])

        db.session.flush()

        # ── Feedback ────────────────────────────────────────────
        feedbacks = [
            LeadStatusFeedback(lead_id=lead_objs[3].id,
                               from_status='Demo', to_status='Close Lost',
                               feedback_text='Budget constraints — renewed next fiscal year possibly.',
                               created_at=now - timedelta(days=10)),
            LeadStatusFeedback(lead_id=lead_objs[8].id,
                               from_status='SAL', to_status='Out',
                               feedback_text='Lead went silent after 3 follow-ups. Marking as Out for now.',
                               created_at=now - timedelta(days=25)),
            LeadStatusFeedback(lead_id=lead_objs[14].id,
                               from_status='New Lead', to_status='Out',
                               feedback_text='Language barrier and no English-speaking team member available.',
                               created_at=now - timedelta(days=30)),
        ]
        db.session.add_all(feedbacks)

        # ── Lead Notes ──────────────────────────────────────────
        notes = [
            LeadNote(lead_id=lead_objs[0].id, note_text='Initial discovery call completed. James is very enthusiastic.',
                     created_by='admin', created_at=now - timedelta(days=58)),
            LeadNote(lead_id=lead_objs[0].id, note_text='Demo went well. Sending formal proposal.',
                     created_by='admin', created_at=now - timedelta(days=40)),
            LeadNote(lead_id=lead_objs[0].id, note_text='Contract signed! Onboarding scheduled for next Monday.',
                     created_by='admin', created_at=now - timedelta(days=33)),
            LeadNote(lead_id=lead_objs[1].id, note_text='Emma is the decision maker. Demo booked for Friday.',
                     created_by='admin', created_at=now - timedelta(days=20)),
            LeadNote(lead_id=lead_objs[1].id, note_text='Demo completed. Very positive feedback. Waiting on board approval.',
                     created_by='admin', created_at=now - timedelta(days=10)),
            LeadNote(lead_id=lead_objs[5].id, note_text='Olivia is evaluating 3 competitors. We need to move fast.',
                     created_by='admin', created_at=now - timedelta(days=16)),
            LeadNote(lead_id=lead_objs[5].id, note_text='Technical demo scheduled with CTO next week.',
                     created_by='admin', created_at=now - timedelta(days=8)),
            LeadNote(lead_id=lead_objs[7].id, note_text='Ava confirmed contract. Largest deal this quarter!',
                     created_by='admin', created_at=now - timedelta(days=28)),
            LeadNote(lead_id=lead_objs[2].id, note_text='Liam wants to start with a 3-farm pilot.',
                     created_by='viewer', created_at=now - timedelta(days=12)),
        ]
        db.session.add_all(notes)

        # ── Contacts ────────────────────────────────────────────
        contacts = [
            Contact(first_name='James', last_name='Wilson', email='james@farmco.com.au',
                    phone='+61412000001', company_id=farmco.id, job_title='Operations Manager',
                    country='Australia', source='Converted from Lead',
                    created_at=now - timedelta(days=34)),
            Contact(first_name='Ava', last_name='Davis', email='ava@midwestgrain.com',
                    phone='+13125551002', job_title='Procurement Head',
                    country='United States', source='Converted from Lead',
                    created_at=now - timedelta(days=29)),
            Contact(first_name='Rachel', last_name='Moore', email='rachel@grainpro.com',
                    phone='+14155551050', company_id=grainpro.id, job_title='CTO',
                    country='United States', source='Manual',
                    created_at=now - timedelta(days=20)),
            Contact(first_name='Tom', last_name='Patterson', email='tom@harvestnz.co.nz',
                    phone='+6421000099', company_id=harvestnz.id, job_title='CEO',
                    country='New Zealand', source='Manual',
                    created_at=now - timedelta(days=15)),
            Contact(first_name='Priya', last_name='Sharma', email='priya@agrocorp.co.uk',
                    phone='+447700000099', company_id=agrocorp.id, job_title='Partnership Manager',
                    country='United Kingdom', source='API',
                    created_at=now - timedelta(days=5)),
        ]
        db.session.add_all(contacts)
        db.session.flush()

        # Link converted contacts back to leads
        lead_objs[0].contact_id = contacts[0].id
        lead_objs[7].contact_id = contacts[1].id

        # ── Tasks ───────────────────────────────────────────────
        tasks = [
            Task(title='Send proposal to Emma Thompson', priority='High',
                 status='Open', assigned_to='admin',
                 due_date=now + timedelta(days=1),
                 related_lead_id=lead_objs[1].id,
                 created_by='admin', created_at=now - timedelta(days=5)),
            Task(title='Follow up with Liam Chen on pilot pricing', priority='High',
                 status='In Progress', assigned_to='admin',
                 due_date=now + timedelta(days=2),
                 related_lead_id=lead_objs[2].id,
                 created_by='admin', created_at=now - timedelta(days=3)),
            Task(title='Schedule demo with Olivia Johnson CTO', priority='Medium',
                 status='Open', assigned_to='viewer',
                 due_date=now + timedelta(days=3),
                 related_lead_id=lead_objs[5].id,
                 created_by='admin', created_at=now - timedelta(days=2)),
            Task(title='Send onboarding documents to FarmCo', priority='Medium',
                 status='Completed', assigned_to='admin',
                 due_date=now - timedelta(days=25),
                 completed_at=now - timedelta(days=25),
                 related_lead_id=lead_objs[0].id,
                 related_contact_id=contacts[0].id,
                 created_by='admin', created_at=now - timedelta(days=30)),
            Task(title='Quarterly check-in with Rachel Moore', priority='Low',
                 status='Open', assigned_to='viewer',
                 due_date=now + timedelta(days=14),
                 related_contact_id=contacts[2].id,
                 created_by='admin', created_at=now - timedelta(days=1)),
            Task(title='Prepare AgriChain demo script v2', priority='Medium',
                 status='Open', assigned_to='admin',
                 due_date=now - timedelta(days=2),  # Overdue
                 created_by='admin', created_at=now - timedelta(days=10)),
            Task(title='Review GrainPro contract terms', priority='High',
                 status='Open', assigned_to='admin',
                 due_date=now,  # Due today
                 related_company_id=grainpro.id,
                 created_by='admin', created_at=now - timedelta(days=5)),
            Task(title='Update CRM with latest lead sources', priority='Low',
                 status='Completed', assigned_to='viewer',
                 due_date=now - timedelta(days=7),
                 completed_at=now - timedelta(days=7),
                 created_by='admin', created_at=now - timedelta(days=14)),
            Task(title='Call William Brown re: ERP integration', priority='High',
                 status='Open', assigned_to='admin',
                 due_date=now + timedelta(hours=4),  # Due today
                 related_lead_id=lead_objs[6].id,
                 created_by='admin', created_at=now - timedelta(days=1)),
            Task(title='Send NZ market report to Skye', priority='Medium',
                 status='Cancelled', assigned_to='admin',
                 due_date=now - timedelta(days=5),
                 created_by='admin', created_at=now - timedelta(days=8)),
        ]
        db.session.add_all(tasks)

        # ── Calendar Events ─────────────────────────────────────
        events = [
            CalendarEvent(
                title='Discovery Call — FarmCo',
                description='Initial discovery with James Wilson.',
                event_type='Call',
                start_datetime=now - timedelta(days=58, hours=-10),
                end_datetime=now - timedelta(days=58, hours=-11),
                related_lead_id=lead_objs[0].id,
                created_by='admin'),
            CalendarEvent(
                title='Demo — HarvestNZ',
                description='Product demo for Emma Thompson.',
                event_type='Demo',
                start_datetime=now - timedelta(days=10, hours=-14),
                end_datetime=now - timedelta(days=10, hours=-15),
                related_lead_id=lead_objs[1].id,
                created_by='admin'),
            CalendarEvent(
                title='Follow-up — GrainPro',
                description='Check in with Olivia on technical requirements.',
                event_type='Follow-up',
                start_datetime=now + timedelta(days=2, hours=9),
                end_datetime=now + timedelta(days=2, hours=10),
                related_lead_id=lead_objs[5].id,
                created_by='admin'),
            CalendarEvent(
                title='Team Sync — Weekly',
                description='Weekly CRM review with sales team.',
                event_type='Meeting',
                start_datetime=now + timedelta(days=1, hours=9),
                end_datetime=now + timedelta(days=1, hours=10),
                created_by='admin'),
            CalendarEvent(
                title='Onboarding Call — FarmCo',
                description='Post-sale onboarding session.',
                event_type='Call',
                start_datetime=now - timedelta(days=30, hours=-14),
                end_datetime=now - timedelta(days=30, hours=-15),
                related_contact_id=contacts[0].id,
                created_by='admin'),
        ]
        db.session.add_all(events)

        # ── Activity Logs ───────────────────────────────────────
        logs = []
        for i, lead in enumerate(lead_objs):
            logs.append(ActivityLog(
                user='admin', action='Created lead',
                entity_type='lead', entity_id=lead.id, entity_name=lead.name,
                created_at=lead.created_at or now
            ))

        # Status change logs for leads with history
        logs += [
            ActivityLog(user='admin', action='Status changed: New Lead → SAL',
                        entity_type='lead', entity_id=lead_objs[0].id, entity_name=lead_objs[0].name,
                        created_at=now - timedelta(days=55)),
            ActivityLog(user='admin', action='Status changed: SAL → Demo',
                        entity_type='lead', entity_id=lead_objs[0].id, entity_name=lead_objs[0].name,
                        created_at=now - timedelta(days=45)),
            ActivityLog(user='admin', action='Status changed: Demo → Close Won',
                        entity_type='lead', entity_id=lead_objs[0].id, entity_name=lead_objs[0].name,
                        created_at=now - timedelta(days=35)),
            ActivityLog(user='admin', action='Converted to contact',
                        entity_type='lead', entity_id=lead_objs[0].id, entity_name=lead_objs[0].name,
                        created_at=now - timedelta(days=34)),
        ]
        db.session.add_all(logs)

        db.session.commit()
        print("Seeded successfully:")
        print(f"   Users: 2 (admin/admin123, viewer/viewer123)")
        print(f"   Companies: {len(companies)}")
        print(f"   Leads: {len(lead_objs)}")
        print(f"   Contacts: {len(contacts)}")
        print(f"   Tasks: {len(tasks)}")
        print(f"   Calendar Events: {len(events)}")
        print("\nStart the app: python app.py")
        print("   Login at: http://localhost:5001")


if __name__ == '__main__':
    seed()
