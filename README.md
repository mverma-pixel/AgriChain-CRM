# AgriChain CRM

Internal CRM for AgriChain — Lead Management, Contacts, Companies, Calendar, Tasks, and Reporting.

## Quick Start

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate          # Mac/Linux
venv\Scripts\activate             # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy environment file
copy .env.example .env            # Windows
cp .env.example .env              # Mac/Linux
# Edit .env and set SECRET_KEY

# 4. Seed the database
python seed.py

# 5. Run the app
python app.py
```

Open: **http://localhost:5000**

Login:
- `admin` / `admin123` (full access)
- `viewer` / `viewer123` (view/edit, no admin functions)

## Hosting on a Subdomain

```bash
# Install gunicorn
pip install gunicorn

# Run with 4 workers
gunicorn -w 4 -b 0.0.0.0:5000 "app:app"
```

**Nginx config** (`/etc/nginx/sites-available/agrichain-crm`):
```nginx
server {
    listen 80;
    server_name agrichain-crm.agrichain.com;
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

Then: `sudo certbot --nginx -d agrichain-crm.agrichain.com`

## API

```bash
# Create a lead via webhook (no auth required)
curl -X POST http://localhost:5000/api/webhook/lead \
  -H "Content-Type: application/json" \
  -d '{"name":"Jane Smith","company":"FarmCo","country":"Australia","email":"jane@farmco.com","source_channel":"Homepage"}'

# Authenticated API (Basic Auth)
curl -u admin:admin123 http://localhost:5000/api/leads
```

## Slack

Set `SLACK_WEBHOOK_URL` in `.env`, or configure in Settings → Integrations.

Notifications sent for: new leads, Close Won, Close Lost, and daily breach alerts (leads stale 7+ days).
