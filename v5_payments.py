import os, json, secrets, hashlib, hmac
from datetime import datetime, timezone, timedelta
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError
from typing import Optional

from fastapi import HTTPException, Header, Request
from pydantic import BaseModel

import v5

MP_ACCESS_TOKEN = (os.getenv('MERCADO_PAGO_ACCESS_TOKEN') or '').strip()
MP_WEBHOOK_SECRET = (os.getenv('MERCADO_PAGO_WEBHOOK_SECRET') or '').strip()
MP_PAYER_EMAIL = (os.getenv('MERCADO_PAGO_PAYER_EMAIL') or 'cliente@bbl.boxtv').strip()
MP_NOTIFICATION_URL = (os.getenv('MERCADO_PAGO_NOTIFICATION_URL') or '').strip()

INFINITEPAY_HANDLE = (os.getenv('INFINITEPAY_HANDLE') or '').strip().lstrip('$')
INFINITEPAY_WEBHOOK_URL = (os.getenv('INFINITEPAY_WEBHOOK_URL') or '').strip()
INFINITEPAY_REDIRECT_URL = (os.getenv('INFINITEPAY_REDIRECT_URL') or '').strip()

DEFAULT_PRICE_CENTS = int(os.getenv('BBL_PAYMENT_PRICE_CENTS') or '3500')
DEFAULT_DAYS = int(os.getenv('BBL_PAYMENT_DAYS') or '30')


def _now():
    return datetime.now(timezone.utc).isoformat()


def _payments_enabled():
    return bool(INFINITEPAY_HANDLE or MP_ACCESS_TOKEN)


def init_payments():
    c = v5.db()
    stmts = [
        "CREATE TABLE IF NOT EXISTS payments(id TEXT PRIMARY KEY,device_id TEXT NOT NULL,provider TEXT NOT NULL DEFAULT 'mercadopago',provider_payment_id TEXT,external_reference TEXT UNIQUE NOT NULL,amount_cents INTEGER NOT NULL,status TEXT NOT NULL DEFAULT 'pending',qr_code TEXT NOT NULL DEFAULT '',qr_code_base64 TEXT NOT NULL DEFAULT '',ticket_url TEXT NOT NULL DEFAULT '',created_at TEXT,updated_at TEXT,approved_at TEXT,expires_at TEXT)",
        "CREATE INDEX IF NOT EXISTS idx_payments_device ON payments(device_id)",
        "CREATE INDEX IF NOT EXISTS idx_payments_provider_id ON payments(provider_payment_id)",
        "CREATE INDEX IF NOT EXISTS idx_payments_external_reference ON payments(external_reference)"
    ]
    for s in stmts:
        try:
            v5.ex(c, s); c.commit()
        except Exception:
            c.rollback()
    for s in [
        "ALTER TABLE devices ADD COLUMN payment_price_cents INTEGER NOT NULL DEFAULT 3500",
        "ALTER TABLE devices ADD COLUMN payment_days INTEGER NOT NULL DEFAULT 30"
    ]:
        try:
            v5.ex(c, s); c.commit()
        except Exception:
            c.rollback()
    c.close()


def _json_request(method, url, body=None, headers=None, timeout=20):
    data = None if body is None else json.dumps(body).encode('utf-8')
    h = {'Accept': 'application/json', 'Content-Type': 'application/json'}
    if headers:
        h.update(headers)
    req = urlrequest.Request(url, data=data, headers=h, method=method)
    try:
        with urlrequest.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode('utf-8')
            return json.loads(raw) if raw else {}
    except HTTPError as e:
        raw = e.read().decode('utf-8', errors='replace')
        try:
            detail = json.loads(raw)
        except Exception:
            detail = raw
        raise HTTPException(502, {'upstream_status': e.code, 'detail': detail})
    except URLError as e:
        raise HTTPException(502, f'falha ao conectar ao provedor: {e.reason}')


def _mp(method, path, body=None, idempotency_key=None):
    if not MP_ACCESS_TOKEN:
        raise HTTPException(503, 'Mercado Pago ainda não configurado no servidor')
    headers = {'Authorization': f'Bearer {MP_ACCESS_TOKEN}'}
    if idempotency_key:
        headers['X-Idempotency-Key'] = idempotency_key
    return _json_request(method, 'https://api.mercadopago.com' + path, body, headers)


def _infinite_create_link(order_nsu, amount_cents, description):
    if not INFINITEPAY_HANDLE:
        raise HTTPException(503, 'InfinitePay ainda não configurada no servidor')
    body = {
        'handle': INFINITEPAY_HANDLE,
        'order_nsu': order_nsu,
        'items': [{
            'quantity': 1,
            'price': int(amount_cents),
            'description': description[:120]
        }]
    }
    if INFINITEPAY_WEBHOOK_URL:
        body['webhook_url'] = INFINITEPAY_WEBHOOK_URL
    if INFINITEPAY_REDIRECT_URL:
        body['redirect_url'] = INFINITEPAY_REDIRECT_URL
    out = _json_request('POST', 'https://api.checkout.infinitepay.io/links', body)
    url = (out.get('url') or '').strip()
    if not url.startswith('https://'):
        raise HTTPException(502, {'provider': 'infinitepay', 'detail': 'checkout sem URL válida'})
    return out


def _infinite_payment_check(order_nsu, transaction_nsu, slug):
    if not INFINITEPAY_HANDLE:
        return {'success': False, 'paid': False}
    body = {
        'handle': INFINITEPAY_HANDLE,
        'order_nsu': order_nsu,
        'transaction_nsu': transaction_nsu,
        'slug': slug
    }
    return _json_request('POST', 'https://api.checkout.infinitepay.io/payment_check', body)


def _auth_device(did, authorization):
    c = v5.db()
    d = v5.authdev(c, did, authorization)
    return c, d


def _payment_payload(r):
    if not r:
        return {'enabled': _payments_enabled(), 'status': 'none'}
    provider = r.get('provider') or 'mercadopago'
    ticket_url = r.get('ticket_url') or ''
    return {
        'enabled': _payments_enabled(),
        'id': r.get('id'),
        'provider': provider,
        'status': r.get('status') or 'pending',
        'amount_cents': int(r.get('amount_cents') or 0),
        'amount': round(int(r.get('amount_cents') or 0) / 100.0, 2),
        'qr_code': r.get('qr_code') or '',
        'qr_code_base64': r.get('qr_code_base64') or '',
        'ticket_url': ticket_url,
        'checkout_url': ticket_url if provider == 'infinitepay' else '',
        'qr_content': ticket_url if provider == 'infinitepay' else (r.get('qr_code') or ''),
        'provider_payment_id': r.get('provider_payment_id') or '',
        'order_nsu': r.get('external_reference') or '',
        'expires_at': r.get('expires_at') or ''
    }


def latest_payment_for_device(c, did):
    return v5.one(c, 'SELECT * FROM payments WHERE device_id=? ORDER BY created_at DESC LIMIT 1', (did,))


def _billing_for_device(c, d):
    plan = None
    if d.get('plan_id'):
        plan = v5.one(c, 'SELECT * FROM plans WHERE id=?', (d.get('plan_id'),))
    if plan:
        return {
            'plan_id': plan.get('id'),
            'plan_name': plan.get('name') or '',
            'price_cents': int(plan.get('price_cents') or 0),
            'days': int(plan.get('days') or DEFAULT_DAYS)
        }
    return {
        'plan_id': None,
        'plan_name': '',
        'price_cents': int(d.get('payment_price_cents') or DEFAULT_PRICE_CENTS),
        'days': int(d.get('payment_days') or DEFAULT_DAYS)
    }


def payment_state_for_policy(c, d):
    p = latest_payment_for_device(c, d.get('id'))
    out = _payment_payload(p)
    out.update(_billing_for_device(c, d))
    return out


def _unlock_payment(c, p, provider_id=''):
    d = v5.one(c, 'SELECT * FROM devices WHERE id=?', (p['device_id'],))
    if not d:
        raise HTTPException(404, 'device não encontrado')
    days = int(_billing_for_device(c, d).get('days') or DEFAULT_DAYS)
    base = datetime.now(timezone.utc)
    if d.get('expires_at'):
        try:
            old = datetime.fromisoformat(str(d['expires_at']).replace('Z', '+00:00'))
            if old > base:
                base = old
        except Exception:
            pass
    new_exp = (base + timedelta(days=days)).isoformat()
    v5.ex(c, 'UPDATE devices SET locked=0,expires_at=? WHERE id=?', (new_exp, p['device_id']))
    v5.ex(c, 'UPDATE payments SET status=?,updated_at=?,approved_at=?,provider_payment_id=? WHERE id=?',
          ('approved', _now(), _now(), provider_id or p.get('provider_payment_id') or '', p['id']))
    try:
        v5.log(c, p['device_id'], 'payment_approved', f'{p.get("provider")}:{provider_id}:unlocked:{new_exp}')
    except Exception:
        pass
    return new_exp


class PaymentCreateBody(BaseModel):
    force_new: bool = False


@v5.app.post('/api/devices/{did}/payment/pix')
def create_pix(did: str, body: PaymentCreateBody = PaymentCreateBody(), authorization: Optional[str] = Header(None)):
    c, d = _auth_device(did, authorization)
    try:
        current = latest_payment_for_device(c, did)
        if current and not body.force_new and current.get('status') in ('pending', 'in_process'):
            if INFINITEPAY_HANDLE:
                if current.get('provider') == 'infinitepay' and current.get('ticket_url'):
                    return _payment_payload(current)
            elif current.get('qr_code'):
                return _payment_payload(current)

        billing = _billing_for_device(c, d)
        amount_cents = int(billing['price_cents'])
        if amount_cents <= 0:
            raise HTTPException(400, 'plano sem valor de cobrança')

        local_id = secrets.token_hex(12)
        external_reference = f'BBL-{did}-{local_id[:12]}'[:64]
        description = f'BBL.BOXTV - {(billing.get("plan_name") or "Mensalidade")} - {d.get("display_name") or did}'

        # Preferência: InfinitePay. O checkout gera Pix e notifica nosso webhook.
        if INFINITEPAY_HANDLE:
            inf = _infinite_create_link(external_reference, amount_cents, description)
            checkout_url = (inf.get('url') or '').strip()
            v5.ex(c, 'INSERT INTO payments(id,device_id,provider,provider_payment_id,external_reference,amount_cents,status,qr_code,qr_code_base64,ticket_url,created_at,updated_at,expires_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                  (local_id, did, 'infinitepay', '', external_reference, amount_cents, 'pending', '', '', checkout_url, _now(), _now(), ''))
            try:
                v5.log(c, did, 'payment_infinitepay_created', f'{external_reference}:{amount_cents}')
            except Exception:
                pass
            c.commit()
            return _payment_payload(v5.one(c, 'SELECT * FROM payments WHERE id=?', (local_id,)))

        # Fallback antigo: Mercado Pago.
        amount = amount_cents / 100.0
        idempotency_key = secrets.token_hex(16)
        req_body = {
            'transaction_amount': amount,
            'description': description,
            'payment_method_id': 'pix',
            'external_reference': external_reference,
            'payer': {'email': MP_PAYER_EMAIL}
        }
        if MP_NOTIFICATION_URL:
            req_body['notification_url'] = MP_NOTIFICATION_URL
        mp = _mp('POST', '/v1/payments', req_body, idempotency_key)
        td = (((mp.get('point_of_interaction') or {}).get('transaction_data')) or {})
        provider_id = str(mp.get('id') or '')
        status = mp.get('status') or 'pending'
        qr_code = td.get('qr_code') or ''
        qr_base64 = td.get('qr_code_base64') or ''
        ticket_url = td.get('ticket_url') or ''
        exp = mp.get('date_of_expiration') or ''
        v5.ex(c, 'INSERT INTO payments(id,device_id,provider,provider_payment_id,external_reference,amount_cents,status,qr_code,qr_code_base64,ticket_url,created_at,updated_at,expires_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
              (local_id, did, 'mercadopago', provider_id, external_reference, amount_cents, status, qr_code, qr_base64, ticket_url, _now(), _now(), exp))
        c.commit()
        return _payment_payload(v5.one(c, 'SELECT * FROM payments WHERE id=?', (local_id,)))
    finally:
        c.close()


@v5.app.get('/api/devices/{did}/payment')
def get_payment(did: str, authorization: Optional[str] = Header(None)):
    c, d = _auth_device(did, authorization)
    try:
        p = latest_payment_for_device(c, did)
        out = _payment_payload(p)
        out.update(_billing_for_device(c, d))
        return out
    finally:
        c.close()


@v5.app.post('/api/payments/infinitepay/webhook')
async def infinitepay_webhook(req: Request):
    try:
        body = await req.json()
    except Exception:
        body = {}

    order_nsu = str(body.get('order_nsu') or '').strip()
    transaction_nsu = str(body.get('transaction_nsu') or '').strip()
    slug = str(body.get('invoice_slug') or body.get('slug') or '').strip()
    if not order_nsu or not transaction_nsu or not slug:
        raise HTTPException(400, 'webhook sem identificadores obrigatórios')

    c = v5.db()
    try:
        p = v5.one(c, "SELECT * FROM payments WHERE provider='infinitepay' AND external_reference=?", (order_nsu,))
        if not p:
            raise HTTPException(400, 'pedido não encontrado')
        if p.get('status') == 'approved':
            return {'success': True, 'message': None}

        # Nunca libera apenas porque recebeu um POST: confirma direto na InfinitePay.
        check = _infinite_payment_check(order_nsu, transaction_nsu, slug)
        paid = bool(check.get('success')) and bool(check.get('paid'))
        checked_amount = int(check.get('amount') or 0)
        expected_amount = int(p.get('amount_cents') or 0)
        if not paid or checked_amount != expected_amount:
            raise HTTPException(400, 'pagamento ainda não confirmado ou valor divergente')

        _unlock_payment(c, p, transaction_nsu)
        c.commit()
        return {'success': True, 'message': None}
    finally:
        c.close()


@v5.app.get('/api/payments/infinitepay/ok')
def infinitepay_ok():
    return {'ok': True, 'message': 'Pagamento concluído. A Box será liberada automaticamente.'}


def _valid_signature(req: Request, data_id: str):
    if not MP_WEBHOOK_SECRET:
        return False
    xs = req.headers.get('x-signature') or ''
    rid = req.headers.get('x-request-id') or ''
    parts = {}
    for p in xs.split(','):
        if '=' in p:
            k, v = p.split('=', 1); parts[k.strip()] = v.strip()
    ts = parts.get('ts') or ''
    expected = parts.get('v1') or ''
    if not ts or not expected:
        return False
    manifest = f'id:{(data_id or "").lower()};request-id:{rid};ts:{ts};'
    digest = hmac.new(MP_WEBHOOK_SECRET.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, expected)


@v5.app.post('/api/payments/mercadopago/webhook')
async def mercado_pago_webhook(req: Request):
    try:
        body = await req.json()
    except Exception:
        body = {}
    data_id = str((body.get('data') or {}).get('id') or req.query_params.get('data.id') or '')
    if not data_id:
        return {'ok': True, 'ignored': 'no_data_id'}
    if not _valid_signature(req, data_id):
        raise HTTPException(401, 'assinatura de webhook inválida')
    mp = _mp('GET', f'/v1/payments/{data_id}')
    provider_id = str(mp.get('id') or data_id)
    status = mp.get('status') or 'unknown'
    external_reference = mp.get('external_reference') or ''
    c = v5.db()
    try:
        p = v5.one(c, "SELECT * FROM payments WHERE provider='mercadopago' AND (provider_payment_id=? OR external_reference=?)", (provider_id, external_reference))
        if not p:
            return {'ok': True, 'ignored': 'payment_not_linked'}
        if status == 'approved':
            _unlock_payment(c, p, provider_id)
        else:
            v5.ex(c, 'UPDATE payments SET status=?,updated_at=? WHERE id=?', (status, _now(), p['id']))
        c.commit()
        return {'ok': True, 'status': status}
    finally:
        c.close()


_orig_payload = v5.payload


def _payload_with_payment(c, d):
    out = _orig_payload(c, d)
    try:
        pay = payment_state_for_policy(c, d)
        out['payment'] = pay
        if isinstance(out.get('policy'), dict):
            out['policy']['payment'] = pay
    except Exception:
        out['payment'] = {'enabled': _payments_enabled(), 'status': 'error'}
    return out


v5.payload = _payload_with_payment
init_payments()