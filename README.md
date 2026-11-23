# Projeto Quanto Custa? — Obras federais (piloto: Ceará)

Cada obra pública com dinheiro federal: quanto foi prometido, quanto já foi reservado no orçamento, em que pé está,
quais estão paradas e há quanto tempo, quem é o órgão responsável. Plano completo da extração: [`PLANO.md`](PLANO.md).

## Fontes
- **ObrasGov.br** (Ministério da Gestão): cadastro das obras, execução física (com motivos de paralisação), empenhos e mapa.
- **IBGE**: municípios, limites municipais (para achar o município pelo ponto da obra) e população.
- **Banco Central**: IPCA (valores de hoje).

## Robô
`python atualizar.py` (todo dia, GitHub Actions). `--semanal` também baixa IBGE e IPCA. `--so-montar` só refaz o site.
`--minutos N` limita o tempo gasto buscando detalhes de obras (os que faltam ficam para o dia seguinte).

- `coletor/obrasgov.py`: consulta o ObrasGov (devagar, com novas tentativas) e descarta dados de pessoas.
- `coletor/ibge.py`: municípios, mapa e população.
- `montagem.py`: padroniza, descobre o município, calcula os indicadores e grava `docs/dados/`.
- `docs/`: o site (estático, abre direto do GitHub Pages ou de qualquer hospedagem).

Usa o núcleo comum do projeto (`quanto-custa-nucleo`, versão fixada no `requirements.txt`) para as requisições,
o IPCA e a máscara de CPF.

## Privacidade
Só órgãos públicos aparecem. O nome do servidor que vem junto do mapa da obra e os textos livres (justificativas,
observações) são descartados antes de gravar.

## Testes
`python -m pytest -q tests`

## Outro estado
Trocar o bloco "ESTADO" em `config.py` (sigla, código IBGE, nome) e o nome no workflow.
