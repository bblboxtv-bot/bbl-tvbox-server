import json
from pathlib import Path
from fastapi import HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
import v5

app = v5.app

_base_nav = v5.nav
def _nav_with_assets(k):
    base = _base_nav(k)
    return base.replace('</div>', f'<a href="/admin/assets?key={k}">Excluir itens</a></div>', 1)
v5.nav = _nav_with_assets

def _ok(k):
    v5.adm(k)

def _go(k):
    return RedirectResponse(f'/admin/assets?key={k}', 303)

def _esc(s):
    import html
    return html.escape(str(s or ''))

@app.get('/admin/assets', response_class=HTMLResponse)
def assets(key: str = ''):
    _ok(key)
    c = v5.db()
    apps = v5.rows(c, 'SELECT * FROM apps ORDER BY created_at DESC')
    banners = v5.rows(c, 'SELECT * FROM banners ORDER BY created_at DESC')
    walls = v5.rows(c, 'SELECT * FROM wallpapers ORDER BY created_at DESC')
    logos = v5.rows(c, 'SELECT * FROM logos ORDER BY created_at DESC')
    c.close()

    def cards(items, kind):
        out = []
        for r in items:
            extra = _esc(r.get('package_name', '')) if kind == 'app' else _esc(r.get('media_type', ''))
            out.append(
                '<div class="card">'
                f'<b>{_esc(r.get("name"))}</b><br>'
                f'<span class="muted">{extra}</span>'
                f'<form method="post" action="/admin/assets/{kind}/{r["id"]}/delete?key={key}" '
                f'onsubmit="return confirm(\'Excluir {_esc(r.get("name"))}? Esta ação não pode ser desfeita.\')">'
                '<button class="danger" style="margin-top:10px">EXCLUIR</button></form></div>'
            )
        return ''.join(out) or '<div class="card muted">Nenhum item.</div>'

    body = (
        '<div class="hero"><b>Gerenciar exclusões</b>'
        '<p class="muted">Exclua aplicativos, banners e planos de fundo. '
        'Ao excluir, a referência também é retirada dos layouts.</p></div>'
        f'<h2>Aplicativos</h2><div class="grid">{cards(apps, "app")}</div>'
        f'<h2>Banners</h2><div class="grid">{cards(banners, "banner")}</div>'
        f'<h2>Planos de fundo</h2><div class="grid">{cards(walls, "wallpaper")}</div>'
        f'<h2>Logomarcas</h2><div class="grid">{cards(logos, "logo")}</div>'
    )
    return v5.page('Excluir itens', body, key)

def _unlink(filename):
    if filename:
        try:
            (v5.UPLOAD_DIR / Path(filename).name).unlink(missing_ok=True)
        except Exception:
            pass

@app.post('/admin/assets/app/{aid}/delete')
def del_app(aid: str, key: str):
    _ok(key)
    c = v5.db()
    a = v5.one(c, 'SELECT * FROM apps WHERE id=?', (aid,))
    if not a:
        c.close()
        raise HTTPException(404)
    for l in v5.rows(c, 'SELECT id,app_ids FROM layouts'):
        try:
            ids = json.loads(l.get('app_ids') or '[]')
        except Exception:
            ids = []
        ids = [x for x in ids if x != aid and x != a.get('package_name')]
        v5.ex(c, 'UPDATE layouts SET app_ids=? WHERE id=?', (json.dumps(ids), l['id']))
    v5.ex(c, 'DELETE FROM apps WHERE id=?', (aid,))
    c.commit()
    c.close()
    _unlink(a.get('filename'))
    return _go(key)

@app.post('/admin/assets/banner/{bid}/delete')
def del_banner(bid: str, key: str):
    _ok(key)
    c = v5.db()
    b = v5.one(c, 'SELECT * FROM banners WHERE id=?', (bid,))
    if not b:
        c.close()
        raise HTTPException(404)
    for l in v5.rows(c, 'SELECT id,banner_ids FROM layouts'):
        try:
            ids = json.loads(l.get('banner_ids') or '[]')
        except Exception:
            ids = []
        v5.ex(c, 'UPDATE layouts SET banner_ids=? WHERE id=?', (json.dumps([x for x in ids if x != bid]), l['id']))
    v5.ex(c, 'DELETE FROM banners WHERE id=?', (bid,))
    v5.ex(c, 'DELETE FROM media_files WHERE filename=?', (b.get('filename') or '',))
    c.commit()
    c.close()
    _unlink(b.get('filename'))
    return _go(key)

@app.post('/admin/assets/wallpaper/{wid}/delete')
def del_wallpaper(wid: str, key: str):
    _ok(key)
    c = v5.db()
    w = v5.one(c, 'SELECT * FROM wallpapers WHERE id=?', (wid,))
    if not w:
        c.close()
        raise HTTPException(404)
    v5.ex(c, 'UPDATE layouts SET wallpaper_id=NULL WHERE wallpaper_id=?', (wid,))
    v5.ex(c, 'DELETE FROM wallpapers WHERE id=?', (wid,))
    v5.ex(c, 'DELETE FROM media_files WHERE filename=?', (w.get('filename') or '',))
    c.commit()
    c.close()
    _unlink(w.get('filename'))
    return _go(key)

@app.post('/admin/assets/logo/{lid}/delete')
def del_logo(lid: str, key: str):
    _ok(key)
    c = v5.db()
    x = v5.one(c, 'SELECT * FROM logos WHERE id=?', (lid,))
    if not x:
        c.close()
        raise HTTPException(404)
    v5.ex(c, 'UPDATE layouts SET logo_id=NULL WHERE logo_id=?', (lid,))
    v5.ex(c, 'DELETE FROM logos WHERE id=?', (lid,))
    v5.ex(c, 'DELETE FROM media_files WHERE filename=?', (x.get('filename') or '',))
    c.commit()
    c.close()
    _unlink(x.get('filename'))
    return _go(key)
