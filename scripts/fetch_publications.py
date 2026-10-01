"""Vai buscar as publicações de cada membro à API pública do ORCID.

Guarda uma lista normalizada por membro em data/orcid/<orcid>.json.
Se a recolha de um membro falhar, mantém o ficheiro anterior (o site
nunca fica sem publicações por causa de uma falha temporária).

Só usa a biblioteca padrão do Python: não é preciso instalar nada.
"""

import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = DATA / "orcid"
API = "https://pub.orcid.org/v3.0/{orcid}/works"


def val(obj, *keys):
    """Acede a campos aninhados do JSON do ORCID sem rebentar em None."""
    for k in keys:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(k)
    return obj


def self_doi(ext_ids):
    for e in (val(ext_ids, "external-id") or []):
        if (e.get("external-id-type") or "").lower() != "doi":
            continue
        if (e.get("external-id-relationship") or "self").lower() != "self":
            continue
        doi = val(e, "external-id-normalized", "value") or e.get("external-id-value") or ""
        doi = doi.strip().lower()
        for prefix in ("https://doi.org/", "http://doi.org/", "http://dx.doi.org/", "doi:"):
            if doi.startswith(prefix):
                doi = doi[len(prefix):]
        if doi:
            return doi
    return ""


def normalize(group):
    summaries = group.get("work-summary") or []
    if not summaries:
        return None
    s = summaries[0]
    title = (val(s, "title", "title", "value") or "").strip()
    if not title:
        return None
    year = val(s, "publication-date", "year", "value")
    doi = self_doi(group.get("external-ids")) or self_doi(s.get("external-ids"))
    return {
        "titulo": title,
        "ano": int(year) if year and str(year).isdigit() else None,
        "tipo": (s.get("type") or "").lower().replace("_", "-"),
        "revista": (val(s, "journal-title", "value") or "").strip(),
        "doi": doi,
        "url": val(s, "url", "value") or "",
    }


def fetch(orcid):
    req = urllib.request.Request(
        API.format(orcid=orcid),
        headers={"Accept": "application/json", "User-Agent": "polo-idmec-isel-site"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    works = [normalize(g) for g in data.get("group") or []]
    return [w for w in works if w]


def main():
    members = json.loads((DATA / "members.json").read_text(encoding="utf-8"))["membros"]
    OUT.mkdir(parents=True, exist_ok=True)
    failures = 0
    for m in members:
        orcid = (m.get("orcid") or "").strip()
        if not orcid:
            print(f"-- {m['nome']}: sem ORCID, ignorado")
            continue
        try:
            works = fetch(orcid)
        except Exception as exc:  # rede, API em baixo, etc.
            failures += 1
            print(f"!! {m['nome']} ({orcid}): falhou ({exc}); mantém dados anteriores")
            continue
        (OUT / f"{orcid}.json").write_text(
            json.dumps(works, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        print(f"ok {m['nome']}: {len(works)} registos")
        time.sleep(1)  # respeitar a API pública
    # Data da última recolha: mostrada no site e garante um commit mensal,
    # o que mantém o agendamento ativo no GitHub.
    (DATA / "ultima_atualizacao.txt").write_text(time.strftime("%Y-%m-%d") + "\n", encoding="utf-8")
    print(f"Concluído. Falhas: {failures}")
    return 0  # nunca falha o workflow: o site é publicado com o que houver


if __name__ == "__main__":
    sys.exit(main())
