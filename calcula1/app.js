// CalculaMate - conecta la interfaz con SymPy (vía Pyodide)

let pyodide = null;
let solverReady = false;
let currentOp = "analizar";
let currentMode = "funcion";

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);
const fxInput = $("#fx");
const gxInput = $("#gx");
const previewEl = $("#preview");
const resultsEl = $("#results");

// ---------- Catálogo de operaciones por modo ----------
const OPS = {
  funcion: [
    { op: "analizar",            label: "📋 Analizar (dominio, rango, tipo)" },
    { op: "derivar",             label: "📈 Derivada (reglas)" },
    { op: "derivada_definicion", label: "ƒ′ Derivada por definición (límite)" },
    { op: "limite",              label: "→ Límite (con técnicas)" },
    { op: "continuidad",         label: "≈ Continuidad (3 criterios)" },
    { op: "asintotas",           label: "⟂ Asíntotas" },
    { op: "tangente",            label: "／ Recta tangente" },
    { op: "criticos",            label: "⌣ Máx/mín y concavidad" },
    { op: "taylor",              label: "Σ Serie de Taylor" },
    { op: "simplificar",         label: "✨ Simplificar / factorizar" },
    { op: "raices",              label: "🎯 Raíces (ceros)" },
  ],
  tramos: [
    { op: "analizar",    label: "📋 Analizar (dominio, rango, continuidad)" },
    { op: "derivar",     label: "📈 Derivada por tramos" },
    { op: "limite",      label: "→ Límite en un punto" },
    { op: "continuidad", label: "≈ Continuidad (3 criterios)" },
  ],
  ecuacion: [
    { op: "resolver_ecuacion", label: "🟰 Resolver ecuación" },
    { op: "simplificar",       label: "✨ Simplificar" },
  ],
  puntos: [
    { op: "recta_puntos", label: "• Hallar ecuación de la recta" },
  ],
  fg: [
    { op: "fg_suma",        label: "+ Suma (f + g)" },
    { op: "fg_resta",       label: "− Resta (f − g)" },
    { op: "fg_producto",    label: "× Producto (f · g)" },
    { op: "fg_cociente",    label: "÷ Cociente (f / g)" },
    { op: "fg_composicion", label: "∘ Composición (f ∘ g)" },
  ],
  razones: [
    { op: "razon_cambio", label: "Δ Ver solución paso a paso" },
  ],
  grafica: [
    { op: "ajustar_curva", label: "✏️ Hallar la ecuación de los puntos" },
  ],
};

const CHIPS = {
  funcion: [
    ["x^2 - 4x + 3", "x²−4x+3"], ["sqrt(2x-10)", "√(2x−10)"], ["(3x^2-2)/(x-4)", "racional"],
    ["(x^2-1)/(x-1)", "límite 0/0"], ["sin(x)", "sin(x)"], ["exp(x)", "eˣ"], ["ln(x-1)", "ln(x−1)"],
    ["x^3 - 27x", "x³−27x"],
  ],
  tramos: [
    ["{ 3x-1 si x>1 ; x^2 si x<=1 }", "3x−1 · x²"],
    ["{ -x si x<0 ; x si x>=0 }", "|x| por tramos"],
    ["{ 1 si x>0 ; -1 si x<0 }", "signo"],
  ],
  ecuacion: [
    ["x^2 - 5x + 6 = 0", "x²−5x+6=0"], ["2x + 3 = 7", "2x+3=7"], ["sin(x) = 0", "sin(x)=0"],
  ],
  puntos: [
    ["(1,2) y (3,8)", "(1,2)·(3,8)"], ["(0,0) y (2,6)", "(0,0)·(2,6)"], ["(-1,4) y (2,-2)", "(−1,4)·(2,−2)"],
  ],
  fg: [
    ["x^2", "f=x²"], ["sqrt(x-2)", "g=√(x−2)"], ["2x", "2x"], ["x+1", "x+1"],
  ],
  razones: [],
  grafica: [],
};

const MODE_UI = {
  funcion:  { label: 'Escribe tu función <span class="hint">(usa x como variable)</span>', ph: "ej: x^2 - 4x + 3" },
  tramos:   { label: 'Función por tramos <span class="hint">({ valor si condición ; ... })</span>', ph: "ej: { 3x-1 si x>1 ; x^2 si x<=1 }" },
  ecuacion: { label: 'Escribe una ecuación <span class="hint">(con = )</span>', ph: "ej: x^2 - 5x + 6 = 0" },
  puntos:   { label: 'Dos puntos <span class="hint">(x,y)</span>', ph: "ej: (1,2) y (3,8)" },
  fg:       { label: 'La función f(x)', ph: "ej: x^2" },
  razones:  { label: 'Problemas de razón de cambio <span class="hint">(derivadas aplicadas)</span>', ph: "" },
  grafica:  { label: 'Marca puntos y obtén la ecuación <span class="hint">(ajuste de curva)</span>', ph: "" },
};

const OPT_FOR = {
  limite:              ["opt-punto", "opt-lado"],
  continuidad:         ["opt-punto"],
  tangente:            ["opt-punto"],
  taylor:              ["opt-punto", "opt-orden"],
  derivada_definicion: ["opt-punto"],
};

// ---------- Arranque ----------
async function boot() {
  const setMsg = (t) => { const el = $("#loadmsg"); if (el) el.textContent = t; };
  try {
    // 1) Empezamos a descargar el solver EN PARALELO con la carga de Pyodide.
    //    (antes era secuencial; esto ahorra una espera)
    const solverPromise = fetch("solver.py").then((r) => r.text());

    setMsg("descargando el motor de Python (una vez, luego queda en caché)…");
    // 2) Cargamos Pyodide y SymPy juntos: 'packages' los baja durante la init,
    //    en paralelo, en lugar de en dos pasos separados.
    pyodide = await loadPyodide({ packages: ["sympy"] });

    setMsg("preparando el solver…");
    const solverCode = await solverPromise;
    pyodide.runPython(solverCode);

    solverReady = true;
    $("#loading").classList.add("hidden");
    $("#app").classList.remove("hidden");

    buildOps();
    buildChips();
    renderPreview();
    plot(fxInput.value);
  } catch (e) {
    $("#loading").innerHTML =
      `<div class="err">No se pudo cargar el motor: ${e}.<br>
       Revisa tu conexión a internet y recarga la página (F5).</div>`;
  }
}

function buildOps() {
  const cont = $("#ops");
  cont.innerHTML = "";
  OPS[currentMode].forEach((o, i) => {
    const btn = document.createElement("button");
    btn.className = "op" + (i === 0 ? " active" : "");
    btn.dataset.op = o.op;
    btn.textContent = o.label;
    btn.addEventListener("click", () => {
      $$(".op").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      currentOp = o.op;
      updateOptPanels();
      solve();
    });
    cont.appendChild(btn);
  });
  currentOp = OPS[currentMode][0].op;
  updateOptPanels();
}

function buildChips() {
  const cont = $("#quick-chips");
  cont.innerHTML = "";
  if (!CHIPS[currentMode].length) return;
  cont.innerHTML = '<span class="qlabel">Ejemplos rápidos:</span>';
  CHIPS[currentMode].forEach(([val, label]) => {
    const chip = document.createElement("button");
    chip.className = "chip";
    chip.textContent = label;
    chip.addEventListener("click", () => {
      fxInput.value = val;
      renderPreview();
      solve();
    });
    cont.appendChild(chip);
  });
}

function updateOptPanels() {
  ["opt-punto", "opt-lado", "opt-orden"].forEach((id) => $("#" + id).classList.add("hidden"));
  (OPT_FOR[currentOp] || []).forEach((id) => $("#" + id).classList.remove("hidden"));
  const lbl = $("#punto-label");
  if (currentOp === "limite") lbl.textContent = "Límite cuando x →";
  else if (currentOp === "tangente") lbl.textContent = "Punto de tangencia x =";
  else if (currentOp === "taylor") lbl.textContent = "Centro a =";
  else if (currentOp === "derivada_definicion") lbl.textContent = "Evaluar en x = (opcional)";
  else lbl.textContent = "Punto x =";
}

// ---------- Vista previa ----------
function renderPreview() {
  if (!solverReady) return;
  if (currentMode === "razones") { previewEl.innerHTML = ""; return; }
  const val = fxInput.value.trim();
  if (currentMode === "puntos") {
    // textContent (no innerHTML) para que NO se interprete como HTML: evita XSS
    previewEl.textContent = val;
    previewEl.style.color = "#9aa3c7";
    return;
  }
  if (!val) { previewEl.innerHTML = ""; return; }
  try {
    const fn = pyodide.globals.get("preview_latex");
    let tex = fn(val);
    if (currentMode === "fg" && gxInput.value.trim()) {
      const texg = fn(gxInput.value.trim());
      fn.destroy();
      if (tex) {
        katex.render(`f(x) = ${tex} \\qquad g(x) = ${texg}`, previewEl,
          { throwOnError: false, displayMode: true });
      }
      return;
    }
    fn.destroy();
    if (tex) {
      const prefix = currentMode === "ecuacion" ? "" : "f(x) = ";
      katex.render(prefix + tex, previewEl, { throwOnError: false, displayMode: true });
    } else {
      previewEl.innerHTML = `<span style="color:#9aa3c7">…</span>`;
    }
  } catch { /* ignore */ }
}

// ---------- Resolver ----------
function solve() {
  if (!solverReady) return;
  resultsEl.innerHTML = `<div class="placeholder">Calculando… ⏳</div>`;

  setTimeout(() => {
    let plotOverride = null, noPlot = false;
    try {
      let exprArg, puntoArg = $("#punto").value || "0", extra1 = "";

      if (currentMode === "grafica") {
        if (PLANE.points.length < 2) return;
        exprArg = JSON.stringify(PLANE.points);
        extra1 = $("#modelo-sel").value;
      } else if (currentMode === "razones") {
        exprArg = $("#razon-sel").value;
      } else if (currentMode === "fg") {
        exprArg = fxInput.value.trim();
        extra1 = gxInput.value.trim();
      } else {
        exprArg = fxInput.value.trim();
        if (currentOp === "limite") extra1 = $("#lado").value || "";
        else if (currentOp === "taylor") extra1 = $("#orden").value || "4";
        else if (currentOp === "derivada_definicion") extra1 = $("#punto").value || "";
      }
      if (!exprArg) return;

      const fn = pyodide.globals.get("resolver");
      const raw = fn(currentOp, exprArg, puntoArg, extra1, "");
      fn.destroy();
      const data = JSON.parse(raw);

      if (!data.ok) {
        showError(data.error);
        return;
      }
      renderSteps(data.pasos);
      if (data.plot) plotOverride = data.plot;
      if (data.noplot || currentMode === "razones") noPlot = true;
      if (currentMode === "grafica") {
        noPlot = true;              // el plano interactivo ya muestra la curva
        if (data.fit) { PLANE.fitExpr = data.fit; drawPlane(); }
      }
    } catch (e) {
      showError("Error: " + e);
    }

    if (noPlot) {
      $("#graph-panel").classList.add("hidden");
    } else {
      $("#graph-panel").classList.remove("hidden");
      plot(plotOverride || fxInput.value);
    }
  }, 20);
}

// ---------- Mensaje de error seguro (sin innerHTML con datos) ----------
function showError(msg) {
  resultsEl.innerHTML = "";
  const div = document.createElement("div");
  div.className = "err";
  div.textContent = "⚠️ " + String(msg);   // textContent = no se interpreta HTML
  resultsEl.appendChild(div);
}

// ---------- Pintar pasos ----------
function renderSteps(pasos) {
  resultsEl.innerHTML = "";
  pasos.forEach((p) => {
    if (p.tag === "RESULTADO") {
      const div = document.createElement("div");
      div.className = "final";
      div.innerHTML = `<span class="check">✅</span>`;
      if (p.latex) {
        const math = document.createElement("div");
        katex.render(p.latex, math, { throwOnError: false, displayMode: true });
        div.appendChild(math);
      } else if (p.text) {
        const t = document.createElement("div");
        t.textContent = p.text;
        div.appendChild(t);
      }
      resultsEl.appendChild(div);
      if (p.geogebra) resultsEl.appendChild(makeGeoGebra(p.geogebra));
      return;
    }
    const div = document.createElement("div");
    div.className = "step";
    const tagSpan = document.createElement("span");
    tagSpan.className = "tag";
    tagSpan.textContent = p.tag;          // textContent: la etiqueta no se interpreta como HTML
    div.appendChild(tagSpan);
    if (p.latex) {
      const math = document.createElement("div");
      math.className = "math";
      katex.render(p.latex, math, { throwOnError: false, displayMode: true });
      div.appendChild(math);
    }
    if (p.text) {
      const t = document.createElement("p");
      t.textContent = p.text;
      div.appendChild(t);
    }
    if (p.explain) {
      const e = document.createElement("p");
      e.className = "explain";
      e.textContent = p.explain;
      div.appendChild(e);
    }
    if (p.geogebra) div.appendChild(makeGeoGebra(p.geogebra));
    resultsEl.appendChild(div);
  });
}

// ---------- Bloque GeoGebra con botón copiar ----------
function makeGeoGebra(cmd) {
  const box = document.createElement("div");
  box.className = "geogebra";
  const head = document.createElement("div");
  head.className = "gg-head";
  head.innerHTML = `<span>📐 En GeoGebra escribe:</span>`;
  const btn = document.createElement("button");
  btn.className = "gg-copy";
  btn.textContent = "Copiar";
  btn.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(cmd);
      btn.textContent = "¡Copiado!";
      setTimeout(() => (btn.textContent = "Copiar"), 1500);
    } catch {
      btn.textContent = "Selecciona y copia";
    }
  });
  head.appendChild(btn);
  const code = document.createElement("pre");
  code.className = "gg-code";
  code.textContent = cmd;
  box.appendChild(head);
  box.appendChild(code);
  return box;
}

// ---------- Graficar ----------
function plot(val) {
  const target = "#plot";
  const width = $("#plot").clientWidth;

  if (currentMode === "puntos") {
    const nums = (String(val).match(/-?\d+\.?\d*/g) || []).map(Number);
    const data = [];
    if (typeof val === "string" && !val.includes("(")) data.push({ fn: val, color: "#22d3ee" });
    if (nums.length >= 4) {
      data.push({ points: [[nums[0], nums[1]], [nums[2], nums[3]]], fnType: "points", graphType: "scatter", color: "#f472b6" });
    }
    try { functionPlot({ target, width, height: 340, grid: true, data }); return; } catch {}
  }

  if (currentMode === "fg") {
    try {
      const pf = pyodide.globals.get("plot_expr");
      const f = JSON.parse(pf(fxInput.value));
      const g = JSON.parse(pf(gxInput.value));
      pf.destroy();
      functionPlot({
        target, width, height: 340, grid: true,
        data: [
          { fn: f.fn, color: "#22d3ee", graphType: "polyline" },
          { fn: g.fn, color: "#f472b6", graphType: "polyline" },
        ],
      });
      return;
    } catch {}
  }

  try {
    const pf = pyodide.globals.get("plot_expr");
    const info = JSON.parse(pf(val));
    pf.destroy();
    let data;
    if (info.piecewise) {
      const colors = ["#22d3ee", "#7c5cff", "#f472b6", "#fbbf24", "#34d399"];
      data = info.tramos.map((t, i) => ({ fn: t.fn, color: colors[i % colors.length], graphType: "polyline" }));
    } else {
      data = [{ fn: info.fn, color: "#22d3ee", graphType: "polyline" }];
    }
    functionPlot({ target, width, height: 340, grid: true, data });
  } catch {
    try {
      functionPlot({
        target, width, height: 340, grid: true,
        data: [{ fn: String(val).replace(/\bln\b/g, "log"), color: "#22d3ee", graphType: "polyline" }],
      });
    } catch {
      $("#plot").innerHTML = `<div style="padding:40px;text-align:center;color:#9aa3c7">No pude graficar esta expresión directamente.</div>`;
    }
  }
}

// ---------- Teclado ----------
function insertText(text, caretOffset = 0) {
  const el = document.activeElement === gxInput ? gxInput : fxInput;
  const start = el.selectionStart ?? el.value.length;
  const end = el.selectionEnd ?? el.value.length;
  el.value = el.value.slice(0, start) + text + el.value.slice(end);
  const pos = start + text.length + caretOffset;
  el.focus();
  el.setSelectionRange(pos, pos);
  renderPreview();
}

function backspace() {
  const el = document.activeElement === gxInput ? gxInput : fxInput;
  const start = el.selectionStart ?? el.value.length;
  const end = el.selectionEnd ?? el.value.length;
  if (start === end && start > 0) {
    el.value = el.value.slice(0, start - 1) + el.value.slice(end);
    el.setSelectionRange(start - 1, start - 1);
  } else {
    el.value = el.value.slice(0, start) + el.value.slice(end);
    el.setSelectionRange(start, start);
  }
  el.focus();
  renderPreview();
}

$$(".key").forEach((key) => {
  key.addEventListener("click", () => {
    if (key.dataset.action === "backspace") { backspace(); return; }
    insertText(key.dataset.ins ?? "", parseInt(key.dataset.caret || "0", 10));
  });
});

$$(".kb-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    $$(".kb-tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    $$(".kb-page").forEach((p) => p.classList.add("hidden"));
    $(`.kb-page[data-page="${tab.dataset.kb}"]`).classList.remove("hidden");
  });
});

// ---------- Modos ----------
$$(".mode").forEach((btn) => {
  btn.addEventListener("click", () => {
    $$(".mode").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    currentMode = btn.dataset.mode;
    const ui = MODE_UI[currentMode];
    $("#input-label").innerHTML = ui.label;
    fxInput.placeholder = ui.ph;

    // mostrar/ocultar elementos según el modo
    $("#gx-row").classList.toggle("hidden", currentMode !== "fg");
    $("#razon-row").classList.toggle("hidden", currentMode !== "razones");
    $("#grafica-row").classList.toggle("hidden", currentMode !== "grafica");
    $("#keyboard").classList.toggle("hidden", currentMode === "razones" || currentMode === "grafica");
    const hideInput = currentMode === "razones" || currentMode === "grafica";
    $("#fx").parentElement.classList.toggle("hidden", hideInput);
    $("#input-label").classList.toggle("hidden", hideInput);
    $("#preview").classList.toggle("hidden", currentMode === "grafica");

    if (currentMode === "fg") { fxInput.value = "x^2"; gxInput.value = "sqrt(x-2)"; }
    else if (CHIPS[currentMode].length) fxInput.value = CHIPS[currentMode][0][0];

    buildOps();
    buildChips();
    renderPreview();

    if (currentMode === "grafica") {
      $("#graph-panel").classList.add("hidden");
      drawPlane();
      if (PLANE.points.length < 2) {
        resultsEl.innerHTML = `<div class="placeholder">Marca al menos 2 puntos en el plano para hallar su ecuación.</div>`;
        return;
      }
    }
    solve();
  });
});

// ---------- Eventos ----------
fxInput.addEventListener("input", debounce(renderPreview, 250));
fxInput.addEventListener("keydown", (e) => { if (e.key === "Enter") solve(); });
gxInput.addEventListener("input", debounce(renderPreview, 250));
gxInput.addEventListener("keydown", (e) => { if (e.key === "Enter") solve(); });
$("#clear-btn").addEventListener("click", () => {
  const el = document.activeElement === gxInput ? gxInput : fxInput;
  el.value = ""; previewEl.innerHTML = ""; el.focus();
});
$("#punto").addEventListener("input", debounce(solve, 400));
$("#lado").addEventListener("change", solve);
$("#orden").addEventListener("input", debounce(solve, 400));
$("#razon-sel").addEventListener("change", solve);

function debounce(fn, ms) {
  let t;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

// ======================= PLANO INTERACTIVO (gráfica→ecuación) =======================
const PLANE = {
  w: 600, h: 400, min: -10, max: 10,   // rango lógico [-10,10] en x e y
  points: [],                           // puntos lógicos [[x,y],...]
  fitExpr: null,                        // última expresión ajustada (texto)
};
const planeEl = $("#plane");

// conversión lógico <-> pantalla
function toScreen(x, y) {
  const sx = (x - PLANE.min) / (PLANE.max - PLANE.min) * PLANE.w;
  const sy = PLANE.h - (y - PLANE.min) / (PLANE.max - PLANE.min) * PLANE.h;
  return [sx, sy];
}
function toLogic(sx, sy) {
  const x = PLANE.min + sx / PLANE.w * (PLANE.max - PLANE.min);
  const y = PLANE.min + (PLANE.h - sy) / PLANE.h * (PLANE.max - PLANE.min);
  return [x, y];
}
function snap(v) { return Math.round(v * 2) / 2; } // a mitades para comodidad

function svgEl(tag, attrs) {
  const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const k in attrs) el.setAttribute(k, attrs[k]);
  return el;
}

function drawPlane() {
  planeEl.innerHTML = "";
  // fondo
  planeEl.appendChild(svgEl("rect", { x: 0, y: 0, width: PLANE.w, height: PLANE.h, fill: "#0b0e20" }));
  // cuadrícula
  for (let i = PLANE.min; i <= PLANE.max; i++) {
    const [vx] = toScreen(i, 0);
    const [, hy] = toScreen(0, i);
    const major = i === 0;
    planeEl.appendChild(svgEl("line", { x1: vx, y1: 0, x2: vx, y2: PLANE.h,
      stroke: major ? "#4b57a0" : "#1d2550", "stroke-width": major ? 1.5 : 1 }));
    planeEl.appendChild(svgEl("line", { x1: 0, y1: hy, x2: PLANE.w, y2: hy,
      stroke: major ? "#4b57a0" : "#1d2550", "stroke-width": major ? 1.5 : 1 }));
  }
  // etiquetas de ejes
  const [ox, oy] = toScreen(0, 0);
  const lx = svgEl("text", { x: PLANE.w - 12, y: oy - 6, fill: "#9aa3c7", "font-size": 12 });
  lx.textContent = "x"; planeEl.appendChild(lx);
  const ly = svgEl("text", { x: ox + 6, y: 14, fill: "#9aa3c7", "font-size": 12 });
  ly.textContent = "y"; planeEl.appendChild(ly);

  // curva ajustada
  if (PLANE.fitExpr) {
    const d = curvePath(PLANE.fitExpr);
    if (d) planeEl.appendChild(svgEl("path", { d, fill: "none", stroke: "#22d3ee", "stroke-width": 2.5 }));
  }

  // puntos
  PLANE.points.forEach(([x, y], i) => {
    const [sx, sy] = toScreen(x, y);
    const c = svgEl("circle", { cx: sx, cy: sy, r: 6, fill: "#f472b6",
      stroke: "#fff", "stroke-width": 1.5, "data-i": i, class: "plane-pt" });
    planeEl.appendChild(c);
  });

  $("#plane-count").textContent = `${PLANE.points.length} punto${PLANE.points.length === 1 ? "" : "s"}`;
}

function curvePath(exprText) {
  // evalúa la expresión ajustada punto a punto usando function-plot's evaluator no; hacemos eval seguro simple
  const f = makeEvaluator(exprText);
  if (!f) return null;
  let d = "", started = false;
  for (let px = 0; px <= PLANE.w; px += 2) {
    const [lx] = toLogic(px, 0);
    const ly = f(lx);
    if (!isFinite(ly) || ly < PLANE.min - 50 || ly > PLANE.max + 50) { started = false; continue; }
    const [, sy] = toScreen(0, ly);
    d += (started ? " L" : " M") + px.toFixed(1) + "," + sy.toFixed(1);
    started = true;
  }
  return d;
}

function makeEvaluator(exprText) {
  // SEGURIDAD: solo permitimos caracteres de expresiones matemáticas.
  // Si aparece cualquier otra cosa (letras raras, símbolos, paréntesis de llamada
  // sospechosos), rechazamos en vez de evaluar: evita inyección de código.
  const permitido = /^[0-9xX+\-*/^().,\s a-z]*$/;   // dígitos, x, operadores y nombres de funciones
  const funcionesOK = /^(x|X|sin|cos|tan|sqrt|exp|log|pi|e|E)$/;
  if (!permitido.test(exprText)) return null;
  // validar que cada "palabra" alfabética sea una función/constante conocida
  const palabras = exprText.match(/[a-zA-Z]+/g) || [];
  for (const w of palabras) {
    if (!funcionesOK.test(w)) return null;
  }
  let js = exprText
    .replace(/\^/g, "**")
    .replace(/\bx\b/g, "(X)")
    .replace(/sin/g, "Math.sin").replace(/cos/g, "Math.cos").replace(/tan/g, "Math.tan")
    .replace(/sqrt/g, "Math.sqrt").replace(/exp/g, "Math.exp").replace(/log/g, "Math.log")
    .replace(/pi/g, "Math.PI");
  try {
    // eslint-disable-next-line no-new-func
    const fn = new Function("X", `"use strict"; try { return ${js}; } catch { return NaN; }`);
    fn(0); // smoke test
    return fn;
  } catch { return null; }
}

// clic en el plano: agregar o borrar punto
planeEl.addEventListener("click", (ev) => {
  const rect = planeEl.getBoundingClientRect();
  const sx = (ev.clientX - rect.left) / rect.width * PLANE.w;
  const sy = (ev.clientY - rect.top) / rect.height * PLANE.h;

  // ¿clic sobre un punto existente? -> borrarlo
  const hitIdx = PLANE.points.findIndex(([x, y]) => {
    const [psx, psy] = toScreen(x, y);
    return Math.hypot(psx - sx, psy - sy) < 10;
  });
  if (hitIdx >= 0) {
    PLANE.points.splice(hitIdx, 1);
  } else {
    let [lx, ly] = toLogic(sx, sy);
    PLANE.points.push([snap(lx), snap(ly)]);
  }
  PLANE.fitExpr = null;
  drawPlane();
  if (PLANE.points.length >= 2) solve();
  else resultsEl.innerHTML = `<div class="placeholder">Marca al menos 2 puntos para hallar la ecuación.</div>`;
});

$("#plane-clear").addEventListener("click", () => {
  PLANE.points = [];
  PLANE.fitExpr = null;
  drawPlane();
  resultsEl.innerHTML = `<div class="placeholder">Plano limpio. Marca puntos con clic.</div>`;
});

$("#modelo-sel").addEventListener("change", () => { if (PLANE.points.length >= 2) solve(); });

boot();
