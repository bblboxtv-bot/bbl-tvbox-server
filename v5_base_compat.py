import secrets, time, json
from datetime import datetime, timezone, timedelta
from typing import Any
from fastapi import Request, HTTPException
import v5_reseller_portal as portal
import v5

app = portal.app

def _payload(req_json: Any):
    return req_json if isinstance(req_json, dict) else {}

def _code(d):
    for k in ('activation_code','activationCode','code','license_key','licenseKey','short_code','shortCode'):
        x=str(d.get(k) or '').strip()
        if x:return x
    return ''

def _device(d):
    for k in ('device_id','deviceId','android_id','androidId'):
        x=str(d.get(k) or '').strip()
        if x:return x
    return secrets.token_hex(8).upper()

def _license_response(code='', device_id='', active=True, days=30):
    exp=int((datetime.now(timezone.utc)+timedelta(days=days)).timestamp()*1000)
    tok=secrets.token_urlsafe(32)
    return {
        'ok': True,
        'status': 'active' if active else 'denied',
        'activation_status': 'active' if active else 'denied',
        'activation_type': 'single',
        'enrolled': active,
        'device_id': device_id,
        'license_id': code or secrets.token_hex(8),
        'token': tok,
        'access_token': tok,
        'refresh_token': tok,
        'expires_at_ms': exp,
        'expiresAtMillis': exp,
        'entitlement_expires_at_ms': exp,
        'trial_eligible': True,
        'server_time_ms': int(time.time()*1000),
        'message': 'BBL.BOXTV',
        'license_public_key': '',
        'transport_public_key': '',
        'lease_signature': '',
        'proof_signature': '',
        'signature': ''
    }

@app.api_route('/api/v1/bootstrap/challenge', methods=['GET','POST'])
async def compat_challenge(request: Request):
    try:d=_payload(await request.json())
    except Exception:d={}
    nonce=secrets.token_urlsafe(24)
    out=_license_response(device_id=_device(d))
    out.update({'challenge':nonce,'nonce':nonce,'bootstrap':'bootstrap-v1'})
    return out

@app.post('/api/v1/bootstrap/enroll')
async def compat_enroll(request: Request):
    try:d=_payload(await request.json())
    except Exception:d={}
    code=_code(d); did=_device(d)
    if code:
        c=v5.db(); k=v5.one(c,'SELECT * FROM activation_keys WHERE key=? AND enabled=1',(code,))
        if not k:
            c.close(); raise HTTPException(403,'activation_denied')
        dev=v5.one(c,'SELECT * FROM devices WHERE id=?',(did,))
        if not dev:
            token=secrets.token_urlsafe(32)
            v5.ex(c,'INSERT INTO devices(id,token,activation_key,created_at,last_seen) VALUES(?,?,?,?,?)',(did,token,code,v5.now(),v5.now()))
            c.commit()
        c.close()
    return _license_response(code,did,True)

@app.post('/api/v1/license/single/redeem')
async def compat_redeem(request: Request):
    try:d=_payload(await request.json())
    except Exception:d={}
    code=_code(d); did=_device(d)
    if not code: raise HTTPException(400,'activation_code required')
    c=v5.db(); k=v5.one(c,'SELECT * FROM activation_keys WHERE key=? AND enabled=1',(code,))
    if not k:
        c.close(); raise HTTPException(403,'activation_denied')
    dev=v5.one(c,'SELECT * FROM devices WHERE id=?',(did,))
    if not dev:
        token=secrets.token_urlsafe(32)
        v5.ex(c,'INSERT INTO devices(id,token,activation_key,created_at,last_seen) VALUES(?,?,?,?,?)',(did,token,code,v5.now(),v5.now()))
    c.commit(); c.close()
    return _license_response(code,did,True)

@app.post('/api/v1/license/trial')
async def compat_trial(request: Request):
    try:d=_payload(await request.json())
    except Exception:d={}
    out=_license_response('trial',_device(d),True,1)
    out['activation_type']='trial'; return out

@app.api_route('/api/v1/license/refresh', methods=['GET','POST'])
async def compat_refresh(request: Request):
    try:d=_payload(await request.json())
    except Exception:d={}
    return _license_response(_code(d),_device(d),True)

@app.api_route('/api/v1/device/status', methods=['GET','POST'])
async def compat_status(request: Request):
    try:d=_payload(await request.json())
    except Exception:d={}
    did=_device(d)
    active=True
    c=v5.db(); dev=v5.one(c,'SELECT * FROM devices WHERE id=?',(did,)); c.close()
    if dev: active=not bool(dev.get('locked'))
    return _license_response(_code(d),did,active)
