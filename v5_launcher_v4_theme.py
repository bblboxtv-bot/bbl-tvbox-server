from fastapi import File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
import v5

app = v5.app
MAX_IMAGE_BYTES = 12 * 1024 * 1024


def _init():
    c = v5.db()
    try:
        v5.ex(c, "CREATE TABLE IF NOT EXISTS launcher_v4_theme(id TEXT PRIMARY KEY, wallpaper_filename TEXT NOT NULL DEFAULT '', banner_filename TEXT NOT NULL DEFAULT '', updated_at TEXT)")
        c.commit()
        for sql in [
            "ALTER TABLE launcher_v4_theme ADD COLUMN wallpaper_data BYTEA",
            "ALTER TABLE launcher_v4_theme ADD COLUMN wallpaper_mime TEXT NOT NULL DEFAULT 'image/jpeg'",
            "ALTER TABLE launcher_v4_theme ADD COLUMN banner_data BYTEA",
            "ALTER TABLE launcher_v4_theme ADD COLUMN banner_mime TEXT NOT NULL DEFAULT 'image/jpeg'"
        ]:
            try:
                v5.ex(c, sql); c.commit()
            except Exception:
                c.rollback()
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


def _bytes(v):
    if v is None:
        return b''
    if isinstance(v, memoryview):
        return v.tobytes()
    return bytes(v)


def _image_response(kind: str):
    t = _theme()
    data = _bytes(t.get(kind + '_data'))
    if data:
        mime = t.get(kind + '_mime') or 'image/jpeg'
        return Response(content=data, media_type=mime, headers={'Cache-Control':'no-store, no-cache, must-revalidate, max-age=0'})
    # Compatibilidade com imagens antigas ainda presentes no disco.
    fn = t.get(kind + '_filename') or ''
    if fn:
        p = v5.UPLOAD_DIR / fn
        if p.exists():
            return Response(content=p.read_bytes(), media_type='image/jpeg', headers={'Cache-Control':'no-store, no-cache, must-revalidate, max-age=0'})
    raise HTTPException(404, 'imagem não disponível')


@app.get('/api/launcher-v4/theme')
def launcher_v4_theme():
    t = _theme()
    version = (t.get('updated_at') or '').replace(':','').replace('+','').replace('.','')
    has_wall = bool(_bytes(t.get('wallpaper_data'))) or bool(t.get('wallpaper_filename'))
    has_banner = bool(_bytes(t.get('banner_data'))) or bool(t.get('banner_filename'))
    return {
        'wallpaper_url': f'/api/launcher-v4/wallpaper?v={version}' if has_wall else '',
        'banner_url': f'/api/launcher-v4/banner?v={version}' if has_banner else '',
        'updated_at': t.get('updated_at') or ''
    }


@app.get('/api/launcher-v4/wallpaper')
def launcher_v4_wallpaper():
    return _image_response('wallpaper')


@app.get('/api/launcher-v4/banner')
def launcher_v4_banner():
    return _image_response('banner')


@app.get('/admin/launcher-v4', response_class=HTMLResponse)
def launcher_v4_admin(key: str = ''):
    v5.adm(key)
    t = _theme()
    version = (t.get('updated_at') or '').replace(':','').replace('+','').replace('.','')
    has_wall = bool(_bytes(t.get('wallpaper_data'))) or bool(t.get('wallpaper_filename'))
    has_banner = bool(_bytes(t.get('banner_data'))) or bool(t.get('banner_filename'))
    wall_preview = f'<img src="/api/launcher-v4/wallpaper?v={version}" style="max-height:260px;border-radius:12px">' if has_wall else '<span class="muted">Nenhum fundo enviado.</span>'
    banner_preview = f'<img src="/api/launcher-v4/banner?v={version}" style="max-height:220px;border-radius:12px">' if has_banner else '<span class="muted">Nenhum banner enviado.</span>'
    body = f'''<div class="hero"><b>Aparência da Launcher V4</b><p class="muted">Fundo e banner ficam gravados no banco de dados e não somem quando o servidor reinicia.</p></div>
    <div class="grid">
      <div class="card"><h2>Plano de fundo</h2>{wall_preview}<form method="post" enctype="multipart/form-data" action="/admin/launcher-v4/wallpaper?key={key}"><input type="file" name="file" accept="image/jpeg,image/png,image/webp" required><button class="good">ENVIAR FUNDO</button></form></div>
      <div class="card"><h2>Banner principal</h2>{banner_preview}<form method="post" enctype="multipart/form-data" action="/admin/launcher-v4/banner?key={key}"><input type="file" name="file" accept="image/jpeg,image/png,image/webp" required><button class="good">ENVIAR BANNER</button></form></div>
    </div>
    <div class="card"><form method="post" action="/admin/launcher-v4/clear?key={key}"><button class="danger">REMOVER FUNDO E BANNER PERSONALIZADOS</button></form></div>'''
    return v5.page('Launcher V4', body, key)


async def _read_image(file: UploadFile):
    mime = (file.content_type or '').lower()
    if mime not in ('image/jpeg','image/png','image/webp'):
        raise HTTPException(400, 'Envie JPG, PNG ou WEBP')
    data = await file.read()
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(400, 'Imagem vazia ou maior que 12 MB')
    return data, mime


@app.post('/admin/launcher-v4/wallpaper')
async def set_launcher_v4_wallpaper(key: str, file: UploadFile = File(...)):
    v5.adm(key)
    data, mime = await _read_image(file)
    c = v5.db()
    try:
        v5.ex(c, "UPDATE launcher_v4_theme SET wallpaper_data=?,wallpaper_mime=?,wallpaper_filename='',updated_at=? WHERE id='global'", (data, mime, v5.now()))
        c.commit()
    finally:
        c.close()
    return RedirectResponse(f'/admin/launcher-v4?key={key}', 303)


@app.post('/admin/launcher-v4/banner')
async def set_launcher_v4_banner(key: str, file: UploadFile = File(...)):
    v5.adm(key)
    data, mime = await _read_image(file)
    c = v5.db()
    try:
        v5.ex(c, "UPDATE launcher_v4_theme SET banner_data=?,banner_mime=?,banner_filename='',updated_at=? WHERE id='global'", (data, mime, v5.now()))
        c.commit()
    finally:
        c.close()
    return RedirectResponse(f'/admin/launcher-v4?key={key}', 303)


@app.post('/admin/launcher-v4/clear')
def clear_launcher_v4_theme(key: str):
    v5.adm(key)
    c = v5.db()
    try:
        v5.ex(c, "UPDATE launcher_v4_theme SET wallpaper_filename='',banner_filename='',wallpaper_data=NULL,banner_data=NULL,updated_at=? WHERE id='global'", (v5.now(),))
        c.commit()
    finally:
        c.close()
    return RedirectResponse(f'/admin/launcher-v4?key={key}', 303)
