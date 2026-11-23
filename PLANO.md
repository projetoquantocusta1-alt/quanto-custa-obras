# Quanto Custa? Obras — plano da extração de dados

Piloto: **obras com dinheiro federal no Ceará**. Para outro estado, só muda o bloco "ESTADO" do `config.py`.
Princípio de privacidade: **só nomes de órgãos públicos, nunca de pessoas**.

## 1. O robô em 5 etapas

| Etapa | O que faz | Onde está |
|---|---|---|
| 1. Coletar | Baixa cada fonte e guarda uma cópia bruta (já sem dados de pessoas) | `coletor/`, `dados_brutos/` |
| 2. Padronizar | Transforma tudo numa ficha única de obra (situação, datas, valores, órgãos) | `montagem.py` |
| 3. Casar | Liga a mesma obra entre as fontes (ver seção 3) | `montagem.py` |
| 4. Calcular | Indicadores: valor de hoje (IPCA), atraso, tempo parada, dinheiro parado, por habitante | `montagem.py` |
| 5. Publicar | Gera os arquivos que o site lê | `docs/dados/` |

Roda sozinho todo dia pelo GitHub Actions (`.github/workflows/atualizar.yml`), como os outros repositórios do projeto.

## 2. Fontes: o que foi testado (23/11/2026)

| Fonte | Situação | O que traz | Observações |
|---|---|---|---|
| **ObrasGov.br** (API pública) | ✅ funcionando, usada no piloto | Cadastro de cada obra; % executado e motivos de paralisação; empenhos; ponto no mapa | Lenta (~0,8 s por obra listada; ~5 s para o detalhe de uma obra). Exige identificação do robô, senão o firewall bloqueia. O total informado pela API não é confiável. Não informa o município. |
| **PNCP** (API pública) | ✅ responde | Contratos e termos aditivos | **Cada contrato tem o campo `identificadorCipi`, que é o código da obra no ObrasGov.** É a ligação direta para os aditivos. Dá para filtrar pelo CNPJ do órgão (a prefeitura executora vem com CNPJ no ObrasGov). |
| **Transferegov** | ⚠️ parcial | Convênios e repasses: valor combinado, liberado e pago | A API pública responde para "transferências especiais" (emendas Pix). Os arquivos de convênios mudaram de endereço; falta achar o atual. O **número do convênio** já aparece no ObrasGov (no mapa: "instrumento 875966"; no nome: "CR 875966/2018") e o robô já o extrai. Alternativa: a API do Portal da Transparência (exige uma chave gratuita, cadastro com e-mail). |
| **CNO** (Receita Federal) | ⚠️ arquivo existe | Cadastro Nacional de Obras | Ver seção 3. Arquivo de ~340 MB atualizado todo mês. O download não foi testado neste ambiente (bloqueado pela proteção da sessão); testar no GitHub Actions. |
| **TCU**, **FNDE**, **Saúde** | a fazer | Obras paralisadas (TCU), creches e escolas (FNDE), postos de saúde | Na fase 4. As obras do FNDE já aparecem no ObrasGov (programa "Obras 2"). |
| **IBGE** | ✅ | Municípios, limites no mapa, população | Usado para descobrir o município pelo ponto da obra. |
| **Banco Central** | ✅ | IPCA | Valor em reais de hoje. |

## 3. Como casar a mesma obra entre as fontes

Não existe um "CPF da obra" comum a todas, mas os testes acharam boas pistas:

1. **Código do ObrasGov (CIPI)** → **PNCP**: o contrato traz `identificadorCipi`. Ligação exata.
2. **Número do convênio** → **Transferegov**: o ObrasGov traz o número do instrumento. Ligação exata.
3. **CNPJ do órgão executor** → **PNCP** e **CNO**: as prefeituras aparecem com CNPJ no ObrasGov.
4. **Município** (pelo órgão, pelo ponto no mapa ou pelo nome) + **nome parecido**: só como último recurso e,
   quando houver dúvida, a obra fica marcada como "não confirmada", nunca juntada à força.

### E o CNO?

O CNO (Cadastro Nacional de Obras, da Receita) tem: número da obra, CNPJ do responsável (dono da obra ou
construtora), endereço, município, **área construída** e **situação** (ativa, suspensa, **paralisada**, encerrada).

- **Não serve como chave principal**: nem o ObrasGov nem o PNCP trazem o número do CNO nos dados abertos.
- **Serve como confirmação e complemento**: ligando pelo CNPJ da prefeitura ou da construtora contratada (que vem
  do PNCP) + município + nome, ele traz a **área em m²**, o que permite calcular **custo por m²**, e uma **segunda
  opinião sobre a situação**: se a Receita diz "paralisada" e o ObrasGov diz "em execução", é um alerta.
- Cuidado: no CNO, quando o responsável é pessoa física, vem o CPF (que a Receita já tira) e o nome não vem.
  Só usaremos obras com responsável CNPJ.

## 4. Indicadores (fase 1, já calculados)

- **Valor previsto** (e em valores de hoje, pelo IPCA desde o ano de início previsto).
- **Empenhado**: dinheiro federal já reservado no orçamento (o "pago" vem do Transferegov na fase 2).
- **Obras paradas**: situação *paralisada* ou *inacabada* no cadastro; **há quanto tempo**.
- **Dinheiro parado**: empenhado em obras paradas.
- **Atraso**: dias desde o fim previsto (obras não concluídas) ou atraso na entrega (concluídas).
- **Por habitante**, por município.
- **Alertas de qualidade**: obra sem valor (R$ 0,01), sem município, situação não atualizada há mais de 1 ano.

## 5. Privacidade

- O ObrasGov traz o **nome e o endereço de um servidor** junto do mapa da obra: descartados antes de gravar.
- **Textos livres** (justificativas, observações) não são gravados nem publicados: podem citar pessoas.
  Das paralisações ficam os **motivos padronizados**.
- Órgãos com código de CPF (pessoa física) são descartados. CPFs em textos são mascarados (núcleo do projeto).
- Nomes de arquivos de documentos não são guardados (só o tipo e a data).

## 6. Fases

1. ✅ **ObrasGov sozinho** (este piloto): lista, situação, valores, empenhos, mapa, paradas, atrasos, municípios.
2. **Transferegov**: quanto já foi pago de cada convênio.
3. **PNCP**: contratos e aditivos ("começou custando X e já está em Y"), construtora contratada.
4. **CNO**, **TCU**, **FNDE** e **Saúde**: confirmação da situação, custo por m², lista do TCU.
5. **Outros estados**: PE, PB, RN, BA (só trocar o bloco ESTADO).

## 7. Riscos conhecidos

- **Lentidão do ObrasGov**: a primeira carga completa dos detalhes leva algumas horas; o robô busca primeiro as
  paradas e em execução, e completa o resto nos dias seguintes (limite de tempo por execução).
- **Firewall do ObrasGov**: se bloquear o GitHub Actions, o robô mantém os dados anteriores e tenta de novo no dia seguinte.
- **Qualidade do cadastro**: depende de quem preenche; o site mostra os alertas em vez de esconder.
