from fastapi import HTTPException
import v5
import v5_base2_apk_storage as storage


def _persistent_download(aid: str):
    return storage.base2_download_apk(aid)


def _add_priority_route(path, endpoint, methods):
    v5.app.add_api_route(path, endpoint, methods=methods)
    route = v5.app.router.routes.pop()
    v5.app.router.routes.insert(0, route)


_add_priority_route('/api/apps/{aid}/download', _persistent_download, ['GET'])
