from fastapi import Request, Form, HTTPException
from fastapi.responses import HTMLResponse
import v5
import v5_base2_gate as admin
import v5_base2_reseller_portal as reseller

app = v5.app


def esc(x):
    import html
    return html.escape(str(x or ''))


def _target_label(x):
    return 'TV BOX' if (x or 'container') == 'device' else 'CONTÊINER'


def _latest_assignments(c, where='', params=()):
    rows = v5.rows(c, f'''SELECT q.id queue_id,q.client_id,q.app_id,q.status,q.created_at,
        COALESCE(q.install_target,'container') install_target,
        a.name app_name,a.package_name,a.version_name,
        cl.name client_name,cl.username client_username,cl.reseller_id
        FROM base2_remote_apps q
        JOIN apps a ON a.id=q.app_id
        JOIN base2_clients cl ON cl.id=q.client_id
        {where}
        ORDER BY q.created_at DESC''', params)
    seen=set(); out=[]
    for x in rows:
        key=(x.get('client_id'),x.get('app_id'),x.get('install_target') or 'container')
        if key in seen: continue
        seen.add(key); out.append(x)
    return out


def _cards(rows, action):
    if not rows:
        return '<div class="card muted">Nenhum aplicativo vinculado a clientes.</div>'
    out=[]
    current=None
    for x in rows:
        client=(x.get('client_name') or 'Cliente')+' • '+(x.get('client_username') or '')
        if client != current:
            out.append(f'<h3>{esc(client)}</h3>'); current=client
        out.append(f'''<div class="card"><b>{esc(x.get('app_name'))}</b><br>
        <span class="muted">{esc(x.get('package_name'))} • {esc(x.get('version_name'))} • {_target_label(x.get('install_target'))}</span>
        <form method="post" action="{action}" onsubmit="return confirm('Remover este aplicativo deste cliente?')">
        <input type="hidden" name="client_id" value="{esc(x.get('client_id'))}">
        <input type="hidden" name="app_id" value="{esc(x.get('app_id'))}">
        <input type="hidden" name="install_target" value="{esc(x.get('install_target') or 'container')}">
        <button class="danger">REMOVER DO CLIENTE</button></form></div>''')
    return ''.join(out)


@app.get('/base2/painel/cliente-apps')
def admin_client_apps(req:Request, ok:str=''):
    if not admin.admin_ok(req): return admin.redir('/base2/painel/login')
    c=v5.db(); rows=_latest_assignments(c); c.close()
    msg=f'<div class="card good">{esc(ok)}</div>' if ok else ''
    body=msg+'<div class="card"><b>Aplicativos vinculados aos clientes</b><br><span class="muted">REMOVER DO CLIENTE tira o aplicativo da lista liberada daquele cliente. No BBL Container, basta usar ATUALIZAR para a lista refletir a mudança.</span></div>'+_cards(rows,'/base2/painel/cliente-apps/remover')
    return admin.page('Apps dos clientes / Remover',body)


@app.post('/base2/painel/cliente-apps/remover')
def admin_remove_client_app(req:Request,client_id:str=Form(...),app_id:str=Form(...),install_target:str=Form('container')):
    admin.adm(req)
    c=v5.db()
    v5.ex(c,"DELETE FROM base2_remote_apps WHERE client_id=? AND app_id=? AND COALESCE(install_target,'container')=?",(client_id,app_id,install_target))
    c.commit(); c.close()
    return admin.redir('/base2/painel/cliente-apps?ok=Aplicativo+removido+do+cliente')


@app.get('/base2/revenda/cliente-apps')
def reseller_client_apps(req:Request, ok:str=''):
    r=reseller.session_reseller(req)
    if not r: return reseller.redir('/base2/revenda/login')
    c=v5.db(); rows=_latest_assignments(c,'WHERE cl.reseller_id=?',(r['id'],)); c.close()
    msg=f'<div class="card good">{esc(ok)}</div>' if ok else ''
    body=msg+'<div class="card"><b>Aplicativos dos seus clientes</b><br><span class="muted">Use REMOVER DO CLIENTE para retirar o aplicativo da lista liberada.</span></div>'+_cards(rows,'/base2/revenda/cliente-apps/remover')
    return reseller.page('Apps dos clientes / Remover',body)


@app.post('/base2/revenda/cliente-apps/remover')
def reseller_remove_client_app(req:Request,client_id:str=Form(...),app_id:str=Form(...),install_target:str=Form('container')):
    r=reseller.require_reseller(req)
    c=v5.db(); cl=v5.one(c,'SELECT id FROM base2_clients WHERE id=? AND reseller_id=?',(client_id,r['id']))
    if not cl:
        c.close(); raise HTTPException(404,'Cliente não encontrado')
    v5.ex(c,"DELETE FROM base2_remote_apps WHERE client_id=? AND app_id=? AND COALESCE(install_target,'container')=?",(client_id,app_id,install_target))
    c.commit(); c.close()
    return reseller.redir('/base2/revenda/cliente-apps?ok=Aplicativo+removido+do+cliente')


def _safe_html_response(original, text):
    headers={k:v for k,v in original.headers.items() if k.lower() not in ('content-length','content-type')}
    return HTMLResponse(text,status_code=original.status_code,headers=headers)


_old_admin_page=admin.page
def _admin_page_with_remove(title,body,nav=True):
    r=_old_admin_page(title,body,nav)
    if nav and isinstance(r,HTMLResponse):
        txt=r.body.decode('utf-8')
        if '/base2/painel/cliente-apps' not in txt:
            txt=txt.replace('<a href="/base2/painel/sair">Sair</a>','<a href="/base2/painel/cliente-apps">Apps dos clientes / Remover</a><a href="/base2/painel/sair">Sair</a>')
        return _safe_html_response(r,txt)
    return r
admin.page=_admin_page_with_remove

_old_reseller_page=reseller.page
def _reseller_page_with_remove(title,body,nav=True):
    r=_old_reseller_page(title,body,nav)
    if nav and isinstance(r,HTMLResponse):
        txt=r.body.decode('utf-8')
        if '/base2/revenda/cliente-apps' not in txt:
            txt=txt.replace('<a href="/base2/revenda/sair">Sair</a>','<a href="/base2/revenda/cliente-apps">Apps dos clientes / Remover</a><a href="/base2/revenda/sair">Sair</a>')
        return _safe_html_response(r,txt)
    return r
reseller.page=_reseller_page_with_remove
