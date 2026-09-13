import os
import secrets
from v5_base_compat import app
import v5_reseller_portal as portal
import v5_base2_gate
import v5_base2_reseller_portal
import v5_base2_tools
import v5_base2_apps
import v5_base2_apps_nav
import v5_base2_apps_list
import v5_base2_apk_storage
import v5_download_compat
import v5
import v5_tudo_liberado_integration


def _seed_reseller_admin():
    username = (os.getenv('RESELLER_ADMIN_USER') or '').strip()
    password = os.getenv('RESELLER_ADMIN_PASSWORD') or ''
    name = (os.getenv('RESELLER_ADMIN_NAME') or 'BBL.BOXTV').strip()
    if not username or not password:
        return
    c = v5.db()
    existing = v5.one(c, 'SELECT * FROM reseller_accounts WHERE lower(username)=lower(?)', (username,))
    pwd = portal.phash(password)
    if existing:
        v5.ex(c, 'UPDATE reseller_accounts SET name=?,password_hash=?,enabled=1,parent_id=NULL,can_create_resellers=1,max_clients=9999,max_resellers=9999 WHERE id=?', (name,pwd,existing['id']))
        v5.ex(c, 'DELETE FROM reseller_sessions WHERE reseller_id=?', (existing['id'],))
    else:
        v5.ex(c, 'INSERT INTO reseller_accounts(id,parent_id,name,username,password_hash,enabled,can_create_resellers,max_clients,max_resellers,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)', (secrets.token_hex(8),None,name,username,pwd,1,1,9999,9999,portal.now()))
    c.commit(); c.close()


_seed_reseller_admin()
