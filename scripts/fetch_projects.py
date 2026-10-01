"""Vai buscar os projetos/financiamentos de cada membro à API pública do ORCID.

Guarda uma lista normalizada por membro em data/orcid_projetos/<orcid>.json.
Se a recolha de um membro falhar, mantém o ficheiro anterior.
Só usa a biblioteca padrão do Python.
"""

import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = DATA / "orcid_projetos"
API = "https://pub.orcid.org/v3.0/{orcid}/fundings"


def val(obj, *keys):
    for k in keys:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(k)
    return obj


def ym(d):
    """Data ORCID -> 'AAAA-MM' (ou 'AAAA'), ou '' se não existir."""
    y = val(d, "year", "value")
    if not y:
        return ""
    m = val(d, "month", "value")
    return f"{y}-{int(m):02d}" if m and str(m).isdigit() else str(y)


def normalize(group):
    summaries = group.get("funding-summary") or []
    if not summaries:
        return None
    s = summaries[0]
    title = (val(s, "title", "title", "value") or "").strip()
    if not title:
        return None
    code = ""
    for x in (val(s, "external-ids", "external-id") or []):
        if x.get("external-id-value"):
            code = x["external-id-value"].strip()
            break
    return {
        "titulo": title,
        "tipo": (s.get("type") or "").lower().replace("_", "-"),
        "financiador": (val(s, "organization", "name") or "").strip(),
        "inicio": ym(s.get("start-date")),
        "fim": ym(s.get("end-date")),
        "codigo": code,
        "url": val(s, "url", "value") or "",
    }


def fetch(orcid):
    req = urllib.request.Request(
        API.format(orcid=orcid),
        headers={"Accept": "application/json", "User-Agent": "polo-idmec-isel-site"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    items = [normalize(g) for g in data.get("group") or []]
    return [i for i in items if i]


def main():
    members = json.loads((DATA / "members.json").read_text(encoding="utf-8"))["membros"]
    OUT.mkdir(parents=True, exist_ok=True)
    failures = 0
    for m in members:
        orcid = (m.get("orcid") or "").strip()
        if not orcid:
            continue
        try:
            items = fetch(orcid)
        except Exception as exc:
            failures += 1
            print(f"!! {m['nome']} ({orcid}): falhou ({exc}); mantém dados anteriores")
            continue
        (OUT / f"{orcid}.json").write_text(
            json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        print(f"ok {m['nome']}: {len(items)} registos")
        time.sleep(1)
    (DATA / "ultima_atualizacao_projetos.txt").write_text(time.strftime("%Y-%m-%d") + "\n", encoding="utf-8")
    print(f"Concluído. Falhas: {failures}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
