"""Gera docs/catalogo/: catálogo de repositórios open source de engenharia reversa via API do GitHub.

Uso: python scripts/build_catalog.py [--quick]  (usa o gh CLI; no Actions, o GITHUB_TOKEN automático)
Só leitura na API; respeita rate limit (pausa ao atingir o limite). Requer o gh CLI.
"""
import json,subprocess,time,re,glob,csv,datetime,sys,os,pathlib,tempfile
AREAS=[("audio",["audio-analysis","music-information-retrieval","audio-processing","source-separation","music-transcription","beat-tracking","audio-fingerprinting","audio-effects","differentiable-dsp","audio-forensics","audio-watermarking"]),
("video",["video-analysis","shot-boundary-detection","scene-detection","video-processing","color-grading","subtitles","ffmpeg","video-codec","media-info"]),
("formatos",["file-format","binary-parser","kaitai-struct","hex-editor","file-format-parser"]),
("protocolos",["protocol-analysis","protocol-reverse-engineering","network-analysis","packet-analysis","usb-reverse-engineering"]),
("binarios",["binary-analysis","reverse-engineering","disassembler","decompiler","malware-analysis","symbolic-execution","dynamic-instrumentation","firmware-analysis","debugger"]),
("modelos_ml",["model-interpretability","mechanistic-interpretability","neural-network-visualization","model-extraction","onnx"]),
("mobile_web",["android-reverse-engineering","ios-reverse-engineering","apk","deobfuscation","javascript-deobfuscation"]),
("hardware",["hardware-reverse-engineering","embedded-security","fpga","sdr"])]
def gh(args):
    for i in range(5):
        r=subprocess.run(["gh","api"]+args,capture_output=True,text=True)
        if r.returncode==0: return json.loads(r.stdout)
        if "rate limit" in (r.stdout+r.stderr).lower(): time.sleep(65); continue
        return None
repos={}
def add(it,area,src):
    n=it["full_name"]
    if n in repos: repos[n]["fontes"].add(src); return
    repos[n]=dict(repo=n,area=area,estrelas=it["stargazers_count"],licenca=(it.get("license") or {}).get("spdx_id") or "NONE",ultimo_push=(it.get("pushed_at") or "")[:10],arquivado=it.get("archived"),descricao=(it.get("description") or "").replace("\n"," ")[:160],topicos=",".join(it.get("topics",[])[:8]),fontes={src})
QUICK="--quick" in sys.argv
FROM=next((a.split("=",1)[1] for a in sys.argv if a.startswith("--from-json=")),None)
if FROM: AREAS=[]
for area,topics in AREAS:
    for t in topics[:1] if QUICK else topics:
        for p in range(1,2 if QUICK else 11):
            d=gh(["-X","GET","search/repositories","-f",f"q=topic:{t}","-f","sort=stars","-f","per_page=100","-f",f"page={p}"])
            time.sleep(2.2)
            if not d or not d.get("items"): break
            for it in d["items"]: add(it,area,"topic:"+t)
            if len(d["items"])<100: break
        print(area,t,len(repos),flush=True)
# awesome lists
AWESOME=["wtsxDev/reverse-engineering","tylerha97/awesome-reversing","alphaSeclab/awesome-reverse-engineering","ReversingID/Awesome-Reversing","ybayle/awesome-deep-learning-music","faroit/awesome-python-scientific-audio","krzemienski/awesome-video"]
names=set()
for a in ([] if FROM else AWESOME):
    rr=subprocess.run(["gh","api",f"repos/{a}/readme","-H","Accept: application/vnd.github.raw"],capture_output=True,text=True)
    f="awesome_"+a.replace("/","_")+".md"
    for m in re.finditer(r"github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)",rr.stdout):
        o,r=m.group(1),m.group(2).removesuffix(".git")
        if o.lower() not in("topics","sponsors","orgs","features","marketplace","apps","settings"): names.add((o,r,f))
amap={"awesome-video":"video","deep-learning-music":"audio","scientific-audio":"audio","music-information":"audio"}
if FROM: names=set()
todo=[(o,r,f) for o,r,f in names if f"{o}/{r}".lower() not in {k.lower() for k in repos}]
print("awesome todo",len(todo),flush=True)
for i in range(0,len(todo),50):
    chunk=todo[i:i+50]
    q="query{"+" ".join(f'r{j}:repository(owner:{json.dumps(o)},name:{json.dumps(r)}){{nameWithOwner stargazerCount pushedAt isArchived description licenseInfo{{spdxId}} repositoryTopics(first:8){{nodes{{topic{{name}}}}}}}}' for j,(o,r,f) in enumerate(chunk))+"}"
    r=subprocess.run(["gh","api","graphql","-f",f"query={q}"],capture_output=True,text=True)
    try: data=json.loads(r.stdout).get("data") or {}
    except: data={}
    for j,(o,rn,f) in enumerate(chunk):
        x=data.get(f"r{j}")
        if not x: continue
        area=next((v for k,v in amap.items() if k in f),"binarios")
        add(dict(full_name=x["nameWithOwner"],stargazers_count=x["stargazerCount"],license={"spdx_id":(x["licenseInfo"] or {}).get("spdxId")},pushed_at=x["pushedAt"],archived=x["isArchived"],description=x["description"],topics=[t["topic"]["name"] for t in x["repositoryTopics"]["nodes"]]),area,"awesome:"+f[8:-3])
    time.sleep(1)
R={k:{**v,"fontes":sorted(v["fontes"])} for k,v in repos.items()}
if FROM: R=json.load(open(FROM))
print("total",len(repos))


# ---- render ----
import collections
OUT=pathlib.Path(__file__).resolve().parent.parent/"docs"/"catalogo"; OUT.mkdir(parents=True,exist_ok=True)
OSI={"MIT","Apache-2.0","BSD-2-Clause","BSD-3-Clause","GPL-2.0","GPL-3.0","LGPL-2.1","LGPL-3.0","AGPL-3.0","MPL-2.0","ISC","Unlicense","0BSD","CC0-1.0","BSL-1.0","EPL-2.0","EPL-1.0","Zlib","Artistic-2.0","EUPL-1.2","BSD-3-Clause-Clear","WTFPL","MS-PL","OFL-1.1","GPL-2.0-or-later","LGPL-2.1-or-later","CECILL-2.1","NCSA","Python-2.0","PostgreSQL","Vim","UPL-1.0","AFL-3.0","OSL-3.0","ECL-2.0","MulanPSL-2.0","BSD-4-Clause"}
today=datetime.date.today()
ORD=["audio","video","formatos","protocolos","binarios","modelos_ml","mobile_web","hardware"]
def manut(r):
    if r["arquivado"]: return "arquivado"
    if not r["ultimo_push"]: return "?"
    d=(today-datetime.date.fromisoformat(r["ultimo_push"])).days
    return "ativo" if d<=365 else ("lento" if d<=730*1.5 else "sem manutenção")
def integ(r):
    gpl=r["licenca"].startswith(("GPL","AGPL"))
    if r["estrelas"]>=1000 and manut(r)=="ativo" and r["area"] in("audio","video"): return "dependência (pip/apt) ou workflow Actions" + (" — GPL: só via CLI isolada" if gpl else "")
    if r["area"] in("audio","video","formatos"): return "referência no índice (submódulo opcional)"
    return "referência no índice"
keep,drop=[],[]
for r in R.values():
    r["manutencao"]=manut(r); r["custo_zero"]="sim"
    if r["licenca"] in OSI: r["integracao"]=integ(r); keep.append(r)
    else: r["motivo"]="sem licença" if r["licenca"]=="NONE" else ("licença não reconhecida pelo GitHub (NOASSERTION)" if r["licenca"]=="NOASSERTION" else "licença não OSI: "+r["licenca"]); drop.append(r)
keep.sort(key=lambda r:(ORD.index(r["area"]),-r["estrelas"]))
F=["area","repo","estrelas","licenca","ultimo_push","manutencao","custo_zero","integracao","descricao","topicos","fontes"]
with open(OUT/"catalogo.csv","w",newline="") as f:
    w=csv.DictWriter(f,F,extrasaction="ignore");w.writeheader()
    for r in keep: w.writerow({**r,"fontes":";".join(r["fontes"])})
with open(OUT/"descartados.csv","w",newline="") as f:
    w=csv.DictWriter(f,["area","repo","estrelas","licenca","motivo"],extrasaction="ignore");w.writeheader()
    for r in sorted(drop,key=lambda r:-r["estrelas"]): w.writerow(r)
c=collections.Counter(r["area"] for r in keep); m=collections.Counter(r["manutencao"] for r in keep); dc=collections.Counter(r["motivo"].split(":")[0] for r in drop)
L=[f"# Catálogo de repositórios open source de engenharia reversa — Fyah Records\n\nGerado automaticamente em {today} pela API do GitHub (buscas por tópico paginadas + awesome lists). Licença verificada no campo `license` da API. Ordem: áudio e vídeo primeiro. Todos são custo zero (open source, self-hosted).\n\n**Filtro:** entra tudo com licença open source reconhecida; fora só sem licença / NOASSERTION / não-OSI (ver `descartados.csv`). Abandonados ficam, marcados como `sem manutenção` ou `arquivado`.\n\nArquivos: `catalogo.csv` (completo, {len(keep)} repos), `descartados.csv` ({len(drop)}), gerador em `scripts/build_catalog.py`.\n\n## Contagem\n| Área | Repos |\n|---|---|"]
L+= [f"| {a} | {c[a]} |" for a in ORD]+[f"| **total** | **{len(keep)}** |","",f"Manutenção: "+", ".join(f"{k}: {v}" for k,v in m.items()),f"\nDescartados: "+", ".join(f"{k}: {v}" for k,v in dc.items()),""]
L.append("Manutenção: ativo = push ≤ 12 meses; lento ≤ 36 meses; sem manutenção > 36 meses.\n")
L.append("\n## Áreas\n"+"\n".join(f"- [{a}]({a}.md) ({c[a]})" for a in ORD)+"\n\n**Avisos legais:** a inclusão no catálogo não é endosso. Ferramentas de download (ex.: yt-dlp) só para material próprio/licenciado e dentro dos termos de uso; ferramentas de cheat, bypass de proteção ou DRM não devem ser usadas. Nenhum código de terceiros é copiado para este repo — só links.")
open(OUT/"README.md","w").write("\n".join(L))
for a in ORD:
    rs=[r for r in keep if r["area"]==a]
    L=[f"# {a} ({len(rs)})\n\n[← índice](README.md)\n\n| Repo | ★ | Licença | Último push | Manutenção | Integração | Descrição |\n|---|---|---|---|---|---|---|"]
    for r in rs: L.append(f"| [{r['repo']}](https://github.com/{r['repo']}) | {r['estrelas']} | {r['licenca']} | {r['ultimo_push']} | {r['manutencao']} | {r['integracao']} | {r['descricao'].replace('|','/')} |")
    open(OUT/f"{a}.md","w").write("\n".join(L))
print(len(keep),len(drop),dict(c),dict(m),dict(dc))
for a in ORD: print(a,[ (r["repo"],r["estrelas"],r["licenca"]) for r in keep if r["area"]==a and r["manutencao"]=="ativo"][:8])
