from fastapi.responses import HTMLResponse
import v5_base2_gate as gate
import v5_base2_reseller_portal as reseller

_old_admin_page = gate.page
def _admin_page(title, body, nav=True):
    r = _old_admin_page(title, body, nav)
    if nav and isinstance(r, HTMLResponse):
        txt = r.body.decode('utf-8')
        if '/base2/painel/aplicativos' not in txt:
            txt = txt.replace('<a href="/base2/painel/gerenciar">Testes / Excluir</a>', '<a href="/base2/painel/aplicativos">Aplicativos</a><a href="/base2/painel/gerenciar">Testes / Excluir</a>')
        return HTMLResponse(txt, status_code=r.status_code)
    return r
gate.page = _admin_page

_old_reseller_page = reseller.page
def _reseller_page(title, body, nav=True):
    r = _old_reseller_page(title, body, nav)
    if nav and isinstance(r, HTMLResponse):
        txt = r.body.decode('utf-8')
        if '/base2/revenda/aplicativos' not in txt:
            txt = txt.replace('<a href="/base2/revenda/gerenciar">Testes / Excluir</a>', '<a href="/base2/revenda/aplicativos">Aplicativos</a><a href="/base2/revenda/gerenciar">Testes / Excluir</a>')
        return HTMLResponse(txt, status_code=r.status_code)
    return r
reseller.page = _reseller_page
