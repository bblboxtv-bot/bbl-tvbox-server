import secrets
from fastapi import Form, HTTPException
from fastapi.responses import HTMLResponse
import v5

app = v5.app

# Nova tela de ativação focada no fluxo da Launcher V4: ativação por código.
# Usuário/senha continuam disponíveis nos módulos que usam login, mas a Launcher V4 usa somente código.

_base_nav = v5.nav

def _nav_activation_code(k):
    html = _base_nav(k)
    html = html.replace('/admin/activation-keys?key=', '/admin/codigos-ativacao?key=')
    return html

v5.nav = _nav_activation_code


def _esc(value):
    import html
    return html.escape(str(value or ''))


def _gen_code():
    return f"BBL-{secrets.token_hex(2).upper()}-{secrets.token_hex(2).upper()}"


@app.get('/admin/codigos-ativacao', response_class=HTMLResponse)
def activation_codes(key: str = ''):
    v5.adm(key)
    c = v5.db()
    keys = v5.rows(c, 'SELECT * FROM activation_keys ORDER BY created_at DESC')
    resellers = v5.rows(c, 'SELECT id,name FROM resellers WHERE enabled=1 ORDER BY name')
    c.close()

    opts = '<option value="">Administrador</option>' + ''.join(
        f'<option value="{_esc(r["id"])}">{_esc(r["name"])}</option>' for r in resellers
    )

    cards = ''
    for x in keys:
        status = 'ATIVO' if x.get('enabled') else 'DESATIVADO'
        cards += (
            '<div class="card">'
            f'<b>{_esc(x.get("label") or "Cliente")}</b><br>'
            f'<span style="font-size:22px;font-weight:800">{_esc(x.get("key"))}</span><br>'
            f'<span class="muted">Código de ativação • {status}</span>'
            '</div>'
        )
    if not cards:
        cards = '<div class="card muted">Nenhum código de ativação criado.</div>'

    body = f'''
    <div class="hero"><b>Ativação da Launcher V4 por código</b><br>
    <span class="muted">Na Launcher V4 o cliente não entra com usuário e senha. Ele informa o código de ativação gerado aqui.</span></div>
    <div class="card">
      <h3>Criar código de ativação</h3>
      <form method="post" action="/admin/codigos-ativacao/criar?key={_esc(key)}">
        <input name="label" placeholder="Nome do cliente / descrição" required>
        <input name="activation_code" placeholder="Código de ativação (deixe vazio para gerar automático)">
        <select name="reseller_id">{opts}</select>
        <button>GERAR CÓDIGO DE ATIVAÇÃO</button>
      </form>
    </div>
    <div class="grid">{cards}</div>
    '''
    return v5.page('Códigos de ativação', body, key)


@app.post('/admin/codigos-ativacao/criar')
def activation_code_create(
    key: str,
    label: str = Form(...),
    activation_code: str = Form(''),
    reseller_id: str = Form('')
):
    v5.adm(key)
    code = activation_code.strip().upper() or _gen_code()
    c = v5.db()
    try:
        v5.ex(
            c,
            'INSERT INTO activation_keys(key,enabled,label,created_at,reseller_id) VALUES(?,?,?,?,?)',
            (code, 1, label.strip(), v5.now(), reseller_id or None)
        )
        c.commit()
    except Exception:
        c.rollback()
        c.close()
        raise HTTPException(409, 'Código de ativação já existe')
    c.close()
    return v5.go('/admin/codigos-ativacao', key)
