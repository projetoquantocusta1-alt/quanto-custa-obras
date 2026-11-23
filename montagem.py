"""Montagem: dos dados brutos do ObrasGov para os arquivos que o site lê.

Etapas (as mesmas do plano): padronizar → descobrir o município → calcular os indicadores → publicar.

Site (docs/dados/):
    meta.json         data, fontes, totais do estado, referência do IPCA
    obras.json        uma linha curta por obra (lista, filtros e mapa)
    municipios.json   totais por município (com valor por habitante)
    o/<id>.json       ficha completa de cada obra

Privacidade: só nomes de órgãos. Textos livres não são publicados (podem citar pessoas); das paralisações
ficam os motivos e indicativos, que são categorias fixas do ObrasGov.
"""
import json
import re
import unicodedata
from datetime import date
from pathlib import Path

from quanto_custa import privacidade

# ------------------------------------------------------------------ situação
# rótulo do ObrasGov → (chave, texto no site)
SITUACOES = {
    "cadastrada": ("cadastrada", "Cadastrada"),
    "em execução": ("em_execucao", "Em execução"),
    "em execucao": ("em_execucao", "Em execução"),
    "paralisada": ("paralisada", "Paralisada"),
    "inacabada": ("inacabada", "Inacabada"),
    "concluída": ("concluida", "Concluída"),
    "concluida": ("concluida", "Concluída"),
    "cancelada": ("cancelada", "Cancelada"),
}
ENCERRADAS = {"concluida", "cancelada"}
PARADAS = {"paralisada", "inacabada"}

VALOR_MINIMO = 100.0   # valores como R$ 0,01 são marcadores de "sem valor" no cadastro


def situacao(rotulo):
    r = (rotulo or "").strip().lower()
    return SITUACOES.get(r, (sem_acento(r).replace(" ", "_") or "desconhecida", rotulo or "Sem informação"))


# ------------------------------------------------------------------ texto
CONTROLE = re.compile(r"[\x00-\x1f\x7f-\x9f\ufffd]+")


def limpo(s) -> str:
    """Tira caracteres de controle e espaços repetidos que vêm do cadastro."""
    return re.sub(r"\s+", " ", CONTROLE.sub(" ", s or "")).strip()


def sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn")


def chave_nome(s: str) -> str:
    s = sem_acento(s).upper().replace("'", "").replace("’", "").replace("-", " ")
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9 ]", " ", s)).strip()


def data(s):
    if not s:
        return None
    try:
        return date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


def r2(x):
    return None if x is None else round(x, 2)


# ------------------------------------------------------------------ municípios
PREFIXOS_MUNICIPIO = re.compile(
    r"^(?:MUNICIPIO|PREFEITURA MUNICIPAL|PREFEITURA|FUNDO MUNICIPAL DE [A-Z ]+?|SECRETARIA MUNICIPAL DE [A-Z ]+?)"
    r" (?:DE |DO |DA |DOS |DAS )?(.+?)(?: CE| CEARA)?$")
MUNICIPIO_NO_TEXTO = re.compile(r"MUNICIPIO (?:DE |DO |DA |DOS |DAS )?([A-Z ]+?)(?: CE\b| CEARA\b| ESTADO\b|$|  )")


class Municipios:
    def __init__(self, lista, malha=None):
        self.por_chave = {chave_nome(m["nome"]): m["ibge"] for m in lista}
        self.nome = {m["ibge"]: m["nome"] for m in lista}
        self.poligonos = []   # (ibge, caixa, [anéis])
        for f in (malha or {}).get("features", []):
            cod = str(f["properties"].get("codarea"))
            g = f["geometry"]
            polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
            for p in polys:
                xs = [x for x, _ in p[0]]
                ys = [y for _, y in p[0]]
                self.poligonos.append((cod, (min(xs), min(ys), max(xs), max(ys)), p))

    def pelo_nome(self, texto):
        return self.por_chave.get(chave_nome(texto or ""))

    def do_orgao(self, nome_orgao):
        """'MUNICIPIO DE TABULEIRO DO NORTE' → código IBGE."""
        m = PREFIXOS_MUNICIPIO.match(chave_nome(nome_orgao or ""))
        if not m:
            return None
        return self.pelo_nome(m.group(1))

    def do_texto(self, texto):
        """Procura 'município de X' no nome/descrição da obra."""
        for m in MUNICIPIO_NO_TEXTO.finditer(chave_nome(texto or "") + "  "):
            cod = self.pelo_nome(m.group(1).strip())
            if cod:
                return cod
            # "MUNICIPIO DE TABULEIRO DO NORTE CE ..." – tenta encurtar palavra por palavra
            palavras = m.group(1).split()
            for n in range(len(palavras) - 1, 0, -1):
                cod = self.pelo_nome(" ".join(palavras[:n]))
                if cod:
                    return cod
        return None

    def do_ponto(self, lon, lat):
        for cod, (x0, y0, x1, y1), aneis in self.poligonos:
            if x0 <= lon <= x1 and y0 <= lat <= y1 and dentro(lon, lat, aneis[0]) \
                    and not any(dentro(lon, lat, a) for a in aneis[1:]):
                return cod
        return None


def dentro(x, y, anel) -> bool:
    """Ponto no polígono (raio horizontal)."""
    d = False
    j = len(anel) - 1
    for i in range(len(anel)):
        xi, yi = anel[i][:2]
        xj, yj = anel[j][:2]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            d = not d
        j = i
    return d


NUM = r"-?\d+(?:\.\d+)?"
PAR = re.compile(rf"({NUM})\s+({NUM})")


def pontos_wkt(wkt: str) -> list[tuple[float, float]]:
    """Todos os pares (lon, lat) de um WKT (POINT, LINESTRING, POLYGON, MULTI...)."""
    out = []
    for a, b in PAR.findall(wkt or ""):
        try:
            lon, lat = float(a), float(b)
        except ValueError:
            continue
        if -75 < lon < -30 and -35 < lat < 6:   # dentro do Brasil (descarta coordenadas trocadas ou zeradas)
            out.append((lon, lat))
    return out


INSTRUMENTO = [
    re.compile(r"instrumento\s+(\d{6,7})", re.I),
    re.compile(r"\b(?:CR|TC|CV|TR|TERMO DE COMPROMISSO|CONV[EÊ]NIO|CONTRATO DE REPASSE)\s*(?:N[º°O.]*\s*)?(\d{6,7})\s*/\s*\d{4}", re.I),
]


def instrumento_transferegov(p: dict, geo: list) -> str | None:
    """Número do convênio/contrato de repasse no Transferegov (liga a obra ao dinheiro repassado)."""
    textos = [g.get("infoAdicionais") or "" for g in geo] + [p.get("nome") or "", p.get("descricao") or ""]
    for t in textos:
        for rx in INSTRUMENTO:
            m = rx.search(t)
            if m:
                return m.group(1)
    return None


# ------------------------------------------------------------------ órgãos
def tipo_orgao(o: dict, municipios: Municipios) -> str:
    nome = chave_nome(o.get("nome"))
    if municipios.do_orgao(o.get("nome")):
        return "municipio"
    if nome.startswith(("ESTADO DO", "ESTADO DE", "GOVERNO DO ESTADO", "SECRETARIA DA", "SECRETARIA DE ESTADO",
                        "SUPERINTENDENCIA DE OBRAS", "DEPARTAMENTO ESTADUAL")):
        return "estado"
    return "federal" if not str(o.get("codigo") or "").isdigit() or len(str(o.get("codigo"))) < 9 else "outro"


def orgaos(lista, municipios):
    out = []
    for o in lista or []:
        nome = privacidade.mascarar_cpf_no_texto((o.get("nome") or "").strip())
        if nome:
            out.append({"nome": nome, "tipo": tipo_orgao(o, municipios)})
    return out


# ------------------------------------------------------------------ obra
def montar_obra(p: dict, det: dict | None, municipios: Municipios, fatores: dict, hoje: date) -> dict:
    det = det or {}
    sit, sit_txt = situacao(p.get("situacao"))
    fontes = p.get("fontesDeRecurso") or []
    previsto = sum(float(f.get("valorInvestimentoPrevisto") or 0) for f in fontes)
    previsto_federal = sum(float(f.get("valorInvestimentoPrevisto") or 0) for f in fontes
                           if (f.get("origem") or "").lower() == "federal")
    alertas = []
    if previsto < VALOR_MINIMO:
        alertas.append("sem_valor")
        previsto = previsto_federal = None

    # execução física: o registro mais recente
    fis = sorted(det.get("fisica") or [], key=lambda x: x.get("dataSituacao") or "")
    ultima = fis[-1] if fis else {}
    pct = ultima.get("percentual")
    paralisacoes = []
    for f in fis:
        for c in f.get("cancelamentosParalisacoes") or []:
            paralisacoes.append({
                "motivos": [m.get("descricao") for m in c.get("motivosParalisacao") or [] if m and m.get("descricao")],
                "indicativos": [m.get("descricao") for m in c.get("indicativosParalisacao") or [] if m and m.get("descricao")],
                "tem_solucao_em_andamento": c.get("possuiTratativa"),
            })

    emp = det.get("financeira") or []
    empenhado = sum(float(e.get("valorEmpenho") or 0) for e in emp) if emp else None

    # município
    geo = det.get("geometria") or []
    pts = [pt for g in geo for pt in pontos_wkt(g.get("geometriaWkt"))]
    muns, origem = [], None
    for o in (p.get("tomadores") or []) + (p.get("executores") or []):
        cod = municipios.do_orgao(o.get("nome"))
        if cod and cod not in muns:
            muns.append(cod)
            origem = "orgao"
    if not muns and pts:
        for lon, lat in pts[:200]:
            cod = municipios.do_ponto(lon, lat)
            if cod and cod not in muns:
                muns.append(cod)
        origem = "mapa" if muns else None
    if not muns:
        cod = municipios.do_texto(p.get("nome")) or municipios.do_texto(p.get("descricao"))
        if cod:
            muns, origem = [cod], "nome"
    if not muns:
        alertas.append("sem_municipio")

    ponto = None
    if pts:
        ponto = [round(sum(y for _, y in pts) / len(pts), 5), round(sum(x for x, _ in pts) / len(pts), 5)]

    # datas e indicadores
    ini_prev, fim_prev = data(p.get("dataInicialPrevista")), data(p.get("dataFinalPrevista"))
    ini_ef, fim_ef = data(p.get("dataInicialEfetiva")), data(p.get("dataFinalEfetiva"))
    data_sit = data(p.get("dataSituacao"))
    dias_atraso = None
    if fim_prev:
        if sit in ENCERRADAS:
            if sit == "concluida" and fim_ef and fim_ef > fim_prev:
                dias_atraso = (fim_ef - fim_prev).days
        elif fim_prev < hoje:
            dias_atraso = (hoje - fim_prev).days
    dias_parada = (hoje - data_sit).days if sit in PARADAS and data_sit else None
    dinheiro_parado = empenhado if sit in PARADAS and empenhado else None
    if sit not in ENCERRADAS and data_sit and (hoje - data_sit).days > 365:
        alertas.append("situacao_antiga")

    ano_ref = (ini_prev or data(p.get("dataCadastro")) or hoje).year
    fator = fatores.get(str(ano_ref), fatores.get(ano_ref)) if fatores else None
    previsto_hoje = r2(previsto * fator) if previsto and fator else None

    def lista(campo):
        return [x.get("descricao") for x in p.get(campo) or [] if x and x.get("descricao")]

    return {
        "id": p["idUnico"],
        "nome": privacidade.mascarar_cpf_no_texto(limpo(p.get("nome"))),
        "descricao": privacidade.mascarar_cpf_no_texto(limpo(p.get("descricao"))),
        "meta": privacidade.mascarar_cpf_no_texto(limpo(p.get("metaGlobal"))) or None,
        "situacao": sit, "situacao_txt": sit_txt, "data_situacao": p.get("dataSituacao"),
        "especie": p.get("especie"), "natureza": p.get("natureza"),
        "eixos": lista("eixos"), "tipos": lista("tipos"), "subtipos": lista("subTipos"),
        "programa": p.get("descPlanoNacionalPoliticaVinculado"),
        "datas": {"cadastro": p.get("dataCadastro"), "inicio_previsto": p.get("dataInicialPrevista"),
                  "fim_previsto": p.get("dataFinalPrevista"), "inicio_efetivo": p.get("dataInicialEfetiva"),
                  "fim_efetivo": p.get("dataFinalEfetiva")},
        "valor_previsto": r2(previsto), "valor_previsto_federal": r2(previsto_federal),
        "valor_previsto_hoje": previsto_hoje, "ano_valor": ano_ref,
        "fontes_recurso": [{"origem": f.get("origem"), "valor": r2(float(f.get("valorInvestimentoPrevisto") or 0))}
                           for f in fontes],
        "empenhado": r2(empenhado), "n_empenhos": len(emp),
        "percentual_fisico": pct, "em_operacao": ultima.get("emOperacao"),
        "paralisacoes": paralisacoes,
        "documentos": [d for f in fis for d in f.get("documentos") or []],
        "executores": orgaos(p.get("executores"), municipios),
        "tomadores": orgaos(p.get("tomadores"), municipios),
        "repassadores": orgaos(p.get("repassadores"), municipios),
        "municipios": muns, "municipio_origem": origem,
        "ponto": ponto,
        "populacao_beneficiada": p.get("populacaoBeneficiada"),
        "empregos": p.get("qdtEmpregosGerados"),
        "instrumento": instrumento_transferegov(p, geo),
        "dias_atraso": dias_atraso, "dias_parada": dias_parada, "dinheiro_parado": r2(dinheiro_parado),
        "detalhe_em": det.get("coletado_em"),
        "alertas": alertas,
    }


def linha_curta(o: dict) -> dict:
    """O mínimo para a lista e o mapa (o arquivo obras.json fica leve)."""
    return {
        "id": o["id"], "n": o["nome"][:140], "s": o["situacao"], "m": o["municipios"],
        "t": (o["tipos"] or [None])[0], "st": (o["subtipos"] or [None])[0], "e": o["especie"],
        "v": o["valor_previsto"], "vh": o["valor_previsto_hoje"], "em": o["empenhado"],
        "pf": o["percentual_fisico"], "da": o["dias_atraso"], "dp": o["dias_parada"],
        "fp": o["datas"]["fim_previsto"], "ds": o["data_situacao"], "p": o["ponto"],
        "pr": o["programa"], "ex": [x["nome"] for x in o["executores"]][:2],
    }


def resumo(obras: list[dict]) -> dict:
    def soma(campo, filtro=lambda o: True):
        return r2(sum(o[campo] or 0 for o in obras if filtro(o)))
    por_sit = {}
    for o in obras:
        s = por_sit.setdefault(o["situacao"], {"texto": o["situacao_txt"], "n": 0, "valor": 0.0})
        s["n"] += 1
        s["valor"] += o["valor_previsto"] or 0
    for s in por_sit.values():
        s["valor"] = r2(s["valor"])
    ativas = [o for o in obras if o["situacao"] not in ENCERRADAS]
    return {
        "n_obras": len(obras),
        "valor_previsto": soma("valor_previsto"),
        "valor_previsto_hoje": soma("valor_previsto_hoje"),
        "empenhado": soma("empenhado"),
        "por_situacao": por_sit,
        "n_paradas": sum(1 for o in obras if o["situacao"] in PARADAS),
        "valor_paradas": soma("valor_previsto", lambda o: o["situacao"] in PARADAS),
        "dinheiro_parado": soma("dinheiro_parado"),
        "n_atrasadas": sum(1 for o in obras if o["situacao"] == "em_execucao" and (o["dias_atraso"] or 0) > 0),
        "n_nao_iniciadas_vencidas": sum(1 for o in obras if o["situacao"] == "cadastrada" and (o["dias_atraso"] or 0) > 0),
        "n_ativas": len(ativas),
        "n_sem_municipio": sum(1 for o in obras if "sem_municipio" in o["alertas"]),
        "n_sem_valor": sum(1 for o in obras if "sem_valor" in o["alertas"]),
        "n_sem_detalhe": sum(1 for o in obras if not o["detalhe_em"]),
    }


def por_municipio(obras, municipios: Municipios, populacao: dict) -> list[dict]:
    out = {}
    for ibge, nome in municipios.nome.items():
        serie = populacao.get(ibge) or {}
        anos = sorted(int(a) for a in serie)
        pop = serie.get(str(anos[-1]), serie.get(anos[-1])) if anos else None
        out[ibge] = {"ibge": ibge, "nome": nome, "populacao": pop, "n": 0, "valor": 0.0,
                     "n_paradas": 0, "valor_paradas": 0.0, "dinheiro_parado": 0.0, "n_atrasadas": 0}
    for o in obras:
        if len(o["municipios"]) != 1:      # obras de vários municípios (estradas) não entram na conta por município
            continue
        m = out.get(o["municipios"][0])
        if not m:
            continue
        m["n"] += 1
        m["valor"] += o["valor_previsto"] or 0
        if o["situacao"] in PARADAS:
            m["n_paradas"] += 1
            m["valor_paradas"] += o["valor_previsto"] or 0
            m["dinheiro_parado"] += o["dinheiro_parado"] or 0
        if o["situacao"] == "em_execucao" and (o["dias_atraso"] or 0) > 0:
            m["n_atrasadas"] += 1
    for m in out.values():
        for k in ("valor", "valor_paradas", "dinheiro_parado"):
            m[k] = r2(m[k])
        m["valor_por_hab"] = r2(m["valor"] / m["populacao"]) if m["populacao"] else None
    return sorted(out.values(), key=lambda m: m["nome"])


# ------------------------------------------------------------------ principal
def _ler(p: Path, padrao=None):
    try:
        return json.loads(p.read_text("utf-8")) if p.exists() else padrao
    except json.JSONDecodeError:
        return padrao


def _gravar(p: Path, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), "utf-8")


def montar(brutos: Path, saida: Path, hoje: date, gerado_em: str):
    import config
    bruto = _ler(brutos / "obrasgov" / "projetos.json", {}) or {}
    projetos = bruto.get("obras", [])
    municipios = Municipios(_ler(brutos / "ibge" / "municipios.json", []) or [],
                            _ler(brutos / "ibge" / "malha.json", {}) or {})
    populacao = _ler(brutos / "ibge" / "populacao.json", {}) or {}
    ipca = _ler(brutos / "ipca.json", {}) or {}
    fatores = ipca.get("fatores", {})

    obras = []
    for p in projetos:
        det = _ler(brutos / "obrasgov" / "detalhe" / f"{p['idUnico'].replace('/', '_')}.json")
        obras.append(montar_obra(p, det, municipios, fatores, hoje))
    obras.sort(key=lambda o: o["id"])

    pasta_o = saida / "o"
    pasta_o.mkdir(parents=True, exist_ok=True)
    ids = set()
    for o in obras:
        nome = o["id"].replace("/", "_")
        ids.add(f"{nome}.json")
        _gravar(pasta_o / f"{nome}.json", o)
    for velho in pasta_o.glob("*.json"):     # obra que saiu do cadastro
        if velho.name not in ids:
            velho.unlink()

    _gravar(saida / "obras.json", [linha_curta(o) for o in obras])
    _gravar(saida / "municipios.json", por_municipio(obras, municipios, populacao))
    _gravar(saida / "meta.json", {
        "uf": config.UF, "estado": config.ESTADO, "do_estado": config.DO_ESTADO,
        "gerado_em": gerado_em, "hoje": hoje.isoformat(),
        "lista_coletada_em": bruto.get("coletado_em"),
        "ipca_referencia": ipca.get("referencia"),
        "fontes": [
            {"nome": "ObrasGov.br (Ministério da Gestão)", "url": "https://obrasgov.gestao.gov.br/",
             "uso": "cadastro das obras, execução física, empenhos e mapa"},
            {"nome": "IBGE", "url": "https://servicodados.ibge.gov.br/", "uso": "municípios, limites e população"},
            {"nome": "Banco Central (IPCA)", "url": "https://www3.bcb.gov.br/sgspub/", "uso": "correção pela inflação"},
        ],
        "resumo": resumo(obras),
        "municipios_nomes": municipios.nome,
    })
    return obras
