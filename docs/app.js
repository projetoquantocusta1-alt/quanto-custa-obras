/* Quanto Custa? Obras — site estático. Lê docs/dados/*.json gerados pelo robô (atualizar.py). */
"use strict";

const SIT = {
  em_execucao: ["Em execução", "var(--s-em_execucao)"],
  paralisada: ["Paralisada", "var(--s-paralisada)"],
  inacabada: ["Inacabada", "var(--s-inacabada)"],
  cadastrada: ["Cadastrada", "var(--s-cadastrada)"],
  concluida: ["Concluída", "var(--s-concluida)"],
  cancelada: ["Cancelada", "var(--s-cancelada)"],
};
const ORDEM_SIT = ["paralisada", "inacabada", "em_execucao", "cadastrada", "concluida", "cancelada"];
const PARADAS = new Set(["paralisada", "inacabada"]);
const ENCERRADAS = new Set(["concluida", "cancelada"]);
const COR_HEX = { em_execucao: "#2475B8", paralisada: "#C84C4C", inacabada: "#8E2F2F", cadastrada: "#8FA3B8",
  concluida: "#16865D", cancelada: "#5B6878" };

let META, OBRAS, MUNS, NOME_MUN = {};
const cacheObra = {};

/* ---------------------------------------------------------------- formatação */
const fmtInt = new Intl.NumberFormat("pt-BR");
const fmtR = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
const fmtR2 = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
function reais(v) { return v == null ? "—" : fmtR.format(v); }
function reaisC(v) { // compacto: R$ 1,2 mi
  if (v == null) return "—";
  const a = Math.abs(v);
  if (a >= 1e9) return "R$ " + (v / 1e9).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + " bi";
  if (a >= 1e6) return "R$ " + (v / 1e6).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + " mi";
  if (a >= 1e3) return "R$ " + (v / 1e3).toLocaleString("pt-BR", { maximumFractionDigits: 0 }) + " mil";
  return fmtR.format(v);
}
function dataBR(s) { if (!s) return "—"; const [a, m, d] = s.slice(0, 10).split("-"); return `${d}/${m}/${a}`; }
function tempo(dias) {
  if (dias == null) return "—";
  if (dias < 60) return `${dias} dias`;
  const anos = dias / 365.25;
  if (anos < 1.5) return `${Math.round(dias / 30.4)} meses`;
  return `${anos.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} anos`;
}
function esc(s) { return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]); }
function selo(s) { const [t, c] = SIT[s] || [s, "var(--s-outra)"]; return `<span class="selo" style="background:${c}">${esc(t)}</span>`; }
function semAcento(s) { return (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase(); }
function nomeMun(ib) { return NOME_MUN[ib] || ib; }
function munsTxt(lista) {
  if (!lista || !lista.length) return "município não identificado";
  if (lista.length > 3) return `${lista.length} municípios`;
  return lista.map(nomeMun).join(", ");
}

/* ---------------------------------------------------------------- dados */
async function carregar(nome) {
  const r = await fetch(`dados/${nome}`, { cache: "no-cache" });
  if (!r.ok) throw new Error(`${nome}: ${r.status}`);
  return r.json();
}
async function obra(id) {
  if (!cacheObra[id]) cacheObra[id] = await carregar(`o/${id.replace(/\//g, "_")}.json`);
  return cacheObra[id];
}

/* ---------------------------------------------------------------- componentes */
function cartaoObra(o) {
  let extra = "";
  if (PARADAS.has(o.s) && o.dp != null) extra = `parada há ${tempo(o.dp)}`;
  else if (!ENCERRADAS.has(o.s) && o.da > 0) extra = `${tempo(o.da)} de atraso`;
  const pf = o.pf != null ? ` · ${Math.round(o.pf)}% executado` : "";
  return `<a class="obra" href="#/obra/${encodeURIComponent(o.id)}">
    <div class="t">${esc(o.n)}</div>
    <div class="dir"><div class="v">${reaisC(o.v)}</div>${extra ? `<div class="x">${extra}</div>` : ""}</div>
    <div class="info">${selo(o.s)} ${esc(munsTxt(o.m))}${o.t ? " · " + esc(o.t) : ""}${pf}</div>
  </a>`;
}

function barraSituacoes(lista, porValor) {
  const tot = {};
  for (const o of lista) tot[o.s] = (tot[o.s] || 0) + (porValor ? (o.v || 0) : 1);
  const soma = Object.values(tot).reduce((a, b) => a + b, 0) || 1;
  const chaves = ORDEM_SIT.filter(k => tot[k]).concat(Object.keys(tot).filter(k => !ORDEM_SIT.includes(k)));
  const barra = chaves.map(k => `<span title="${esc((SIT[k] || [k])[0])}" style="width:${(100 * tot[k] / soma).toFixed(2)}%;background:${(SIT[k] || [0, "var(--s-outra)"])[1]}"></span>`).join("");
  const leg = chaves.map(k => `<span><i style="background:${(SIT[k] || [0, "var(--s-outra)"])[1]}"></i>${esc((SIT[k] || [k])[0])}: ${porValor ? reaisC(tot[k]) : fmtInt.format(tot[k])}</span>`).join("");
  return `<div class="barra">${barra}</div><div class="legenda">${leg}</div>`;
}

function kpi(rot, val, det, alerta) {
  return `<div class="kpi${alerta ? " alerta" : ""}"><div class="rot">${rot}</div><div class="val">${val}</div>${det ? `<div class="det">${det}</div>` : ""}</div>`;
}

/* ---------------------------------------------------------------- telas */
function telaInicio(app) {
  const r = META.resumo;
  const paradas = OBRAS.filter(o => PARADAS.has(o.s)).sort((a, b) => (b.v || 0) - (a.v || 0));
  const atrasadas = OBRAS.filter(o => !ENCERRADAS.has(o.s) && !PARADAS.has(o.s) && o.da > 0).sort((a, b) => b.da - a.da);
  const munsParadas = MUNS.filter(m => m.n_paradas).sort((a, b) => b.valor_paradas - a.valor_paradas).slice(0, 8);
  app.innerHTML = `
    <div class="etiqueta">Obras com dinheiro federal · ${esc(META.estado)}</div>
    <h1>Quanto custam as obras federais ${esc(META.do_estado)}?</h1>
    <p class="lead">Cada obra pública com recursos da União cadastrada no ObrasGov.br: quanto foi prometido,
    quanto já foi reservado no orçamento, em que pé está e quais estão paradas.</p>
    <div class="kpis">
      ${kpi("Obras cadastradas", fmtInt.format(r.n_obras), `${fmtInt.format(r.n_ativas)} ainda não concluídas`)}
      ${kpi("Valor previsto", reaisC(r.valor_previsto), r.valor_previsto_hoje ? `${reaisC(r.valor_previsto_hoje)} em valores de hoje` : "")}
      ${kpi("Obras paradas", fmtInt.format(r.n_paradas), `paralisadas ou inacabadas · ${reaisC(r.valor_paradas)} previstos`, true)}
      ${kpi("Dinheiro parado", reaisC(r.dinheiro_parado), "já reservado (empenhado) em obras paradas", true)}
      ${kpi("Atrasadas", fmtInt.format(r.n_atrasadas), "em andamento e já passaram do prazo")}
    </div>
    <div class="painel">
      <div class="etiqueta">Situação das obras (pelo valor previsto)</div>
      ${barraSituacoes(OBRAS, true)}
    </div>
    <h2>As maiores obras paradas</h2>
    <div class="obras">${paradas.slice(0, 8).map(cartaoObra).join("") || "<p>Nenhuma obra parada.</p>"}</div>
    ${paradas.length > 8 ? `<p><a href="#/paradas">Ver as ${fmtInt.format(paradas.length)} obras paradas →</a></p>` : ""}
    <h2>As mais atrasadas entre as que estão andando</h2>
    <div class="obras">${atrasadas.slice(0, 6).map(cartaoObra).join("") || "<p>Nenhuma.</p>"}</div>
    <p><a href="#/obras?ordem=atraso">Ver todas pela ordem de atraso →</a></p>
    <h2>Municípios com mais dinheiro em obras paradas</h2>
    ${tabelaMunicipios(munsParadas, true)}
    <p><a href="#/municipios">Ver todos os municípios →</a></p>`;
}

function parametros() {
  const q = location.hash.split("?")[1] || "";
  return Object.fromEntries(new URLSearchParams(q));
}

function telaObras(app, fixo = {}) {
  const p = Object.assign({ busca: "", sit: "", mun: "", tipo: "", ordem: "valor" }, parametros(), fixo);
  const tipos = [...new Set(OBRAS.map(o => o.t).filter(Boolean))].sort();
  const munsCom = [...new Set(OBRAS.flatMap(o => o.m || []))].sort((a, b) => nomeMun(a).localeCompare(nomeMun(b)));
  const titulo = fixo.paradas ? "Obras paradas" : "Todas as obras";
  app.innerHTML = `
    <div class="etiqueta">${esc(META.estado)}</div>
    <h1>${titulo}</h1>
    ${fixo.paradas ? `<p class="lead">Obras que o próprio cadastro federal marca como <b>paralisadas</b> ou <b>inacabadas</b>.
      “Dinheiro parado” é o que já foi empenhado (reservado no orçamento federal) para elas.</p>` : ""}
    <div class="filtros">
      <input id="f-busca" type="search" placeholder="Buscar pelo nome, órgão ou programa" value="${esc(p.busca)}" aria-label="Buscar">
      ${fixo.paradas ? "" : `<select id="f-sit" aria-label="Situação"><option value="">Todas as situações</option>
        <option value="paradas">Paradas (paralisadas e inacabadas)</option>
        <option value="atrasadas">Atrasadas (em andamento)</option>
        ${ORDEM_SIT.map(k => `<option value="${k}">${SIT[k][0]}</option>`).join("")}</select>`}
      <select id="f-mun" aria-label="Município"><option value="">Todos os municípios</option>
        ${munsCom.map(m => `<option value="${m}">${esc(nomeMun(m))}</option>`).join("")}</select>
      <select id="f-tipo" aria-label="Tipo"><option value="">Todos os tipos</option>
        ${tipos.map(t => `<option>${esc(t)}</option>`).join("")}</select>
      <select id="f-ordem" aria-label="Ordem">
        <option value="valor">Maior valor</option><option value="atraso">Mais atraso</option>
        <option value="parada">Parada há mais tempo</option><option value="pf">Menos executada</option>
        <option value="nome">Nome</option></select>
    </div>
    <div class="contagem" id="contagem"></div>
    <div class="obras" id="lista"></div>
    <button class="btn-sec mais" id="mais" hidden>Mostrar mais</button>`;
  const $ = id => document.getElementById(id);
  if ($("f-sit")) $("f-sit").value = p.sit;
  $("f-mun").value = p.mun; $("f-tipo").value = p.tipo; $("f-ordem").value = p.ordem;
  let limite = 60;
  function aplicar() {
    const busca = semAcento($("f-busca").value.trim());
    const sit = $("f-sit") ? $("f-sit").value : "", mun = $("f-mun").value, tipo = $("f-tipo").value, ordem = $("f-ordem").value;
    let l = OBRAS.filter(o => {
      if (fixo.paradas && !PARADAS.has(o.s)) return false;
      if (sit === "paradas" && !PARADAS.has(o.s)) return false;
      if (sit === "atrasadas" && !(o.da > 0 && !ENCERRADAS.has(o.s) && !PARADAS.has(o.s))) return false;
      if (sit && !["paradas", "atrasadas"].includes(sit) && o.s !== sit) return false;
      if (mun && !(o.m || []).includes(mun)) return false;
      if (tipo && o.t !== tipo) return false;
      if (busca) {
        const alvo = semAcento([o.n, o.id, o.pr, (o.ex || []).join(" "), munsTxt(o.m), o.t, o.st].join(" "));
        if (!busca.split(/\s+/).every(w => alvo.includes(w))) return false;
      }
      return true;
    });
    const ord = {
      valor: (a, b) => (b.v || 0) - (a.v || 0),
      atraso: (a, b) => (ENCERRADAS.has(a.s) ? -1 : a.da || -1) < (ENCERRADAS.has(b.s) ? -1 : b.da || -1) ? 1 : -1,
      parada: (a, b) => (b.dp ?? -1) - (a.dp ?? -1),
      pf: (a, b) => (a.pf ?? 101) - (b.pf ?? 101),
      nome: (a, b) => a.n.localeCompare(b.n),
    }[ordem];
    l.sort(ord);
    const soma = l.reduce((s, o) => s + (o.v || 0), 0);
    $("contagem").textContent = `${fmtInt.format(l.length)} obras · ${reaisC(soma)} previstos`;
    $("lista").innerHTML = l.slice(0, limite).map(cartaoObra).join("") || "<p>Nenhuma obra com esses filtros.</p>";
    $("mais").hidden = l.length <= limite;
    const q = new URLSearchParams();
    for (const [k, v] of [["busca", $("f-busca").value], ["sit", sit], ["mun", mun], ["tipo", tipo], ["ordem", ordem !== "valor" ? ordem : ""]]) if (v) q.set(k, v);
    const base = location.hash.split("?")[0];
    history.replaceState(null, "", base + (q.toString() ? "?" + q : ""));
  }
  for (const id of ["f-busca", "f-sit", "f-mun", "f-tipo", "f-ordem"]) if ($(id)) $(id).addEventListener("input", () => { limite = 60; aplicar(); });
  $("mais").addEventListener("click", () => { limite += 120; aplicar(); });
  aplicar();
}

function tabelaMunicipios(lista, curta) {
  return `<div class="tabela-wrap"><table>
    <thead><tr><th>Município</th><th class="n">Obras</th><th class="n">Valor previsto</th>${curta ? "" : `<th class="n">Por habitante</th>`}
    <th class="n">Paradas</th><th class="n">Valor das paradas</th><th class="n">Dinheiro parado</th></tr></thead>
    <tbody>${lista.map(m => `<tr><td><a href="#/municipio/${m.ibge}">${esc(m.nome)}</a></td>
      <td class="n">${fmtInt.format(m.n)}</td><td class="n">${reaisC(m.valor)}</td>
      ${curta ? "" : `<td class="n">${m.valor_por_hab != null ? fmtR2.format(m.valor_por_hab) : "—"}</td>`}
      <td class="n">${m.n_paradas ? fmtInt.format(m.n_paradas) : "—"}</td><td class="n">${m.n_paradas ? reaisC(m.valor_paradas) : "—"}</td>
      <td class="n">${m.dinheiro_parado ? reaisC(m.dinheiro_parado) : "—"}</td></tr>`).join("")}</tbody></table></div>`;
}

function telaMunicipios(app) {
  let ordem = parametros().ordem || "valor";
  app.innerHTML = `<div class="etiqueta">${esc(META.estado)}</div><h1>Obras por município</h1>
    <p class="lead">Só entram as obras de um município só. Estradas e obras que passam por vários municípios aparecem
    na lista de obras, mas não na conta de cada um. “Por habitante” usa a população mais recente do IBGE.</p>
    <div class="filtros"><input id="f-busca" type="search" placeholder="Buscar município" aria-label="Buscar município">
    <select id="f-ordem" aria-label="Ordem"><option value="valor">Maior valor</option><option value="hab">Maior valor por habitante</option>
    <option value="paradas">Mais dinheiro em obras paradas</option><option value="n">Mais obras</option><option value="nome">Nome</option></select></div>
    <div id="tab"></div>`;
  const $ = id => document.getElementById(id);
  $("f-ordem").value = ordem;
  function aplicar() {
    const b = semAcento($("f-busca").value);
    const o = $("f-ordem").value;
    const f = { valor: (a, c) => c.valor - a.valor, hab: (a, c) => (c.valor_por_hab || 0) - (a.valor_por_hab || 0),
      paradas: (a, c) => c.valor_paradas - a.valor_paradas || c.n_paradas - a.n_paradas, n: (a, c) => c.n - a.n,
      nome: (a, c) => a.nome.localeCompare(c.nome) }[o];
    $("tab").innerHTML = tabelaMunicipios(MUNS.filter(m => !b || semAcento(m.nome).includes(b)).slice().sort(f), false);
  }
  $("f-busca").addEventListener("input", aplicar); $("f-ordem").addEventListener("input", aplicar);
  aplicar();
}

function telaMunicipio(app, ibge) {
  const m = MUNS.find(x => x.ibge === ibge);
  if (!m) { app.innerHTML = "<p>Município não encontrado.</p>"; return; }
  const lista = OBRAS.filter(o => (o.m || []).includes(ibge)).sort((a, b) => (b.v || 0) - (a.v || 0));
  app.innerHTML = `<div class="etiqueta"><a href="#/municipios">Municípios</a> · ${esc(META.estado)}</div>
    <h1>${esc(m.nome)}</h1>
    <div class="kpis">
      ${kpi("Obras federais", fmtInt.format(lista.length), m.populacao ? `${fmtInt.format(m.populacao)} habitantes` : "")}
      ${kpi("Valor previsto", reaisC(m.valor), m.valor_por_hab != null ? `${fmtR2.format(m.valor_por_hab)} por habitante` : "")}
      ${kpi("Obras paradas", fmtInt.format(m.n_paradas), m.n_paradas ? `${reaisC(m.valor_paradas)} previstos` : "", m.n_paradas > 0)}
      ${kpi("Dinheiro parado", reaisC(m.dinheiro_parado), "empenhado em obras paradas", m.dinheiro_parado > 0)}
    </div>
    ${lista.length ? `<div class="painel">${barraSituacoes(lista, false)}</div>` : ""}
    <h2>Obras</h2><div class="obras">${lista.map(cartaoObra).join("") || "<p>Nenhuma obra federal cadastrada.</p>"}</div>`;
}

async function telaObra(app, id) {
  app.innerHTML = `<p class="carregando">Carregando a obra…</p>`;
  let o;
  try { o = await obra(id); } catch (e) { app.innerHTML = "<p>Obra não encontrada.</p>"; return; }
  const ativa = !ENCERRADAS.has(o.situacao);
  const linhas = [];
  const d = o.datas;
  if (d.inicio_previsto) linhas.push(["Início previsto", dataBR(d.inicio_previsto)]);
  if (d.inicio_efetivo) linhas.push(["Início de fato", dataBR(d.inicio_efetivo)]);
  if (d.fim_previsto) linhas.push(["Fim previsto", dataBR(d.fim_previsto), o.dias_atraso > 0]);
  if (d.fim_efetivo) linhas.push(["Fim de fato", dataBR(d.fim_efetivo)]);
  if (o.data_situacao) linhas.push([`Situação “${o.situacao_txt}” desde`, dataBR(o.data_situacao)]);
  const avisos = [];
  if (o.alertas.includes("sem_valor")) avisos.push("O cadastro não informa o valor desta obra (aparece como R$ 0,01 ou vazio).");
  if (o.alertas.includes("situacao_antiga")) avisos.push("A situação desta obra não é atualizada há mais de um ano. Ela pode já ter mudado.");
  if (o.alertas.includes("sem_municipio")) avisos.push("Não foi possível saber em que município fica esta obra.");
  if (!o.detalhe_em) avisos.push("Os detalhes desta obra (execução e empenhos) ainda não foram buscados pelo robô.");
  const orgs = (rot, l) => l.length ? `<dt>${rot}</dt><dd>${l.map(x => esc(x.nome)).join("<br>")}</dd>` : "";
  app.innerHTML = `
    <div class="etiqueta"><a href="#/obras">Obras</a> · ${esc(munsTxt(o.municipios))}</div>
    <h1>${esc(o.nome)}</h1>
    <div class="ficha-topo">${selo(o.situacao)} ${o.tipos.map(t => `<span class="tag">${esc(t)}</span>`).join("")}
      ${o.subtipos.map(t => `<span class="tag">${esc(t)}</span>`).join("")}</div>
    ${avisos.map(a => `<div class="aviso">${a}</div>`).join("")}
    <div class="kpis">
      ${kpi("Valor previsto", reais(o.valor_previsto), o.valor_previsto_hoje ? `${reais(o.valor_previsto_hoje)} em valores de hoje (IPCA)` : "")}
      ${kpi("Empenhado (reservado)", reais(o.empenhado), o.n_empenhos ? `${o.n_empenhos} empenho(s) no orçamento federal` : "")}
      ${kpi("Executado", o.percentual_fisico != null ? `${Math.round(o.percentual_fisico)}%` : "—", "da obra física, segundo o cadastro")}
      ${PARADAS.has(o.situacao) ? kpi("Parada há", tempo(o.dias_parada), o.dinheiro_parado ? `${reaisC(o.dinheiro_parado)} já empenhados` : "", true)
        : (ativa && o.dias_atraso > 0 ? kpi("Atraso", tempo(o.dias_atraso), "desde o fim previsto", true)
        : (o.situacao === "concluida" && o.dias_atraso > 0 ? kpi("Entregue com atraso de", tempo(o.dias_atraso), "") : ""))}
    </div>
    ${o.percentual_fisico != null ? `<div class="progresso" aria-label="Executado"><span style="width:${Math.min(100, o.percentual_fisico)}%"></span></div>` : ""}
    <div class="grade2">
      <div>
        ${o.descricao && o.descricao !== o.nome ? `<h2>O que é</h2><p>${esc(o.descricao)}</p>` : ""}
        ${o.meta ? `<p><b>Meta:</b> ${esc(o.meta)}</p>` : ""}
        ${o.paralisacoes.length ? `<h2>Por que parou</h2>${o.paralisacoes.map(p => `<div class="painel" style="margin-bottom:8px">
          ${p.motivos.length ? `<div><b>Motivo:</b> ${p.motivos.map(esc).join("; ")}</div>` : ""}
          ${p.indicativos.length ? `<div><b>Sinal de paralisação:</b> ${p.indicativos.map(esc).join("; ")}</div>` : ""}
          ${p.tem_solucao_em_andamento != null ? `<div><b>Há providência em andamento?</b> ${p.tem_solucao_em_andamento ? "Sim" : "Não"}</div>` : ""}
        </div>`).join("")}` : ""}
        <h2>Prazos</h2>
        <ul class="linha-tempo">${linhas.map(([r, v, at]) => `<li class="${at ? "atraso" : ""}"><b>${r}:</b> ${v}</li>`).join("")}</ul>
        <h2>Quem é responsável</h2>
        <dl class="dados">
          ${orgs("Executor", o.executores)}${orgs("Tomador", o.tomadores)}${orgs("Repassador (de onde vem o dinheiro)", o.repassadores)}
          ${o.programa ? `<dt>Programa</dt><dd>${esc(o.programa)}</dd>` : ""}
        </dl>
      </div>
      <div>
        ${o.ponto ? `<div id="mapa-obra" class="mapa pequeno"></div>` : ""}
        <h3>Ficha</h3>
        <dl class="dados">
          <dt>Código no ObrasGov</dt><dd class="num">${esc(o.id)}</dd>
          ${o.instrumento ? `<dt>Convênio/repasse</dt><dd class="num">${esc(o.instrumento)} (Transferegov)</dd>` : ""}
          ${o.especie ? `<dt>Espécie</dt><dd>${esc(o.especie)}</dd>` : ""}
          ${o.natureza ? `<dt>Natureza</dt><dd>${esc(o.natureza)}</dd>` : ""}
          <dt>Município</dt><dd>${o.municipios.map(m => `<a href="#/municipio/${m}">${esc(nomeMun(m))}</a>`).join(", ") || "—"}
            ${o.municipio_origem === "mapa" ? " <small>(pelo ponto no mapa)</small>" : o.municipio_origem === "nome" ? " <small>(pelo nome da obra)</small>" : ""}</dd>
          ${o.fontes_recurso.length ? `<dt>Origem do dinheiro</dt><dd>${o.fontes_recurso.map(f => `${esc(f.origem)}: ${reais(f.valor)}`).join("<br>")}</dd>` : ""}
          ${o.populacao_beneficiada ? `<dt>População beneficiada</dt><dd>${fmtInt.format(o.populacao_beneficiada)}</dd>` : ""}
          ${o.datas.cadastro ? `<dt>Cadastrada em</dt><dd>${dataBR(o.datas.cadastro)}</dd>` : ""}
          ${o.detalhe_em ? `<dt>Dados buscados em</dt><dd>${dataBR(o.detalhe_em)}</dd>` : ""}
        </dl>
        <p style="font-size:13px;color:var(--muted)">Confira no <a href="https://obrasgov.gestao.gov.br/obrasgov/" target="_blank" rel="noopener">ObrasGov.br</a>
        buscando pelo código ${esc(o.id)}.</p>
      </div>
    </div>`;
  if (o.ponto && window.L) {
    const m = L.map("mapa-obra", { scrollWheelZoom: false }).setView(o.ponto, 14);
    camadaBase().addTo(m);
    L.circleMarker(o.ponto, { radius: 9, color: "#fff", weight: 2, fillColor: COR_HEX[o.situacao] || "#B9A26A", fillOpacity: 1 }).addTo(m);
  }
}

function camadaBase() {
  return L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    { maxZoom: 18, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' });
}

function telaMapa(app) {
  const com = OBRAS.filter(o => o.p);
  app.innerHTML = `<div class="etiqueta">${esc(META.estado)}</div><h1>Mapa das obras</h1>
    <p class="lead">${fmtInt.format(com.length)} de ${fmtInt.format(OBRAS.length)} obras têm localização no cadastro.
    Toque num ponto para ver a obra.</p>
    <div class="filtros"><select id="f-sit" aria-label="Situação"><option value="">Todas as situações</option>
    <option value="paradas">Só as paradas</option>${ORDEM_SIT.map(k => `<option value="${k}">${SIT[k][0]}</option>`).join("")}</select></div>
    <div id="mapa" class="mapa"></div>
    <div class="legenda" style="margin-top:8px">${ORDEM_SIT.map(k => `<span><i style="background:${COR_HEX[k]}"></i>${SIT[k][0]}</span>`).join("")}</div>`;
  if (!window.L) { document.getElementById("mapa").textContent = "Não foi possível carregar o mapa."; return; }
  const mapa = L.map("mapa").setView([-5.2, -39.5], 7);
  camadaBase().addTo(mapa);
  let grupo = L.layerGroup().addTo(mapa);
  function aplicar() {
    const s = document.getElementById("f-sit").value;
    grupo.clearLayers();
    const l = com.filter(o => !s || (s === "paradas" ? PARADAS.has(o.s) : o.s === s));
    l.sort((a, b) => (PARADAS.has(a.s) ? 1 : 0) - (PARADAS.has(b.s) ? 1 : 0));   // paradas por cima
    for (const o of l) {
      L.circleMarker(o.p, { radius: PARADAS.has(o.s) ? 7 : 5, color: "#fff", weight: 1, fillColor: COR_HEX[o.s] || "#B9A26A", fillOpacity: .9 })
        .bindPopup(`<b>${esc(o.n)}</b><br>${selo(o.s)} ${reaisC(o.v)}<br><a href="#/obra/${encodeURIComponent(o.id)}">Ver a obra →</a>`)
        .addTo(grupo);
    }
  }
  document.getElementById("f-sit").addEventListener("input", aplicar);
  aplicar();
}

function telaComo(app) {
  const r = META.resumo;
  app.innerHTML = `<div class="texto"><div class="etiqueta">Metodologia</div><h1>Como calculamos</h1>
  <h2>De onde vêm os dados</h2>
  <ul>${META.fontes.map(f => `<li><a href="${f.url}" target="_blank" rel="noopener">${esc(f.nome)}</a>: ${esc(f.uso)}.</li>`).join("")}</ul>
  <p>O <b>ObrasGov.br</b> é o cadastro oficial das obras feitas com dinheiro federal (Decreto 10.496/2020). Quem
  preenche são os próprios órgãos e prefeituras. Por isso, a qualidade de cada ficha depende de quem cadastrou.</p>
  <h2>O que cada número quer dizer</h2>
  <ul>
    <li><b>Valor previsto</b>: o investimento previsto no cadastro, somando todas as origens do dinheiro. Valores como R$ 0,01
    são tratados como “sem valor”. <b>Em valores de hoje</b>: corrigido pelo IPCA desde o ano de início previsto${META.ipca_referencia ? ` (até ${esc(META.ipca_referencia)})` : ""}.</li>
    <li><b>Empenhado</b>: o dinheiro que o governo federal já reservou no orçamento para a obra. Empenhar ainda não é pagar.
    O valor efetivamente pago entra numa próxima etapa, com os dados do Transferegov.</li>
    <li><b>Obras paradas</b>: as que o cadastro marca como <i>paralisadas</i> ou <i>inacabadas</i>. <b>Há quanto tempo</b>:
    desde a data em que essa situação foi registrada.</li>
    <li><b>Dinheiro parado</b>: o que já foi empenhado para as obras paradas.</li>
    <li><b>Atraso</b>: para obras não concluídas, os dias desde o fim previsto até hoje. Para as concluídas, a diferença entre o fim previsto e o fim de fato.</li>
    <li><b>Município</b>: o ObrasGov não informa. Ele é descoberto, nesta ordem, pelo órgão responsável (“Município de…”),
    pelo ponto da obra no mapa (limites do IBGE) ou pelo nome da obra. ${fmtInt.format(r.n_sem_municipio)} obras ficaram sem município.</li>
    <li><b>Por habitante</b>: valor previsto das obras de um só município dividido pela população mais recente do IBGE.</li>
  </ul>
  <h2>Limites que você precisa saber</h2>
  <ul>
    <li>Só obras com dinheiro federal. Obras pagas só com dinheiro da prefeitura ou do estado não aparecem.</li>
    <li>O cadastro depende de quem preenche: há obras sem valor (${fmtInt.format(r.n_sem_valor)}), sem localização ou com a situação desatualizada.
    Quando a situação não muda há mais de um ano, a ficha da obra avisa.</li>
    <li>Ainda não entram os aditivos de contrato (aumentos de valor e de prazo), que virão do PNCP.</li>
  </ul>
  <h2>Privacidade</h2>
  <p>Mostramos só órgãos públicos, nunca nomes de pessoas. O cadastro traz, por exemplo, o nome do servidor responsável
  pelo mapa da obra: esse campo é descartado antes de qualquer gravação. Textos livres (justificativas) também não são publicados,
  porque podem citar pessoas. Das paralisações, ficam só os motivos padronizados.</p>
  <h2>Atualização</h2>
  <p>Um robô consulta o ObrasGov todos os dias. Última atualização: ${esc((META.gerado_em || "").slice(0, 10).split("-").reverse().join("/"))}.</p>
  </div>`;
}

/* ---------------------------------------------------------------- rotas */
function rota() {
  const app = document.getElementById("app");
  const h = decodeURIComponent((location.hash || "#/").slice(1).split("?")[0]);
  const [, sec, arg] = h.split("/");
  document.querySelectorAll(".menu a").forEach(a => a.toggleAttribute("aria-current", false));
  const ativo = { "": "inicio", obras: "obras", obra: "obras", paradas: "paradas", municipios: "municipios", municipio: "municipios", mapa: "mapa", como: "como" }[sec || ""];
  const link = document.querySelector(`.menu a[data-r="${ativo}"]`);
  if (link) link.setAttribute("aria-current", "page");
  window.scrollTo(0, 0);
  if (!sec) return telaInicio(app);
  if (sec === "obras") return telaObras(app);
  if (sec === "paradas") return telaObras(app, { paradas: true });
  if (sec === "obra") return telaObra(app, arg);
  if (sec === "municipios") return telaMunicipios(app);
  if (sec === "municipio") return telaMunicipio(app, arg);
  if (sec === "mapa") return telaMapa(app);
  if (sec === "como") return telaComo(app);
  app.innerHTML = "<p>Página não encontrada.</p>";
}

async function iniciar() {
  try {
    [META, OBRAS, MUNS] = await Promise.all([carregar("meta.json"), carregar("obras.json"), carregar("municipios.json")]);
  } catch (e) {
    document.getElementById("app").innerHTML = `<p>Não foi possível carregar os dados (${esc(e.message)}).</p>`;
    return;
  }
  NOME_MUN = META.municipios_nomes || {};
  document.getElementById("sub-estado").textContent = `Obras federais · ${META.estado}`;
  document.getElementById("atualizado").textContent = META.gerado_em ? `Atualizado em ${META.gerado_em.slice(0, 10).split("-").reverse().join("/")}.` : "";
  document.title = `Quanto Custa? Obras federais · ${META.estado}`;
  window.addEventListener("hashchange", rota);
  rota();
}
iniciar();
