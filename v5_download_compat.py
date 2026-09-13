from fastapi import File, UploadFile
from fastapi.responses import RedirectResponse
import v5
import v5_base2_apk_storage as storage
import v5_base2_apps as base2apps


def persistent_download(aid: str):
    return storage.base2_download_apk(aid)


def persistent_upload(key: str, apk: UploadFile = File(...)):
    v5.adm(key)
    base2apps.save_app(apk, '')
    return RedirectResponse('/admin/apps?key=' + key, 303)


def add_priority_route(path, endpoint, methods):
    v5.app.add_api_route(path, endpoint, methods=methods)
    route = v5.app.router.routes.pop()
    v5.app.router.routes.insert(0, route)


add_priority_route('/admin/apps/upload', persistent_upload, ['POST'])
add_priority_route('/api/apps/{aid}/download', persistent_download, ['GET'])
