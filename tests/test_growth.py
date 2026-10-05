import json
from datetime import datetime,timedelta,timezone
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.request
import urllib.error

from sayelf_x_growth.service import XGrowth,METRICS
from sayelf_x_growth.gates import DIMENSIONS,content_payload
from sayelf_x_growth.manifest import CAPABILITIES,FORBIDDEN
from sayelf_x_growth.connector import OfflineConnector,OfficialXConnector
from sayelf_x_growth.adapter import Work2ContentAdapter
from sayelf_x_growth.web import make_server
from sayelf_agent_ops.runtime import Conflict,digest


class GrowthCase(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.service=XGrowth(self.root/'runtime.sqlite3')
        self.path=self.root/'source.txt'
        self.text='The local build passed 12 focused checks.'
        self.path.write_text(self.text,encoding='utf-8')
        self.e=self.service.evidence(self.path,self.text,'Public','tester')

    def tearDown(self):
        self.tmp.cleanup()

    def draft(self,classification='Public',kind='BUILD',trend=False):
        s=self.service.ingest({'kind':kind,'text':self.text,'classification':classification,
                              'evidence_ids':[self.e['id']],'trend':trend,
                              'claims':[{'text':self.text,'label':'Observation','evidence_id':self.e['id']}]})
        return self.service.prepare(s['id'],'OldGuyLab','2026-10-04')

    def review(self,d,score=90):
        return self.service.review(d['id'],'tester',{k:score for k in DIMENSIONS},
                      {k:True for k in ('claims_complete','evidence_checked','compliance_checked','original_work')})

    def approved(self,kind='BUILD',trend=False,mode='offline'):
        d=self.review(self.draft(kind=kind,trend=trend))
        self.service.run('OldGuyLab','2026-10-04')
        return self.service.decide(d['id'],'tester','APPROVE',mode)

    def test_manifest_reuses_registry(self):
        r=self.service.registry
        self.assertTrue('media.content-planner' in r.roles)
        self.assertEqual(set(CAPABILITIES),set(r.roles['x.growth-operator'].allowed_skills))
        self.assertFalse(set(FORBIDDEN)&set(r.skills))

    def test_empty_day(self):
        self.assertEqual(self.service.run('OldGuyLab','2026-10-04')['state'],'NO_POST_RECOMMENDED')

    def test_no_implicit_human_review(self):
        d=self.draft()
        self.assertEqual(self.service.run('OldGuyLab',d['day'])['recommended_ids'],[])

    def test_automatic_recommendation_not_approval(self):
        s=self.service.ingest({'kind':'BUILD','text':self.text,'classification':'Public','original_work':True,
                              'evidence_ids':[self.e['id']],
                              'claims':[{'text':self.text,'label':'Observation','evidence_id':self.e['id']}]})
        d=self.service.prepare(s['id'],'OldGuyLab','2026-10-04')
        self.assertIn(d['id'],self.service.run('OldGuyLab',d['day'])['visible_ids'])
        with self.assertRaises(Conflict):
            self.service.decide(d['id'],'tester','APPROVE')

    def test_cap_across_reruns(self):
        for i in range(5):
            self.review(self.draft(),95-i)
            self.service.run('OldGuyLab','2026-10-04')
        run=self.service.run('OldGuyLab','2026-10-04')
        self.assertEqual(len(run['recommended_ids']),2)
        again=XGrowth(self.root/'runtime.sqlite3')
        self.assertEqual(again.run('OldGuyLab','2026-10-04')['recommended_ids'],run['recommended_ids'])

    def test_low_quality_holds(self):
        d=self.review(self.draft(),79)
        self.assertEqual(d['gate']['state'],'HOLD')
        self.assertFalse(self.service.run('OldGuyLab',d['day'])['recommended_ids'])

    def test_high_score_cannot_override_nonpublic(self):
        d=self.review(self.draft('Internal'),100)
        self.assertEqual(d['gate']['state'],'BLOCKED')
        with self.assertRaises(Conflict):
            self.service.decide(d['id'],'tester','APPROVE')

    def test_missing_fact_evidence(self):
        d=self.draft()
        with self.service.runtime.transaction() as c:
            d['claims'][0]['evidence_id']='missing'
            self.service.runtime.put(c,'draft',d['id'],d)
        self.assertIn('FACT_EVIDENCE_MISSING',self.review(d,100)['gate']['reasons'])

    def test_changed_file_blocks_publication(self):
        d=self.approved()
        self.path.write_text('changed',encoding='utf-8')
        with self.assertRaises(Conflict):
            self.service.publish(d['id'],OfflineConnector())

    def test_current_review_digest(self):
        d=self.review(self.draft())
        with self.service.runtime.transaction() as c:
            d['text']+=' changed'
            self.service.runtime.put(c,'draft',d['id'],d)
        self.service.run('OldGuyLab',d['day'])
        self.assertIn('CURRENT_HUMAN_REVIEW_REQUIRED',self.service.snapshot()['draft'][0]['gate']['reasons'])

    def test_edit_invalidates_approval(self):
        d=self.approved()
        edited=self.service.decide(d['id'],'tester','EDIT',text=d['text']+'\nEdited',claims=d['claims'])
        self.assertEqual(edited['revision'],2)
        self.assertEqual(edited['review'],{})
        with self.assertRaises(Conflict):
            self.service.publish(d['id'],OfflineConnector())

    def test_rereview_invalidates_approval(self):
        d=self.approved()
        self.review(d)
        with self.assertRaises(Conflict):
            self.service.publish(d['id'],OfflineConnector())

    def test_edit_review_can_be_recommended_again(self):
        d=self.approved()
        d=self.service.decide(d['id'],'tester','EDIT',text=d['text']+'\nUpdated',claims=d['claims'])
        self.review(d)
        self.service.run('OldGuyLab',d['day'])
        self.assertEqual(self.service.decide(d['id'],'tester','APPROVE')['state'],'APPROVED')

    def test_mode_bound(self):
        d=self.approved()
        with self.assertRaises(Conflict):
            self.service.publish(d['id'],OfficialXConnector())

    def test_hold_and_resume(self):
        d=self.approved()
        self.service.decide(d['id'],'tester','HOLD')
        with self.assertRaises(Conflict):
            self.service.publish(d['id'],OfflineConnector())
        self.assertEqual(self.service.resume(d['id'])['state'],'PREPARED')

    def test_reject_not_recommended(self):
        d=self.approved()
        self.service.decide(d['id'],'tester','REJECT')
        self.assertFalse(self.service.run('OldGuyLab',d['day'])['visible_ids'])

    def test_trend_requires_approval(self):
        d=self.review(self.draft(trend=True))
        self.service.run('OldGuyLab',d['day'])
        with self.assertRaises(Conflict):
            self.service.publish(d['id'],OfflineConnector())
        self.service.decide(d['id'],'tester','APPROVE')
        self.assertEqual(self.service.publish(d['id'],OfflineConnector())['state'],'SIMULATED')

    def test_live_disabled_no_network(self):
        d=self.approved(mode='live')
        with self.assertRaisesRegex(ValueError,'OFFICIAL_X_NOT_CONFIGURED'):
            self.service.publish(d['id'],OfficialXConnector())
        self.assertEqual(self.service.snapshot()['draft'][0]['state'],'APPROVED')

    def test_forbidden_connector(self):
        d=self.approved()
        class Browser:
            mode='live'
        with self.assertRaisesRegex(Conflict,'CONNECTOR_FORBIDDEN'):
            self.service.publish(d['id'],Browser())

    def test_live_connector_cannot_claim_offline_mode(self):
        d=self.approved()
        connector=OfficialXConnector()
        connector.mode='offline'
        with self.assertRaisesRegex(Conflict,'CONNECTOR_MODE_TAMPERED'):
            self.service.publish(d['id'],connector)

    def test_official_metric_mapping_no_likes_or_fake_conversion(self):
        from unittest.mock import patch
        connector=OfficialXConnector('OldGuyLab',lambda:'test-token',True)
        with patch.object(connector,'_request',side_effect=[
            {'data':{'username':'OldGuyLab'}},
            {'data':{'public_metrics':{'reply_count':4,'quote_count':2,'like_count':999}}}]):
            metrics=connector.analytics('123')
        self.assertEqual(metrics['replies'],4)
        self.assertEqual(metrics['quotes'],2)
        self.assertIsNone(metrics['follow_conversions'])
        self.assertNotIn('likes',metrics)

    def test_official_connector_verifies_credential_account(self):
        from unittest.mock import patch
        d=self.approved(mode='live')
        connector=OfficialXConnector('OldGuyLab',lambda:'test-token',True)
        with patch.object(connector,'_request',return_value={'data':{'username':'OtherAccount'}}) as request:
            with self.assertRaisesRegex(Conflict,'PUBLICATION_OUTCOME_UNKNOWN'):
                self.service.publish(d['id'],connector)
        self.assertEqual(request.call_count,1)

    def test_no_double_publication(self):
        d=self.approved()
        self.service.publish(d['id'],OfflineConnector())
        with self.assertRaises(Conflict):
            self.service.publish(d['id'],OfflineConnector())
        self.assertEqual(len(self.service.snapshot()['publication']),1)

    def test_bad_postcheck_unknown_no_retry(self):
        d=self.approved()
        from unittest.mock import patch
        with patch.object(OfflineConnector,'create',return_value={'id':'bad'}):
            with self.assertRaisesRegex(Conflict,'PUBLICATION_OUTCOME_UNKNOWN'):
                self.service.publish(d['id'],OfflineConnector())
        self.assertEqual(self.service.snapshot()['draft'][0]['state'],'UNKNOWN')
        with self.assertRaises(Conflict):
            self.service.publish(d['id'],OfflineConnector())

    def test_schedule_early_block_and_cancel(self):
        d=self.approved()
        due=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()
        self.service.schedule(d['id'],due)
        with self.assertRaisesRegex(Conflict,'SCHEDULE_NOT_DUE'):
            self.service.publish(d['id'],OfflineConnector())
        self.service.decide(d['id'],'tester','HOLD')
        with self.service.runtime.transaction() as c:
            self.assertEqual(c.execute("SELECT state FROM tasks WHERE kind='publish'").fetchone()[0],'CANCELLED')

    def test_analytics_and_learning(self):
        d=self.approved()
        p=self.service.publish(d['id'],OfflineConnector())
        self.assertEqual(len(self.service.snapshot()['due_tasks']),0)
        base=datetime.fromisoformat(p['published_at'])
        metrics=dict(zip(METRICS,[3,2,None,None,1]))
        for h in (2,24,72):
            self.service.observe(p['id'],h,metrics,'offline test',(base+timedelta(hours=h)).isoformat())
        learning=self.service.learn(p['id'])
        self.assertTrue(learning['simulation'])
        self.assertEqual(learning['epistemic'],'Hypothesis')
        self.assertEqual(learning['status'],'UNVALIDATED')
        self.assertEqual(learning['negative_signal_action'],'human review')
        self.assertNotIn('likes',learning['metrics'])
        self.assertEqual(self.service.runtime.health()['pending_tasks'],0)

    def test_early_observation_rejected(self):
        p=self.service.publish(self.approved()['id'],OfflineConnector())
        with self.assertRaisesRegex(ValueError,'WINDOW_NOT_DUE'):
            self.service.observe(p['id'],2,{k:None for k in METRICS},'manual')

    def test_learning_requires_all_windows(self):
        p=self.service.publish(self.approved()['id'],OfflineConnector())
        with self.assertRaisesRegex(Conflict,'ALL_WINDOWS_REQUIRED'):
            self.service.learn(p['id'])

    def test_likes_not_accepted(self):
        with self.assertRaises(ValueError):
            self.service.observe('P',2,{'likes':999},'manual')

    def test_work2content_dedup_and_conflict(self):
        a=Work2ContentAdapter(self.service)
        event={'id':'1','source_id':'notebook','type':'Failure','text':self.text}
        self.assertEqual(a.ingest(event)['id'],a.ingest(event)['id'])
        with self.assertRaisesRegex(ValueError,'WORK_EVENT_CHANGED'):
            a.ingest({**event,'text':'changed source'})

    def test_work2content_bus_has_no_content_in_journal(self):
        a=Work2ContentAdapter(self.service)
        a.enqueue({'id':'w1','source_id':'notebook','type':'Result','text':self.text})
        self.service.runtime.deliver(a.consume)
        self.assertEqual(len(self.service.snapshot()['signal']),1)
        with self.service.runtime.transaction() as c:
            journal=' '.join(r[0] for r in c.execute('SELECT summary FROM events'))
        self.assertNotIn(self.text,journal)

    def test_secret_input_rejected(self):
        with self.assertRaisesRegex(ValueError,'SIGNAL_TOO_LARGE_OR_SECRET'):
            self.service.ingest({'kind':'BUILD','text':'access_token=secret1234567890'})

    def test_unknown_classification_blocks(self):
        self.assertEqual(self.review(self.draft('Unknown'))['gate']['state'],'BLOCKED')

    def test_no_fact_promotion_of_inference(self):
        d=self.draft()
        with self.service.runtime.transaction() as c:
            d['claims']=[{'text':self.text,'label':'Inference','basis':[]}]
            self.service.runtime.put(c,'draft',d['id'],d)
        self.assertIn('INFERENCE_BASIS_MISSING',self.review(d)['gate']['reasons'])

    def test_event_bus_delivery(self):
        seen=[]
        delivered=self.service.runtime.deliver(lambda row:seen.append(row['id']))
        self.assertGreater(delivered,0)
        self.assertEqual(self.service.runtime.deliver(lambda row:seen.append(row['id'])),0)

    def test_audit_no_raw_content(self):
        d=self.approved()
        with self.service.runtime.transaction() as c:
            rows=' '.join(row[0] for row in c.execute('SELECT summary FROM events'))
        self.assertNotIn(self.text,rows)
        self.assertNotIn(str(self.path),rows)

    def test_role_deactivation_blocks(self):
        self.service.registry.deactivate_role('x.growth-operator')
        with self.assertRaisesRegex(Conflict,'CAPABILITY_NOT_AUTHORIZED'):
            self.service.ingest({'kind':'BUILD','text':'test'})

    def test_foreign_runtime_database_untouched(self):
        import sqlite3
        from contextlib import closing
        from sayelf_agent_ops.runtime import LocalRuntime
        path=self.root/'foreign.sqlite3'
        with closing(sqlite3.connect(path)) as c:
            c.execute('CREATE TABLE private_data(value TEXT)')
        with self.assertRaisesRegex(Conflict,'FOREIGN_RUNTIME_DATABASE'):
            LocalRuntime(path)
        with closing(sqlite3.connect(path)) as c:
            self.assertEqual(c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall(),[('private_data',)])

    def test_all_composer_kinds_preserve_statement(self):
        for k in ('BUILD','DEMO','FAILURE','INSIGHT','HUMAN','QUOTE','THREAD'):
            self.assertIn(self.text,self.draft(kind=k)['text'])


class WebCase(unittest.TestCase):
    setUp=GrowthCase.setUp
    tearDown=GrowthCase.tearDown
    def test_loopback_csrf_and_read(self):
        server=make_server(self.service,0)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            with urllib.request.urlopen(base+'/') as r:
                html=r.read().decode()
            self.assertIn('X TODAY',html)
            csrf=html.split("const csrf='")[1].split("'")[0]
            with urllib.request.urlopen(base+'/api/today') as r:
                self.assertEqual(json.loads(r.read())['code'],0)
            body=json.dumps({'op':'run','account':'OldGuyLab','day':'2026-10-04'}).encode()
            request=urllib.request.Request(base+'/api/action',data=body,headers={'Content-Type':'application/json'})
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(request)
            self.assertEqual(error.exception.code,403)
            error.exception.close()
            request=urllib.request.Request(base+'/api/action',data=body,
                          headers={'Content-Type':'application/json','Origin':base,'X-CSRF-Token':csrf})
            with urllib.request.urlopen(request) as r:
                self.assertEqual(json.loads(r.read())['data']['state'],'NO_POST_RECOMMENDED')
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__=='__main__':
    unittest.main()
