"""Projeto Quanto Custa — Obras públicas federais de um estado (configuração).

Piloto: Ceará. Para abrir outro estado, só o bloco "ESTADO" muda.
"""
# --- ESTADO (muda em cada estado) ---
UF = "CE"
CODIGO_UF_IBGE = 23
ESTADO = "Ceará"
DO_ESTADO = "do Ceará"
# --- fim do bloco ESTADO ---

USER_AGENT = "ProjetoQuantoCusta/1.0 (painel de transparencia com dados abertos)"

# --- ObrasGov.br (Cadastro Integrado de Projetos de Investimento, Decreto 10.496/2020) ---
# A API é lenta (~0,8 s por obra listada) e fica atrás de um firewall que bloqueia acessos rápidos:
# páginas de 50 e pausa entre chamadas. Páginas de 200 estouram o tempo (erro 524).
OBRASGOV = "https://api.obrasgov.gestao.gov.br/obrasgov/api"
OBRASGOV_TAMANHO_PAGINA = 50
OBRASGOV_PAUSA = 1.0
# Detalhes (execução física, financeira e mapa) de cada obra: renovados quando a obra muda de
# situação ou depois deste número de dias.
DETALHE_VALIDADE_DIAS = 30

# --- IBGE ---
IBGE_MUNICIPIOS = f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{CODIGO_UF_IBGE}/municipios"
IBGE_MALHA = (f"https://servicodados.ibge.gov.br/api/v3/malhas/estados/{CODIGO_UF_IBGE}"
              "?intrarregiao=municipio&formato=application/vnd.geo+json&qualidade=intermediaria")
IBGE_ESTIMATIVA = ("https://servicodados.ibge.gov.br/api/v3/agregados/6579/periodos/all/"
                   f"variaveis/9324?localidades=N6[N3[{CODIGO_UF_IBGE}]]")
IBGE_CENSO_2022 = ("https://servicodados.ibge.gov.br/api/v3/agregados/4714/periodos/2022/"
                   f"variaveis/93?localidades=N6[N3[{CODIGO_UF_IBGE}]]")
SIDRA_ESTIMATIVA = f"https://apisidra.ibge.gov.br/values/t/6579/n6/in%20n3%20{CODIGO_UF_IBGE}/v/9324/p/all"
SIDRA_CENSO_2022 = f"https://apisidra.ibge.gov.br/values/t/4714/n6/in%20n3%20{CODIGO_UF_IBGE}/v/93/p/2022"

ANO_INICIAL_IPCA = 2000
