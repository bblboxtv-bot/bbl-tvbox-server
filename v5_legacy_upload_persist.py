from fastapi import File, UploadFile
from fastapi.responses import RedirectResponse
import v5
import v5_base2_apps as base2apps


def persistent_legacy_upload(key: str, apk: UploadFile = File(...)):
    v5.adm(key)
    base2apps.save_app(apk, '')
    return RedirectResponse('/admin/apps?key=' + key, 303)

v5.app.add_api_route('/admin/apps/upload', persistent_legacy_upload, methods=['POST'])
route = v5.app.router.routes.pop()
v5.app.router.routes.insert(0, route)
