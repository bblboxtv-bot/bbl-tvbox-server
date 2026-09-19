import os
import secrets
import time
import psycopg
from psycopg.conninfo import conninfo_to_dict

# TEMPORARY emergency cleanup approved by admin.
# Runs before panel imports and clears only obsolete APK binary storage.
_dburl=(os.getenv('DATABASE_URL') or '').replace('postgres://','postgresql://',1)
_cleanup_ok=False
_cleanup_last=None
for _attempt in range(40):
    for _mode in ('internal','external'):
        c=None
        try:
            params=conninfo_to_dict(_dburl)
            host=(params.get('host') or '').strip()
            if _mode=='external' and host.startswith('dpg-') and '.' not in host:
                params['host']=host+'.virginia-postgres.render.com'
                params['sslmode']='require'
            params['connect_timeout']='2'
            c=psycopg.connect(autocommit=False,**params)
            print('CLEANUP_CONNECTED',_mode)
            for _table in ('base2_app_chunks','base2_app_blobs','base2_app_files'):
                try:
                    cur=c.cursor()
                    cur.execute(f'TRUNCATE TABLE {_table}')
                    c.commit()
                    print('CLEANUP_OK',_table)
                except Exception as _e:
                    try:c.rollback()
                    except Exception:pass
                    print('CLEANUP_TABLE_ERROR',_table,type(_e).__name__,str(_e))
            try:c.close()
            except Exception:pass
            _cleanup_ok=True
            break
        except Exception as _e:
            _cleanup_last=_e
            try:
                if c:c.close()
            except Exception:pass
            print('CLEANUP_CONNECT_RETRY',_attempt+1,_mode,type(_e).__name__,str(_e))
    if _cleanup_ok:
        break
    time.sleep(1)
if not _cleanup_ok:
    print('CLEANUP_GAVE_UP',type(_cleanup_last).__name__ if _cleanup_last else 'unknown',str(_cleanup_last) if _cleanup_last else '')

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
import v5_base2_legacy_panel
import v5_tudo_liberado_integration
import v5_base2_client_apps_manage
import v5_launcher_v4_theme
import v5_activation_code_panel


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
