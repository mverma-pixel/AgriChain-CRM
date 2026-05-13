"""
Google Analytics 4 Data API integration.

Configure via Settings → Integrations → Google Analytics, or via .env:
  GA_PROPERTY_ID=123456789
  GA_CREDENTIALS_FILE=C:/path/to/service-account.json
"""
import os


def ga_is_configured():
    """Check at call-time so settings changes take effect without restart."""
    prop  = os.environ.get('GA_PROPERTY_ID', '').strip()
    creds = os.environ.get('GA_CREDENTIALS_FILE', '').strip()
    return bool(prop and creds and os.path.exists(creds))


def get_ga_users_by_country(date_from, date_to):
    """
    Returns {country_code: {YYYYMMDD: user_count}} or None if GA not available.
    country_code ∈ {AU, CA, USA, NZ}
    """
    prop       = os.environ.get('GA_PROPERTY_ID', '').strip()
    creds_file = os.environ.get('GA_CREDENTIALS_FILE', '').strip()

    if not (prop and creds_file and os.path.exists(creds_file)):
        return None

    try:
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.analytics.data_v1beta.types import (
            DateRange, Dimension, Metric, RunReportRequest,
        )
        from google.oauth2 import service_account

        creds  = service_account.Credentials.from_service_account_file(
            creds_file,
            scopes=['https://www.googleapis.com/auth/analytics.readonly'],
        )
        client = BetaAnalyticsDataClient(credentials=creds)

        resp = client.run_report(RunReportRequest(
            property=f"properties/{prop}",
            dimensions=[Dimension(name="date"), Dimension(name="country")],
            metrics=[Metric(name="activeUsers")],
            date_ranges=[DateRange(
                start_date=date_from.strftime('%Y-%m-%d'),
                end_date=date_to.strftime('%Y-%m-%d'),
            )],
        ))

        _MAP = {
            'Australia':     'AU',
            'Canada':        'CA',
            'United States': 'USA',
            'New Zealand':   'NZ',
        }
        result = {}
        for row in resp.rows:
            yyyymmdd = row.dimension_values[0].value
            country  = row.dimension_values[1].value
            users    = int(row.metric_values[0].value)
            code     = _MAP.get(country)
            if code:
                result.setdefault(code, {})
                result[code][yyyymmdd] = result[code].get(yyyymmdd, 0) + users

        return result or None

    except Exception as exc:
        print(f"[GA] Error fetching data: {exc}")
        return None


def test_ga_connection():
    """
    Returns (True, 'Connected — property …') or (False, 'error message').
    """
    prop       = os.environ.get('GA_PROPERTY_ID', '').strip()
    creds_file = os.environ.get('GA_CREDENTIALS_FILE', '').strip()

    if not prop:
        return False, 'GA Property ID is not set.'
    if not creds_file:
        return False, 'Credentials file path is not set.'
    if not os.path.exists(creds_file):
        return False, f'Credentials file not found: {creds_file}'

    try:
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.analytics.data_v1beta.types import (
            DateRange, Dimension, Metric, RunReportRequest,
        )
        from google.oauth2 import service_account
        from datetime import date, timedelta

        creds  = service_account.Credentials.from_service_account_file(
            creds_file,
            scopes=['https://www.googleapis.com/auth/analytics.readonly'],
        )
        client = BetaAnalyticsDataClient(credentials=creds)
        today  = date.today()

        client.run_report(RunReportRequest(
            property=f"properties/{prop}",
            dimensions=[Dimension(name="date")],
            metrics=[Metric(name="activeUsers")],
            date_ranges=[DateRange(
                start_date=(today - timedelta(days=1)).strftime('%Y-%m-%d'),
                end_date=today.strftime('%Y-%m-%d'),
            )],
        ))
        return True, f'Connected — Property ID {prop}'

    except Exception as exc:
        return False, str(exc)
