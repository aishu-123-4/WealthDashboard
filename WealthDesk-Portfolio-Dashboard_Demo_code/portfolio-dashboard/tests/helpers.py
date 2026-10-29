import json,os,sys,tempfile,threading,unittest,urllib.request,urllib.error
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
class HTTPTestCase(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();app.DB=Path(self.tmp.name)/'test.sqlite3';self.env=patch.dict(os.environ,{'OPENAI_API_KEY':'','OPENAI_MODEL':'','PORTFOLIO_DEMO':'0'});self.env.start();app.init();self.server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler);threading.Thread(target=self.server.serve_forever,daemon=True).start();self.base='http://127.0.0.1:'+str(self.server.server_port)
 def tearDown(self):self.server.shutdown();self.server.server_close();self.env.stop();self.tmp.cleanup()
 def call(self,path,role='owner',data=None):
  req=urllib.request.Request(self.base+'/api/'+path,headers={'Authorization':'Bearer demo-'+role,'Content-Type':'application/json'},data=None if data is None else json.dumps(data).encode())
  try:
   with urllib.request.urlopen(req,timeout=40) as r:return r.status,json.load(r)
  except urllib.error.HTTPError as e:return e.code,json.load(e)
 def create(self,business=True,personal=False):
  code,out=self.call('onboard',data={'name':'Isolated test fixture','owner':'Test owner','industry':'Test','business_pnc':business,'personal_pnc':personal});self.assertEqual(code,200,out);return out['client']
 def detail(self,hid,role='owner'):return self.call('portfolio?id='+hid,role)
 def invite(self,hid,role,scopes):
  code,out=self.call('invite',data=dict(client=hid,role=role,name='Test '+role,scopes=scopes,use_existing=True));self.assertEqual(code,200,out);return out
