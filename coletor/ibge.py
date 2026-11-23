"""IBGE: lista de municípios, mapa dos limites municipais e população.

O ObrasGov não diz em que município fica a obra. Ele é descoberto pela montagem (montagem.py):
pelo órgão executor ("MUNICIPIO DE X"), pelo ponto da obra no mapa ou pelo nome da obra.
"""
from quanto_custa import http

import config


def baixar_municipios() -> list[dict]:
    r = http.get(config.IBGE_MUNICIPIOS, timeout=(20, 120)).json()
    return [{"ibge": str(m["id"]), "nome": m["nome"]} for m in r]


def baixar_malha() -> dict:
    """GeoJSON dos limites municipais (qualidade intermediária, ~300 KB por estado)."""
    return http.get(config.IBGE_MALHA, timeout=(20, 180)).json()


# ------------------------------------------------------------------ população
def ler_ibge(json_ibge) -> dict[str, dict[int, int]]:
    """{ibge7: {ano: pop}} a partir da resposta da API de agregados do IBGE."""
    out: dict[str, dict[int, int]] = {}
    for var in json_ibge or []:
        for res in var.get("resultados", []):
            for s in res.get("series", []):
                cod = str(s["localidade"]["id"])
                for ano, v in (s.get("serie") or {}).items():
                    try:
                        out.setdefault(cod, {})[int(ano)] = int(v)
                    except (TypeError, ValueError):
                        pass
    return out


def ler_sidra(linhas) -> dict[str, dict[int, int]]:
    """{ibge7: {ano: pop}} a partir da API do SIDRA (1ª linha é cabeçalho)."""
    out: dict[str, dict[int, int]] = {}
    for r in (linhas or [])[1:]:
        if not isinstance(r, dict):
            continue
        cods = [str(v) for k, v in r.items() if k.startswith("D") and k.endswith("C")]
        mun = next((c for c in cods if len(c) == 7 and c.isdigit()), None)
        ano = next((c for c in cods if len(c) == 4 and c.isdigit() and 1990 <= int(c) <= 2100), None)
        try:
            v = int(float(str(r.get("V", "")).replace(",", ".")))
        except ValueError:
            continue
        if mun and ano:
            out.setdefault(mun, {})[int(ano)] = v
    return out


def _uma_fonte(api, sidra):
    try:
        r = ler_ibge(http.get(api, timeout=(20, 120)).json())
        if r:
            return r
    except Exception:  # noqa: BLE001
        pass
    return ler_sidra(http.get(sidra, timeout=(20, 120)).json())


def baixar_populacao() -> dict[str, dict[int, int]]:
    pop = _uma_fonte(config.IBGE_ESTIMATIVA, config.SIDRA_ESTIMATIVA)
    try:
        for cod, s in _uma_fonte(config.IBGE_CENSO_2022, config.SIDRA_CENSO_2022).items():
            pop.setdefault(cod, {}).update(s)
    except Exception:  # noqa: BLE001 — o censo é complemento
        pass
    return pop


def populacao_mais_recente(serie: dict) -> tuple[int, int] | None:
    if not serie:
        return None
    ano = max(int(a) for a in serie)
    return ano, serie.get(ano, serie.get(str(ano)))
