"""Explicit Work2Content event intake, reusable with the shared outbox consumer."""
import json
import sqlite3
from pathlib import Path
from sayelf_agent_ops.runtime import digest

EVENT_KINDS={'Failure':'FAILURE','Breakthrough':'BUILD','Demo':'DEMO','Result':'INSIGHT'}


class Work2ContentAdapter:
    def __init__(self,service):
        self.service=service

    def ingest(self,event):
        if event.get('type') not in EVENT_KINDS or not event.get('id') or not event.get('source_id'):
            raise ValueError('WORK_EVENT_INVALID')
        key=digest({'source':event['source_id'],'id':event['id']})
        fingerprint=digest(event)
        runtime=self.service.runtime
        # Dedupe and signal write in a single transaction, including source conflict detection.
        with runtime.transaction() as c:
            existing=runtime.get(c,'work2content',key)
            if existing:
                if existing['digest']!=fingerprint:
                    raise ValueError('WORK_EVENT_CHANGED')
                return runtime.get(c,'signal',existing['signal_id'])
            signal=self.service._ingest(c,{'kind':EVENT_KINDS[event['type']],
                                    'text':event['text'],'claims':event.get('claims',[]),
                                    'evidence_ids':event.get('evidence_ids',[]),
                                    'classification':event.get('classification','Unknown'),
                                    'original_work':event.get('original_work',False),
                                    'origin':'work2content:'+event['source_id']})
            runtime.put(c,'work2content',key,{'id':key,'signal_id':signal['id'],'digest':fingerprint})
        return signal

    def consume(self,row):
        if row['topic']=='work2content':
            reference=json.loads(row['summary'])['event_ref']
            with self.service.runtime.transaction() as c:
                event=self.service.runtime.get(c,'work-event',reference)
            if not event:
                raise ValueError('WORK_EVENT_REFERENCE_MISSING')
            self.ingest(event['payload'])

    def consume_local_outbox(self):
        with self.service.runtime.transaction() as c:
            rows = [dict(r) for r in c.execute(
                "SELECT * FROM events WHERE topic='work2content' AND delivered=0 ORDER BY id")]
        for row in rows:
            self.consume(row)
            with self.service.runtime.transaction() as c:
                c.execute('UPDATE events SET delivered=1 WHERE id=?',(row['id'],))
        return len(rows)

    def consume_external_outbox(self, database):
        """Read only the shared-runtime Work2Content outbox; never scan desktop workflow logs."""
        source = Path(database).resolve()
        if not source.is_file() or source == self.service.runtime.path:
            raise ValueError('AGENT_OPS_SOURCE_UNAVAILABLE')
        uri = source.as_uri() + '?mode=ro'
        try:
            connection = sqlite3.connect(uri, uri=True, timeout=5)
            connection.row_factory = sqlite3.Row
            with connection:
                tables = {row[0] for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")}
                if not {'runtime_metadata','records','events'} <= tables:
                    raise ValueError('AGENT_OPS_SOURCE_UNSUPPORTED')
                metadata = dict(connection.execute('SELECT key,value FROM runtime_metadata'))
                if metadata != {'app':'sayelf.shared-runtime','schema':'1'}:
                    raise ValueError('AGENT_OPS_SOURCE_UNSUPPORTED')
                rows = connection.execute(
                    "SELECT id,summary FROM events WHERE topic='work2content' AND delivered=0 ORDER BY id LIMIT 1000").fetchall()
                imported = 0
                for row in rows:
                    try:
                        reference = json.loads(row['summary'])['event_ref']
                        record = connection.execute(
                            "SELECT payload FROM records WHERE namespace='work-event' AND id=?",
                            (reference,)).fetchone()
                        if not record:
                            continue
                        event = json.loads(record['payload'])['payload']
                    except (ValueError, KeyError, TypeError):
                        continue
                    self.ingest(event)  # target-side dedupe makes redelivery safe
                    imported += 1
                return {'state':'CONNECTED','imported':imported}
        except sqlite3.Error as error:
            raise ValueError('AGENT_OPS_SOURCE_UNAVAILABLE') from error
        finally:
            if 'connection' in locals():
                connection.close()

    def enqueue(self,event):
        if event.get('type') not in EVENT_KINDS or not event.get('id') or not event.get('source_id'):
            raise ValueError('WORK_EVENT_INVALID')
        reference=digest(event)
        with self.service.runtime.transaction() as c:
            if not self.service.runtime.get(c,'work-event',reference):
                self.service.runtime.put(c,'work-event',reference,{'id':reference,'payload':event})
                self.service.runtime.event(c,'work2content',reference,{'event_ref':reference})
        return reference
