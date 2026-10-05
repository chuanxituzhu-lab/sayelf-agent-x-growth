"""Local daily preparation; this entry point never publishes."""
import argparse
from datetime import datetime, timedelta, timezone
import os
import re
from .adapter import Work2ContentAdapter
from .trends import OfficialXTrendsProvider, REGIONS, match_trends


def generate(service, account, day, region='Tokyo', provider=None):
    from .service import valid_day
    valid_day(day)
    if not re.fullmatch('[A-Za-z0-9_]{1,15}',account):
        raise ValueError('ACCOUNT_INVALID')
    if region not in REGIONS:
        raise ValueError('TREND_REGION_INVALID')
    adapter = Work2ContentAdapter(service)
    adapter.consume_local_outbox()
    source_status = {'state':'NOT_CONFIGURED','imported':0}
    source_path = os.environ.get('SAYELF_AGENT_OPS_EVENT_DB')
    if source_path:
        try:
            source_status = adapter.consume_external_outbox(source_path)
        except ValueError as error:
            source_status = {'state':str(error),'imported':0}
    with service.runtime.transaction() as c:
        context = service.runtime.get(c,'trend-context',region)
    fresh = False
    if context and context.get('state') == 'READY':
        try:
            age = datetime.now(timezone.utc)-datetime.fromisoformat(context['observed_at'])
            fresh = timedelta(0) <= age < timedelta(hours=4)
        except (ValueError,TypeError,KeyError):
            fresh = False
    if not fresh:
        try:
            context = (provider or OfficialXTrendsProvider()).fetch(region)
        except ValueError as error:
            context = {'state':str(error),'region':region,'names':[]}
        with service.runtime.transaction() as c:
            service.runtime.put(c,'trend-context',region,context)
    key = account+':'+day
    with service.runtime.transaction() as c:
        selected = service.runtime.get(c,'daily-source',key)
        consumed = {s['signal_id'] for s in service.runtime.list(c,'daily-source') if s['account']==account}
        drafts = service.runtime.list(c,'draft')
        signals = []
        for signal in service.runtime.list(c,'signal'):
            owners = {d['account'] for d in drafts if d['signal_id']==signal['id']}
            if signal['id'] in consumed or (owners and account not in owners):
                continue
            if signal.get('created_at'):
                try:
                    if datetime.now(timezone.utc)-datetime.fromisoformat(signal['created_at']) > timedelta(days=7):
                        continue
                except (ValueError,TypeError):
                    continue
            signals.append(signal)
    if not selected and signals:
        signals.sort(key=lambda s:s.get('created_at',''),reverse=True)
        # Match only literal overlap; trend context is never inserted as a factual claim.
        signals.sort(key=lambda s:len(match_trends(s['text'],context)),reverse=True)
        signal = signals[0]
        matches = match_trends(signal['text'],context)
        drafts = [service.prepare(signal['id'],account,day,v,matches) for v in ('NARRATIVE','QUESTION')]
        selected = {'id':key,'account':account,'signal_id':signal['id'],
                    'draft_ids':[d['id'] for d in drafts if 'account' in d]}
        with service.runtime.transaction() as c:
            service.runtime.put(c,'daily-source',key,selected)
    run = service.run(account,day)
    status = {'id':key,'account':account,'day':day,'updated_at':datetime.now(timezone.utc).isoformat(),
              'state':run['state'],'draft_ids':selected['draft_ids'] if selected else [],
              'source_state':'AVAILABLE' if selected else 'NO_FRESH_WORK',
              'agent_ops':source_status,'trends':context,
              'composer':'local source-preserving framing; no model connected'}
    with service.runtime.transaction() as c:
        service.runtime.put(c,'automation',key,status)
    return status


def main():
    from .service import XGrowth
    parser = argparse.ArgumentParser()
    parser.add_argument('--database',required=True)
    parser.add_argument('--account',default='OldGuyLab')
    parser.add_argument('--region',choices=REGIONS,default='Tokyo')
    args = parser.parse_args()
    day = datetime.now(timezone(timedelta(hours=9))).date().isoformat()
    result = generate(XGrowth(args.database),args.account,day,args.region)
    print(result['state']+'; candidates='+str(len(result['draft_ids'])))


if __name__ == '__main__':
    main()
