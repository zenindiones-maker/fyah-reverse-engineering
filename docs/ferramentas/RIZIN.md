# Rizin no runner gratuito

Estado: o pacote APT `rizin` **não é uma instalação confiável** no `ubuntu-latest` usado por este repositório. `setup-er` registra `apt: rizin indisponível` e agora inclui a última linha do erro do APT, em vez de engolir a saída.

Caminho reproduzível, ainda sem custo: o release oficial `rizinorg/rizin` baixado por `scripts/er_releases.sh` com `ER_RIZIN=1`. O workflow `capabilities-e2e`, job `rizin`, tenta o APT, cai para esse release e roda `rz-bin -I -j` sobre o `python3` do próprio runner.

Se nem o APT nem o release produzirem `rz-bin` ou `r2`, `fyah-re doctor` marca `binary-inspect` como `blocked_missing_dependency` e `probe_disassembler` grava `available: false` com campo `error`. Essa ausência não é tratada como sucesso.
