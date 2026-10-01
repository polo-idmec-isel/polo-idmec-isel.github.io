"""Gera o site estático (pasta _site/) a partir dos ficheiros em data/.

Só usa a biblioteca padrão do Python.
"""

import json
import re
import time
from collections import Counter
from itertools import combinations
import unicodedata
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SITE = ROOT / "_site"

TIPOS = {
    "journal-article": "Artigo em revista",
    "conference-paper": "Comunicação em conferência",
    "book-chapter": "Capítulo de livro",
    "book": "Livro",
}


def e(s):
    return escape(str(s or ""), quote=True)


def title_key(title, year):
    t = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", t) + f"|{year}"


def load_publications(members, cfg):
    start = int(cfg.get("ano_inicio", 2024))
    tipos = set(cfg.get("tipos_incluidos", TIPOS))
    pubs, by_doi, by_title = [], {}, {}
    for idx, m in enumerate(members):
        f = DATA / "orcid" / f"{m.get('orcid', '')}.json"
        if not m.get("orcid") or not f.exists():
            continue
        for w in json.loads(f.read_text(encoding="utf-8")):
            if not w.get("ano") or w["ano"] < start or w.get("tipo") not in tipos:
                continue
            # retira códigos internos no início do título, ex. "[CI.49] "
            w = dict(w, titulo=re.sub(r"^\s*\[[^\]]{1,15}\]\s*", "", w["titulo"]))
            tk = title_key(w["titulo"], "")
            p = by_doi.get(w["doi"]) if w.get("doi") else None
            p = p or by_title.get(tk)
            if p is None:
                p = dict(w, membros=[])
                pubs.append(p)
            else:  # completar dados em falta com o registo de outro membro
                for k in ("doi", "revista", "url"):
                    if not p.get(k) and w.get(k):
                        p[k] = w[k]
            if idx not in p["membros"]:
                p["membros"].append(idx)
            if p.get("doi"):
                by_doi[p["doi"]] = p
            by_title[tk] = p
    pubs.sort(key=lambda p: (-p["ano"], p["titulo"].lower()))
    return pubs


def link(p):
    if p.get("doi"):
        return "https://doi.org/" + p["doi"]
    return p.get("url") or ""


def render_member(m):
    links = []
    if m.get("orcid"):
        links.append(f'<a href="https://orcid.org/{e(m["orcid"])}">ORCID</a>')
    if m.get("cienciavitae"):
        links.append(f'<a href="https://www.cienciavitae.pt/{e(m["cienciavitae"])}">Ciência Vitae</a>')
    if m.get("isel"):
        links.append(f'<a href="{e(m["isel"])}">Página ISEL</a>')
    chips = "".join(f"<li>{e(i)}</li>" for i in m.get("interesses") or [])
    role = f'<span class="role">{e(m["funcao"])}</span>' if m.get("funcao") else ""
    dept = f'<p class="dept">{e(m["departamento"])}</p>' if m.get("departamento") else ""
    return f"""
      <article class="card{' card--lead' if m.get('funcao') else ''}">
        <header><h3>{e(m['nome'])}</h3>{role}</header>
        {dept}
        {f'<ul class="chips">{chips}</ul>' if chips else ''}
        <p class="links">{' · '.join(links)}</p>
      </article>"""


def render_pubs(pubs, members):
    if not pubs:
        return '<p class="muted">As publicações aparecem aqui após a primeira atualização automática.</p>'
    out, year = [], None
    for p in pubs:
        if p["ano"] != year:
            if year is not None:
                out.append("</ol></section>")
            year = p["ano"]
            out.append(f'<section class="year" data-year="{year}"><h3>{year}</h3><ol class="pubs">')
        url = link(p)
        title = f'<a href="{e(url)}">{e(p["titulo"])}</a>' if url else e(p["titulo"])
        venue = " · ".join(x for x in (e(p.get("revista")), TIPOS.get(p["tipo"], "")) if x)
        who = ", ".join(e(members[i]["nome"]) for i in p["membros"])
        ids = " ".join(str(i) for i in p["membros"])
        joint = len(p["membros"]) > 1
        badge = ' <span class="badge">Conjunta</span>' if joint else ""
        out.append(
            f'<li data-m=" {ids} " data-c="{1 if joint else 0}"><p class="pt">{title}</p>'
            f'<p class="pv">{venue}</p><p class="pm">{who}{badge}</p></li>'
        )
    out.append("</ol></section>")
    return "\n".join(out)


def render_collabs(pubs, members):
    pairs = Counter()
    for p in pubs:
        ms = sorted(p["membros"])
        for a, b in combinations(ms, 2):
            pairs[(a, b)] += 1
    if not pairs:
        return ""
    rows = "".join(
        f'<li><span>{e(members[a]["nome"])} · {e(members[b]["nome"])}</span><strong>{n}</strong></li>'
        for (a, b), n in sorted(pairs.items(), key=lambda kv: (-kv[1], members[kv[0][0]]["nome"]))[:12]
    )
    return (
        '<div class="collab"><h3>Colaborações entre membros</h3>'
        '<p class="muted">Número de publicações em coautoria, desde o ano indicado acima.</p>'
        f'<ul>{rows}</ul></div>'
    )


# ---------- projetos ----------

MESES = ["jan.", "fev.", "mar.", "abr.", "mai.", "jun.", "jul.", "ago.", "set.", "out.", "nov.", "dez."]
TIPOS_PROJ = {"grant": "Projeto", "contract": "Contrato", "award": "Prémio"}


def fmt_ym(d):
    if not d:
        return ""
    if "-" in d:
        y, m = d.split("-")[:2]
        return f"{MESES[int(m) - 1]} {y}"
    return d


def code_key(c):
    return re.sub(r"[^a-z0-9]", "", (c or "").lower())


def load_projects(members, cfg):
    today = time.strftime("%Y-%m")
    tipos = set(cfg.get("tipos_projeto", ["grant", "contract"]))
    name_idx = {m["nome"]: i for i, m in enumerate(members)}

    def ended(p):
        f = p.get("fim") or ""
        if not f:  # sem data de fim: assume 3 anos de duração a partir do início
            i = p.get("inicio") or ""
            if not i:
                return False
            y = int(i[:4]) + 3
            f = f"{y}{i[4:]}"
        return f < today[: len(f)]

    def institutional(w):
        """Financiamento estratégico de unidades (LAETA, UID...), não é um projeto."""
        c = (w.get("codigo") or "").upper()
        t = (w.get("titulo") or "").lower()
        return (c.startswith(("UID", "LA/P", "PEST"))
                or "laboratório associado" in t or "associate laboratory" in t
                or "strategic project" in t or "projecto estratégico" in t or "projeto estratégico" in t)

    projs, manual = [], []
    mf = DATA / "projetos.json"
    if mf.exists():
        for p in json.loads(mf.read_text(encoding="utf-8")).get("projetos", []):
            q = dict(p, membros=[name_idx[n] for n in p.get("membros", []) if n in name_idx])
            q["funcoes"] = {name_idx[n]: f for n, f in (p.get("funcoes") or {}).items() if n in name_idx}
            q["_ck"] = code_key(p.get("codigo"))
            manual.append(q)
            projs.append(q)
    by_title = {title_key(p["titulo"], ""): p for p in projs}

    def find(w):
        ck = code_key(w.get("codigo"))
        tk = title_key(w["titulo"], "")
        for p in projs:
            pk = p.get("_ck") or code_key(p.get("codigo"))
            if ck and pk and (ck == pk or (len(pk) >= 6 and (pk in ck or ck in pk))):
                return p
            if pk and len(pk) >= 6 and pk in tk:
                return p
        return by_title.get(tk)

    for idx, m in enumerate(members):
        f = DATA / "orcid_projetos" / f"{m.get('orcid', '')}.json"
        if not m.get("orcid") or not f.exists():
            continue
        for w in json.loads(f.read_text(encoding="utf-8")):
            if w.get("tipo") not in tipos or institutional(w):
                continue
            p = find(w)
            if p is None:
                p = dict(w, membros=[], funcoes={})
                projs.append(p)
                by_title[title_key(w["titulo"], "")] = p
            else:
                for k in ("financiador", "inicio", "fim", "url", "codigo"):
                    if not p.get(k) and w.get(k):
                        p[k] = w[k]
            if idx not in p["membros"]:
                p["membros"].append(idx)
    # só projetos já iniciados: propostas em avaliação registadas no ORCID com
    # data de início futura não aparecem (um projeto aprovado aparece quando começar)
    started = lambda p: (p.get("inicio") or "") <= today[: len(p.get("inicio") or "")]
    projs = [p for p in projs if not ended(p) and started(p)]
    projs.sort(key=lambda p: (p.get("inicio") or "0000"), reverse=True)
    return projs


def render_projects(projs, members):
    items = []
    for p in projs:
        title = f'<a href="{e(p["url"])}">{e(p["titulo"])}</a>' if p.get("url") else e(p["titulo"])
        tipo = p.get("tipo_label") or TIPOS_PROJ.get(p.get("tipo"), "Projeto")
        per = " – ".join(x for x in (fmt_ym(p.get("inicio")), fmt_ym(p.get("fim"))) if x)
        if (p.get("inicio") or "") > time.strftime("%Y-%m")[: len(p.get("inicio") or "")]:
            per = f"a iniciar em {fmt_ym(p['inicio'])}"
        meta = " · ".join(e(x) for x in (tipo, p.get("financiador"), p.get("codigo"), per) if x)
        who = ", ".join(
            e(members[i]["nome"]) + (f' — {e(p["funcoes"][i])}' if i in (p.get("funcoes") or {}) else "")
            for i in p["membros"]
        )
        items.append(f'<li><p class="pt">{title}</p><p class="pv">{meta}</p><p class="pm">{who}</p></li>')
    return "\n".join(items)


def read_date(name):
    f = DATA / name
    if not f.exists():
        return ""
    y, mth, d = f.read_text().strip().split("-")
    return f"{d}/{mth}/{y}"


def main():
    cfg = json.loads((DATA / "config.json").read_text(encoding="utf-8"))
    members = json.loads((DATA / "members.json").read_text(encoding="utf-8"))["membros"]
    # coordenação primeiro, restantes por ordem alfabética
    members.sort(key=lambda m: (not m.get("funcao"), unicodedata.normalize("NFKD", m["nome"])))
    pubs = load_publications(members, cfg)
    projs = load_projects(members, cfg)
    n_joint = sum(1 for p in pubs if len(p["membros"]) > 1)
    upd = read_date("ultima_atualizacao.txt")
    upd_p = read_date("ultima_atualizacao_projetos.txt")
    depts = {m["departamento"] for m in members if m.get("departamento")}
    show_joint = n_joint >= int(cfg.get("mostrar_conjuntas_a_partir_de", 10))
    options = ('<option value="c">Só publicações conjuntas</option>' if show_joint else "") + "".join(
        f'<option value="{i}">{e(m["nome"])}</option>' for i, m in enumerate(members) if m.get("orcid")
    )
    contacts = "".join(
        f'<li>{e(c["nome"])} — <a href="mailto:{e(c["email"])}">{e(c["email"])}</a></li>'
        for c in cfg.get("contactos", [])
    )
    proj_section = ""
    if projs:
        note = f"Projetos em curso registados no ORCID dos membros (atualizado em {upd_p}), complementados manualmente." if upd_p else "Projetos e redes em curso."
        proj_section = (
            '<section class="block" id="projetos"><h2>Projetos e redes</h2>'
            f'<p class="muted" style="font-size:14px;margin:0 0 8px">{e(note)}</p>'
            f'<ol class="pubs">{render_projects(projs, members)}</ol></section>'
        )
    html = TEMPLATE.format(
        titulo=e(cfg.get("titulo", "Polo IDMEC no ISEL")),
        n_membros=len(members),
        n_depts=len(depts),
        n_pubs=len(pubs),
        tile_conjuntas=f'<div><strong>{n_joint}</strong>publicações conjuntas</div>' if show_joint else "",
        ano_inicio=int(cfg.get("ano_inicio", 2024)),
        membros="".join(render_member(m) for m in members),
        projetos=proj_section,
        nav_projetos='<a href="#projetos">Projetos</a>' if projs else "",
        colaboracoes=render_collabs(pubs, members) if show_joint else "",
        publicacoes=render_pubs(pubs, members),
        opcoes=options,
        atualizado=f"Atualizado automaticamente a partir do ORCID em {upd}." if upd else "Atualizado automaticamente a partir do ORCID.",
        contactos=contacts,
    )
    SITE.mkdir(exist_ok=True)
    (SITE / "index.html").write_text(html, encoding="utf-8")
    print(f"Site gerado: {len(members)} membros, {len(pubs)} publicações ({n_joint} conjuntas), {len(projs)} projetos.")


TEMPLATE = """<!doctype html>
<html lang="pt">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{titulo}</title>
<meta name="description" content="Polo do IDMEC – Instituto de Engenharia Mecânica no Instituto Superior de Engenharia de Lisboa (ISEL).">
<style>
:root {{
  --bg: #fbfaf7; --surface: #ffffff; --ink: #1b2430; --muted: #5d6673;
  --line: #e4e1da; --accent: #0f4c5c; --accent-soft: #e3eef0; --chip: #f1efe9;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --bg: #11161c; --surface: #171e26; --ink: #e8eaed; --muted: #9aa4b0;
    --line: #2a3440; --accent: #6fb7c7; --accent-soft: #1b3038; --chip: #202a34;
  }}
}}
* {{ box-sizing: border-box; }}
html {{ scroll-behavior: smooth; }}
body {{ margin: 0; background: var(--bg); color: var(--ink);
  font: 16px/1.6 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }}
a {{ color: var(--accent); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
.wrap {{ max-width: 1040px; margin: 0 auto; padding: 0 20px; }}
.top {{ border-bottom: 1px solid var(--line); background: var(--surface); position: sticky; top: 0; z-index: 5; }}
.top .wrap {{ display: flex; align-items: center; justify-content: space-between; height: 58px; gap: 16px; }}
.brand {{ font-weight: 650; color: var(--ink); letter-spacing: .01em; white-space: nowrap; }}
.brand span {{ color: var(--accent); }}
nav a {{ color: var(--muted); margin-left: 20px; font-size: 15px; }}
nav a:hover {{ color: var(--ink); text-decoration: none; }}
.hero {{ padding: 72px 0 48px; }}
.hero h1 {{ font-family: Georgia, "Times New Roman", serif; font-weight: 400; font-size: clamp(34px, 5vw, 52px);
  line-height: 1.1; margin: 0 0 18px; }}
.hero p {{ font-size: 19px; color: var(--muted); max-width: 680px; margin: 0; }}
.stats {{ display: flex; gap: 36px; margin-top: 36px; flex-wrap: wrap; }}
.stats div {{ font-size: 14px; color: var(--muted); }}
.stats strong {{ display: block; font-size: 30px; font-weight: 500; color: var(--ink); font-variant-numeric: tabular-nums; }}
section.block {{ padding: 48px 0; border-top: 1px solid var(--line); }}
h2 {{ font-family: Georgia, "Times New Roman", serif; font-weight: 400; font-size: 30px; margin: 0 0 20px; }}
.prose {{ max-width: 720px; }}
.prose p {{ margin: 0 0 14px; }}
.chips {{ list-style: none; padding: 0; margin: 10px 0 0; display: flex; flex-wrap: wrap; gap: 6px; }}
.chips li {{ background: var(--chip); border-radius: 999px; padding: 2px 10px; font-size: 13px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(290px, 1fr)); gap: 16px; }}
.card {{ background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 18px 20px; }}
.card--lead {{ border-color: var(--accent); }}
.card header {{ display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }}
.card h3 {{ margin: 0; font-size: 17px; font-weight: 600; }}
.role {{ font-size: 12px; color: var(--accent); background: var(--accent-soft); padding: 2px 8px; border-radius: 999px; white-space: nowrap; }}
.dept {{ margin: 2px 0 0; font-size: 14px; color: var(--muted); }}
.links {{ margin: 12px 0 0; font-size: 14px; }}
.toolbar {{ display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin-bottom: 8px; color: var(--muted); font-size: 14px; }}
select {{ font: inherit; padding: 6px 10px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface); color: var(--ink); }}
.year h3 {{ font-size: 15px; color: var(--muted); font-weight: 600; margin: 28px 0 8px; letter-spacing: .04em; }}
.pubs {{ list-style: none; margin: 0; padding: 0; }}
.pubs li {{ padding: 12px 0; border-bottom: 1px solid var(--line); }}
.pubs p {{ margin: 0; }}
.pt {{ font-weight: 500; }}
.pt a {{ color: var(--ink); }}
.pt a:hover {{ color: var(--accent); }}
.pv, .pm {{ font-size: 14px; color: var(--muted); }}
.pm {{ color: var(--accent); }}
.muted {{ color: var(--muted); }}
.badge {{ font-size: 11px; color: var(--accent); background: var(--accent-soft); padding: 1px 7px; border-radius: 999px; margin-left: 6px; vertical-align: 1px; }}
.collab {{ margin: 24px 0 8px; padding: 16px 20px; background: var(--surface); border: 1px solid var(--line); border-radius: 10px; }}
.collab h3 {{ margin: 0 0 2px; font-size: 16px; font-weight: 600; }}
.collab .muted {{ font-size: 13px; margin: 0 0 10px; }}
.collab ul {{ list-style: none; margin: 0; padding: 0; columns: 2 280px; column-gap: 32px; }}
.collab li {{ display: flex; justify-content: space-between; gap: 12px; padding: 4px 0; border-bottom: 1px solid var(--line); font-size: 14px; break-inside: avoid; }}
.collab strong {{ font-weight: 600; font-variant-numeric: tabular-nums; }}
footer {{ border-top: 1px solid var(--line); padding: 28px 0 40px; font-size: 14px; color: var(--muted); }}
@media (max-width: 640px) {{
  nav {{ display: none; }}
  .hero {{ padding: 48px 0 32px; }}
  .stats {{ gap: 24px; }}
}}
</style>
</head>
<body>
<div class="top"><div class="wrap">
  <a class="brand" href="#">Polo <span>IDMEC</span> · ISEL</a>
  <nav><a href="#sobre">Sobre</a><a href="#membros">Membros</a>{nav_projetos}<a href="#publicacoes">Publicações</a><a href="#contacto">Contacto</a></nav>
</div></div>

<main class="wrap">
  <section class="hero">
    <h1>{titulo}</h1>
    <p>Investigação em engenharia mecânica e áreas afins no Instituto Superior de Engenharia de Lisboa, em associação com o IDMEC – Instituto de Engenharia Mecânica.</p>
    <div class="stats">
      <div><strong>{n_membros}</strong>investigadores</div>
      <div><strong>{n_depts}</strong>departamentos do ISEL</div>
      <div><strong>{n_pubs}</strong>publicações desde {ano_inicio}</div>
      {tile_conjuntas}
    </div>
  </section>

  <section class="block" id="sobre">
    <h2>Sobre o polo</h2>
    <div class="prose">
      <p>O Polo IDMEC no ISEL foi constituído em 2024, na sequência de décadas de participação de docentes do ISEL no IDMEC – Instituto de Engenharia Mecânica. Reúne docentes de vários departamentos do ISEL que desenvolvem investigação no âmbito do IDMEC, nomeadamente em projetos financiados, nacionais e internacionais.</p>
      <p>O polo desenvolve métodos de otimização global, multiobjetivo e com variáveis mistas – contínuas, discretas e categóricas – e aplica-os, em conjunto com as restantes competências do grupo, à resolução de problemas reais de engenharia e da indústria.</p>
      <p>Áreas de atuação:</p>
      <ul class="chips">
        <li>Otimização global e multiobjetivo</li><li>Otimização com variáveis mistas e categóricas</li>
        <li>Mecânica computacional e estrutural</li><li>Materiais compósitos e estruturas avançadas</li>
        <li>Biomecânica e sistemas multicorpo</li><li>Fabrico e fabrico aditivo</li>
        <li>Energia, fluidos e AVAC</li><li>Robótica e inteligência artificial</li>
        <li>Aplicações industriais</li>
      </ul>
      <p style="margin-top:18px"><a href="https://www.idmec.tecnico.ulisboa.pt/">IDMEC</a> · <a href="https://www.isel.pt/">ISEL</a></p>
    </div>
  </section>

  <section class="block" id="membros">
    <h2>Membros</h2>
    <div class="grid">{membros}
    </div>
  </section>

  {projetos}

  <section class="block" id="publicacoes">
    <h2>Publicações</h2>
    <div class="toolbar">
      <label for="f">Filtrar por membro:</label>
      <select id="f"><option value="">Todos</option>{opcoes}</select>
      <span id="count"></span>
    </div>
    <p class="muted" style="font-size:14px;margin:0">{atualizado}</p>
    {colaboracoes}
    {publicacoes}
  </section>

  <section class="block" id="contacto">
    <h2>Contacto</h2>
    <div class="prose">
      <p>ISEL – Instituto Superior de Engenharia de Lisboa<br>Rua Conselheiro Emídio Navarro, 1, 1959-007 Lisboa</p>
      <p>Coordenação:</p>
      <ul>{contactos}</ul>
    </div>
  </section>
</main>

<footer><div class="wrap">Polo IDMEC no ISEL · Publicações obtidas automaticamente dos perfis ORCID dos membros.</div></footer>

<script>
(function () {{
  var sel = document.getElementById('f'), count = document.getElementById('count');
  if (!sel) return;
  function apply() {{
    var v = sel.value, n = 0;
    document.querySelectorAll('#publicacoes .pubs li').forEach(function (li) {{
      var show = !v || (v === 'c' ? li.getAttribute('data-c') === '1' : li.getAttribute('data-m').indexOf(' ' + v + ' ') !== -1);
      li.hidden = !show; if (show) n++;
    }});
    document.querySelectorAll('#publicacoes section.year').forEach(function (s) {{
      s.hidden = !s.querySelector('li:not([hidden])');
    }});
    count.textContent = v ? n + ' publicações' : '';
  }}
  sel.addEventListener('change', apply);
}})();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
