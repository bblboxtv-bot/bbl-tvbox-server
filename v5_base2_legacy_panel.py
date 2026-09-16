import secrets
from datetime import datetime, timezone, timedelta
from fastapi import Request, Form, HTTPException
from fastapi.responses import RedirectResponse
import v5
import v5_base2_gate as gate


def _add_priority_route(path, endpoint, methods):
    v5.app.add_api_route(path, endpoint, methods=methods)
    route = v5.app.router.routes.pop()
    v5.app.router.routes.insert(0, route)


def _esc(x):
    import html
    return html.escape(str(x or ''))


def activation_page(request: Request, key: str, ok: str = '', erro: str = ''):
    v5.adm(key)
    c = v5.db()
    clients = v5.rows(c, 'SELECT id,name,username,enabled,expires_at,device_id,created_at FROM base2_clients ORDER BY created_at DESC LIMIT 100')
    activations = v5.rows(c, 'SELECT key,label,enabled,created_at FROM activation_keys ORDER BY created_at DESC LIMIT 100')
    c.close()
    msg = ''
    if ok:
        msg = f'<div class="card"><span class="ok">{_esc(ok)}</span></div>'
    if erro:
        msg = f'<div class="card"><span class="bad">{_esc(erro)}</span></div>'
    rows = ''.join(
        f'<div class="card"><b>{_esc(x["name"])}</b><br>'
        f'Usuário: <b>{_esc(x["username"])}</b><br>'
        f'Status: {"ATIVO" if x["enabled"] else "BLOQUEADO"}<br>'
        f'Vence: {_esc(x.get("expires_at") or "sem vencimento")}<br>'
        f'Aparelho: {_esc(x.get("device_id") or "não vinculado")}</div>'
        for x in clients
    ) or '<div class="card">Nenhum usuário criado ainda.</div>'
    old = ''.join(
        f'<div class="card"><b>{_esc(x["label"] or "Cliente Launcher")}</b><br>'
        f'Código de ativação: <b>{_esc(x["key"])}</b><br>'
        f'Status: {"ATIVO" if x["enabled"] else "BLOQUEADO"}</div>'
        for x in activations[:50]
    ) or '<div class="card">Nenhum código de ativação criado ainda.</div>'
    body = msg + f'''
    <div class="grid">
      <div class="card">
        <h3>Opção 1 • Cliente com usuário e senha</h3>
        <form method="post" action="/admin/activation-keys/create-base2?key={_esc(key)}">
          <input name="name" placeholder="Nome do cliente" required>
          <input name="username" placeholder="Usuário (ex.: BBL0000)" required>
          <input name="password" type="password" placeholder="Senha" minlength="4" required>
          <input name="days" type="number" value="30" min="1" placeholder="Dias de acesso">
          <button class="good">CRIAR USUÁRIO + SENHA</button>
        </form>
        <div class="muted">Use esta opção nos aplicativos que entram com usuário e senha.</div>
      </div>

      <div class="card">
        <h3>Opção 2 • Launcher V4 por código</h3>
        <form method="post" action="/admin/activation-keys/create-launcher?key={_esc(key)}">
          <input name="name" placeholder="Nome do cliente" required>
          <input name="activation_code" placeholder="Código de ativação (deixe vazio para gerar)">
          <input name="days" type="number" value="30" min="1" placeholder="Dias de acesso">
          <button class="good">GERAR / CRIAR CÓDIGO DE ATIVAÇÃO</button>
        </form>
        <div class="muted">A Launcher V4 ativa por código, sem usuário e senha. Se deixar o campo vazio, o painel gera automaticamente um código no formato BBL-XXXX-XXXX.</div>
      </div>
    </div>

    <h3>Clientes com usuário e senha</h3>
    <div class="grid">{rows}</div>
    <h3>Códigos de ativação da Launcher V4</h3>
    <div class="grid">{old}</div>
    '''
    return v5.page('Ativações • Usuário/Senha ou Código', body, key)


def create_base2_user(
    request: Request,
    key: str,
    name: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    days: int = Form(30),
):
    v5.adm(key)
    name = name.strip()
    username = username.strip()
    password = password.strip()
    if not name or not username or len(password) < 4:
        return RedirectResponse(f'/admin/activation-keys?key={key}&erro=Preencha+nome,+usuário+e+senha', 303)
    exp = (datetime.now(timezone.utc) + timedelta(days=max(1, days))).isoformat()
    c = v5.db()
    try:
        if v5.one(c, 'SELECT id FROM base2_clients WHERE lower(username)=lower(?)', (username,)):
            raise HTTPException(409, 'Usuário já existe')
        v5.ex(c, 'INSERT INTO base2_clients(id,reseller_id,name,username,password_hash,enabled,expires_at,device_id,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
              (secrets.token_hex(8), None, name, username, gate.phash(password), 1, exp, '', gate.now()))
        c.commit()
    except HTTPException:
        c.rollback(); c.close(); raise
    except Exception:
        c.rollback(); c.close()
        return RedirectResponse(f'/admin/activation-keys?key={key}&erro=Falha+ao+criar+usuário', 303)
    c.close()
    return RedirectResponse(f'/admin/activation-keys?key={key}&ok=Usuário+{username}+criado+com+sucesso', 303)


def create_launcher_code(
    request: Request,
    key: str,
    name: str = Form(...),
    activation_code: str = Form(''),
    days: int = Form(30),
):
    v5.adm(key)
    name = name.strip()
    if not name:
        return RedirectResponse(f'/admin/activation-keys?key={key}&erro=Informe+o+nome+do+cliente', 303)
    code = activation_code.strip().upper()
    if not code:
        code = 'BBL-' + secrets.token_hex(2).upper() + '-' + secrets.token_hex(2).upper()
    c = v5.db()
    try:
        if v5.one(c, 'SELECT key FROM activation_keys WHERE key=?', (code,)):
            raise HTTPException(409, 'Código de ativação já existe')
        v5.ex(c, 'INSERT INTO activation_keys(key,enabled,label,created_at) VALUES(?,?,?,?)',
              (code, 1, name, v5.now()))
        c.commit()
    except HTTPException:
        c.rollback(); c.close(); raise
    except Exception:
        c.rollback(); c.close()
        return RedirectResponse(f'/admin/activation-keys?key={key}&erro=Falha+ao+criar+código+de+ativação', 303)
    c.close()
    return RedirectResponse(f'/admin/activation-keys?key={key}&ok=Código+de+ativação+{code}+criado+com+sucesso', 303)


_add_priority_route('/admin/activation-keys', activation_page, ['GET'])
_add_priority_route('/admin/activation-keys/create-base2', create_base2_user, ['POST'])
_add_priority_route('/admin/activation-keys/create-launcher', create_launcher_code, ['POST'])
