"""Read-only official X trends. Only fixed api.x.com GET requests are permitted."""
from datetime import datetime, timezone
import json
import os
import re
import urllib.request


REGIONS = {'Tokyo': '1118370', 'Worldwide': '1'}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('TRENDS_REDIRECT_FORBIDDEN')


class OfficialXTrendsProvider:
    endpoint = 'https://api.x.com/2/trends/by/woeid/'

    def __init__(self, bearer_token=None):
        self.bearer_token = bearer_token if bearer_token is not None else os.environ.get('SAYELF_X_BEARER_TOKEN')
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def fetch(self, region='Tokyo'):
        if region not in REGIONS:
            raise ValueError('TREND_REGION_INVALID')
        if not isinstance(self.bearer_token, str) or not self.bearer_token.strip():
            raise ValueError('TRENDS_NOT_CONFIGURED')
        request = urllib.request.Request(
            self.endpoint + REGIONS[region],
            headers={'Authorization': 'Bearer ' + self.bearer_token.strip(), 'Accept': 'application/json'},
            method='GET')
        try:
            with self.opener.open(request, timeout=12) as response:
                raw = response.read(65537)
        except Exception as error:
            # Do not retain or expose response bodies, credentials, or transport details.
            raise ValueError('TRENDS_UNAVAILABLE') from error
        if len(raw) > 65536:
            raise ValueError('TRENDS_RESPONSE_TOO_LARGE')
        try:
            data = json.loads(raw).get('data', [])
        except (ValueError, AttributeError, TypeError) as error:
            raise ValueError('TRENDS_RESPONSE_INVALID') from error
        names = []
        if not isinstance(data, list):
            raise ValueError('TRENDS_RESPONSE_INVALID')
        for row in data[:50]:
            name = row.get('trend_name') if isinstance(row, dict) else None
            if isinstance(name, str) and name.strip() and len(name) <= 160:
                names.append(name.strip())
        if not names:
            raise ValueError('TRENDS_EMPTY')
        return {'state': 'READY', 'region': region, 'woeid': REGIONS[region],
                'observed_at': datetime.now(timezone.utc).isoformat(),
                'source': self.endpoint + REGIONS[region], 'names': names[:30]}


def match_trends(source_text, trend_context, limit=3):
    """Conservative exact phrase overlap; this ranks context and never edits copy."""
    if not trend_context or trend_context.get('state') != 'READY':
        return []
    source = source_text.casefold()
    result = []
    for name in trend_context.get('names', []):
        phrase = name.casefold().strip().lstrip('#')
        matched = (bool(re.search(r'(?<![a-z0-9])'+re.escape(phrase)+r'(?![a-z0-9])',source))
                   if phrase.isascii() else phrase in source)
        if len(phrase) >= 2 and matched:
            result.append(name)
        if len(result) >= limit:
            break
    return result
