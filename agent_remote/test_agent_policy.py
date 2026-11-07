import asyncio,importlib.util,json,sqlite3,sys,tempfile,types,unittest
from pathlib import Path
class HTTPException(Exception):
 def __init__(self,status_code,detail):self.status_code=status_code;self.detail=detail
class App:
 def get(self,*a,**kw):return lambda f:f
 post=get
temp=tempfile.TemporaryDirectory();dbpath=Path(temp.name)/'test.db'
def db():c=sqlite3.connect(dbpath);c.row_factory=sqlite3.Row;return c
def one(c,sql,args=()):r=c.execute(sql,args).fetchone();return dict(r) if r else None
v5=types.SimpleNamespace(app=App(),db=db,ex=lambda c,s,p=():c.execute(s,p),one=one,rows=lambda c,s,p=():[dict(r) for r in c.execute(s,p)],page=lambda *a:'page',adm=lambda k:None,go=lambda *a:None)
sys.modules['v5']=v5;sys.modules['fastapi']=types.SimpleNamespace(Request=object,Header=lambda *a:None,HTTPException=HTTPException,Form=lambda *a:None);sys.modules['fastapi.responses']=types.SimpleNamespace(HTMLResponse=object)
spec=importlib.util.spec_from_file_location('agent',Path(__file__).with_name('v5_bblia_agent.py'));agent=importlib.util.module_from_spec(spec);spec.loader.exec_module(agent)
class Policy(unittest.TestCase):
 def setUp(self):
  c=db();c.execute('CREATE TABLE IF NOT EXISTS devices(id TEXT PRIMARY KEY)');c.execute("INSERT OR IGNORE INTO devices VALUES('BOX-TEST')");c.execute('DELETE FROM bblia_agent_jobs');c.execute('DELETE FROM bblia_agents');c.commit();c.close()
  self.link=agent.provision('BOX-TEST');c=db();c.execute('UPDATE bblia_agents SET report=?',(json.dumps({'apps':[{'package':'com.example.test','label':'Teste','system':False},{'package':'com.android.settings','label':'Configurações','system':True}]}),));c.commit();c.close()
 def test_queue_exact_uninstall_and_diagnosis(self):
  c=db();j=agent.queue(c,'BOX-TEST','Desinstale Teste na TV Box');self.assertEqual(j['operation'],'uninstall');payload=json.loads(one(c,'SELECT payload FROM bblia_agent_jobs WHERE id=?',(j['id'],))['payload']);self.assertEqual(payload['packages'],['com.example.test']);c.close()
 def test_protected_and_injection_rejected(self):
  c=db()
  for text in ['Desinstale Configurações','Desinstale com.example.test; reboot','Resete tudo']:
   with self.assertRaises(HTTPException):agent.queue(c,'BOX-TEST',text)
  self.assertEqual(one(c,'SELECT COUNT(*) AS n FROM bblia_agent_jobs')['n'],0);c.close()
 def test_agent_token_not_owner_token(self):
  c=db();self.assertEqual(agent.auth(c,'Bearer '+self.link['token']),'BOX-TEST')
  with self.assertRaises(HTTPException):agent.auth(c,'Bearer '+self.link['token'],True)
  with self.assertRaises(HTTPException):agent.auth(c,'Bearer wrong')
  c.close()
if __name__=='__main__':unittest.main()
