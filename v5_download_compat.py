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
    import v5_base2_apps as base2apps
    base2apps.save_app(apk, name)
    return RedirectResponse('/admin/apps?key=' + key, 303)

def add_priority_route(path, endpoint, methods):
    v5.app.add_api_route(path, endpoint, methods=methods)
    route = v5.app.router.routes.pop()
    v5.app.router.routes.insert(0, route)


add_priority_route('/admin/apps/upload', persistent_upload, ['POST'])
add_priority_route('/api/apps/{aid}/download', persistent_download, ['GET'])
