from fastapi import File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
import v5

app = v5.app


def _init():
    c = v5.db()
    try:
        v5.ex(c, "CREATE TABLE IF NOT EXISTS launcher_v4_theme(id TEXT PRIMARY KEY, wallpaper_filename TEXT NOT NULL DEFAULT '', banner_filename TEXT NOT NULL DEFAULT '', updated_at TEXT)")
        row = v5.one(c, "SELECT id FROM launcher_v4_theme WHERE id='global'")
        if not row:
            v5.ex(c, "INSERT INTO launcher_v4_theme(id,updated_at) VALUES('global',?)", (v5.now(),))
        c.commit()
    finally:
        c.close()

_init()

_base_nav = v5.nav
def _nav(k):
    base = _base_nav(k)
    if 'Launcher V4' in base:
        return base
    return base.replace('</div>', f'<a href="/admin/launcher-v4?key={k}">Launcher V4</a></div>', 1)
v5.nav = _nav


def _theme():
    c = v5.db()
    try:
        return v5.one(c, "SELECT * FROM launcher_v4_theme WHERE id='global'") or {}
    finally:
        c.close()

@app.get('/api/launcher-v4/theme')
def launcher_v4_theme():
    t = _theme()
    wf = t.get('wallpaper_filename') or ''
    bf = t.get('banner_filename') or ''
    return {
        'wallpaper_url': f'/api/media/{wf}' if wf else '',
        'banner_url': f'/api/media/{bf}' if bf else '',
        'updated_at': t.get('updated_at') or ''
    }

@app.get('/admin/launcher-v4', response_class=HTMLResponse)
def launcher_v4_admin(key: str = ''):
    v5.adm(key)
    t = _theme()
    wf = t.get('wallpaper_filename') or ''
    bf = t.get('banner_filename') or ''
    wall_preview = f'<img src="/api/media/{wf}" style="max-height:260px;border-radius:12px">' if wf else '<span class="muted">Nenhum fundo enviado.</span>'
    banner_preview = f'<img src="/api/media/{bf}" style="max-height:220px;border-radius:12px">' if bf else '<span class="muted">Nenhum banner enviado.</span>'
    body = f'''<div class="hero"><b>Aparência da Launcher V4</b><p class="muted">Troque o fundo e o banner da launcher sem gerar outro APK. A TV Box busca estas alterações automaticamente.</p></div>
    <div class="grid">
      <div class="card"><h2>Plano de fundo</h2>{wall_preview}<form method="post" enctype="multipart/form-data" action="/admin/launcher-v4/wallpaper?key={key}"><input type="file" name="file" accept="image/*" required><button class="good">ENVIAR FUNDO</button></form></div>
      <div class="card"><h2>Banner principal</h2>{banner_preview}<form method="post" enctype="multipart/form-data" action="/admin/launcher-v4/banner?key={key}"><input type="file" name="file" accept="image/*" required><button class="good">ENVIAR BANNER</button></form></div>
    </div>
    <div class="card"><form method="post" action="/admin/launcher-v4/clear?key={key}"><button class="danger">REMOVER FUNDO E BANNER PERSONALIZADOS</button></form></div>'''
    return v5.page('Launcher V4', body, key)

@app.post('/admin/launcher-v4/wallpaper')
def set_launcher_v4_wallpaper(key: str, file: UploadFile = File(...)):
    v5.adm(key)
    fn = v5.save(file, 'launcherv4_wallpaper', {'.jpg','.jpeg','.png','.webp'})
    c = v5.db()
    try:
        v5.ex(c, "UPDATE launcher_v4_theme SET wallpaper_filename=?,updated_at=? WHERE id='global'", (fn, v5.now()))
        c.commit()
    finally:
        c.close()
    return RedirectResponse(f'/admin/launcher-v4?key={key}', 303)

@app.post('/admin/launcher-v4/banner')
def set_launcher_v4_banner(key: str, file: UploadFile = File(...)):
    v5.adm(key)
    fn = v5.save(file, 'launcherv4_banner', {'.jpg','.jpeg','.png','.webp'})
    c = v5.db()
    try:
        v5.ex(c, "UPDATE launcher_v4_theme SET banner_filename=?,updated_at=? WHERE id='global'", (fn, v5.now()))
        c.commit()
    finally:
        c.close()
    return RedirectResponse(f'/admin/launcher-v4?key={key}', 303)

@app.post('/admin/launcher-v4/clear')
def clear_launcher_v4_theme(key: str):
    v5.adm(key)
    c = v5.db()
    try:
        v5.ex(c, "UPDATE launcher_v4_theme SET wallpaper_filename='',banner_filename='',updated_at=? WHERE id='global'", (v5.now(),))
        c.commit()
    finally:
        c.close()
    return RedirectResponse(f'/admin/launcher-v4?key={key}', 303)
