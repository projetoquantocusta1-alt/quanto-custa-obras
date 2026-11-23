"""ObrasGov.br — cadastro federal de obras (projetos de investimento com dinheiro da União).

Rotas usadas (todas públicas, sem chave):
    projeto-investimento?uf=CE           ficha de cada obra (situação, datas, valores, órgãos)
    execucao-fisica?idUnico=...          % executado, paralisações (motivos) e documentos
    execucao-financeira?idProjetoInvestimento=...   empenhos (dinheiro reservado no orçamento)
    geometria?idUnico=...                ponto(s) ou traçado da obra no mapa

Observações de quem testou (nov/2026):
- A API é lenta: cerca de 0,8 s por obra listada. Páginas de 50 levam ~40 s; de 200 estouram o tempo.
- O total informado pela API ("totalElements") não é confiável: a lista acaba quando vem uma página incompleta.
- Filtrar por "uf" só funciona na rota de projetos; nas outras, o filtro é ignorado e vem o Brasil inteiro.
- Sem identificação (User-Agent) o firewall da API recusa o acesso.

Privacidade: o mapa traz o nome de uma pessoa ("nomeAreaExecutora") e o endereço dela; isso é descartado
antes de gravar. Só ficam nomes de órgãos.
"""
import logging
import time

from quanto_custa import http, privacidade

import config

log = logging.getLogger("obrasgov")

# campos com dados de pessoas que nunca são gravados
CAMPOS_PESSOAIS_GEOMETRIA = ("nomeAreaExecutora", "enderecoAreaExecutora", "cepAreaExecutora")
# textos livres escritos por servidores (podem citar pessoas): não são gravados. Das paralisações ficam
# os motivos e indicativos, que são categorias fixas do ObrasGov.
TEXTOS_LIVRES = ("justificativa", "faseTratativa", "observacoes", "justificativaEmOperacao")


def _get(rota: str, params: dict, tentativas: int = 5):
    """GET com novas tentativas (o firewall às vezes devolve uma página de bloqueio ou o servidor estoura o tempo)."""
    url = f"{config.OBRASGOV}/{rota}"
    ultimo = None
    for t in range(tentativas):
        try:
            r = http.get(url, params=params, timeout=(20, 150))
            return r.json()
        except http.SiteForaDoAr:
            raise
        except Exception as e:  # noqa: BLE001 — 403 do firewall, 524 de tempo, JSON cortado
            ultimo = e
            if getattr(getattr(e, "response", None), "status_code", None) == 404:
                # 404 = "obra sem esse dado" (ex.: sem empenho). Não é falha do site: desfaz a contagem
                # do núcleo, senão depois de 10 obras assim o site seria dado como fora do ar.
                host = url.split("/")[2]
                http._falhas[host] = 0
                http._falhas_total[host] = max(0, http._falhas_total.get(host, 0) - 1)
                return None
            espera = 10 * (t + 1)
            log.warning("ObrasGov %s %s falhou (%s); nova tentativa em %s s", rota, params, str(e)[:120], espera)
            time.sleep(espera)
    raise RuntimeError(f"ObrasGov {rota} {params}: {ultimo}")


def _conteudo(d):
    if d is None:
        return []
    if isinstance(d, list):
        return d
    return d.get("content") or []


def listar_projetos(uf: str, situacao: str | None = None, progresso=None) -> list[dict]:
    """Todas as obras do estado. Para quando vem uma página incompleta."""
    tam = config.OBRASGOV_TAMANHO_PAGINA
    out, pag = [], 0
    while True:
        params = {"uf": uf, "pagina": pag, "tamanhoDaPagina": tam}
        if situacao:
            params["situacao"] = situacao
        c = _conteudo(_get("projeto-investimento", params))
        out += [limpar_projeto(p) for p in c]
        if progresso:
            progresso(pag, len(out))
        if len(c) < tam:
            break
        pag += 1
    # a paginação da API não tem ordem garantida: remove repetidas
    vistos, unicas = set(), []
    for p in out:
        if p.get("idUnico") and p["idUnico"] not in vistos:
            vistos.add(p["idUnico"])
            unicas.append(p)
    return unicas


def projeto(id_unico: str) -> dict | None:
    c = _conteudo(_get("projeto-investimento", {"idUnico": id_unico, "pagina": 0, "tamanhoDaPagina": 10}))
    return limpar_projeto(c[0]) if c else None


def execucao_fisica(id_unico: str) -> list[dict]:
    c = _conteudo(_get("execucao-fisica", {"idUnico": id_unico, "pagina": 0, "tamanhoDaPagina": 50}))
    out = []
    for x in c:
        if x.get("idUnico") != id_unico:     # se a API ignorar o filtro, não mistura obras
            continue
        x = {k: v for k, v in x.items() if k not in TEXTOS_LIVRES}
        x["cancelamentosParalisacoes"] = [{k: v for k, v in c.items() if k not in TEXTOS_LIVRES}
                                          for c in x.get("cancelamentosParalisacoes") or []]
        # documentos: só o tipo e a data (o nome do arquivo às vezes traz nome de pessoa)
        x["documentos"] = [{"tipo": d.get("tipoDocumento"), "data": d.get("dataCriacao")}
                           for d in x.get("documentos") or []]
        out.append(x)
    return out


def execucao_financeira(id_unico: str) -> list[dict]:
    out, pag = [], 0
    while True:
        c = _conteudo(_get("execucao-financeira",
                           {"idProjetoInvestimento": id_unico, "pagina": pag, "tamanhoDaPagina": 50}))
        c = [x for x in c if x.get("idProjetoInvestimento") == id_unico]
        out += [{k: v for k, v in x.items() if k not in ("pagina", "tamanhoDaPagina", "nomeFavorecido")} for x in c]
        if len(c) < 50 or pag > 40:
            return out
        pag += 1


def geometria(id_unico: str) -> list[dict]:
    d = _get("geometria", {"idUnico": id_unico})
    return [{k: v for k, v in g.items() if k not in CAMPOS_PESSOAIS_GEOMETRIA and k != "geometria"}
            for g in _conteudo(d)]


def detalhe(id_unico: str) -> dict:
    return {
        "fisica": execucao_fisica(id_unico),
        "financeira": execucao_financeira(id_unico),
        "geometria": geometria(id_unico),
    }


def limpar_projeto(p: dict) -> dict:
    """Tira de tomadores/executores/repassadores quem tem código de CPF (11 dígitos): só órgãos ficam."""
    p = {k: v for k, v in p.items() if k not in ("observacoesPertinentes",)}
    for campo in ("tomadores", "executores", "repassadores"):
        p[campo] = [o for o in p.get(campo) or [] if not _parece_cpf(o.get("codigo"))]
    return p


def cnpj_valido(d: str) -> bool:
    if len(d) != 14 or not d.isdigit() or len(set(d)) == 1:
        return False
    for n in (12, 13):
        pesos = list(range(n - 7, 1, -1)) + list(range(9, 1, -1))
        soma = sum(int(d[i]) * pesos[i] for i in range(n))
        dv = 0 if soma % 11 < 2 else 11 - soma % 11
        if dv != int(d[n]):
            return False
    return True


def _parece_cpf(codigo) -> bool:
    """O código vem como número (sem zeros à esquerda): CNPJ de prefeitura, código SIORG de órgão federal...
    É pessoa só se for um CPF válido e não for um CNPJ válido."""
    if codigo is None:
        return False
    s = str(codigo)
    if not s.isdigit():
        return False
    if cnpj_valido(s.zfill(14)):
        return False
    return len(s) == 11 and privacidade.cpf_valido(s)
