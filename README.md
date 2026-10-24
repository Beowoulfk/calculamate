# ∑ CalculaMate

Calculadora de **Cálculo 1** que corre 100% en el navegador: resuelve paso a paso
(estilo Symbolab), grafica, tiene teclado matemático en pantalla y te dice cómo
escribir cada cosa en **GeoGebra**. Está alineada con el temario del curso
([`calculo.md`](calculo.md)).

El motor matemático es **SymPy**, ejecutado en el navegador con **Pyodide**
(no necesita servidor con Python: todo es estático).

➡️ **La app está en la carpeta [`calcula1/`](calcula1/).**

---

## 🚀 Publicar en GitHub Pages

La app es un sitio estático, así que GitHub Pages la sirve sin backend.
Ya viene configurado un workflow en `.github/workflows/deploy.yml` que publica
la carpeta `calcula1/` como raíz del sitio.

### Pasos (una sola vez)

1. Crea un repositorio en GitHub y sube este proyecto:
   ```bash
   git init
   git add .
   git commit -m "CalculaMate"
   git branch -M main
   git remote add origin https://github.com/<tu-usuario>/<tu-repo>.git
   git push -u origin main
   ```

2. En GitHub: **Settings → Pages → Build and deployment → Source: GitHub Actions**.

3. Cada `push` a `main` despliega automáticamente. También puedes lanzarlo a mano
   desde la pestaña **Actions → Deploy CalculaMate to GitHub Pages → Run workflow**.

4. La URL final será:
   ```
   https://<tu-usuario>.github.io/<tu-repo>/
   ```

> El workflow publica `calcula1/` como raíz, de modo que `index.html`, `app.js`,
> `solver.py` y `styles.css` quedan en la raíz del sitio y los `fetch` relativos
> (como `fetch("solver.py")`) funcionan igual que en local.

---

## 💻 Probar en local

Como la app usa `fetch()` para cargar el motor, **no funciona con doble clic** sobre
el HTML. Levanta un mini servidor dentro de `calcula1`:

```bash
cd calcula1
python -m http.server 8000
```
Abre `http://localhost:8000`. La primera vez tarda unos segundos (descarga SymPy).

También sirve `npx serve` (Node) o la extensión **Live Server** de VS Code.

---

## 📁 Estructura

```
calculamate/
├─ index.html                 ← redirige a calcula1/ (por comodidad en local)
├─ calculo.md                 ← temario del curso de Cálculo 1
├─ README.md
├─ .github/workflows/deploy.yml   ← despliegue automático a Pages
└─ calcula1/                  ← LA APP
   ├─ index.html
   ├─ app.js
   ├─ solver.py               ← motor SymPy (corre en el navegador)
   ├─ styles.css
   ├─ .nojekyll
   └─ LEEME.md
```

---

## 🌐 Requisitos

Navegador moderno (Chrome, Edge, Firefox) y **conexión a internet la primera vez**
(descarga Pyodide/SymPy, KaTeX y function-plot desde un CDN; luego queda en caché).

> Nota: el botón **Copiar** de los comandos de GeoGebra usa `navigator.clipboard`,
> que requiere `https` o `localhost`. En GitHub Pages (https) funciona sin problema.
