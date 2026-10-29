"""Run python app.py; no third-party packages required."""
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse,parse_qs
import argparse,json,os,sqlite3
import core,portfolios,chat,demo_data
ROOT=Path(__file__).resolve().parent
DB=Path(os.environ.get('PORTFOLIO_DB',str(ROOT/'portfolio.sqlite3')))
def connect():
    c=sqlite3.connect(DB,timeout=30);c.row_factory=sqlite3.Row;return c
def init():
    core.init(connect);portfolios.init(connect);chat.init(connect)
    if os.environ.get('PORTFOLIO_DEMO','1')=='1':demo_data.seed(connect)
class Handler(BaseHTTPRequestHandler):
    def send(self,status,data):
        body=json.dumps(data,allow_nan=False).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(body)
    def user(self):return core.auth(self.headers.get('Authorization','').removeprefix('Bearer '))
    def do_GET(self):
        url=urlparse(self.path);path=url.path
        if path in ('/','/app.js','/style.css'):
            name,mime={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8')}[path]
            self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write((ROOT/'web'/name).read_bytes());return
        try:
            if path=='/api/profiles':return self.send(200,{'profiles':demo_data.PROFILES if os.environ.get('PORTFOLIO_DEMO','1')=='1' else [],'demo_enabled':os.environ.get('PORTFOLIO_DEMO','1')=='1'})
            u=self.user();q={k:v[-1] for k,v in parse_qs(url.query).items()}
            if path=='/api/profiles':out={'profiles':demo_data.PROFILES if os.environ.get('PORTFOLIO_DEMO','1')=='1' else [],'demo_enabled':os.environ.get('PORTFOLIO_DEMO','1')=='1'}
            elif path=='/api/book':out=portfolios.book(u)
            elif path=='/api/portfolio':out=portfolios.view(u,q.get('id',''))
            elif path=='/api/notifications':out={'alerts':portfolios.alerts(u)}
            elif path=='/api/chat':out=chat.history(u,q.get('id',''),q.get('account','personal'))
            elif path=='/api/advisor-requests':out=chat.requests(u,q.get('id',''))
            else:raise core.Problem('Not found',404)
            self.send(200,out)
        except core.Problem as e:self.send(e.status,{'error':e.message})
        except (ValueError,KeyError,TypeError):self.send(400,{'error':'Invalid request'})
    def do_POST(self):
        try:
            u=self.user();n=int(self.headers.get('Content-Length','0'));core.require(0<=n<=100000,'Request too large',413)
            d=json.loads(self.rfile.read(n) or b'{}');core.require(isinstance(d,dict),'JSON object required')
            if self.path=='/api/chat':out=chat.ask(u,d)
            elif self.path=='/api/connect-advisor':out=chat.connect(u,d)
            elif self.path=='/api/advisor-reply':out=chat.reply(u,d)
            elif self.path in ('/api/onboard','/api/invite','/api/access','/api/signal','/api/introduction'):
                out=core.post(u,self.path,d)
                if self.path!='/api/onboard':portfolios.dispatch(d['client'])
            else:out=portfolios.post(u,self.path,d)
            self.send(200,out)
        except core.Problem as e:self.send(e.status,{'error':e.message})
        except (ValueError,KeyError,TypeError):self.send(400,{'error':'Invalid request'})
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=int(os.environ.get('PORT','8080')));args,_=parser.parse_known_args();init();print(f'Portfolio dashboard: http://{args.host}:{args.port}',flush=True);ThreadingHTTPServer((args.host,args.port),Handler).serve_forever()
