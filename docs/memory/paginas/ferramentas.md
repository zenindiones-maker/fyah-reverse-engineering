# Como rodar ferramentas sob o AI Memory

- Uma ferramenta: `python -m aimem run-tool media-inspect --input URL --out out/media-inspect.json`
- Qualquer comando: `python -m aimem session --agent fyah-er --label rotulo --result out/x.json -- comando ...`
- Fora do Actions, defina o destino da memória: `export AIMEM_SYNC_REF=<branch>` (sem fallback para main).
- Contrato das ferramentas: `python -m tools run NOME --input ARQ --out out.json` → JSON com `schema` e `ok`.
- Pelo celular: Actions → `er-aimemory`, `er-analyze` ou `er-harness` → Run workflow.
