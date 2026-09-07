import json
import v5

TUDO_PACKAGE = "com.bbl.boxtv.revenda"


def _is_tudo(app):
    if not app:
        return False
    pkg = (app.get("package_name") or "").strip().lower()
    name = (app.get("name") or "").strip().lower()
    return pkg == TUDO_PACKAGE or name == "tudo liberado" or name.startswith("tudo liberado ")


def _is_hidden_motor(app):
    if not app:
        return False
    name = (app.get("name") or "").strip().lower()
    pkg = (app.get("package_name") or "").strip().lower()
    return "motor oculto" in name or pkg.endswith(".motor.oculto") or pkg.endswith(".hiddenmotor")


def _normalize_apps(apps):
    unique = []
    seen = set()
    for app in apps or []:
        if _is_hidden_motor(app):
            continue
        pkg = (app.get("package_name") or "").strip().lower()
        key = pkg or str(app.get("id") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(app)
    tudo = [a for a in unique if _is_tudo(a)]
    other = [a for a in unique if not _is_tudo(a)]
    return (tudo + other)[:8]


def _sync_existing_layouts():
    """When TUDO LIBERADO already exists in Apps, keep it in Primary slot 1 of all layouts."""
    c = v5.db()
    try:
        apps = v5.rows(c, "SELECT * FROM apps ORDER BY created_at DESC")
        tudo = next((a for a in apps if _is_tudo(a)), None)
        if not tudo:
            return
        layouts = v5.rows(c, "SELECT * FROM layouts")
        for layout in layouts:
            try:
                ids = json.loads(layout.get("app_ids") or "[]")
            except Exception:
                ids = []
            clean = []
            for x in ids:
                if x and x != tudo["id"] and x not in clean:
                    clean.append(x)
            new_ids = [tudo["id"]] + clean[:7]
            if ids != new_ids:
                v5.ex(c, "UPDATE layouts SET app_ids=? WHERE id=?", (json.dumps(new_ids), layout["id"]))
        c.commit()
    finally:
        c.close()


_original_payload = v5.payload


def payload_with_tudo(c, d):
    out = _original_payload(c, d)
    apps = _normalize_apps(out.get("apps") or [])
    out["apps"] = apps
    out["allowed_apps"] = [a.get("package_name") for a in apps if a.get("package_name")]
    out["primary_apps"] = apps[:3]
    out["secondary_apps"] = apps[3:8]
    policy = out.get("policy")
    if isinstance(policy, dict):
        policy["apps"] = apps
        policy["allowed_apps"] = out["allowed_apps"]
        policy["primary_apps"] = out["primary_apps"]
        policy["secondary_apps"] = out["secondary_apps"]
    return out


v5.payload = payload_with_tudo
_sync_existing_layouts()
