"""Inspeção estática de APK (androguard, Apache-2.0). Só APKs próprios, open source ou com permissão; sem contornar proteções."""
from __future__ import annotations

import hashlib
import json
import zipfile


def inspect_apk(path: str) -> dict:
    from androguard.core.apk import APK
    try:
        from loguru import logger
        logger.remove()
    except Exception:  # noqa: BLE001
        pass
    a = APK(path)
    data = open(path, "rb").read()
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
    libs = sorted({n.split("/")[1] for n in names if n.startswith("lib/") and n.count("/") >= 2})
    return {
        "schema": "fyah-re/apk-inspect@1",
        "sha256": hashlib.sha256(data).hexdigest(),
        "size_bytes": len(data),
        "package": a.get_package(),
        "app_name": a.get_app_name(),
        "version_name": a.get_androidversion_name(),
        "version_code": a.get_androidversion_code(),
        "min_sdk": a.get_min_sdk_version(),
        "target_sdk": a.get_target_sdk_version(),
        "permissions": sorted(a.get_permissions()),
        "activities": sorted(a.get_activities()),
        "services": sorted(a.get_services()),
        "receivers": sorted(a.get_receivers()),
        "providers": sorted(a.get_providers()),
        "main_activity": a.get_main_activity(),
        "native_abis": libs,
        "dex_files": sorted(n for n in names if n.endswith(".dex")),
        "files": len(names),
        "signed_v1_v2_v3": [a.is_signed_v1(), a.is_signed_v2(), a.is_signed_v3()],
    }


def to_markdown(d: dict) -> str:
    return (f"## APK: {d['app_name']} (`{d['package']}`)\n\n"
            f"| Versão | minSdk | targetSdk | Tamanho | DEX | ABIs |\n|---|---|---|---|---|---|\n"
            f"| {d['version_name']} ({d['version_code']}) | {d['min_sdk']} | {d['target_sdk']} | {d['size_bytes']} B | {len(d['dex_files'])} | {', '.join(d['native_abis']) or '—'} |\n\n"
            f"**Permissões ({len(d['permissions'])}):** " + ", ".join(f"`{p.split('.')[-1]}`" for p in d["permissions"]) + "\n\n"
            f"Activities: {len(d['activities'])} · Services: {len(d['services'])} · Receivers: {len(d['receivers'])} · Providers: {len(d['providers'])}\n")


def main(argv=None) -> int:
    import argparse, pathlib
    ap = argparse.ArgumentParser(prog="python -m apps.apk")
    ap.add_argument("apk"); ap.add_argument("--out"); ap.add_argument("--md")
    x = ap.parse_args(argv)
    d = inspect_apk(x.apk)
    for p, txt in ((x.out, json.dumps(d, indent=2, ensure_ascii=False)), (x.md, to_markdown(d))):
        if p:
            pathlib.Path(p).parent.mkdir(parents=True, exist_ok=True); pathlib.Path(p).write_text(txt)
    print(to_markdown(d))
    return 0
