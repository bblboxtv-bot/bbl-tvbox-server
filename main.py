import os, secrets, json
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Header, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tvbox.db")
ADMIN_KEY = os.getenv("ADMIN_KEY", "troque-esta-chave")
DEFAULT_ACTIVATION_KEY = os.getenv("ACTIVATION_KEY", "BBL-2026")
app = FastAPI(title="BBL TV Box Manager API", version="2.0.0")

def now_iso(): return datetime.now(timezone.utc).isoformat()
def is_postgres(): return DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://")
def db_connect():
    if is_postgres():
        import psycopg
        return psycopg.connect(DATABASE_URL.replace("postgres://", "postgresql://", 1), autocommit=False)
    import sqlite3
    path = DATABASE_URL.replace("sqlite:///", "", 1) if DATABASE_URL.startswith("sqlite:///") else DATABASE_URL
    c=sqlite3.connect(path); c.row_factory=sqlite3.Row; return c

def execute(c, sql, params=()):
    if is_postgres(): sql=sql.replace("?", "%s")
    cur=c.cursor(); cur.execute(sql, params); return cur

def row_to_dict(row, cur=None):
    if row is None: return None
    try: return dict(row)
    except Exception:
        cols=[d.name if hasattr(d,"name") else d[0] for d in cur.description]; return dict(zip(cols,row))

def init_db():
    c=db_connect()
    execute(c,"""CREATE TABLE IF NOT EXISTS devices(id TEXT PRIMARY KEY,token TEXT UNIQUE NOT NULL,activation_key TEXT,locked INTEGER NOT NULL DEFAULT 0,allowed_apps TEXT NOT NULL DEFAULT '[]',managed_apps TEXT NOT NULL DEFAULT '[]',display_name TEXT NOT NULL DEFAULT '',notes TEXT NOT NULL DEFAULT '',created_at TEXT,last_seen TEXT)""")
    execute(c,"""CREATE TABLE IF NOT EXISTS activation_keys(key TEXT PRIMARY KEY,enabled INTEGER NOT NULL DEFAULT 1,label TEXT NOT NULL DEFAULT '',created_at TEXT)""")
    c.commit()
    try: execute(c,"INSERT INTO activation_keys(key,enabled,label,created_at) VALUES (?,?,?,?)",(DEFAULT_ACTIVATION_KEY,1,"Chave padrão",now_iso())); c.commit()
    except Exception: c.rollback()
    c.close()

@app.on_event("startup")
def startup(): init_db()

class EnrollBody(BaseModel):
    activationCode: Optional[str]=None
    activation: Optional[str]=None
    activation_code: Optional[str]=None
    enrollmentKey: Optional[str]=None
    deviceId: Optional[str]=None
    device_id: Optional[str]=None

def bearer_token(auth):
    if not auth or not auth.lower().startswith("bearer "): return None
    return auth.split(" ",1)[1].strip()

def row_policy(r):
    allowed=json.loads(r.get("allowed_apps") or "[]"); managed=json.loads(r.get("managed_apps") or "[]")
    p={"locked":bool(r.get("locked")),"allowed_apps":allowed,"managed_apps":managed,"allowedApps":allowed,"apps":allowed}
    return {**p,"policy":p}

def admin_ok(k): return bool(k) and secrets.compare_digest(k,ADMIN_KEY)

@app.get("/health")
def health(): return {"ok":True,"service":"bbl-tvbox-manager","version":"2.0.0","database":"postgresql" if is_postgres() else "sqlite"}

@app.post("/api/enroll")
def enroll(body:EnrollBody):
    key=body.activationCode or body.activation or body.activation_code or body.enrollmentKey
    if not key: raise HTTPException(400,"activation key required")
    c=db_connect(); cur=execute(c,"SELECT key FROM activation_keys WHERE key=? AND enabled=1",(key,))
    if not cur.fetchone(): c.close(); raise HTTPException(403,"invalid activation key")
    device_id=body.deviceId or body.device_id or secrets.token_hex(8)
    cur=execute(c,"SELECT * FROM devices WHERE id=?",(device_id,)); existing=row_to_dict(cur.fetchone(),cur)
    if existing:
        token=existing["token"]; execute(c,"UPDATE devices SET last_seen=? WHERE id=?",(now_iso(),device_id))
    else:
        token=secrets.token_urlsafe(32); execute(c,"INSERT INTO devices(id,token,activation_key,created_at,last_seen) VALUES(?,?,?,?,?)",(device_id,token,key,now_iso(),now_iso()))
    c.commit(); c.close()
    return {"device_id":device_id,"device_token":token,"deviceId":device_id,"deviceToken":token,"token":token,"status":"ok"}

@app.get("/api/devices/{device_id}/policy")
def policy(device_id:str,authorization:Optional[str]=Header(default=None)):
    token=bearer_token(authorization); c=db_connect(); cur=execute(c,"SELECT * FROM devices WHERE id=?",(device_id,)); r=row_to_dict(cur.fetchone(),cur)
    if not r or not token or not secrets.compare_digest(token,r["token"]): c.close(); raise HTTPException(401,"unauthorized")
    execute(c,"UPDATE devices SET last_seen=? WHERE id=?",(now_iso(),device_id)); c.commit(); out=row_policy(r); c.close(); return out

@app.post("/api/devices/{device_id}/policy")
def policy_post(device_id:str,authorization:Optional[str]=Header(default=None)): return policy(device_id,authorization)

class PolicyUpdate(BaseModel):
    locked: Optional[bool]=None
    allowed_apps: Optional[list[str]]=None
    managed_apps: Optional[list[str]]=None

@app.get("/api/admin/devices")
def admin_devices(x_admin_key:Optional[str]=Header(default=None)):
    if not admin_ok(x_admin_key): raise HTTPException(401,"bad admin key")
    c=db_connect(); cur=execute(c,"SELECT * FROM devices ORDER BY created_at DESC"); out=[]
    for rr in cur.fetchall():
        r=row_to_dict(rr,cur); r["locked"]=bool(r["locked"]); r["allowed_apps"]=json.loads(r.get("allowed_apps") or "[]"); r["managed_apps"]=json.loads(r.get("managed_apps") or "[]"); r["token"]="***"; out.append(r)
    c.close(); return out

@app.put("/api/admin/devices/{device_id}/policy")
def admin_update(device_id:str,body:PolicyUpdate,x_admin_key:Optional[str]=Header(default=None)):
    if not admin_ok(x_admin_key): raise HTTPException(401,"bad admin key")
    c=db_connect(); cur=execute(c,"SELECT * FROM devices WHERE id=?",(device_id,)); r=row_to_dict(cur.fetchone(),cur)
    if not r: c.close(); raise HTTPException(404,"device not found")
    locked=int(body.locked) if body.locked is not None else r["locked"]
    allowed=json.dumps(body.allowed_apps if body.allowed_apps is not None else json.loads(r.get("allowed_apps") or "[]")); managed=json.dumps(body.managed_apps if body.managed_apps is not None else json.loads(r.get("managed_apps") or "[]"))
    execute(c,"UPDATE devices SET locked=?,allowed_apps=?,managed_apps=? WHERE id=?",(locked,allowed,managed,device_id)); c.commit(); cur=execute(c,"SELECT * FROM devices WHERE id=?",(device_id,)); r=row_to_dict(cur.fetchone(),cur); c.close(); return row_policy(r)

CSS='''body{font-family:Arial,sans-serif;background:#0c0f14;color:#e8edf3;margin:0}.wrap{max-width:1100px;margin:32px auto;padding:0 18px}h1{margin-bottom:4px}.muted{color:#9aa6b2}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}.card{background:#171c23;border:1px solid #262e38;border-radius:14px;padding:16px}.ok{color:#55d187}.bad{color:#ff6b6b}input,textarea,button{box-sizing:border-box;padding:10px;border-radius:8px;border:1px solid #34404d;background:#0f141a;color:#fff}input,textarea{width:100%;margin:5px 0}button{cursor:pointer;margin:5px 4px 5px 0}.danger{background:#3a1518}.good{background:#12351f}.top{display:flex;gap:10px;flex-wrap:wrap;align-items:end}.top>div{flex:1;min-width:220px}.pill{display:inline-block;padding:4px 8px;border-radius:999px;background:#242d38;font-size:12px}.row{display:flex;gap:8px;flex-wrap:wrap}.row>*{flex:1}.section{margin-top:28px}'''

def login_page(): return f'''<!doctype html><meta name="viewport" content="width=device-width"><title>BBL TV Box Manager</title><style>{CSS}</style><div class="wrap" style="max-width:460px"><h1>BBL TV Box Manager</h1><p class="muted">Painel administrativo</p><form><input name="key" type="password" placeholder="ADMIN_KEY"><button>Entrar</button></form></div>'''

@app.get("/",response_class=HTMLResponse)
def dashboard(key:str="",q:str=""):
    if not admin_ok(key): return HTMLResponse(login_page())
    c=db_connect()
    if q.strip():
        like=f"%{q.strip()}%"; cur=execute(c,"SELECT * FROM devices WHERE id LIKE ? OR display_name LIKE ? OR notes LIKE ? ORDER BY created_at DESC",(like,like,like))
    else: cur=execute(c,"SELECT * FROM devices ORDER BY created_at DESC")
    rows=[row_to_dict(x,cur) for x in cur.fetchall()]; cur2=execute(c,"SELECT * FROM activation_keys ORDER BY created_at DESC"); keys=[row_to_dict(x,cur2) for x in cur2.fetchall()]; c.close()
    cards=""
    for r in rows:
        state="BLOQUEADO" if r["locked"] else "ATIVO"; state_cls="bad" if r["locked"] else "ok"; apps=", ".join(json.loads(r.get("allowed_apps") or "[]"))
        cards+=f'''<div class="card"><div class="row"><div><b>{r.get('display_name') or 'Sem nome'}</b><br><span class="muted">{r['id']}</span></div><div style="text-align:right"><span class="{state_cls}"><b>{state}</b></span></div></div><p class="muted">Último contato: {r.get('last_seen') or '-'}<br>Chave: {r.get('activation_key') or '-'}</p><form method="post" action="/admin/device/{r['id']}/toggle?key={key}"><button class="{'good' if r['locked'] else 'danger'}">{'Desbloquear' if r['locked'] else 'Bloquear'}</button></form><form method="post" action="/admin/device/{r['id']}/edit?key={key}"><input name="display_name" value="{r.get('display_name') or ''}" placeholder="Nome do cliente/aparelho"><textarea name="notes" placeholder="Observações">{r.get('notes') or ''}</textarea><input name="apps" value="{apps}" placeholder="com.app1, com.app2"><button>Salvar dados</button></form><form method="post" action="/admin/device/{r['id']}/delete?key={key}" onsubmit="return confirm('Excluir este dispositivo?')"><button class="danger">Excluir</button></form></div>'''
    key_cards=""
    for k in keys:
        status="ativa" if k["enabled"] else "desativada"; key_cards+=f'''<div class="card"><b>{k['key']}</b> <span class="pill">{status}</span><br><span class="muted">{k.get('label') or ''}</span><form method="post" action="/admin/key/{k['key']}/toggle?key={key}"><button>{'Desativar' if k['enabled'] else 'Ativar'}</button></form></div>'''
    return f'''<!doctype html><meta name="viewport" content="width=device-width"><title>BBL TV Box Manager</title><style>{CSS}</style><div class="wrap"><h1>BBL TV Box Manager</h1><p class="muted">Servidor v2 • dispositivos cadastrados: {len(rows)}</p><form class="top"><div><label>Buscar cliente/aparelho</label><input name="q" value="{q}" placeholder="nome, ID ou observação"><input type="hidden" name="key" value="{key}"></div><div style="flex:0"><button>Buscar</button></div></form><div class="section"><h2>Clientes / aparelhos</h2><div class="grid">{cards or '<div class="card">Nenhum dispositivo cadastrado.</div>'}</div></div><div class="section"><h2>Chaves de ativação</h2><form method="post" action="/admin/key/create?key={key}" class="top"><div><input name="new_key" placeholder="Ex.: CLIENTE-001" required></div><div><input name="label" placeholder="Descrição"></div><div style="flex:0"><button>Criar chave</button></div></form><div class="grid">{key_cards}</div></div></div>'''

@app.post("/admin/device/{device_id}/toggle")
def web_toggle(device_id:str,key:str):
    if not admin_ok(key): raise HTTPException(401)
    c=db_connect(); cur=execute(c,"SELECT locked FROM devices WHERE id=?",(device_id,)); r=row_to_dict(cur.fetchone(),cur)
    if not r: c.close(); raise HTTPException(404)
    execute(c,"UPDATE devices SET locked=? WHERE id=?",(0 if r["locked"] else 1,device_id)); c.commit(); c.close(); return RedirectResponse(url=f"/?key={key}",status_code=303)

@app.post("/admin/device/{device_id}/edit")
def web_edit(device_id:str,key:str,display_name:str=Form(default=""),notes:str=Form(default=""),apps:str=Form(default="")):
    if not admin_ok(key): raise HTTPException(401)
    vals=[x.strip() for x in apps.split(",") if x.strip()]; c=db_connect(); execute(c,"UPDATE devices SET display_name=?,notes=?,allowed_apps=?,managed_apps=? WHERE id=?",(display_name.strip(),notes.strip(),json.dumps(vals),json.dumps(vals),device_id)); c.commit(); c.close(); return RedirectResponse(url=f"/?key={key}",status_code=303)

@app.post("/admin/device/{device_id}/delete")
def web_delete(device_id:str,key:str):
    if not admin_ok(key): raise HTTPException(401)
    c=db_connect(); execute(c,"DELETE FROM devices WHERE id=?",(device_id,)); c.commit(); c.close(); return RedirectResponse(url=f"/?key={key}",status_code=303)

@app.post("/admin/key/create")
def key_create(key:str,new_key:str=Form(...),label:str=Form(default="")):
    if not admin_ok(key): raise HTTPException(401)
    value=new_key.strip()
    if not value: raise HTTPException(400,"empty key")
    c=db_connect()
    try: execute(c,"INSERT INTO activation_keys(key,enabled,label,created_at) VALUES(?,?,?,?)",(value,1,label.strip(),now_iso())); c.commit()
    except Exception: c.rollback(); c.close(); raise HTTPException(409,"key already exists")
    c.close(); return RedirectResponse(url=f"/?key={key}",status_code=303)

@app.post("/admin/key/{activation_key}/toggle")
def key_toggle(activation_key:str,key:str):
    if not admin_ok(key): raise HTTPException(401)
    c=db_connect(); cur=execute(c,"SELECT enabled FROM activation_keys WHERE key=?",(activation_key,)); r=row_to_dict(cur.fetchone(),cur)
    if not r: c.close(); raise HTTPException(404)
    execute(c,"UPDATE activation_keys SET enabled=? WHERE key=?",(0 if r["enabled"] else 1,activation_key)); c.commit(); c.close(); return RedirectResponse(url=f"/?key={key}",status_code=303)
