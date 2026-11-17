/* Muro de arrimo — interface para celular.
   Só desenha: formulário, validação e cálculo vêm do Python (android/ponte.py + core/). */
"use strict";

const $ = (s, raiz = document) => raiz.querySelector(s);
const $$ = (s, raiz = document) => [...raiz.querySelectorAll(s)];
const el = (tag, attrs = {}, ...filhos) => {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") n.className = v;
    else if (k === "text") n.textContent = v;
    else if (v !== null && v !== undefined && v !== false) n.setAttribute(k, v === true ? "" : v);
  }
  for (const f of filhos) if (f !== null && f !== undefined) n.append(f);
  return n;
};
const CHAVE = "muro-arrimo/dados/v1";
const CHAVE_META = "muro-arrimo/meta/v1";

let esquema = null;        // seções e campos (vem do Python)
let campos = {};           // nome -> definição
let dados = {};            // nome -> valor (null = segue o campo vinculado)
let ultimo = null;         // último resultado válido
let pedido = 0;

/* ------------------------------------------------------------------ motor (Web Worker) */
const motor = new Worker("motor.js", { type: "module" });
const espera = new Map();
let seq = 0;
function chamar(funcao, objeto) {
  return new Promise((ok, falha) => {
    const id = ++seq;
    espera.set(id, { ok, falha });
    motor.postMessage({ id, funcao, texto: JSON.stringify(objeto) });
  });
}
motor.onmessage = (ev) => {
  const m = ev.data;
  if (m.tipo === "progresso") $("#msg-carga").textContent = m.texto;
  else if (m.tipo === "pronto") iniciar(JSON.parse(m.esquema));
  else if (m.tipo === "falha") falhaDeCarga(m.texto);
  else if (m.tipo === "resposta") {
    const p = espera.get(m.id);
    espera.delete(m.id);
    if (m.erro) p.falha(new Error(m.erro)); else p.ok(JSON.parse(m.texto));
  }
};
motor.onerror = (ev) => falhaDeCarga(ev.message || "erro ao carregar o motor de cálculo");

function falhaDeCarga(texto) {
  $("#carregando").replaceChildren(
    el("p", { class: "erro", text: "Não foi possível carregar o motor de cálculo." }),
    el("p", { class: "fraco", text: texto }),
    el("p", { class: "fraco", text: "Na primeira abertura é preciso estar com internet. Feche e abra o aplicativo de novo." }),
  );
  estado("falhou", "nok");
}
function estado(texto, classe = "") {
  const e = $("#estado");
  e.textContent = texto;
  e.className = "estado " + classe;
}

/* ------------------------------------------------------------------ armazenamento */
function guardar() {
  try {
    localStorage.setItem(CHAVE, JSON.stringify(dados));
    localStorage.setItem(CHAVE_META, JSON.stringify(meta()));
  } catch (_) { /* sem armazenamento (modo privado): segue sem guardar */ }
}
function ler(chave) {
  try { return JSON.parse(localStorage.getItem(chave) || "null"); } catch (_) { return null; }
}
const meta = () => ({ nome: $("#proj-nome").value, obra: $("#proj-obra").value, autor: $("#proj-autor").value });

/* ------------------------------------------------------------------ formulário */
const fmtNumero = (v) => (v === null || v === undefined ? "" : String(Math.round(v * 1e6) / 1e6));
const rotulo = (c) => el("span", {}, c.rotulo, c.unidade ? el("span", { class: "un", text: ` (${c.unidade})` }) : null);

function criarCampo(c) {
  const id = "c-" + c.nome;
  const caixa = el("div", { "data-campo": c.nome });
  const ajuda = c.ajuda ? el("div", { class: "ajuda", text: c.ajuda }) : "";   // "" não acrescenta nada
  if (c.tipo === "bool") {
    const inp = el("input", { type: "checkbox", id });
    inp.addEventListener("change", () => mudar(c.nome, inp.checked));
    caixa.append(el("label", { class: "chave" }, inp, el("span", { text: c.rotulo })), ajuda);
    return caixa;
  }
  if (c.tipo === "enum" || c.tipo === "bitola") {
    const sel = el("select", { id });
    for (const o of c.opcoes) {
      const valor = c.tipo === "enum" ? o.valor : o;
      const texto = c.tipo === "enum" ? o.valor + (o.legada ? "  ·  legado" : "") : "ϕ " + String(valor).replace(".", ",");
      sel.append(el("option", { value: valor, text: texto }));
    }
    sel.addEventListener("change", () => mudar(c.nome, c.tipo === "enum" ? sel.value : Number(sel.value)));
    caixa.append(el("label", { class: "campo" }, rotulo(c), sel));
    if (c.tipo === "enum") caixa.append(el("div", { class: "legado", hidden: true, text: "⚠ Opção legada: reproduz o GEO5 e se afasta do critério padrão." }));
    caixa.append(ajuda);
    return caixa;
  }
  const inp = el("input", { type: "number", id, inputmode: c.tipo === "int" ? "numeric" : "decimal",
    step: c.tipo === "int" ? 1 : "any", min: c.min, max: c.max });
  const ler = () => {
    const v = inp.value.trim() === "" ? NaN : Number(inp.value);
    const ok = Number.isFinite(v) && (c.min === null || v >= c.min) && (c.max === null || v <= c.max);
    inp.classList.toggle("invalido", !ok);
    if (Number.isFinite(v)) mudar(c.nome, c.tipo === "int" ? Math.round(v) : v);
  };
  inp.addEventListener("input", ler);
  if (c.vinculo) {
    const chk = el("input", { type: "checkbox", id: id + "-vinc" });
    chk.addEventListener("change", () => {
      if (chk.checked) mudar(c.nome, null);
      else { inp.value = fmtNumero(dados[c.vinculo]); mudar(c.nome, Number(dados[c.vinculo])); }
      pintar();
    });
    caixa.append(el("label", { class: "chave" }, chk, el("span", { text: `${c.rotulo}: igual a “${c.vinculo_rotulo}”` })));
  }
  caixa.append(el("label", { class: "campo" }, rotulo(c), inp), ajuda);
  return caixa;
}

function montarFormulario() {
  for (const estrutural of [false, true]) {
    const destino = $(estrutural ? "#form-estrutural" : "#form-dados");
    destino.replaceChildren();
    for (const s of esquema.secoes.filter((x) => x.estrutural === estrutural)) {
      const corpo = el("div", { class: "corpo" });
      for (const c of s.campos) corpo.append(criarCampo(c));
      const selo = el("span", { class: "selo", "data-selo": s.chave || "" });
      const det = el("details", { "data-secao": s.prefixo }, el("summary", {}, el("span", { text: s.titulo }), selo), corpo);
      if (s.prefixo === "1.") det.open = true;
      destino.append(det);
    }
  }
}

/* Põe os valores de `dados` nos controles (sem disparar eventos). */
function pintar() {
  for (const c of Object.values(campos)) {
    const inp = $("#c-" + c.nome);
    if (!inp) continue;
    const v = dados[c.nome];
    if (c.tipo === "bool") inp.checked = !!v;
    else if (c.tipo === "enum" || c.tipo === "bitola") {
      if (c.tipo === "bitola" && ![...inp.options].some((o) => Number(o.value) === Number(v))) {
        inp.append(el("option", { value: v, text: "ϕ " + String(v).replace(".", ",") }));
      }
      inp.value = String(v);
      const leg = $(`[data-campo="${c.nome}"] .legado`);
      if (leg) leg.hidden = !(c.opcoes.find((o) => o.valor === v) || {}).legada;
    } else {
      const vinc = $("#c-" + c.nome + "-vinc");
      if (vinc) {
        vinc.checked = v === null;
        inp.disabled = v === null;
        if (v === null) { inp.value = fmtNumero(dados[c.vinculo]); continue; }
      }
      if (document.activeElement !== inp) inp.value = fmtNumero(v);
    }
  }
  for (const selo of $$("[data-selo]")) {
    const k = selo.dataset.selo;
    selo.textContent = k && dados[k] ? "ativo" : "";
  }
}

let relogio = null;
function mudar(nome, valor) {
  dados[nome] = valor;
  guardar();
  const c = campos[nome];
  if (c.tipo === "bool" || c.tipo === "enum") pintar();
  clearTimeout(relogio);
  relogio = setTimeout(recalcular, 350);
}

/* ------------------------------------------------------------------ cálculo e resultados */
async function recalcular() {
  const meu = ++pedido;
  estado("calculando…");
  let r, desab;
  try {
    [r, desab] = await Promise.all([chamar("calcular_json", dados), chamar("desabilitados_json", dados)]);
  } catch (erro) {
    if (meu === pedido) { estado("erro", "nok"); mostrarErros(["Falha no motor de cálculo: " + erro.message]); }
    return;
  }
  if (meu !== pedido) return;          // chegou um pedido mais novo
  for (const c of Object.values(campos)) {
    const inp = $("#c-" + c.nome);
    const off = desab.includes(c.nome);
    if (inp) inp.disabled = off || (c.vinculo && dados[c.nome] === null);
    const vinc = $("#c-" + c.nome + "-vinc");
    if (vinc) vinc.disabled = off;
  }
  if (!r.ok) { estado("dados inválidos", "nok"); mostrarErros(r.erros); return; }
  ultimo = r;
  mostrarErros([]);
  mostrar(r);
  estado(r.geral ? "ATENDE" : "NÃO ATENDE", r.geral ? "ok" : "nok");
}

function mostrarErros(lista) {
  $("#erros").replaceChildren(...lista.map((t) => el("div", { class: "erro", text: t })));
  if (lista.length) $("#erros").prepend(el("div", { class: "erro", text: "Corrija os dados abaixo. Os resultados mostrados são do último cálculo válido." }));
}

const faixa = (texto, ok) => el("div", { class: "faixa " + (ok ? "ok" : "nok"), text: texto + (ok ? "ATENDE" : "NÃO ATENDE") });

function mostrar(r) {
  $("#vereditos").replaceChildren(
    faixa("Estabilidade externa (NBR 11682): ", r.estab),
    faixa("Dimensionamento estrutural (NBR 6118): ", r.dim),
  );
  $("#veredito-dim").replaceChildren(faixa("Dimensionamento estrutural (NBR 6118): ", r.dim));
  $("#cartoes").replaceChildren(...r.cartoes.map((c) =>
    el("div", { class: "cartao" + (c.ok ? "" : " nok") },
      el("div", { class: "t", text: c.t }), el("div", { class: "v", text: c.v }),
      el("div", { class: "l", text: `${c.lim}  ${c.ok ? "✔ OK" : "✖ NÃO OK"}` }))));
  const avisos = r.avisos.map((a) => el("div", { class: "aviso", text: `Aviso (Fase ${a.fase}): ${a.texto}` }));
  if (r.legadas.length) avisos.push(el("div", { class: "aviso", text: "Opções legadas (compatibilidade GEO5) ativas: " + r.legadas.join("; ") }));
  $("#avisos").replaceChildren(...avisos);

  const tv = $("#tab-verif");
  tv.replaceChildren(el("tr", {}, el("th", { text: "Verificação" }), ...r.fases.map((n) => el("th", { text: "Fase " + n })),
    el("th", { text: "Limite" }), el("th", { text: "" })));
  for (const l of r.verif) {
    tv.append(el("tr", {}, el("td", { text: l.rot + (l.un ? ` (${l.un})` : "") }), ...l.vals.map((v) => el("td", { text: v })),
      el("td", { text: l.lim }),
      el("td", { class: l.ok === null ? "" : l.ok ? "ok" : "nok", text: l.ok === null ? "" : l.ok ? "✔" : "✖" })));
  }
  $("#forcas").replaceChildren(...r.forcas.map((f) => {
    const t = el("table", {}, el("tr", {}, ...["Força", "Fx (kN/m)", "Fz (kN/m)", "x (m)", "z (m)", "M estab.", "M tomb."].map((h) => el("th", { text: h }))));
    for (const l of f.linhas) t.append(el("tr", {}, ...[l.nome, l.Fx, l.Fz, l.x, l.z, l.Mres, l.Movr].map((v) => el("td", { text: v }))));
    t.append(el("tr", {}, ...["TOTAIS", f.total.Fx, f.total.Fz, "", "", f.total.Mres, f.total.Movr].map((v) => el("td", { text: v }))));
    return el("div", { class: "corpo" }, el("p", { class: "fraco", text: `Fase ${f.fase} — Fx > 0 empurra o muro para a frente; momentos em torno da aresta inferior da ponta.` }),
      el("div", { class: "rolagem" }, t));
  }));

  const destino = $("#checks");
  destino.replaceChildren();
  let grupo = "";
  for (const c of r.checks) {
    if (c.grupo !== grupo) { grupo = c.grupo; destino.append(el("div", { class: "grupo", text: grupo })); }
    const ok = c.sit === "OK";
    destino.append(el("div", { class: "check" + (ok ? "" : " nok") },
      el("div", { class: "n", text: c.nome }),
      el("div", { class: "d", text: `${c.sol} × ${c.res} ${c.un}  ·  ${ok ? "✔ OK" : "✖ " + c.sit}` })));
  }
  $("#notas").replaceChildren(...r.notas.map((n) => el("li", { text: n })));
  $("#croqui").replaceChildren(croqui(r.croqui));
}

/* ------------------------------------------------------------------ croqui (SVG) */
function croqui(c) {
  const NS = "http://www.w3.org/2000/svg";
  const s = (tag, attrs, texto) => {
    const n = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    if (texto !== undefined) n.textContent = texto;
    return n;
  };
  const fmt = (v, casas = 2) => v.toFixed(casas).replace(".", ",");
  const xMin = -1.0, xMax = c.B + 1.5;
  const zTerMax = Math.max(c.H, ...c.terreno.map((p) => p[1]));
  const temEstaca = c.estacas[0] !== null;
  const fundo = temEstaca ? Math.min(1.2, c.estacas[2]) : 0.75;
  const zMin = -fundo - 0.55, zMax = zTerMax + 0.75;
  const k = 100;                                  // unidades do desenho por metro
  const X = (x) => (x - xMin) * k, Z = (z) => (zMax - z) * k;
  const larg = (xMax - xMin) * k, alt = (zMax - zMin) * k;
  const pts = (lista) => lista.map((p) => `${X(p[0]).toFixed(1)},${Z(p[1]).toFixed(1)}`).join(" ");
  const svg = s("svg", { viewBox: `0 0 ${larg.toFixed(0)} ${alt.toFixed(0)}`, role: "img",
    "aria-label": `Croqui do muro: altura ${fmt(c.H)} m, base ${fmt(c.B)} m` });
  const esc = larg / 520;                         // mantém textos legíveis em qualquer proporção
  const tx = (x, z, texto, extra = {}) => svg.append(s("text", { x: X(x), y: Z(z), "font-size": 13 * esc, fill: "var(--tinta)",
    "font-family": "system-ui, sans-serif", ...extra }, texto));
  const seta = (x0, z0, x1, z1, cor) => {
    const a = Math.atan2(Z(z1) - Z(z0), X(x1) - X(x0)), t = 9 * esc;
    svg.append(s("line", { x1: X(x0), y1: Z(z0), x2: X(x1), y2: Z(z1), stroke: cor, "stroke-width": 2.4 * esc }));
    svg.append(s("polygon", { fill: cor, points: [[0, 0], [-t, t / 2.2], [-t, -t / 2.2]].map(([dx, dy]) =>
      `${(X(x1) + dx * Math.cos(a) - dy * Math.sin(a)).toFixed(1)},${(Z(z1) + dx * Math.sin(a) + dy * Math.cos(a)).toFixed(1)}`).join(" ") }));
  };
  const SOLO = "#d9c7a0", FUND = "#c9b58a";
  // solo de fundação, aterro e solo da frente
  svg.append(s("rect", { x: 0, y: Z(0), width: larg, height: alt - Z(0), fill: FUND, opacity: .55 }));
  const [t0, t1] = c.terreno;
  svg.append(s("polygon", { points: pts([[c.B, 0], [xMax, 0], [xMax, t1[1]], t0, ...c.muro.slice(3, 5).reverse()]), fill: SOLO, opacity: .7 }));
  if (c.D > 0) svg.append(s("polygon", { points: pts([[xMin, 0], [0, 0], [0, Math.min(c.D, c.hs)], ...(c.D > c.hs ? [c.muro[6], c.terreno_frente[1]] : []), [xMin, c.D]]), fill: SOLO, opacity: .7 }));
  svg.append(s("polyline", { points: pts(c.terreno), fill: "none", stroke: "var(--tinta2)", "stroke-width": 1.5 * esc }));
  if (c.D > 0) svg.append(s("polyline", { points: pts(c.terreno_frente), fill: "none", stroke: "var(--tinta2)", "stroke-width": 1.5 * esc }));
  // estacas, contraforte e muro
  for (const xe of c.estacas.slice(0, 2)) {
    if (xe === null) continue;
    svg.append(s("rect", { x: X(xe - c.estacas[3] / 2), y: Z(0), width: c.estacas[3] * k, height: fundo * k, fill: "#b9b8b0", stroke: "var(--tinta)", "stroke-width": 1.2 * esc, "stroke-dasharray": `${5 * esc} ${3 * esc}` }));
  }
  if (c.contraforte) svg.append(s("polygon", { points: pts(c.contraforte), fill: "#b9b8b0", opacity: .75, stroke: "var(--tinta)", "stroke-width": 1 * esc }));
  svg.append(s("polygon", { points: pts(c.muro), fill: "#cfcec8", stroke: "var(--tinta)", "stroke-width": 2 * esc, "stroke-linejoin": "round" }));
  svg.append(s("polyline", { points: pts(c.plano), fill: "none", stroke: "#eb6834", "stroke-width": 2 * esc, "stroke-dasharray": `${7 * esc} ${5 * esc}` }));
  for (const [chave, cor] of [["na_atras", "#2a78d6"], ["na_frente", "#2a78d6"]]) {
    if (c[chave]) svg.append(s("polyline", { points: pts(c[chave]), fill: "none", stroke: cor, "stroke-width": 1.6 * esc, "stroke-dasharray": `${3 * esc} ${3 * esc}` }));
  }
  // cargas no terrapleno
  const tb = Math.tan(c.beta * Math.PI / 180), zt = (d) => c.z_ter + d * tb;
  if (c.q > 0) tx((c.x_bt + xMax) / 2, zt((xMax - c.x_bt) / 2) + 0.12, `q = ${fmt(c.q, 1)} kPa`, { "text-anchor": "middle", fill: "var(--tinta2)" });
  if (c.faixa[0] > 0) {
    const x0 = Math.min(c.x_bt + c.faixa[1], xMax - 0.05), x1 = Math.min(x0 + c.faixa[2], xMax);
    svg.append(s("rect", { x: X(x0), y: Z(zt(x0 - c.x_bt) + 0.12), width: (x1 - x0) * k, height: 0.12 * k, fill: "#eb6834", opacity: .8 }));
    tx((x0 + x1) / 2, zt(x0 - c.x_bt) + 0.42, `faixa ${fmt(c.faixa[0], 1)} kPa`, { "text-anchor": "middle", fill: "var(--tinta2)" });
  }
  for (const [carga, txt, nivel] of [[c.linha, "kN/m", 0], [c.ponto, "kN", 1]]) {
    if (!(carga[0] > 0)) continue;
    const x = Math.min(c.x_bt + carga[1], xMax - 0.08);
    seta(x, zt(x - c.x_bt) + 0.42, x, zt(x - c.x_bt) + 0.03, "#eb6834");
    tx(x, zt(x - c.x_bt) + 0.48 + 0.16 * nivel, `${fmt(carga[0], 1)} ${txt}`, { "text-anchor": "end", fill: "var(--tinta2)" });
  }
  // resultantes
  if (c.Pah > 0) { seta(c.B + 1.05, c.zPa, c.B + 0.08, c.zPa, "#2a78d6"); tx(c.B + 0.12, c.zPa + 0.12, `Pa,h = ${fmt(c.Pah, 1)} kN/m`, { "font-weight": 600 }); }
  if (c.N > 0) { seta(c.xR, -fundo + 0.05, c.xR, -0.04, "#1baf7a"); tx(c.xR + 0.08, -fundo + 0.18, `N = ${fmt(c.N, 1)} kN/m`, { "font-weight": 600 }); }
  if (c.sig_max !== null) tx(xMin + 0.05, -0.22, `σmáx = ${fmt(c.sig_max, 1)} kPa (${c.sig_em})`, { fill: "var(--tinta2)" });
  // cotas
  tx(c.B / 2, zMin + 0.12, `B = ${fmt(c.B)} m`, { "text-anchor": "middle", fill: "var(--tinta2)" });
  svg.append(s("line", { x1: X(0), y1: Z(zMin + 0.32), x2: X(c.B), y2: Z(zMin + 0.32), stroke: "var(--tinta2)", "stroke-width": 1 * esc }));
  tx(xMin + 0.05, c.H - 0.05, `H = ${fmt(c.H)} m`, { fill: "var(--tinta2)" });
  return svg;
}

/* ------------------------------------------------------------------ solo */
let solo = null;
async function atualizarSolo() {
  const tipo = $("#solo-tipo").value;
  const argila = tipo.startsWith("Argila");
  $("#solo-nd").disabled = !argila;
  if (!argila) $("#solo-nd").checked = false;
  const nspt = Number($("#solo-nspt").value);
  if (!Number.isFinite(nspt) || nspt < 0) return;
  solo = await chamar("solo_json", { tipo, nspt, postura: Number($("#solo-postura").value), nao_drenado: $("#solo-nd").checked });
  const v = (x, casas = 1) => x.toFixed(casas).replace(".", ",");
  const t = el("table", {}, el("tr", {}, el("th", { text: "Parâmetro" }), el("th", { text: "Faixa" }), el("th", { text: "Un." })));
  for (const [p, f, u] of solo.faixas) t.append(el("tr", {}, el("td", { text: p }), el("td", { text: f }), el("td", { text: u })));
  $("#solo-saida").replaceChildren(
    el("p", {}, el("b", { text: "Classificação: " }), solo.classe.toLowerCase()),
    el("div", { class: "metricas" },
      ...[["γ (kN/m³)", v(solo.gama)], ["φ (°)", v(solo.phi)], ["c (kPa)", v(solo.c)], ["δ (°)", v(solo.delta)], ["α adesão", v(solo.alfa, 2)], ["qult (kPa)", v(solo.qult, 0)]]
        .map(([r, x]) => el("div", {}, el("b", { text: x }), el("span", { text: r })))),
    el("div", { class: "rolagem" }, t),
    ...solo.obs.map((o) => el("p", { class: "fraco", text: o })),
  );
}
function aplicarSolo(onde) {
  if (!solo) return;
  if (onde === "aterro") {
    if (solo.phi < 5) { alert("φ < 5° não é aceito para o aterro. Use a condição drenada."); return; }
    Object.assign(dados, { gam_at: solo.gama, gsat_at: Math.max(dados.gsat_at, solo.gama), phi_at: solo.phi, c_at: solo.c,
      delta_est: solo.delta, beta_t: Math.min(dados.beta_t, solo.phi) });
  } else {
    Object.assign(dados, { gam_f: solo.gama, gsat_f: Math.max(dados.gsat_f, solo.gama), phi_f: solo.phi, c_f: solo.c, k_c: solo.alfa });
  }
  guardar(); pintar(); recalcular();
  abrirAba("resultado");
}

/* ------------------------------------------------------------------ projeto */
function baixar(nome, texto, tipo) {
  const a = el("a", { href: URL.createObjectURL(new Blob([texto], { type: tipo })), download: nome });
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}
function salvarProjeto() {
  const m = meta();
  const projeto = { formato: "muro-arrimo", versao: 1, salvo_em: new Date().toISOString().slice(0, 19), ...m, entrada: dados };
  const nome = (m.nome || "muro").normalize("NFD").replace(/[^\w\- ]/g, "").trim().replace(/\s+/g, "_") || "muro";
  baixar(nome + ".json", JSON.stringify(projeto, null, 2), "application/json");
  $("#proj-msg").textContent = "Projeto salvo na pasta de downloads. O mesmo arquivo abre no aplicativo de computador.";
}
async function abrirProjeto(arquivo) {
  try {
    const p = JSON.parse(await arquivo.text());
    if (p.formato !== "muro-arrimo") throw new Error("O arquivo não é um projeto de muro de arrimo deste aplicativo.");
    const novos = padroes();
    for (const [k, v] of Object.entries(p.entrada || {})) if (k in campos) novos[k] = v;
    const r = await chamar("calcular_json", novos);
    if (!r.ok) throw new Error("Dados inválidos no arquivo: " + r.erros.join("; "));
    dados = novos;
    $("#proj-nome").value = p.nome || ""; $("#proj-obra").value = p.obra || ""; $("#proj-autor").value = p.autor || "";
    guardar(); pintar(); await recalcular();
    $("#proj-msg").textContent = `Projeto “${p.nome || arquivo.name}” aberto.`;
  } catch (erro) {
    $("#proj-msg").textContent = "Não foi possível abrir: " + erro.message;
  }
}
function resumo() {
  if (!ultimo) return "";
  const m = meta();
  const l = [`Muro de arrimo${m.nome ? " — " + m.nome : ""}${m.obra ? " (" + m.obra + ")" : ""}`,
    `H = ${String(dados.H_muro).replace(".", ",")} m; B = ${ultimo.croqui.B.toFixed(2).replace(".", ",")} m`,
    `Estabilidade (NBR 11682): ${ultimo.estab ? "ATENDE" : "NÃO ATENDE"}`,
    ...ultimo.cartoes.map((c) => `  ${c.t}: ${c.v} (${c.lim}) ${c.ok ? "OK" : "NÃO OK"}`),
    `Dimensionamento (NBR 6118): ${ultimo.dim ? "ATENDE" : "NÃO ATENDE"}`,
    ...ultimo.checks.filter((c) => c.sit !== "OK").map((c) => `  NÃO OK: ${c.nome} (${c.sol} × ${c.res} ${c.un})`)];
  return l.join("\n");
}
async function compartilhar() {
  const texto = resumo();
  if (!texto) return;
  try {
    if (navigator.share) await navigator.share({ title: "Muro de arrimo", text: texto });
    else { await navigator.clipboard.writeText(texto); $("#proj-msg").textContent = "Resumo copiado."; }
  } catch (_) { /* compartilhamento cancelado */ }
}
function padroes() {
  const d = {};
  for (const c of Object.values(campos)) d[c.nome] = c.padrao;
  return d;
}

/* ------------------------------------------------------------------ navegação e início */
function abrirAba(nome) {
  for (const a of $$(".aba")) a.hidden = a.id !== "aba-" + nome;
  for (const b of $$("nav button")) b.classList.toggle("ativa", b.dataset.aba === nome);
  window.scrollTo(0, 0);
}

function iniciar(esq) {
  esquema = esq;
  for (const s of esquema.secoes) for (const c of s.campos) campos[c.nome] = c;
  dados = padroes();
  const salvo = ler(CHAVE);
  if (salvo) for (const [k, v] of Object.entries(salvo)) if (k in campos) dados[k] = v;
  const m = ler(CHAVE_META) || {};
  $("#proj-nome").value = m.nome || ""; $("#proj-obra").value = m.obra || ""; $("#proj-autor").value = m.autor || "";
  montarFormulario();
  pintar();
  for (const t of esquema.tipos_de_solo) $("#solo-tipo").append(el("option", { value: t, text: t }));
  $("#carregando").hidden = true;
  $("main").hidden = false;
  $("nav").hidden = false;
  recalcular();
  atualizarSolo();
}

for (const b of $$("nav button")) b.addEventListener("click", () => abrirAba(b.dataset.aba));
for (const id of ["solo-tipo", "solo-nspt", "solo-postura", "solo-nd"]) $("#" + id).addEventListener("input", atualizarSolo);
$("#solo-aterro").addEventListener("click", () => aplicarSolo("aterro"));
$("#solo-fund").addEventListener("click", () => aplicarSolo("fundacao"));
for (const id of ["proj-nome", "proj-obra", "proj-autor"]) $("#" + id).addEventListener("input", guardar);
$("#proj-salvar").addEventListener("click", salvarProjeto);
$("#proj-abrir").addEventListener("click", () => $("#proj-arquivo").click());
$("#proj-arquivo").addEventListener("change", (ev) => { if (ev.target.files[0]) abrirProjeto(ev.target.files[0]); ev.target.value = ""; });
$("#proj-resumo").addEventListener("click", compartilhar);
$("#proj-padrao").addEventListener("click", () => {
  if (!confirm("Restaurar todos os dados para os valores padrão? Os dados atuais serão perdidos.")) return;
  dados = padroes(); guardar(); pintar(); recalcular();
});
$("#versao").textContent = "Versão __VERSAO__";

if ("serviceWorker" in navigator && location.protocol.startsWith("http")) {
  navigator.serviceWorker.register("sw.js").catch(() => { /* sem armazenamento offline: segue funcionando online */ });
}
