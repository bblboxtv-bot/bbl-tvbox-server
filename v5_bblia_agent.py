"""Device-scoped companion agent. No arbitrary shell or cross-device commands."""
import hashlib,html,json,re,secrets,time,unicodedata
from urllib.parse import quote
from fastapi import Request,Header,HTTPException,Form
from fastapi.responses import HTMLResponse
import v5
app=v5.app
PROTECTED={'android','com.bbl.boxtv.launcher','com.bbl.boxtv.agent','com.bbl.boxtv.updateguard','com.android.systemui','com.android.settings','com.android.packageinstaller'}
def digest(value):return hashlib.sha256(value.encode()).hexdigest()
def norm(value):return ''.join(c for c in unicodedata.normalize('NFD',str(value).lower()) if not unicodedata.combining(c)).strip()
def render_result(raw):
 try:data=json.loads(raw)
 except Exception:return html.escape(raw)
 report=data.get('report')
 if not report:return '<p>'+html.escape(data.get('error') or '\n'.join(x.get('package','')+': '+x.get('message','') for x in data.get('results',[])))+'</p>'
 gb=lambda n:f'{int(n or 0)/1073741824:.2f} GB'
 fields=[('Aparelho',report.get('model')),('Android informado',str(report.get('android'))+' • API '+str(report.get('sdk'))),('Memória livre / total',gb(report.get('memory_free'))+' / '+gb(report.get('memory_total'))),('Espaço livre / total',gb(report.get('storage_free'))+' / '+gb(report.get('storage_total'))),('Rede',report.get('network')),('Temperatura reportada',str(report.get('temperature_c','Indisponível'))+' °C'),('Root do agente','Liberado' if report.get('root') else 'Não liberado')]
 cards='<div class="grid">'+''.join('<div class="card"><b>'+label+'</b><p>'+html.escape(str(value))+'</p></div>' for label,value in fields)+'</div>'
 apps=''.join('<tr><td>'+html.escape(a.get('label',''))+'</td><td>'+html.escape(a.get('package',''))+'</td><td>'+('Sistema' if a.get('system') else 'Usuário')+'</td></tr>' for a in report.get('apps',[]))
 return cards+'<p>Dados informados pelo Android. Esta análise não testa fisicamente fonte, placa ou conectores.</p><details><summary>Aplicativos e pacotes ('+str(len(report.get('apps',[])))+')</summary><table>'+apps+'</table></details>'
def init():
 c=v5.db()
 for sql in [
 'CREATE TABLE IF NOT EXISTS bblia_agents(device_id TEXT PRIMARY KEY,token_hash TEXT NOT NULL,last_seen INTEGER NOT NULL DEFAULT 0,report TEXT NOT NULL DEFAULT \'{}\')',
 'CREATE TABLE IF NOT EXISTS bblia_agent_jobs(id TEXT PRIMARY KEY,device_id TEXT NOT NULL,operation TEXT NOT NULL,payload TEXT NOT NULL,status TEXT NOT NULL,created INTEGER NOT NULL,claimed INTEGER NOT NULL DEFAULT 0,result TEXT NOT NULL DEFAULT \'{}\')',
 'CREATE TABLE IF NOT EXISTS bblia_agent_links(code_hash TEXT PRIMARY KEY,device_id TEXT NOT NULL,expires INTEGER NOT NULL)',
 'CREATE TABLE IF NOT EXISTS bblia_agent_owners(token_hash TEXT PRIMARY KEY,device_id TEXT NOT NULL,expires INTEGER NOT NULL)']:
  v5.ex(c,sql)
 c.commit();c.close()
def provision(did):
 c=v5.db()
 if not v5.one(c,'SELECT id FROM devices WHERE id=?',(did,)):c.close();raise ValueError('Aparelho não cadastrado')
 token=secrets.token_urlsafe(32)
 v5.ex(c,'INSERT INTO bblia_agents(device_id,token_hash) VALUES(?,?) ON CONFLICT(device_id) DO UPDATE SET token_hash=excluded.token_hash',(did,digest(token)))
 c.commit();c.close();return {'device_id':did,'token':token,'server':'https://152.67.55.60'}
def auth(c,authorization,owner=False):
 if not authorization or not authorization.startswith('Bearer '):raise HTTPException(401,'Conexão não autorizada')
 table='bblia_agent_owners' if owner else 'bblia_agents'
 row=v5.one(c,'SELECT * FROM '+table+' WHERE token_hash=?',(digest(authorization[7:]),))
 if not row or (owner and row['expires']<int(time.time())):raise HTTPException(401,'Conexão expirada ou inválida')
 return row['device_id']
async def body(request,limit=300000):
 raw=await request.body()
 if len(raw)>limit:raise HTTPException(413,'Pedido grande demais')
 try:value=json.loads(raw)
 except Exception:raise HTTPException(400,'JSON inválido')
 if not isinstance(value,dict):raise HTTPException(400,'Pedido inválido')
 return value
def queue(c,did,text):
 cleaned=re.sub(r'\s+(?:na|da|desta)\s+(?:tv\s*)?box[.!?]*$','',norm(text))
 if not cleaned or len(cleaned)>1000:raise HTTPException(400,'Descreva o comando')
 payload={};op='diagnose'
 if re.search(r'\b(desinstal\w*|remov\w*)\b',cleaned):
  row=v5.one(c,'SELECT report,last_seen FROM bblia_agents WHERE device_id=?',(did,))
  report=json.loads(row['report']) if row else {}
  if not report.get('apps'):raise HTTPException(409,'Faça um diagnóstico primeiro para identificar os aplicativos')
  names=re.split(r'\s*,\s*|\s+e\s+',re.sub(r'^.*?\b(?:desinstal\w*|remov\w*)\s+(?:(?:os?|as?)\s+)?(?:(?:aplicativos?|apps?)\s+)?','',cleaned).strip(' .'))
  apps=report['apps'];packages=[]
  for name in names:
   matches=[a for a in apps if norm(a.get('package'))==name or norm(a.get('label'))==name]
   if len(matches)!=1:raise HTTPException(409,'Aplicativo ausente ou nome ambíguo: '+name+'. Use o pacote exato da lista')
   target=matches[0];pkg=target['package']
   if target.get('system') or pkg in PROTECTED or pkg.startswith('com.bbl.'):raise HTTPException(400,'Aplicativo protegido: '+pkg)
   if not re.fullmatch(r'[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+',pkg):raise HTTPException(400,'Pacote inválido')
   if pkg not in packages:packages.append(pkg)
  if not 1<=len(packages)<=10:raise HTTPException(400,'Use de um a dez aplicativos')
  op='uninstall';payload={'packages':packages}
 elif not re.search(r'diagnos|analis|verific|status|aplicativ|apps|memoria|armazenamento|temperatura',cleaned):
  raise HTTPException(400,'Comandos disponíveis: diagnóstico da TV Box ou desinstalar aplicativos pelo nome/pacote exato')
 jid=secrets.token_urlsafe(18)
 v5.ex(c,'INSERT INTO bblia_agent_jobs(id,device_id,operation,payload,status,created) VALUES(?,?,?,?,?,?)',(jid,did,op,json.dumps(payload),'pending',int(time.time())))
 c.commit();return {'id':jid,'device_id':did,'operation':op,'status':'pending'}
@app.get('/api/agent/v1/commands')
def agent_commands(authorization:str|None=Header(None)):
 c=v5.db()
 try:
  did=auth(c,authorization);now=int(time.time())
  v5.ex(c,'UPDATE bblia_agents SET last_seen=? WHERE device_id=?',(now,did))
  row=v5.one(c,"SELECT * FROM bblia_agent_jobs WHERE device_id=? AND (status='pending' OR (status='processing' AND claimed<?)) ORDER BY created LIMIT 1",(did,now-180))
  if row:v5.ex(c,"UPDATE bblia_agent_jobs SET status='processing',claimed=? WHERE id=?",(now,row['id']))
  c.commit();return {'job':{'id':row['id'],'operation':row['operation'],'payload':json.loads(row['payload'])} if row else None}
 finally:c.close()
@app.post('/api/agent/v1/results/{jid}')
async def agent_result(jid:str,request:Request,authorization:str|None=Header(None)):
 data=await body(request);c=v5.db()
 try:
  did=auth(c,authorization);job=v5.one(c,'SELECT * FROM bblia_agent_jobs WHERE id=? AND device_id=?',(jid,did))
  if not job:raise HTTPException(404,'Comando não encontrado')
  status=data.get('status')
  if status not in ('completed','partial','failed'):raise HTTPException(400,'Estado inválido')
  if job['status'] in ('completed','partial','failed'):return {'ok':True,'duplicate':True}
  v5.ex(c,'UPDATE bblia_agent_jobs SET status=?,result=? WHERE id=?',(status,json.dumps(data,ensure_ascii=False),jid))
  if job['operation']=='diagnose' and isinstance(data.get('report'),dict):v5.ex(c,'UPDATE bblia_agents SET report=? WHERE device_id=?',(json.dumps(data['report'],ensure_ascii=False),did))
  c.commit();return {'ok':True}
 finally:c.close()
@app.post('/api/agent/owner/exchange')
async def exchange(request:Request):
 data=await body(request,4096);code=str(data.get('code',''));c=v5.db()
 try:
  row=v5.one(c,'SELECT * FROM bblia_agent_links WHERE code_hash=?',(digest(code),))
  if not row or row['expires']<int(time.time()):raise HTTPException(401,'Vínculo inválido ou expirado. Abra o painel para gerar outro')
  # DELETE is the atomic one-use claim even with concurrent exchange requests.
  cur=v5.one(c,'DELETE FROM bblia_agent_links WHERE code_hash=? RETURNING device_id',(digest(code),))
  if not cur:raise HTTPException(401,'Vínculo já utilizado')
  token=secrets.token_urlsafe(32)
  v5.ex(c,'INSERT INTO bblia_agent_owners(token_hash,device_id,expires) VALUES(?,?,?)',(digest(token),row['device_id'],int(time.time())+90*86400));c.commit()
  return {'token':token,'device_id':row['device_id']}
 finally:c.close()
@app.post('/api/agent/owner/command')
async def owner_command(request:Request,authorization:str|None=Header(None)):
 data=await body(request,4096);c=v5.db()
 try:return queue(c,auth(c,authorization,True),data.get('text',''))
 finally:c.close()
@app.get('/api/agent/owner/jobs/{jid}')
def owner_job(jid:str,authorization:str|None=Header(None)):
 c=v5.db()
 try:
  did=auth(c,authorization,True);row=v5.one(c,'SELECT id,operation,status,result,created FROM bblia_agent_jobs WHERE id=? AND device_id=?',(jid,did))
  if not row:raise HTTPException(404,'Comando não encontrado')
  row['result']=json.loads(row['result']);return row
 finally:c.close()
@app.get('/admin/agent',response_class=HTMLResponse)
def admin_agents(key:str):
 v5.adm(key);c=v5.db()
 try:devices=v5.rows(c,'SELECT id,display_name FROM devices ORDER BY display_name')
 finally:c.close()
 links=''.join('<p><a href="/admin/device/'+quote(d['id'])+'/assistant?key='+quote(key)+'">'+html.escape(d.get('display_name') or d['id'])+'</a></p>' for d in devices)
 return v5.page('Agente BBLIA',links,key)
@app.get('/admin/device/{did}/assistant',response_class=HTMLResponse)
def admin_agent(did:str,key:str):
 v5.adm(key);c=v5.db()
 try:
  device=v5.one(c,'SELECT id FROM devices WHERE id=?',(did,))
  if not device:raise HTTPException(404,'Aparelho não encontrado')
  agent=v5.one(c,'SELECT last_seen,report FROM bblia_agents WHERE device_id=?',(did,))
  jobs=v5.rows(c,'SELECT id,operation,status,result FROM bblia_agent_jobs WHERE device_id=? ORDER BY created DESC LIMIT 8',(did,))
 finally:c.close()
 state='Online' if agent and int(time.time())-agent['last_seen']<45 else 'Offline ou agente ainda não instalado'
 base='/admin/device/'+quote(did)+'/assistant'
 form='<form method="post" action="'+base+'?key='+quote(key)+'"><input name="text" placeholder="Diagnóstico da TV Box ou desinstale Nome do aplicativo" required><button>Executar comando</button></form>'
 pair='<form method="post" action="'+base+'/link?key='+quote(key)+'"><button>Vincular esta TV Box à BBLIA do celular</button></form>'
 results=''.join('<div class="card"><b>'+html.escape(j['operation']+' • '+j['status'])+'</b>'+render_result(j['result'])+'</div>' for j in jobs)
 return v5.page('Agente BBLIA • '+html.escape(did),'<div class="card"><h3>'+state+'</h3>'+form+pair+'</div>'+results,key)
@app.post('/admin/device/{did}/assistant')
def admin_command(did:str,key:str,text:str=Form(...)):
 v5.adm(key);c=v5.db()
 try:queue(c,did,text)
 finally:c.close()
 return v5.go('/admin/device/'+did+'/assistant',key)
@app.post('/admin/device/{did}/assistant/link',response_class=HTMLResponse)
def admin_link(did:str,key:str):
 v5.adm(key);c=v5.db()
 try:
  if not v5.one(c,'SELECT device_id FROM bblia_agents WHERE device_id=?',(did,)):raise HTTPException(409,'Instale o agente nesta box primeiro')
  code=secrets.token_urlsafe(18);v5.ex(c,'INSERT INTO bblia_agent_links(code_hash,device_id,expires) VALUES(?,?,?)',(digest(code),did,int(time.time())+600));c.commit()
 finally:c.close()
 url='https://bblia-teste.onrender.com/?tv_pair='+quote(code)
 return v5.page('Vincular BBLIA','<div class="card"><p>Abra no celular em que usa a BBLIA. O vínculo é exclusivo desta TV Box e pode ser usado uma vez, por dez minutos.</p><a href="'+url+'">Conectar TV Box na BBLIA</a></div>',key)
init()
_page=v5.page
def agent_page(title,content,key=''):
 if key:content='<p><a href="/admin/agent?key='+quote(key)+'">Agente BBLIA • diagnóstico e comandos</a></p>'+content
 return _page(title,content,key)
v5.page=agent_page
