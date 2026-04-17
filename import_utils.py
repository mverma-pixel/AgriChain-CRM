"""
Smart spreadsheet import utility.
Reads CSV / XLSX / XLS and maps columns intelligently to known field names
using keyword aliases and fuzzy matching as a fallback.
"""
import csv
import io
import difflib


# ── Field alias map ────────────────────────────────────────────────────────────
# Each entry: canonical_field -> [list of recognised header variants]
# All values are compared case-insensitively after stripping whitespace.

LEAD_ALIASES = {
    'name':           ['name', 'lead name', 'full name', 'contact name', 'person',
                       'lead', 'fullname', 'prospect name'],
    'company':        ['company', 'company name', 'organisation', 'organization',
                       'org', 'firm', 'business', 'employer', 'account'],
    'country':        ['country', 'nation', 'country name', 'location'],
    'email':          ['email', 'e-mail', 'email address', 'mail', 'e mail',
                       'email id', 'e-mail address'],
    'phone':          ['phone', 'telephone', 'tel', 'mobile', 'cell', 'ph',
                       'phone number', 'contact number', 'mobile number'],
    'source_channel': ['source channel', 'source', 'channel', 'lead source',
                       'origin', 'source_channel', 'acquisition'],
    'source_url':     ['source url', 'source_url', 'url', 'landing page',
                       'page url', 'referral url'],
    'message':        ['message', 'notes', 'note', 'comments', 'comment',
                       'description', 'inquiry', 'enquiry', 'details'],
    'assigned_to':    ['assigned to', 'assigned', 'assignee', 'owner',
                       'sales rep', 'rep', 'assigned_to', 'salesperson',
                       'account owner'],
    'status':         ['status', 'stage', 'lead status', 'lead stage', 'state'],
}

CONTACT_ALIASES = {
    'first_name':  ['first name', 'firstname', 'first', 'given name', 'forename',
                    'first_name'],
    'last_name':   ['last name', 'lastname', 'last', 'surname', 'family name',
                    'last_name'],
    'full_name':   ['name', 'full name', 'contact name', 'fullname',
                    'full_name', 'display name'],
    'email':       ['email', 'e-mail', 'email address', 'mail', 'e mail',
                    'email id', 'e-mail address'],
    'phone':       ['phone', 'telephone', 'tel', 'mobile', 'cell', 'ph',
                    'phone number', 'contact number', 'mobile number'],
    'company':     ['company', 'company name', 'organisation', 'organization',
                    'org', 'firm', 'business', 'employer', 'account'],
    'country':     ['country', 'nation', 'country name', 'location'],
    'job_title':   ['job title', 'title', 'position', 'role', 'designation',
                    'job', 'occupation', 'job_title', 'function'],
}

COMPANY_ALIASES = {
    'name':     ['name', 'company name', 'company', 'organisation', 'organization',
                 'org', 'firm', 'business', 'account name'],
    'industry': ['industry', 'sector', 'type', 'business type', 'industry type',
                 'vertical', 'segment'],
    'country':  ['country', 'nation', 'country name', 'location'],
    'website':  ['website', 'web', 'url', 'site', 'web address', 'website url',
                 'homepage'],
    'phone':    ['phone', 'telephone', 'tel', 'mobile', 'phone number',
                 'contact number', 'main phone'],
    'address':  ['address', 'street address', 'office address', 'addr',
                 'mailing address', 'hq address'],
    'notes':    ['notes', 'note', 'comments', 'description', 'remarks', 'details'],
}


# ── Core helpers ───────────────────────────────────────────────────────────────

def _normalise(s):
    return s.strip().lower()


def build_column_map(headers, aliases):
    """
    Given a list of raw header strings and an alias dict, return a dict
    mapping each canonical field name to the raw header that best matches it
    (or None if no match found).

    Strategy:
    1. Exact match against alias list.
    2. Substring match (alias appears in header or vice versa).
    3. Fuzzy match via difflib (cutoff 0.7) as a last resort.
    """
    norm_headers = {h: _normalise(h) for h in headers}
    col_map = {}          # canonical_field -> raw_header
    claimed = set()       # raw headers already assigned

    # Pass 1: exact match
    for field, alts in aliases.items():
        for raw, norm in norm_headers.items():
            if raw in claimed:
                continue
            if norm in alts:
                col_map[field] = raw
                claimed.add(raw)
                break

    # Pass 2: substring match
    for field, alts in aliases.items():
        if field in col_map:
            continue
        for raw, norm in norm_headers.items():
            if raw in claimed:
                continue
            if any(a in norm or norm in a for a in alts):
                col_map[field] = raw
                claimed.add(raw)
                break

    # Pass 3: fuzzy match
    remaining_fields = [f for f in aliases if f not in col_map]
    remaining_headers = [h for h in headers if h not in claimed]
    for field in remaining_fields:
        alts = aliases[field]
        best_score = 0.0
        best_raw = None
        for raw in remaining_headers:
            norm = _normalise(raw)
            for a in alts:
                score = difflib.SequenceMatcher(None, norm, a).ratio()
                if score > best_score:
                    best_score = score
                    best_raw = raw
        if best_score >= 0.70 and best_raw:
            col_map[field] = best_raw
            remaining_headers.remove(best_raw)

    return col_map


def _get(row, col_map, field, default=''):
    raw_header = col_map.get(field)
    if not raw_header:
        return default
    return (row.get(raw_header) or '').strip()


def read_spreadsheet(file):
    """
    Read an uploaded file object (CSV / XLSX / XLS) and return:
      - headers: list of column header strings
      - rows:    list of dicts {header: value}
    """
    filename = (file.filename or '').lower()

    if filename.endswith('.csv'):
        content = file.stream.read().decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)
        headers = reader.fieldnames or []
        return headers, rows

    elif filename.endswith('.xlsx'):
        import openpyxl
        wb = openpyxl.load_workbook(file.stream, read_only=True, data_only=True)
        ws = wb.active
        all_rows = list(ws.iter_rows(values_only=True))
        wb.close()
        if not all_rows:
            return [], []
        headers = [str(c).strip() if c is not None else '' for c in all_rows[0]]
        rows = []
        for r in all_rows[1:]:
            if all(c is None for c in r):
                continue
            rows.append({headers[i]: (str(r[i]).strip() if r[i] is not None else '')
                         for i in range(len(headers))})
        return headers, rows

    elif filename.endswith('.xls'):
        import xlrd
        content = file.stream.read()
        wb = xlrd.open_workbook(file_contents=content)
        ws = wb.sheet_by_index(0)
        if ws.nrows == 0:
            return [], []
        headers = [str(ws.cell_value(0, c)).strip() for c in range(ws.ncols)]
        rows = []
        for r in range(1, ws.nrows):
            row_vals = [ws.cell_value(r, c) for c in range(ws.ncols)]
            if all(v == '' or v is None for v in row_vals):
                continue
            rows.append({headers[i]: str(row_vals[i]).strip() if row_vals[i] is not None else ''
                         for i in range(len(headers))})
        return headers, rows

    else:
        raise ValueError(f'Unsupported file type: {filename}')
