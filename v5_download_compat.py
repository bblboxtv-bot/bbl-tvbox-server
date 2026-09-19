import secrets
import hashlib
from fastapi import File, UploadFile, Form, HTTPException
from fastapi.responses import RedirectResponse, Response, FileResponse
import v5
import v5_base2_apk_storage as storage


def persistent_download(aid: str):
    # 1) Fonte atual/persistente do painel V5.
    c = v5.db()
    a = v5.one(c, 'SELECT * FROM apps WHERE id=?', (aid,))
    if a:
        m = v5.one(c, 'SELECT mime_type,data FROM media_files WHERE filename=?', (a.get('filename') or '',))
        c.close()
        if m and m.get('data') is not None:
            return Response(
                content=bytes(m['data']),
                media_type=m.get('mime_type') or 'application/vnd.android.package-archive',
                headers={'Content-Disposition': f'attachment; filename="{a.get("filename") or "app.apk"}"'}
            )
        p = v5.UPLOAD_DIR / (a.get('filename') or '')
        if p.exists():
            return FileResponse(
                p,
                media_type='application/vnd.android.package-archive',
                filename=a.get('filename') or 'app.apk'
            )
    else:
        c.close()

    # 2) Compatibilidade com o armazenamento legado Base2, se ainda existir.
    try:
        return storage.base2_download_apk(aid)
    except HTTPException as e:
        if e.status_code != 404:
            raise

    raise HTTPException(404, 'Arquivo APK não disponível. Reenvie este APK no painel.')


def persistent_upload(key: str, name: str = Form(''), apk: UploadFile = File(...)):
    v5.adm(key)
    fn = v5.save(apk, 'apk', {'.apk'})
    p = v5.UPLOAD_DIR / fn
    size = p.stat().st_size
    if size > 120 * 1024 * 1024:
        p.unlink(missing_ok=True)
        raise HTTPException(413, 'APK maior que 120 MB')

    m = v5.apkmeta(p)
    m['name'] = name.strip() or m['name']
    data = p.read_bytes()
    h = hashlib.sha256(data).hexdigest()

    c = v5.db()
    used = v5.one(c, "SELECT COALESCE(SUM(size_bytes),0) total FROM media_files WHERE filename LIKE 'apk_%%'") or {'total': 0}
    if int(used.get('total') or 0) + size > 450 * 1024 * 1024:
        c.close()
        p.unlink(missing_ok=True)
        raise HTTPException(507, 'Limite seguro de 450 MB para APKs persistentes atingido')

    aid = secrets.token_hex(8)
    v5.ex(c, 'INSERT INTO apps(id,name,package_name,version_name,version_code,filename,size_bytes,sha256,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
          (aid, m['name'], m['package_name'], m['version_name'], m['version_code'], fn, size, h, v5.now()))
    v5.ex(c, 'INSERT INTO media_files(filename,mime_type,size_bytes,data,created_at) VALUES(?,?,?,?,?)',
          (fn, 'application/vnd.android.package-archive', size, data, v5.now()))
    c.commit()
    c.close()
    return RedirectResponse('/admin/apps?key=' + key, 303)


def add_priority_route(path, endpoint, methods):
    v5.app.add_api_route(path, endpoint, methods=methods)
    route = v5.app.router.routes.pop()
    v5.app.router.routes.insert(0, route)


add_priority_route('/admin/apps/upload', persistent_upload, ['POST'])
add_priority_route('/api/apps/{aid}/download', persistent_download, ['GET'])
