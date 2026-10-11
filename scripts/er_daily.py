"""Rotina diária custo zero: repos novos/atualizados em tópicos-chave + arXiv RSS. Escreve docs/diario/AAAA-MM-DD.md."""
import datetime, json, os, pathlib, subprocess, urllib.request, xml.etree.ElementTree as ET

TOPICS = ["audio-analysis", "music-information-retrieval", "source-separation", "video-analysis",
          "scene-detection", "reverse-engineering", "binary-analysis", "file-format"]
ARXIV = {"eess.AS (áudio e fala)": "eess.AS", "cs.SD (som)": "cs.SD", "cs.MM (multimídia)": "cs.MM", "cs.CR (segurança)": "cs.CR"}
KEYWORDS = ["music", "audio", "mix", "separation", "beat", "transcription", "video", "shot", "scene", "codec",
            "reverse engineering", "binary", "decompil", "firmware", "protocol", "watermark", "fingerprint", "effect"]
OSI = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "GPL-2.0", "GPL-3.0", "LGPL-2.1", "LGPL-3.0", "AGPL-3.0",
       "MPL-2.0", "ISC", "Unlicense", "0BSD", "CC0-1.0", "BSL-1.0", "EPL-2.0", "Zlib"}


def gh(path, **params):
    args = ["gh", "api", "-X", "GET", path] + sum([["-f", f"{k}={v}"] for k, v in params.items()], [])
    r = subprocess.run(args, capture_output=True, text=True)
    return json.loads(r.stdout) if r.returncode == 0 else {}


def repos(since):
    out = []
    for t in TOPICS:
        d = gh("search/repositories", q=f"topic:{t} pushed:>={since} stars:>=20", sort="updated", per_page=10)
        for it in d.get("items", []):
            lic = (it.get("license") or {}).get("spdx_id") or "NONE"
            if lic in OSI:
                out.append((t, it["full_name"], it["stargazers_count"], lic, (it.get("description") or "")[:120]))
    return out


def arxiv():
    res = {}
    for label, cat in ARXIV.items():
        try:
            req = urllib.request.Request(f"https://rss.arxiv.org/rss/{cat}", headers={"User-Agent": "fyah-re-daily"})
            root = ET.fromstring(urllib.request.urlopen(req, timeout=30).read())
        except Exception as e:  # noqa: BLE001
            res[label] = [("erro ao ler RSS", str(e)[:80])]; continue
        items = []
        for it in root.iter("item"):
            title, link = it.findtext("title") or "", it.findtext("link") or ""
            if cat in ("eess.AS", "cs.SD") or any(k in title.lower() for k in KEYWORDS):
                items.append((title.strip(), link.strip()))
        res[label] = items[:15]
    return res


def main():
    today = datetime.date.today()
    since = (today - datetime.timedelta(days=3 if today.weekday() == 0 else 1)).isoformat()
    L = [f"# Diário do E.R. — {today}", "", "Rotina automática custo zero (GitHub Actions). Só leitura de fontes públicas; nada é baixado ou copiado.", "",
         f"## Repositórios open source atualizados desde {since}", "", "| Tópico | Repo | ★ | Licença | Descrição |", "|---|---|---|---|---|"]
    seen = set()
    for t, n, s, lic, desc in repos(since):
        if n in seen: continue
        seen.add(n); L.append(f"| {t} | [{n}](https://github.com/{n}) | {s} | {lic} | {desc.replace('|', '/')} |")
    L += ["", "## arXiv (RSS do dia)"]
    for label, items in arxiv().items():
        L += ["", f"### {label}"] + ([f"- [{t}]({u})" for t, u in items] or ["- (nada relevante hoje)"])
    L += ["", "## Para estudar", "- Escolher 1 artigo acima e registrar hipótese em `writeups/` seguindo [o método](../metodologia.md)."]
    p = pathlib.Path(__file__).resolve().parent.parent / "docs" / "diario" / f"{today}.md"
    p.parent.mkdir(parents=True, exist_ok=True); p.write_text("\n".join(L) + "\n")
    print(p)


if __name__ == "__main__":
    main()
