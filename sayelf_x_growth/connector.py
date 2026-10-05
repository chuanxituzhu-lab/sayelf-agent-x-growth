"""Final write adapter. Default disabled; no browser, proxy, arbitrary URL, or retries."""
import json
import re
import urllib.request
from urllib.parse import urlencode
from .gates import SECRET


class OfflineConnector:
    mode='offline'
    def preflight(self,draft):
        pass

    def create(self,draft):
        # Offline results are labelled SIMULATED all the way through observations/learning.
        return {'id':'0'}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise ValueError('REDIRECT_FORBIDDEN')


class OfficialXConnector:
    mode='live'
    endpoint='https://api.x.com/2/tweets'
    def __init__(self,account=None,token_provider=None,enabled=False):
        self.account=account
        self.token_provider=token_provider
        self.enabled=enabled
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())

    def _request(self,path,token,payload=None):
        request=urllib.request.Request('https://api.x.com'+path,
                    data=json.dumps(payload).encode() if payload is not None else None,
                    headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'},
                    method='POST' if payload is not None else 'GET')
        with self.opener.open(request,timeout=20) as response:
            raw=response.read(65537)
            if len(raw)>65536:
                raise ValueError('RESPONSE_TOO_LARGE')
            return json.loads(raw)

    def preflight(self,draft):
        if not self.enabled or not self.token_provider or self.account!=draft['account']:
            raise ValueError('OFFICIAL_X_NOT_CONFIGURED')
        if draft['kind'] in {'QUOTE','THREAD'}:
            # These need a separately reviewed multi-post / quote-ID API payload.
            raise ValueError('QUOTE_THREAD_WRITE_PAYLOAD_NOT_IMPLEMENTED')
        if SECRET.search(draft['text']):
            raise ValueError('LEAK_CHECK_BLOCKED')

    def create(self,draft):
        self.preflight(draft)
        token=self.token_provider()
        if not isinstance(token,str) or not token.strip():
            raise ValueError('TOKEN_UNAVAILABLE')
        # Credential identity is validated, never inferred from configured account name.
        me=self._request('/2/users/me',token)
        if me.get('data',{}).get('username','').lower()!=self.account.lower():
            raise ValueError('TOKEN_ACCOUNT_MISMATCH')
        value=self._request('/2/tweets',token,{'text':draft['text']})
        data=value.get('data',{})
        if value.get('errors') or not re.fullmatch('[0-9]{1,30}',str(data.get('id',''))):
            raise ValueError('X_POST_RESULT_UNVERIFIED')
        return {'id':str(data['id'])}

    def analytics(self,post_id):
        if not self.enabled or not self.token_provider or not re.fullmatch('[0-9]{1,30}',post_id):
            raise ValueError('ANALYTICS_NOT_CONFIGURED')
        token=self.token_provider()
        me=self._request('/2/users/me',token)
        if me.get('data',{}).get('username','').lower()!=(self.account or '').lower():
            raise ValueError('TOKEN_ACCOUNT_MISMATCH')
        value=self._request('/2/tweets/'+post_id+'?'+urlencode({'tweet.fields':'public_metrics'}),token)
        metrics=value.get('data',{}).get('public_metrics',{})
        # Unavailable fields remain null; profile and follow attribution cannot be inferred.
        return {'replies':metrics.get('reply_count'),'quotes':metrics.get('quote_count'),
                'profile_visits':None,'follow_conversions':None,'negative_signals':None}
