# Polo IDMEC no ISEL

Site: https://polo-idmec-isel.github.io

## Como funciona

- O site é gerado automaticamente a partir dos ficheiros em `data/`.
- Dia 1 de cada mês: o GitHub vai buscar as publicações de cada membro ao ORCID e volta a publicar o site.
- Dia 15 de cada mês: o mesmo para os projetos (secção *Financiamento* do ORCID; só os que estão em curso).
- Também é regenerado sempre que se altera um ficheiro no repositório.
- O site tem versão portuguesa (raiz) e inglesa (`/en/`). Os textos fixos estão em `scripts/build.py` (dicionário `T`); os interesses em inglês estão no campo `interests` de `data/members.json`.

## Tarefas habituais

**Acrescentar ou alterar um membro:** editar `data/members.json` (lápis no GitHub → *Commit changes*). O site atualiza-se em 1–2 minutos.

**Acrescentar um projeto ou rede que não está no ORCID (ou indicar uma função, ex. líder de grupo de trabalho):** editar `data/projetos.json`.

**Mudar o ano a partir do qual aparecem publicações:** `ano_inicio` em `data/config.json`.

**Forçar uma atualização das publicações:** separador *Actions* → *Atualizar e publicar o site* → *Run workflow*.

## Notas

- Só aparecem as publicações que estão no ORCID de cada membro. Quem sincroniza o Ciência Vitae com o ORCID não precisa de fazer nada.
- Artigos com vários membros aparecem uma só vez (duplicados eliminados pelo DOI ou pelo título).
- Se o ORCID falhar num mês, o site mantém a lista anterior.
