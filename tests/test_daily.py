import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from sayelf_x_growth.service import XGrowth
from sayelf_x_growth.daily import generate
from sayelf_x_growth.adapter import Work2ContentAdapter
from sayelf_x_growth.trends import OfficialXTrendsProvider
from sayelf_agent_ops.runtime import Conflict


class DailyCase(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.service=XGrowth(Path(self.tmp.name)/'x.sqlite3')
        self.provider=MagicMock()
        self.provider.fetch.return_value={'state':'READY','region':'Tokyo','names':['AI'],
            'observed_at':datetime.now(timezone.utc).isoformat(),'source':'https://api.x.com/2/trends/by/woeid/1118370'}

    def tearDown(self):
        self.tmp.cleanup()

    def source(self,classification='Public'):
        text='I think AI work needs 12 focused checks.'
        return self.service.ingest({'kind':'BUILD','text':text,'classification':classification,
            'original_work':True,'claims':[{'label':'Opinion','text':text}]})

    def test_daily_two_choices_idempotent_and_no_approval(self):
        self.source()
        with patch.dict(os.environ,{'SAYELF_AGENT_OPS_EVENT_DB':''}):
            first=generate(self.service,'OldGuyLab','2026-10-05',provider=self.provider)
            again=generate(self.service,'OldGuyLab','2026-10-05',provider=self.provider)
        self.assertEqual(first['draft_ids'],again['draft_ids'])
        drafts=self.service.snapshot()['draft']
        self.assertEqual({d['variant'] for d in drafts},{'NARRATIVE','QUESTION'})
        self.assertEqual(len({d['text'] for d in drafts}),2)
        self.assertEqual(len(self.service.snapshot()['daily'][0]['visible_ids']),2)
        self.assertTrue(all(d['matched_trends']==['AI'] for d in drafts))
        with self.assertRaises(Conflict):
            self.service.decide(drafts[0]['id'],'tester','APPROVE')
        tomorrow=generate(self.service,'OldGuyLab','2026-10-06',provider=self.provider)
        self.assertEqual(tomorrow['source_state'],'NO_FRESH_WORK')

    def test_internal_choices_stay_blocked(self):
        self.source('Internal')
        result=generate(self.service,'OldGuyLab','2026-10-05',provider=self.provider)
        self.assertEqual(len(result['draft_ids']),2)
        self.assertEqual(result['state'],'NO_POST_RECOMMENDED')
        self.assertTrue(all(d['gate']['state']=='BLOCKED' for d in self.service.snapshot()['draft']))

    def test_other_account_source_is_not_reused(self):
        signal=self.source()
        self.service.prepare(signal['id'],'QA','2026-10-05')
        result=generate(self.service,'OldGuyLab','2026-10-05',provider=self.provider)
        self.assertEqual(result['draft_ids'],[])

    def test_readonly_external_outbox(self):
        upstream=XGrowth(Path(self.tmp.name)/'ops.sqlite3')
        event={'id':'work-1','source_id':'agent-ops','type':'Result','text':'A local result passed 12 checks.',
               'classification':'Internal','original_work':True,'claims':[]}
        Work2ContentAdapter(upstream).enqueue(event)
        before=upstream.runtime.path.read_bytes()
        adapter=Work2ContentAdapter(self.service)
        adapter.consume_external_outbox(upstream.runtime.path)
        adapter.consume_external_outbox(upstream.runtime.path)
        self.assertEqual(len(self.service.snapshot()['signal']),1)
        self.assertEqual(before,upstream.runtime.path.read_bytes())

    def test_daily_consumer_does_not_ack_other_topics(self):
        self.source()
        generate(self.service,'OldGuyLab','2026-10-05',provider=self.provider)
        with self.service.runtime.transaction() as c:
            self.assertGreater(c.execute("SELECT count(*) FROM events WHERE topic='signal' AND delivered=0").fetchone()[0],0)

    def test_official_trends_fixed_get_and_no_token_no_network(self):
        provider=OfficialXTrendsProvider('')
        with patch.object(provider.opener,'open') as opened:
            with self.assertRaisesRegex(ValueError,'TRENDS_NOT_CONFIGURED'):
                provider.fetch()
            opened.assert_not_called()
        provider=OfficialXTrendsProvider('mock-token')
        response=MagicMock()
        response.__enter__.return_value.read.return_value=json.dumps({'data':[{'trend_name':'AI'}]}).encode()
        with patch.object(provider.opener,'open',return_value=response) as opened:
            self.assertEqual(provider.fetch('Worldwide')['names'],['AI'])
            request=opened.call_args.args[0]
            self.assertEqual(request.full_url,'https://api.x.com/2/trends/by/woeid/1')
            self.assertEqual(request.get_method(),'GET')


if __name__=='__main__':
    unittest.main()
