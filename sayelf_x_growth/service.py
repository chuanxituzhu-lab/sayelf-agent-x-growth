from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
import re
import uuid

from sayelf_agent_ops.registry import build_default_registry
from sayelf_agent_ops.runtime import LocalRuntime, Conflict, digest, utcnow
from desktop.runtime.media_workflow import _hash
from .manifest import register, KINDS
from .models import Signal,Opportunity,Draft,Evidence,Publication,Observation,Learning
from .gates import inspect,content_payload,DIMENSIONS,SECRET,score_local

DAILY_TRANSITIONS = {'INBOX':{'EVALUATING'},'EVALUATING':{'REVIEW','NO_POST_RECOMMENDED'},
                     'REVIEW':{'EVALUATING'},'NO_POST_RECOMMENDED':{'EVALUATING'}}
METRICS = ('replies','quotes','profile_visits','follow_conversions','negative_signals')


def identifier(prefix):
    return prefix+'-'+uuid.uuid4().hex


def valid_day(value):
    date.fromisoformat(value)
    return value


class LocalComposer:
    """Local, model-free copy framing. It preserves source claims verbatim."""
    HOOK = {'BUILD':'Build notes:','DEMO':'Demo notes:','FAILURE':'From a setback:',
            'INSIGHT':'One thing I learned:','HUMAN':'Behind the build:',
            'QUOTE':'My take:','THREAD':'A short build log:'}
    def compose(self, signal, variant='NARRATIVE'):
        if variant not in {'NARRATIVE','QUESTION'}:
            raise ValueError('VARIANT_INVALID')
        if any('\u4e00'<=ch<='\u9fff' for ch in signal.text):
            hook={'BUILD':'开发记录：','DEMO':'Demo 记录：','FAILURE':'一次碰壁：',
                  'INSIGHT':'做完才发现：','HUMAN':'项目背后：','QUOTE':'我的看法：','THREAD':'一段开发记录：'}
            if variant=='NARRATIVE':
                return hook[signal.kind]+'\n\n'+signal.text+'\n\n你会先验证哪一步？'
            return '这件事让我想先确认一个问题：\n\n'+signal.text+'\n\n你会先核实哪项限制？'
        if variant=='NARRATIVE':
            return self.HOOK[signal.kind]+'\n\n'+signal.text+'\n\nWhat would you test next?'
        return 'One question from this work:\n\n'+signal.text+'\n\nWhich constraint would you verify first?'


class XGrowth:
    def __init__(self, database, composer=None):
        self.runtime = LocalRuntime(database)
        self.registry = register(build_default_registry())
        self.composer = composer or LocalComposer()

    def require(self, capability):
        role = self.registry.roles['x.growth-operator']
        if role.id not in self.registry.active_role_ids or capability not in role.allowed_skills:
            raise Conflict('CAPABILITY_NOT_AUTHORIZED')

    def evidence(self, path, excerpt, classification, verified_by):
        self.require('x.evidence.validate')
        source = Path(path).resolve()
        if not verified_by or classification not in {'Public','Internal','Sensitive','Restricted','Unknown'}:
            raise ValueError('EVIDENCE_ATTESTATION_REQUIRED')
        if Path(path).is_symlink() or not source.is_file() or source.stat().st_size>1024*1024:
            raise ValueError('EVIDENCE_FILE_INVALID')
        raw = source.read_bytes()
        if not excerpt or excerpt not in raw.decode('utf-8'):
            raise ValueError('EXCERPT_NOT_IN_SOURCE')
        e = asdict(Evidence(identifier('E'),str(source),_hash(raw),excerpt,classification,verified_by))
        with self.runtime.transaction() as c:
            self.runtime.put(c,'evidence',e['id'],e)
            self.runtime.event(c,'evidence',e['id'],{'sha256':e['sha256'],'classification':classification})
        return e

    def ingest(self, value):
        with self.runtime.transaction() as c:
            return self._ingest(c,value)

    def _ingest(self,c,value):
        self.require('x.signal.ingest')
        if value.get('kind') not in KINDS or not isinstance(value.get('text'),str) or not value['text'].strip():
            raise ValueError('SIGNAL_INVALID')
        if len(value['text'])>4000 or SECRET.search(value['text']):
            raise ValueError('SIGNAL_TOO_LARGE_OR_SECRET')
        signal = asdict(Signal(identifier('S'),value['kind'],value['text'],value.get('evidence_ids',[]),
                               value.get('classification','Unknown'),value.get('origin','manual'),
                               value.get('trend',False),value.get('claims',[]),value.get('original_work',False)))
        if type(signal['trend']) is not bool or type(signal['original_work']) is not bool:
            raise ValueError('TREND_FLAG_INVALID')
        self.runtime.put(c,'signal',signal['id'],signal)
        self.runtime.event(c,'signal',signal['id'],{'origin_digest':digest(signal['origin']),'kind':signal['kind']})
        return signal

    def prepare(self, signal_id, account, day, variant='NARRATIVE', matched_trends=None):
        self.require('x.opportunity.evaluate')
        self.require('x.publish.draft')
        valid_day(day)
        if not re.fullmatch('[A-Za-z0-9_]{1,15}',account):
            raise ValueError('ACCOUNT_INVALID')
        if variant not in {'NARRATIVE','QUESTION'}:
            raise ValueError('VARIANT_INVALID')
        matched_trends = list(dict.fromkeys(matched_trends or []))[:3]
        with self.runtime.transaction() as c:
            signal = self.runtime.get(c,'signal',signal_id)
            if not signal:
                raise ValueError('SIGNAL_UNKNOWN')
            self.require('x.content.'+signal['kind'].lower())
            existing = next((d for d in self.runtime.list(c,'draft') if
                             (d['signal_id'],d['account'],d['day'],d.get('variant','NARRATIVE'))==
                             (signal_id,account,day,variant)),None)
            if existing:
                return existing
            # Empty evidence may be acceptable for an explicitly labelled personal opinion,
            # but no unlabelled factual assertion can enter recommendation.
            decision = ('IGNORE' if len(signal['text'].strip())<10 else
                        ('DRAFT_NOW' if signal['claims'] else 'HOLD'))
            opportunity = asdict(Opportunity(identifier('O'),signal_id,decision,
                                 'Real-work source supplied' if decision=='DRAFT_NOW' else 'Claim labels needed'))
            self.runtime.put(c,'opportunity',opportunity['id'],opportunity)
            if decision=='IGNORE':
                return opportunity
            text = self.composer.compose(Signal(**signal),variant)
            d = asdict(Draft(identifier('D'),signal_id,account,day,signal['kind'],text,
                            signal['claims'],signal['evidence_ids'],signal['classification'],{}, {},
                            signal['trend'] or bool(matched_trends),variant=variant,matched_trends=matched_trends))
            covered=' '.join(claim.get('text','') for claim in signal['claims'])
            # Composer adds only structural framing and a question. Source assertions must be
            # exhaustively labelled; this check is structural, human semantic review is separate.
            d['review']={'actor':'local-structural-gate','content_digest':digest(content_payload(d)),
                         'claims_complete':covered==signal['text'],'evidence_checked':True,
                         'compliance_checked':signal['classification']=='Public',
                         'original_work':signal['original_work'],
                         'quality_source':'local structural heuristic v0.3; semantic quality unvalidated'}
            duplicate=any(old['text']==text for old in self.runtime.list(c,'draft'))
            d['scores']=score_local(d,duplicate)
            self.runtime.put(c,'draft',d['id'],d)
            self.runtime.event(c,'draft',d['id'],{'revision':1,'digest':digest(content_payload(d))})
            return d

    def _gate(self,c,d,require_human=False):
        self.require('x.evidence.validate')
        self.require('x.quality.score')
        return inspect(d,{e['id']:e for e in self.runtime.list(c,'evidence')},require_human)

    def review(self, draft_id, actor, scores, attestations):
        with self.runtime.transaction() as c:
            d = self._draft(c,draft_id)
            if d['state'] in {'PUBLISHED','SIMULATED','PUBLISHING','UNKNOWN'}:
                raise Conflict('DRAFT_LOCKED')
            if set(scores)!=set(DIMENSIONS) or not all(type(v) is int and 0<=v<=100 for v in scores.values()):
                raise ValueError('QUALITY_RUBRIC_INVALID')
            d['scores'] = scores
            d['review'] = {**{k:attestations.get(k) is True for k in
                             ('claims_complete','evidence_checked','compliance_checked','original_work')},
                           'actor':actor,'content_digest':digest(content_payload(d))}
            if not actor:
                raise ValueError('ACTOR_REQUIRED')
            gate = self._gate(c,d)
            if d['state']=='APPROVED':
                d['state']='PREPARED'
                c.execute('DELETE FROM approvals WHERE subject=?',(draft_id,))
            d['gate'] = gate
            self.runtime.put(c,'draft',draft_id,d)
            self.runtime.event(c,'review',draft_id,{'state':gate['state'],'score':gate['score']})
            return d

    def _draft(self,c,id):
        d = self.runtime.get(c,'draft',id)
        if not d:
            raise ValueError('DRAFT_UNKNOWN')
        return d

    def run(self,account,day):
        valid_day(day)
        run_id = account+':'+day
        with self.runtime.transaction() as c:
            run = self.runtime.get(c,'daily',run_id) or {'id':run_id,'state':'INBOX','recommended_ids':[]}
            self.runtime.transition(c,'daily',run,'EVALUATING',DAILY_TRANSITIONS)
            drafts = [d for d in self.runtime.list(c,'draft') if d['account']==account and d['day']==day]
            ready = []
            for d in drafts:
                gate = self._gate(c,d)
                d['gate'] = gate
                self.runtime.put(c,'draft',d['id'],d)
                if gate['state']=='PASS' and d['state'] in {'PREPARED','RECOMMENDED','APPROVED'}:
                    ready.append(d)
            ready.sort(key=lambda d:(-d['gate']['score'],d['id']))
            for d in ready:
                if d['id'] not in run['recommended_ids'] and len(run['recommended_ids'])<2:
                    run['recommended_ids'].append(d['id'])
                if d['id'] in run['recommended_ids'] and d['state']=='PREPARED':
                    d['state']='RECOMMENDED'
                    self.runtime.put(c,'draft',d['id'],d)
            visible = [d['id'] for d in ready if d['id'] in run['recommended_ids']]
            run['visible_ids'] = visible
            self.runtime.transition(c,'daily',run,'REVIEW' if visible else 'NO_POST_RECOMMENDED',DAILY_TRANSITIONS)
            return run

    def scope(self,d,mode):
        if mode not in {'live','offline'}:
            raise ValueError('MODE_INVALID')
        return {'tool':'official-x-api.create-post','endpoint':'https://api.x.com/2/tweets',
                'account':d['account'],'mode':mode,'draft_id':d['id'],'revision':d['revision']}

    def decide(self,draft_id,actor,decision,mode='offline',text=None,claims=None):
        if decision not in {'APPROVE','EDIT','REJECT','HOLD'} or not actor:
            raise ValueError('DECISION_INVALID')
        with self.runtime.transaction() as c:
            d = self._draft(c,draft_id)
            if d['state'] in {'PUBLISHED','SIMULATED','PUBLISHING','UNKNOWN'}:
                raise Conflict('DRAFT_LOCKED')
            if decision=='APPROVE':
                if d['state'] not in {'RECOMMENDED','APPROVED'} or self._gate(c,d,require_human=True)['state']!='PASS':
                    raise Conflict('APPROVAL_GATE_BLOCKED')
                d['state']='APPROVED'
            elif decision=='EDIT':
                if not isinstance(text,str) or not text.strip() or len(text)>4000 or SECRET.search(text):
                    raise ValueError('EDIT_INVALID')
                d.update(text=text,claims=claims or [],revision=d['revision']+1,state='PREPARED',review={},scores={})
                c.execute("UPDATE tasks SET state='CANCELLED' WHERE subject=? AND kind='publish'",(draft_id,))
            else:
                d['state']='REJECTED' if decision=='REJECT' else 'HELD'
                c.execute("UPDATE tasks SET state='CANCELLED' WHERE subject=? AND kind='publish'",(draft_id,))
            self.runtime.approve(c,draft_id,content_payload(d),actor,decision,self.scope(d,mode))
            self.runtime.put(c,'draft',draft_id,d)
            return d

    def resume(self,draft_id):
        with self.runtime.transaction() as c:
            d = self._draft(c,draft_id)
            if d['state']!='HELD':
                raise Conflict('NOT_HELD')
            d['state']='PREPARED'
            c.execute('DELETE FROM approvals WHERE subject=?',(draft_id,))
            self.runtime.put(c,'draft',draft_id,d)
            return d

    def schedule(self,draft_id,due_at,mode='offline'):
        self.require('x.publish.schedule')
        stamp=datetime.fromisoformat(due_at)
        if stamp.tzinfo is None or stamp.astimezone(timezone.utc)<=datetime.now(timezone.utc):
            raise ValueError('FUTURE_TIME_REQUIRED')
        with self.runtime.transaction() as c:
            d=self._draft(c,draft_id)
            if d['state']!='APPROVED' or not self.runtime.authorized(c,draft_id,content_payload(d),self.scope(d,mode)):
                raise Conflict('EXACT_APPROVAL_REQUIRED')
            self.runtime.schedule(c,draft_id+':publish:'+str(d['revision']),'publish',draft_id,due_at)
            self.runtime.event(c,'scheduled',draft_id,{'revision':d['revision'],'due_at':due_at})
            return {'state':'SCHEDULED','due_at':due_at,'execution':'explicit due-task invocation required'}

    def publish(self,draft_id,connector):
        self.require('x.publish.execute')
        # Only our fixed connector types can be used by the write path.
        from .connector import OfficialXConnector,OfflineConnector
        if type(connector) not in {OfficialXConnector,OfflineConnector}:
            raise Conflict('CONNECTOR_FORBIDDEN')
        expected_mode='live' if type(connector) is OfficialXConnector else 'offline'
        if connector.mode!=expected_mode:
            raise Conflict('CONNECTOR_MODE_TAMPERED')
        with self.runtime.transaction() as c:
            d=self._draft(c,draft_id)
            scope=self.scope(d,connector.mode)
            if d['state']!='APPROVED' or self._gate(c,d,require_human=True)['state']!='PASS':
                raise Conflict('PUBLICATION_GATE_BLOCKED')
            if not self.runtime.authorized(c,draft_id,content_payload(d),scope):
                raise Conflict('EXACT_APPROVAL_REQUIRED')
            connector.preflight(d)
            pending=c.execute("SELECT due_at FROM tasks WHERE subject=? AND kind='publish' AND state='PENDING'",(draft_id,)).fetchone()
            if pending and pending[0]>utcnow():
                raise Conflict('SCHEDULE_NOT_DUE')
            publication=asdict(Publication(identifier('P'),draft_id,'PUBLISHING',digest(content_payload(d))))
            d['state']='PUBLISHING'
            self.runtime.put(c,'draft',draft_id,d)
            self.runtime.put(c,'publication',publication['id'],publication)
            self.runtime.event(c,'tool-precheck',publication['id'],{'permission':'approved','scope':scope,
                                'digest':publication['content_digest'],'classification':'Public'})
        # Reserve durably before a network side effect. Unknown outcome never retries automatically.
        try:
            result=connector.create(d)
            if not isinstance(result,dict) or not re.fullmatch('[0-9]{1,30}',str(result.get('id',''))):
                raise ValueError('CONNECTOR_OUTPUT_INVALID')
        except Exception:
            with self.runtime.transaction() as c:
                publication['state']='UNKNOWN'
                d['state']='UNKNOWN'
                self.runtime.put(c,'publication',publication['id'],publication)
                self.runtime.put(c,'draft',draft_id,d)
                self.runtime.event(c,'tool-postcheck',publication['id'],{'state':'UNKNOWN','next_check':'manual reconciliation'})
            raise Conflict('PUBLICATION_OUTCOME_UNKNOWN') from None
        with self.runtime.transaction() as c:
            publication.update(state='PUBLISHED' if connector.mode=='live' else 'SIMULATED',
                               post_id=str(result['id']),published_at=utcnow())
            d['state']=publication['state']
            self.runtime.put(c,'publication',publication['id'],publication)
            self.runtime.put(c,'draft',draft_id,d)
            c.execute("UPDATE tasks SET state='DONE' WHERE subject=? AND kind='publish' AND state='PENDING'",(draft_id,))
            published=datetime.fromisoformat(publication['published_at'])
            for hours in (2,24,72):
                self.runtime.schedule(c,publication['id']+':'+str(hours),'analytics',publication['id'],
                                      (published+timedelta(hours=hours)).isoformat())
            self.runtime.event(c,'tool-postcheck',publication['id'],{'state':publication['state'],'post_id':publication['post_id'],
                              'next_check':'2h/24h/72h','evidence':publication['content_digest']})
            return publication

    def observe(self,publication_id,hours,metrics,source,observed_at=None):
        self.require('x.analytics.collect')
        if hours not in (2,24,72) or set(metrics)!=set(METRICS) or not source:
            raise ValueError('OBSERVATION_INVALID')
        if any(v is not None and (type(v) is not int or v<0) for v in metrics.values()):
            raise ValueError('METRICS_INVALID')
        stamp=datetime.fromisoformat(observed_at or utcnow())
        if stamp.tzinfo is None:
            raise ValueError('TIMEZONE_REQUIRED')
        with self.runtime.transaction() as c:
            p=self.runtime.get(c,'publication',publication_id)
            if not p or p['state'] not in {'PUBLISHED','SIMULATED'}:
                raise Conflict('PUBLICATION_NOT_CONFIRMED')
            if p['state']=='PUBLISHED' and stamp>datetime.now(timezone.utc)+timedelta(minutes=1):
                raise ValueError('FUTURE_OBSERVATION_FORBIDDEN')
            due=datetime.fromisoformat(p['published_at'])+timedelta(hours=hours)
            if stamp<due:
                raise ValueError('WINDOW_NOT_DUE')
            id=publication_id+':'+str(hours)
            if self.runtime.get(c,'observation',id):
                raise Conflict('OBSERVATION_ALREADY_RECORDED')
            o=asdict(Observation(id,publication_id,hours,metrics,source,stamp.isoformat()))
            o['simulation']=p['state']=='SIMULATED'
            o['late_by_seconds']=int((stamp-due).total_seconds())
            self.runtime.put(c,'observation',id,o)
            c.execute("UPDATE tasks SET state='DONE' WHERE id=?",(id,))
            self.runtime.event(c,'observation',id,{'window':hours,'simulation':o['simulation'],
                              'available_metrics':sum(v is not None for v in metrics.values())})
            return o

    def collect_analytics(self,publication_id,hours,connector):
        self.require('x.analytics.collect')
        from .connector import OfficialXConnector
        if type(connector) is not OfficialXConnector or connector.mode!='live':
            raise Conflict('ANALYTICS_CONNECTOR_FORBIDDEN')
        with self.runtime.transaction() as c:
            p=self.runtime.get(c,'publication',publication_id)
            if not p or p['state']!='PUBLISHED' or hours not in (2,24,72):
                raise Conflict('LIVE_PUBLICATION_REQUIRED')
            d=self._draft(c,p['draft_id'])
            connector.preflight(d)
            if datetime.now(timezone.utc)<datetime.fromisoformat(p['published_at'])+timedelta(hours=hours):
                raise Conflict('WINDOW_NOT_DUE')
        try:
            metrics=connector.analytics(p['post_id'])
        except Exception:
            raise Conflict('ANALYTICS_UNAVAILABLE') from None
        return self.observe(publication_id,hours,metrics,'official-x-api public_metrics')

    def learn(self,publication_id):
        self.require('x.learning.evaluate')
        with self.runtime.transaction() as c:
            observations=[o for o in self.runtime.list(c,'observation') if o['publication_id']==publication_id]
            if {o['window_hours'] for o in observations}!={2,24,72}:
                raise Conflict('ALL_WINDOWS_REQUIRED')
            last=next(o for o in observations if o['window_hours']==72)
            m=last['metrics']
            hypothesis=('Investigate whether the demonstrated mechanism invites useful conversation; compare against a baseline.'
                        if m['replies'] is not None and m['quotes'] is not None
                        else 'Conversation metrics unavailable; no mechanism conclusion can be drawn.')
            l=asdict(Learning(publication_id,publication_id,hypothesis,[o['id'] for o in observations]))
            l['metrics']=m
            l['simulation']=last['simulation']
            l['next_experiment']='Test the mechanism on new original work; never rewrite a previous hit.'
            l['negative_signal_action']='human review' if (m['negative_signals'] or 0)>0 else 'no automatic promotion'
            l['conversion_status']='unavailable' if m['follow_conversions'] is None else 'observed, attribution unverified'
            self.runtime.put(c,'learning',l['id'],l)
            self.runtime.event(c,'learning',l['id'],{'epistemic':'Hypothesis','status':'UNVALIDATED'})
            return l

    def conversation(self,draft_id):
        self.require('x.conversation.recommend')
        with self.runtime.transaction() as c:
            d=self._draft(c,draft_id)
            return {'state':'HUMAN_ACTION_ONLY','prompt':'Ask readers what they would test next.',
                    'draft_id':d['id'],'automatic_action':False}

    def snapshot(self):
        with self.runtime.transaction() as c:
            data={name:self.runtime.list(c,name) for name in
                  ('signal','opportunity','draft','evidence','daily','publication','observation','learning','automation')}
            for d in data['draft']:
                d['gate']=self._gate(c,d)
        data['due_tasks']=self.runtime.due()
        data['health']=self.runtime.health()
        return data
