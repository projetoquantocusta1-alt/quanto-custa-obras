from datetime import date

import montagem as M
from coletor import obrasgov

MUNS = M.Municipios(
    [{"ibge": "2313203", "nome": "Tabuleiro do Norte"}, {"ibge": "2304400", "nome": "Fortaleza"},
     {"ibge": "2300101", "nome": "Abaiara"}],
    {"features": [{"properties": {"codarea": "2304400"},
                   "geometry": {"type": "Polygon", "coordinates": [[[-38.7, -3.9], [-38.4, -3.9], [-38.4, -3.6],
                                                                    [-38.7, -3.6], [-38.7, -3.9]]]}}]})
HOJE = date(2026, 11, 23)


def proj(**kw):
    p = {"idUnico": "1.23-45", "nome": "Obra X", "descricao": "", "situacao": "Em execução",
         "dataSituacao": "2026-01-01", "fontesDeRecurso": [{"origem": "Federal", "valorInvestimentoPrevisto": 1000000}],
         "tomadores": [], "executores": [], "repassadores": [], "tipos": [], "subTipos": [], "eixos": []}
    p.update(kw)
    return p


def test_municipio_pelo_orgao():
    assert MUNS.do_orgao("MUNICIPIO DE TABULEIRO DO NORTE") == "2313203"
    assert MUNS.do_orgao("PREFEITURA MUNICIPAL DE FORTALEZA") == "2304400"
    assert MUNS.do_orgao("FUNDO NACIONAL DE DESENVOLVIMENTO DA EDUCAÇÃO") is None


def test_municipio_pelo_texto_e_ponto():
    assert MUNS.do_texto("CR 875966/2018 - PAVIMENTAÇÃO NO MUNICÍPIO DE TABULEIRO DO NORTE / CE") == "2313203"
    assert MUNS.do_ponto(-38.5, -3.7) == "2304400"
    assert MUNS.do_ponto(-40.0, -7.0) is None


def test_pontos_wkt():
    assert M.pontos_wkt("POINT (-38.01045 -5.39079)") == [(-38.01045, -5.39079)]
    assert len(M.pontos_wkt("LINESTRING (-38.1 -5.1, -38.2 -5.2)")) == 2
    assert M.pontos_wkt("POINT (0 0)") == []      # coordenada zerada é descartada


def test_instrumento():
    assert M.instrumento_transferegov(proj(nome="CR 875966/2018 - PAVIMENTAÇÃO"), []) == "875966"
    geo = [{"infoAdicionais": "Cadastro automatizado da obra pelo Transferegov da proposta 052741/2018 e instrumento 875966"}]
    assert M.instrumento_transferegov(proj(), geo) == "875966"


def test_paralisada_dinheiro_parado_e_tempo():
    p = proj(situacao="Paralisada", dataSituacao="2024-04-29", dataFinalPrevista="2025-12-26",
             executores=[{"nome": "MUNICIPIO DE TABULEIRO DO NORTE", "codigo": 7891682000119}])
    det = {"financeira": [{"valorEmpenho": 911877.39}], "fisica": [{"percentual": 40, "dataSituacao": "2024-04-29",
           "cancelamentosParalisacoes": [{"motivosParalisacao": [{"descricao": "Chuvas"}], "justificativa": "texto livre"}]}],
           "coletado_em": "2026-11-23"}
    o = M.montar_obra(p, det, MUNS, {}, HOJE)
    assert o["situacao"] == "paralisada"
    assert o["municipios"] == ["2313203"] and o["municipio_origem"] == "orgao"
    assert o["dinheiro_parado"] == 911877.39
    assert o["dias_parada"] == (HOJE - date(2024, 4, 29)).days
    assert o["dias_atraso"] == (HOJE - date(2025, 12, 26)).days
    assert o["paralisacoes"][0]["motivos"] == ["Chuvas"]
    assert "texto livre" not in str(o)          # justificativa (texto livre) não é publicada
    assert "situacao_antiga" in o["alertas"]


def test_valor_marcador_e_concluida_com_atraso():
    p = proj(situacao="Concluída", dataFinalPrevista="2012-05-20", dataFinalEfetiva="2012-06-19",
             fontesDeRecurso=[{"origem": "Federal", "valorInvestimentoPrevisto": 0.01}])
    o = M.montar_obra(p, None, MUNS, {}, HOJE)
    assert o["valor_previsto"] is None and "sem_valor" in o["alertas"]
    assert o["dias_atraso"] == 30
    assert o["dinheiro_parado"] is None


def test_ipca():
    p = proj(dataInicialPrevista="2020-03-01")
    o = M.montar_obra(p, None, MUNS, {"2020": 1.5}, HOJE)
    assert o["valor_previsto_hoje"] == 1500000


def test_privacidade_orgaos():
    p = obrasgov.limpar_projeto(proj(tomadores=[{"nome": "FULANO DE TAL", "codigo": 11144477735},
                                                {"nome": "MUNICIPIO DE ABAIARA", "codigo": 7891682000119},
                                                {"nome": "FNDE", "codigo": 253}]))
    assert [t["nome"] for t in p["tomadores"]] == ["MUNICIPIO DE ABAIARA", "FNDE"]


def test_resumo_e_municipios():
    obras = [M.montar_obra(proj(idUnico="a", situacao="Paralisada",
                                executores=[{"nome": "MUNICIPIO DE ABAIARA"}]), {"financeira": [{"valorEmpenho": 10}]},
                           MUNS, {}, HOJE),
             M.montar_obra(proj(idUnico="b", executores=[{"nome": "MUNICIPIO DE ABAIARA"}]), None, MUNS, {}, HOJE)]
    r = M.resumo(obras)
    assert r["n_obras"] == 2 and r["n_paradas"] == 1 and r["dinheiro_parado"] == 10
    ms = {m["ibge"]: m for m in M.por_municipio(obras, MUNS, {"2300101": {"2025": 1000}})}
    assert ms["2300101"]["n"] == 2 and ms["2300101"]["valor_por_hab"] == 2000
