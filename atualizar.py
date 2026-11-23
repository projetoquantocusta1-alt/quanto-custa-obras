"""Robô das obras públicas federais de um estado (ObrasGov.br); o estado está em config.py.

Uso:
    python atualizar.py                 # lista de obras + detalhes que faltam/venceram, e monta o site
    python atualizar.py --semanal       # também IBGE (municípios, mapa, população) e IPCA
    python atualizar.py --so-montar     # só remonta o site com o que já está salvo
    python atualizar.py --minutos 90    # tempo máximo para buscar detalhes das obras

Brutos (dados_brutos/):
    obrasgov/projetos.json                    ficha de todas as obras do estado
    obrasgov/detalhe/<idUnico>.json           execução física, financeira e mapa de cada obra
    ibge/municipios.json, ibge/malha.json, ibge/populacao.json, ipca.json
Site (docs/dados/): ver montagem.py
"""
import argparse
import json
import logging
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

from quanto_custa import http, ipca

import config
import montagem
from coletor import ibge, obrasgov

RAIZ = Path(__file__).parent
BRUTOS = RAIZ / "dados_brutos"
SAIDA = RAIZ / "docs" / "dados"
log = logging.getLogger("obras")


def ler(p: Path, padrao=None):
    try:
        return json.loads(p.read_text("utf-8")) if p.exists() else padrao
    except json.JSONDecodeError:
        return padrao


def gravar(p: Path, obj, bonito=False):
    p.parent.mkdir(parents=True, exist_ok=True)
    txt = json.dumps(obj, ensure_ascii=False, indent=1 if bonito else None,
                     separators=None if bonito else (",", ":"))
    p.write_text(txt, "utf-8")


def nome_arquivo(id_unico: str) -> str:
    return id_unico.replace("/", "_")


# ------------------------------------------------------------------ coleta
def coletar_projetos(minutos: float):
    """Lista completa. Se não der tempo, o progresso fica em listagem_parcial.json e a próxima execução continua;
    enquanto isso, vale a última lista completa."""
    log.info("ObrasGov: listando as obras de %s (leva horas na primeira vez; retoma de onde parou)", config.UF)
    projetos, completa = obrasgov.listar_projetos(
        config.UF, progresso=lambda pag, n: log.info("  página %s: %s obras", pag, n),
        checkpoint=BRUTOS / "obrasgov" / "listagem_parcial.json", limite_segundos=minutos * 60)
    if not completa:
        raise RuntimeError(f"lista incompleta ({len(projetos)} obras até agora); continua na próxima execução")
    if not projetos:
        raise RuntimeError("ObrasGov devolveu a lista vazia; mantendo a anterior")
    anterior = ler(BRUTOS / "obrasgov" / "projetos.json", {}) or {}
    if anterior.get("obras") and len(projetos) < 0.8 * len(anterior["obras"]):
        raise RuntimeError(f"ObrasGov devolveu {len(projetos)} obras (antes {len(anterior['obras'])}); "
                           "lista incompleta, mantendo a anterior")
    projetos.sort(key=lambda p: p["idUnico"])
    gravar(BRUTOS / "obrasgov" / "projetos.json",
           {"coletado_em": date.today().isoformat(), "uf": config.UF, "obras": projetos}, bonito=True)
    log.info("ObrasGov: %s obras", len(projetos))
    return projetos


def precisa_detalhe(p: dict, salvo: dict | None, hoje: date) -> bool:
    if not salvo:
        return True
    if salvo.get("situacao") != p.get("situacao") or salvo.get("dataSituacao") != p.get("dataSituacao"):
        return True
    try:
        idade = (hoje - date.fromisoformat(salvo["coletado_em"])).days
    except (KeyError, ValueError):
        return True
    return idade >= config.DETALHE_VALIDADE_DIAS


def ordem_de_prioridade(p: dict) -> int:
    """Primeiro as que mais interessam: paralisadas, em execução; concluídas e canceladas por último."""
    return {"Paralisada": 0, "Inacabada": 0, "Em execução": 1, "Cadastrada": 2}.get(p.get("situacao"), 3)


def coletar_detalhes(projetos: list[dict], minutos: float):
    hoje = date.today()
    pasta = BRUTOS / "obrasgov" / "detalhe"
    fila = []
    for p in projetos:
        salvo = ler(pasta / f"{nome_arquivo(p['idUnico'])}.json")
        if precisa_detalhe(p, salvo, hoje):
            fila.append(p)
    fila.sort(key=ordem_de_prioridade)
    log.info("Detalhes: %s obras para buscar (limite de %s min)", len(fila), minutos)
    fim = time.time() + minutos * 60
    feitas = 0
    for p in fila:
        if time.time() > fim:
            break
        try:
            d = obrasgov.detalhe(p["idUnico"])
        except http.SiteForaDoAr:
            log.warning("ObrasGov fora do ar; paro os detalhes por hoje")
            break
        except Exception as e:  # noqa: BLE001
            log.warning("Detalhe de %s falhou: %s", p["idUnico"], str(e)[:150])
            continue
        d.update({"idUnico": p["idUnico"], "coletado_em": hoje.isoformat(),
                  "situacao": p.get("situacao"), "dataSituacao": p.get("dataSituacao")})
        gravar(pasta / f"{nome_arquivo(p['idUnico'])}.json", d, bonito=True)
        feitas += 1
        if feitas % 25 == 0:
            log.info("  %s/%s detalhes", feitas, len(fila))
    log.info("Detalhes: %s buscados; faltam %s", feitas, len(fila) - feitas)


def coletar_semanal():
    for nome, func in (("municipios", ibge.baixar_municipios), ("malha", ibge.baixar_malha),
                       ("populacao", ibge.baixar_populacao)):
        try:
            gravar(BRUTOS / "ibge" / f"{nome}.json", func())
            log.info("IBGE: %s ok", nome)
        except Exception as e:  # noqa: BLE001
            log.warning("IBGE %s falhou (mantém o anterior): %s", nome, e)
    try:
        gravar(BRUTOS / "ipca.json", ipca.fatores_por_ano(ipca.baixar_ipca(config.ANO_INICIAL_IPCA)))
        log.info("IPCA ok")
    except Exception as e:  # noqa: BLE001
        log.warning("IPCA falhou (mantém o anterior): %s", e)


# ------------------------------------------------------------------ principal
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--semanal", action="store_true")
    ap.add_argument("--so-montar", action="store_true")
    ap.add_argument("--so-lista", action="store_true", help="só a lista de obras (sem detalhes nem site)")
    ap.add_argument("--minutos", type=float, default=90, help="tempo máximo para os detalhes das obras")
    ap.add_argument("--minutos-lista", type=float, default=150, help="tempo máximo para a lista de obras")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    http.configurar(user_agent=config.USER_AGENT, pausa=config.OBRASGOV_PAUSA)

    if not a.so_montar:
        if a.semanal or not (BRUTOS / "ibge" / "malha.json").exists() or not (BRUTOS / "ipca.json").exists():
            coletar_semanal()
        try:
            projetos = coletar_projetos(a.minutos_lista)
        except Exception as e:  # noqa: BLE001
            log.warning("Lista de obras não atualizada: %s", e)
            projetos = (ler(BRUTOS / "obrasgov" / "projetos.json", {}) or {}).get("obras", [])
        if a.so_lista:
            return 0
        coletar_detalhes(projetos, a.minutos)

    montagem.montar(BRUTOS, SAIDA, hoje=date.today(),
                    gerado_em=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
