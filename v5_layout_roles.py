import json
from fastapi import Form, HTTPException
from fastapi.responses import HTMLResponse
from v5 import app, db, rows, one, ex, adm, page, go, now

# Remove the original layout routes so these improved versions take precedence.
def _remove_route(path, methods):
    keep=[]
    wanted=set(methods)
    for r in app.router.routes:
        if getattr(r,'path',None)==path and wanted.intersection(set(getattr(r,'methods',set()) or set())):
            continue
        keep.append(r)
    app.router.routes = keep

_remove_route('/admin/layouts', {'GET'})
_remove_route('/admin/layouts/create', {'POST'})

def _opts(apps, selected=''):
    out=['<option value="">-- vazio --</option>']
    for a in apps:
        sel=' selected' if a['id']==selected else ''
        out.append(f'<option value="{a["id"]}"{sel}>{a["name"]}</option>')
    return ''.join(out)

def _form_slots(apps, selected_ids):
    selected_ids=list(selected_ids or [])[:8]
    selected_ids += ['']*(8-len(selected_ids))
    prim=''.join(f'<label>Primário {i+1}</label><select name="primary_{i+1}">{_opts(apps,selected_ids[i])}</select>' for i in range(3))
    sec=''.join(f'<label>Secundário {i+1}</label><select name="secondary_{i+1}">{_opts(apps,selected_ids[i+3])}</select>' for i in range(5))
    return f'<div class="grid"><div class="card"><h3>Aplicativos primários</h3><p class="muted">Até 3 apps. Eles aparecem na parte de cima.</p>{prim}</div><div class="card"><h3>Aplicativos secundários</h3><p class="muted">Até 5 apps. Eles aparecem na parte de baixo.</p>{sec}</div></div>'

def _chosen(values):
    out=[]
    for x in values:
        x=(x or '').strip()
        if x and x not in out:
            out.append(x)
    return out

@app.get('/admin/layouts', response_class=HTMLResponse)
def layouts_roles(key:str=''):
    adm(key)
    c=db(); ls=rows(c,'SELECT * FROM layouts ORDER BY created_at DESC'); aa=rows(c,'SELECT * FROM apps ORDER BY name'); ww=rows(c,'SELECT * FROM wallpapers ORDER BY name'); bb=rows(c,'SELECT * FROM banners ORDER BY name'); c.close()
    walls='<option value="">Sem fundo</option>'+''.join(f'<option value="{w["id"]}">{w["name"]}</option>' for w in ww)
    bans=''.join(f'<label><input style="width:auto" type="checkbox" name="banner_ids" value="{b["id"]}"> {b["name"]}</label><br>' for b in bb)
    cards=''
    for l in ls:
        ids=json.loads(l.get('app_ids') or '[]')
        cards += f'<div class="card"><b>{l["name"]}</b><br><span class="muted">Primários: {min(3,len(ids))} • Secundários: {max(0,min(5,len(ids)-3))}</span><br><br><a href="/admin/layouts/{l["id"]}/edit?key={key}">Editar layout</a></div>'
    form=f'''<div class="card"><form method="post" action="/admin/layouts/create?key={key}">
    <input name="name" placeholder="Nome do layout" required>
    <select name="wallpaper_id">{walls}</select>
    <input name="logo_url" placeholder="URL da logo">
    {_form_slots(aa,[])}
    <h3>Banners</h3>{bans}
    <button>ADD LAYOUT</button></form></div>'''
    return page('Meus Layouts',form+f'<div class="grid">{cards}</div>',key)

@app.post('/admin/layouts/create')
def layoutcreate_roles(key:str,name:str=Form(...),wallpaper_id:str=Form(''),logo_url:str=Form(''),banner_ids:list[str]=Form(default=[]),primary_1:str=Form(''),primary_2:str=Form(''),primary_3:str=Form(''),secondary_1:str=Form(''),secondary_2:str=Form(''),secondary_3:str=Form(''),secondary_4:str=Form(''),secondary_5:str=Form('')):
    adm(key)
    ids=_chosen([primary_1,primary_2,primary_3,secondary_1,secondary_2,secondary_3,secondary_4,secondary_5])
    c=db(); ex(c,'INSERT INTO layouts(id,name,app_ids,created_at,wallpaper_id,banner_ids,logo_url) VALUES(?,?,?,?,?,?,?)',(__import__('secrets').token_hex(8),name.strip(),json.dumps(ids),now(),wallpaper_id or None,json.dumps(banner_ids),logo_url.strip())); c.commit(); c.close()
    return go('/admin/layouts',key)

@app.get('/admin/layouts/{lid}/edit', response_class=HTMLResponse)
def layoutedit(lid:str,key:str=''):
    adm(key)
    c=db(); l=one(c,'SELECT * FROM layouts WHERE id=?',(lid,)); aa=rows(c,'SELECT * FROM apps ORDER BY name'); ww=rows(c,'SELECT * FROM wallpapers ORDER BY name'); bb=rows(c,'SELECT * FROM banners ORDER BY name'); c.close()
    if not l: raise HTTPException(404,'layout não encontrado')
    ids=json.loads(l.get('app_ids') or '[]')
    selected_b=set(json.loads(l.get('banner_ids') or '[]'))
    walls='<option value="">Sem fundo</option>'+''.join(f'<option value="{w["id"]}" {"selected" if l.get("wallpaper_id")==w["id"] else ""}>{w["name"]}</option>' for w in ww)
    bans=''.join(f'<label><input style="width:auto" type="checkbox" name="banner_ids" value="{b["id"]}" {"checked" if b["id"] in selected_b else ""}> {b["name"]}</label><br>' for b in bb)
    body=f'''<div class="card"><form method="post" action="/admin/layouts/{lid}/edit?key={key}">
    <input name="name" value="{l["name"]}" required>
    <select name="wallpaper_id">{walls}</select>
    <input name="logo_url" value="{l.get("logo_url") or ""}" placeholder="URL da logo">
    {_form_slots(aa,ids)}
    <h3>Banners</h3>{bans}
    <button>Salvar layout</button></form></div>'''
    return page('Editar layout',body,key)

@app.post('/admin/layouts/{lid}/edit')
def layoutsave(lid:str,key:str,name:str=Form(...),wallpaper_id:str=Form(''),logo_url:str=Form(''),banner_ids:list[str]=Form(default=[]),primary_1:str=Form(''),primary_2:str=Form(''),primary_3:str=Form(''),secondary_1:str=Form(''),secondary_2:str=Form(''),secondary_3:str=Form(''),secondary_4:str=Form(''),secondary_5:str=Form('')):
    adm(key)
    ids=_chosen([primary_1,primary_2,primary_3,secondary_1,secondary_2,secondary_3,secondary_4,secondary_5])
    c=db(); ex(c,'UPDATE layouts SET name=?,app_ids=?,wallpaper_id=?,banner_ids=?,logo_url=? WHERE id=?',(name.strip(),json.dumps(ids),wallpaper_id or None,json.dumps(banner_ids),logo_url.strip(),lid)); c.commit(); c.close()
    return go('/admin/layouts',key)
