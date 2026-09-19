import secrets
import hashlib
from fastapi import File, UploadFile, Form
from fastapi.responses import RedirectResponse
import v5
import v5_base2_apk_storage as storage


def persistent_download(aid: str):
    return storage.base2_download_apk(aid)


def persistent_upload(key: str, name: str = Form(''), apk: UploadFile = File(...)):
    v5.adm(key)
    fn = v5.save(apk, 'apk', {'.apk'})
    p = v5.UPLOAD_DIR / fn
    m = v5.apkmeta(p)
    m['name'] = name.strip() or m['name']
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    c = v5.db()
    v5.ex(c, 'INSERT INTO apps(id,name,package_name,version_name,version_code,filename,size_bytes,sha256,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
          (secrets.token_hex(8),m['name'],m['package_name'],m['version_name'],m['version_code'],fn,p.stat().st_size,h,v5.now()))
    c.commit()
    c.close()
    return RedirectResponse('/admin/apps?key=' + key, 303)


def add_priority_route(path, endpoint, methods):
    v5.app.add_api_route(path, endpoint, methods=methods)
    route = v5.app.router.routes.pop()
    v5.app.router.routes.insert(0, route)


add_priority_route('/admin/apps/upload', persistent_upload, ['POST'])
add_priority_route('/api/apps/{aid}/download', persistent_download, ['GET'])
