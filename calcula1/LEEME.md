# 🧮 CalculaMate — Tu Symbolab con esteroides (Cálculo 1)

Calculadora de Cálculo 1 hecha con **SymPy** que corre 100% en el navegador.
Resuelve **paso a paso** (estilo Symbolab), **grafica**, incluye **teclado matemático en
pantalla** y te dice **cómo escribir cada cosa en GeoGebra** (con botón de copiar).

Está alineada con el temario del curso (ver `../calculo.md`): relaciones y funciones,
límites y derivadas.

---

## ✨ Modos de entrada

- **ƒ Función** — una función normal, p. ej. `x^2 - 4x + 3`
- **⎰ Por tramos** — funciones a trozos, p. ej. `{ 3x-1 si x>1 ; x^2 si x<=1 }`
- **= Ecuación** — resuelve ecuaciones, p. ej. `x^2 - 5x + 6 = 0`
- **• Recta por puntos** — recta que pasa por dos puntos, p. ej. `(1,2) y (3,8)`
- **f·g Operar f y g** — suma, resta, producto, cociente y composición, con sus dominios
- **Δ Razones de cambio** — problemas aplicados del curso resueltos paso a paso
- **✏️ Gráfica → ecuación** — marca puntos en un plano y obtén la ecuación que mejor se
  ajusta (recta, parábola o cúbica) por mínimos cuadrados, con R² y comando de GeoGebra

---

## 🎓 Qué resuelve (por unidad del curso)

**Unidad I — Relaciones y funciones**
- Analizar: clasifica la función (constante, lineal, cuadrática, racional, radical,
  exponencial, logarítmica, trigonométrica), halla **dominio** con los *tips del curso*
  (raíz → inecuación, denominador ≠ 0, log > 0), **rango**, cortes, simetría y **vértice**.
- Operaciones entre f y g: (f±g), (f·g), (f/g) y composición (f∘g), con dominios.

**Unidad II — Límites**
- Límites con **evaluación directa** y, ante 0/0, **técnica de cancelación** (factorizar
  y cancelar) o **racionalización** (multiplicar por el conjugado), paso a paso.
- Límites laterales e infinitos.
- **Continuidad** con los **3 criterios** del curso (existe el límite, existe la imagen,
  y son iguales).

**Unidad III — Derivadas**
- Derivada **por reglas** (nombra la regla: suma, producto, cociente, cadena, trig).
- Derivada **por definición** (límite del cociente incremental).
- **Recta tangente** en un punto (y − f(a) = m(x − a)).
- **Criterio de 1ª y 2ª derivada**: crecimiento/decrecimiento, máximos/mínimos,
  concavidad y puntos de inflexión.
- **Razones de cambio**: globo esférico, escalera que resbala, tanque cónico.

Extras: asíntotas, serie de Taylor, raíces, simplificar/factorizar.

---

## 📐 GeoGebra

Muchos pasos incluyen un bloque **"En GeoGebra escribe:"** con el comando listo para copiar,
por ejemplo `f(x)=x^2-4x+3`, `Derivada(f)`, `Raiz(f)`, `Limite(f,1)`, `Tangente(A,f)`,
`Recta(A,B)`. Así puedes verlo también de forma visual en GeoGebra.

---

## ⌨️ Teclado en pantalla

Tres pestañas: **Básico** (números y operadores), **Funciones** (sin, cos, tan, ln, log,
eˣ, inversas, hiperbólicas, |x|, √, ∞) y **Tramos** (`si`, `;`, `<=`, `>=`, `otro`).
Inserta en la posición del cursor del campo activo (f o g).

---

## ✅ Cómo probarlo (local)

La app usa `fetch()` para cargar el motor, así que **no funciona con doble clic**.
Levanta un mini servidor:

```
cd ruta/donde/guardaste/calcula1
python -m http.server 8000
```
Abre `http://localhost:8000`. La primera vez tarda unos segundos (descarga SymPy).

Alternativas: `npx serve` (Node) o la extensión **Live Server** de VS Code.

---

## ✍️ Cómo escribir

- Potencias: `x^2` · Multiplicación implícita: `3x`, `2sin(x)`
- Raíz: `sqrt(x-1)` · Valor absoluto: `Abs(x)`
- Log natural: `ln(x)` · Exponencial: `exp(x)` · Constante e: `E`
- Infinito: `oo` · Pi: `pi`
- Por tramos: `{ valor si condición ; valor si condición ; valor otro }`
- Recta por puntos: `(1,2) y (3,8)`

---

## 📁 Archivos

| Archivo       | Qué hace                                            |
|---------------|-----------------------------------------------------|
| `index.html`  | Interfaz: modos, teclado, paneles                   |
| `styles.css`  | Diseño visual                                       |
| `solver.py`   | 🧠 El cerebro: SymPy, pasos detallados y GeoGebra   |
| `app.js`      | Conecta interfaz, teclado, gráficas y copiar        |

---

## 🌐 Requisitos

Navegador moderno y **conexión a internet la primera vez** (descarga Pyodide/SymPy,
KaTeX y function-plot desde un CDN; luego queda en caché).
