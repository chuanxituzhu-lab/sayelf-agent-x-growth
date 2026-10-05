"""Loopback X TODAY. Offline publication only; live API is never enabled by UI."""
import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler,HTTPServer
import json
from pathlib import Path
import secrets
from urllib.parse import urlsplit

from .service import XGrowth
from .connector import OfflineConnector
from .adapter import Work2ContentAdapter


def make_server(service,port=8765):
    token=secrets.token_urlsafe(32)
    html=Path(__file__).with_name('today.html').read_text(encoding='utf-8')
    logo=Path(__file__).parents[1].joinpath('assets','sayelf-logo.png').read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):
            pass  # No raw input, URL, credentials or payload in HTTP logs.

        def allowed_host(self):
            return self.headers.get('Host')==f'127.0.0.1:{self.server.server_port}'

        def send(self,code,value,content_type='application/json'):
            if content_type=='application/json':
                body=json.dumps(value,ensure_ascii=False).encode()
            elif isinstance(value,bytes):
                body=value
            else:
                body=value.encode()
            self.send_response(code)
            charset='; charset=utf-8' if content_type in ('application/json','text/html') else ''
            self.send_header('Content-Type',content_type+charset)
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('X-Frame-Options','DENY')
            self.send_header('Content-Security-Policy',"default-src 'none'; script-src 'nonce-"+token+"'; style-src 'unsafe-inline'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not self.allowed_host():
                return self.send(403,{'code':1,'msg':'HOST_DENIED','data':{}})
            if self.path=='/':
                return self.send(200,html.replace('__TOKEN__',token),'text/html')
            if self.path=='/assets/sayelf-logo.png':
                return self.send(200,logo,'image/png')
            if self.path=='/api/today':
                return self.send(200,{'code':0,'msg':'ok','data':service.snapshot()})
            self.send(404,{'code':1,'msg':'NOT_FOUND','data':{}})

        def do_POST(self):
            origin=f'http://127.0.0.1:{self.server.server_port}'
            if (not self.allowed_host() or self.headers.get('Origin')!=origin
                    or self.headers.get('X-CSRF-Token')!=token):
                return self.send(403,{'code':1,'msg':'ORIGIN_OR_SESSION_DENIED','data':{}})
            if self.path!='/api/action':
                return self.send(404,{'code':1,'msg':'NOT_FOUND','data':{}})
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=32768 or self.headers.get('Content-Type')!='application/json':
                    raise ValueError('REQUEST_INVALID')
                value=json.loads(self.rfile.read(length))
                op=value['op']
                if op=='intake':
                    signal=service.ingest(value['signal'])
                    result=service.prepare(signal['id'],value['account'],value['day'])
                elif op=='evidence':
                    result=service.evidence(value['path'],value['excerpt'],value['classification'],value['actor'])
                elif op=='run':
                    from .daily import generate
                    result=generate(service,value['account'],value['day'],value.get('region','Tokyo'))
                elif op=='review':
                    result=service.review(value['id'],value['actor'],value['scores'],value['attestations'])
                elif op=='decision':
                    # UI approval can authorize only offline mode.
                    result=service.decide(value['id'],value['actor'],value['decision'],'offline',
                                          value.get('text'),value.get('claims'))
                elif op=='resume':
                    result=service.resume(value['id'])
                elif op=='publish':
                    result=service.publish(value['id'],OfflineConnector())
                elif op=='schedule':
                    result=service.schedule(value['id'],value['due_at'],'offline')
                elif op=='due':
                    result=[]
                    for task in service.runtime.due():
                        if task['kind']=='publish':
                            result.append(service.publish(task['subject'],OfflineConnector()))
                elif op=='observe':
                    result=service.observe(value['id'],value['hours'],value['metrics'],value['source'],value.get('observed_at'))
                elif op=='learn':
                    result=service.learn(value['id'])
                elif op=='work2content':
                    signal=Work2ContentAdapter(service).ingest(value['event'])
                    result=service.prepare(signal['id'],value['account'],value['day'])
                else:
                    raise ValueError('ACTION_UNKNOWN')
                self.send(200,{'code':0,'msg':'ok','data':result})
            except (ValueError,KeyError,TypeError) as error:
                # Emit only our enum-style error code; source text and exception details are suppressed.
                code=str(error)
                if not code or any(ch not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789' for ch in code):
                    code='INPUT_OR_STATE_INVALID'
                self.send(400,{'code':1,'msg':code,'data':{}})
            except Exception:
                self.send(500,{'code':1,'msg':'LOCAL_OPERATION_FAILED','data':{}})

    return HTTPServer(('127.0.0.1',port),Handler)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--database',default='local-data/x-growth.sqlite3')
    args=parser.parse_args()
    service=XGrowth(args.database)
    server=make_server(service,args.port)
    print(f'X TODAY: http://127.0.0.1:{server.server_port} — live publication disabled',flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__=='__main__':
    main()
