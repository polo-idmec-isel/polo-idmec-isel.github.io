# Polo IDMEC no ISEL

Site: https://polo-idmec-isel.github.io

## Como funciona

- O site é gerado automaticamente a partir dos ficheiros em `data/`.
- No dia 1 de cada mês, o GitHub vai buscar as publicações de cada membro ao ORCID e volta a publicar o site.
- Também é regenerado sempre que se altera um ficheiro no repositório.

## Tarefas habituais

**Acrescentar ou alterar um membro:** editar `data/members.json` (lápis no GitHub → *Commit changes*). O site atualiza-se em 1–2 minutos.

**Mudar o ano a partir do qual aparecem publicações:** `ano_inicio` em `data/config.json`.

**Forçar uma atualização das publicações:** separador *Actions* → *Atualizar e publicar o site* → *Run workflow*.

## Notas

- Só aparecem as publicações que estão no ORCID de cada membro. Quem sincroniza o Ciência Vitae com o ORCID não precisa de fazer nada.
- Artigos com vários membros aparecem uma só vez (duplicados eliminados pelo DOI ou pelo título).
- Se o ORCID falhar num mês, o site mantém a lista anterior.
