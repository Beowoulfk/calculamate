"""
CalculaMate - Motor de Cálculo 1 con SymPy  (alineado al temario del curso)
===========================================================================
Explicaciones paso a paso estilo Symbolab + instrucciones de GeoGebra.

Cada "paso" es un dict:
  { "tag", "latex", "text", "explain", "geogebra" }
y al final un paso con tag "RESULTADO".
Todo se devuelve como JSON para que JavaScript lo pinte.

Temario cubierto (calculo.md):
  U1 Relaciones y funciones: dominio/imagen (tips), clases de función,
     operaciones entre funciones (suma, resta, producto, cociente, composición).
  U2 Límites: cálculo, técnicas de cancelación y racionalización, continuidad (3 criterios).
  U3 Derivadas: definición (cociente incremental), reglas, recta tangente,
     criterio de 1ª y 2ª derivada (crecimiento, concavidad, inflexión),
     razones de cambio (problemas-tipo guiados).
"""
import json
import re
import sympy as sp
from sympy import (
    symbols, latex, diff, integrate, limit, simplify, nsimplify,
    oo, S, Interval, Union, factor, Symbol, Piecewise, solveset,
    EmptySet, series, Rational, Abs, sign, zoo, nan, together, cancel,
    fraction, sqrt, expand, degree, Poly
)
from sympy import solve as sym_solve
from sympy.calculus.util import continuous_domain, function_range
from sympy.calculus.singularities import singularities

x = symbols('x', real=True)
h = symbols('h', real=True)


# ======================= PARSER =======================

def _parse(expr_str):
    from sympy.parsing.sympy_parser import (
        parse_expr, standard_transformations,
        implicit_multiplication_application, convert_xor
    )
    transformations = standard_transformations + (
        implicit_multiplication_application,
        convert_xor,
    )
    s = expr_str.strip()
    s = s.replace("sen(", "sin(").replace("sen ", "sin ")
    s = re.sub(r"\bln\b", "log", s)
    return parse_expr(s, transformations=transformations,
                      local_dict={'x': x}, evaluate=True)


def _parse_point(punto):
    p = str(punto).strip()
    if p in ("oo", "+oo", "inf", "+inf", "infinito"):
        return oo
    if p in ("-oo", "-inf", "-infinito"):
        return -oo
    return _parse(p)


def _step(tag, latex_str="", text="", explain="", geogebra=""):
    return {"tag": tag, "latex": latex_str, "text": text,
            "explain": explain, "geogebra": geogebra}


def _gg(expr):
    """Convierte una expresión SymPy a sintaxis GeoGebra (texto)."""
    s = str(expr)
    s = s.replace("**", "^").replace("*", " ")
    s = s.replace("log(", "ln(")
    s = s.replace("Abs(", "abs(")
    s = s.replace("exp(", "exp(")
    return s


def _gg_slider_dominio(f, dom):
    """GeoGebra con un deslizador para RECORRER la función y verificar el dominio/rango.
    Mueve 'a' y observa el punto P=(a, f(a)): donde P existe, a está en el dominio;
    la altura de P recorre el rango."""
    # intentar extraer límites numéricos del dominio para el rango del slider
    lo, hi = -5, 5
    try:
        if isinstance(dom, Interval):
            if dom.left.is_finite:
                lo = float(dom.left)
            if dom.right.is_finite:
                hi = float(dom.right)
            if not dom.right.is_finite:
                hi = lo + 10
            if not dom.left.is_finite:
                lo = hi - 10
    except Exception:
        pass
    return (f"f(x)={_gg(f)}\n"
            f"a=Deslizador({_num_simple(lo)},{_num_simple(hi)},0.1)\n"
            f"P=(a, f(a))\n"
            f"# Mueve el deslizador 'a': si P aparece, ese x está en el dominio;\n"
            f"# la ALTURA de P recorre el rango. Donde P desaparece, x no está en el dominio.")


def _num_simple(v):
    f = float(v)
    if abs(f - round(f)) < 1e-9:
        return str(int(round(f)))
    return f"{f:g}"


# ======================= FUNCIONES POR TRAMOS (parser) =======================

def _parse_piecewise(expr_str):
    s = expr_str.strip()
    s = re.sub(r"^\s*f\s*\(?\s*x?\s*\)?\s*=", "", s, flags=re.IGNORECASE)
    s = s.strip().strip("{}[]").strip()
    s = s.replace(" si ", " @ ").replace(" if ", " @ ").replace(" cuando ", " @ ")
    partes = _split_top(s)
    condiciones = []
    for parte in partes:
        parte = parte.strip()
        if not parte:
            continue
        if "@" in parte:
            valor, cond = parte.split("@", 1)
        else:
            valor, cond = parte, "otro"
        valor, cond = valor.strip(), cond.strip().lower()
        condiciones.append((_parse(valor), _parse_cond(cond), valor, cond))
    pw = Piecewise(*[(e, c) for (e, c, _, _) in condiciones])
    return pw, condiciones


def _split_top(s):
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch in ";," and depth == 0:
            out.append(cur); cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur)
    return out


def _parse_cond(cond):
    c = cond.strip().lower()
    if c in ("otro", "otros", "resto", "else", "otherwise", "en otro caso", ""):
        return True
    c = c.replace(" and ", " y ")
    piezas = [p.strip() for p in c.split(" y ")]
    rels = [_parse_rel(p) for p in piezas]
    if len(rels) == 1:
        return rels[0]
    cond_total = rels[0]
    for r in rels[1:]:
        cond_total = sp.And(cond_total, r)
    return cond_total


def _parse_rel(p):
    p = p.replace("≤", "<=").replace("≥", ">=").replace("≠", "!=")
    for op, fn in (("<=", sp.Le), (">=", sp.Ge), ("!=", sp.Ne),
                   ("<", sp.Lt), (">", sp.Gt), ("=", sp.Eq)):
        if op in p:
            izq, der = p.split(op, 1)
            return fn(_parse(izq), _parse(der))
    return sp.Eq(x, _parse(p))


# ======================= U1: ANÁLISIS DE FUNCIONES =======================

def _clasificar(f):
    """Clasifica la función según el temario del curso."""
    try:
        if f.is_constant():
            return "constante", "f(x) = k. Su gráfica es una recta horizontal; pendiente 0."
    except Exception:
        pass
    num, den = fraction(together(f))
    if den != 1 and den.has(x):
        return "racional", ("Cociente de polinomios. El dominio excluye los valores que "
                            "anulan el denominador; suele tener asíntotas.")
    if f.has(sp.sin, sp.cos, sp.tan, sp.cot, sp.sec, sp.csc):
        return "trigonométrica", "Derivada de las razones trigonométricas; es periódica."
    if f.has(sp.exp) or (f.has(sp.Pow) and f.atoms(sp.Pow) and any(
            (not p.base.has(x)) and p.exp.has(x) for p in f.atoms(sp.Pow))):
        return "exponencial", "De la forma a^x. Dominio ℝ, codominio los reales positivos."
    if f.has(sp.log):
        return "logarítmica", "De la forma log_a(x). Solo definida para argumento positivo."
    if any(getattr(p.exp, "is_Rational", False) and not p.exp.is_Integer
           for p in f.atoms(sp.Pow)):
        return "con radicales", "Tiene raíces; el radicando (índice par) debe ser ≥ 0."
    try:
        p = Poly(f, x)
        g = p.degree()
        if g == 0:
            return "constante", "f(x) = k. Recta horizontal."
        if g == 1:
            return "lineal (1er grado)", "f(x) = mx + b. Su gráfica es una recta."
        if g == 2:
            return "cuadrática", "f(x) = ax²+bx+c. Su gráfica es una parábola."
        return f"polinómica de grado {g}", "Polinomio; dominio ℝ."
    except Exception:
        return "función", ""


def _resolver_inecuacion_pasos(expr_rel, simbolo, titulo, intro):
    """Resuelve una inecuación lineal/sencilla mostrando el despeje paso a paso.
    expr_rel: la relación SymPy (p.ej. 2*x - 10 >= 0).
    Devuelve (lista_pasos, conjunto_solucion)."""
    pasos = []
    lhs = expr_rel.lhs - expr_rel.rhs  # todo a la izquierda
    rel_op = expr_rel.rel_op           # '>=', '>', '<=', '<'
    pasos.append(_step(titulo,
                       f"{latex(expr_rel.lhs)} \\;{_rel_tex(rel_op)}\\; {latex(expr_rel.rhs)}",
                       explain=intro))

    # intentar despeje lineal: a*x + b (op) 0  ->  x (op) -b/a
    try:
        poly = Poly(lhs, x)
        if poly.degree() == 1:
            a = poly.coeff_monomial(x)
            b = poly.coeff_monomial(1)
            # paso 1: mover el término independiente
            if b != 0:
                pasos.append(_step("Pasamos el término independiente al otro lado",
                                   f"{latex(a*x)} \\;{_rel_tex(rel_op)}\\; {latex(-b)}",
                                   explain=f"Restamos {latex(b)} en ambos lados."))
            # paso 2: dividir por el coeficiente (si es 1, no hace falta)
            objetivo = simplify(-b / a)
            op_final = rel_op
            if a.is_negative:
                op_final = _invertir_rel(rel_op)
                pasos.append(_step("Dividimos entre el coeficiente (negativo)",
                                   f"x \\;{_rel_tex(op_final)}\\; {latex(objetivo)}",
                                   explain=f"Al dividir entre {latex(a)} (negativo), la "
                                           f"desigualdad CAMBIA de sentido."))
            elif a != 1:
                pasos.append(_step("Despejamos x",
                                   f"x \\;{_rel_tex(op_final)}\\; {latex(objetivo)}",
                                   explain=f"Dividimos ambos lados entre {latex(a)}."))
    except Exception:
        pass

    try:
        sol = sp.solve_univariate_inequality(expr_rel, x, relational=False)
    except Exception:
        sol = S.Reals
    pasos.append(_step("Solución de la inecuación",
                       f"x \\in {latex(sol)}",
                       explain="Este intervalo es el conjunto de x que cumple la condición."))
    return pasos, sol


def _rel_tex(op):
    return {">=": "\\geq", "<=": "\\leq", ">": ">", "<": "<",
            "==": "=", "!=": "\\neq"}.get(op, op)


def _invertir_rel(op):
    return {">=": "<=", "<=": ">=", ">": "<", "<": ">"}.get(op, op)


def _regla_dominio(f, tipo):
    """Enuncia la REGLA de dominio que aplica según el tipo de función."""
    reglas = []
    num, den = fraction(together(f))
    tiene_den = den != 1 and den.has(x)
    tiene_raiz = any(getattr(p.exp, "is_Rational", False) and p.exp.q % 2 == 0 and p.base.has(x)
                     for p in f.atoms(sp.Pow))
    tiene_log = any(l.args[0].has(x) for l in f.atoms(sp.log))

    if not (tiene_den or tiene_raiz or tiene_log):
        reglas.append(_step(
            "Regla aplicable · Función polinómica",
            "\\text{Dom}(f) = \\mathbb{R} = (-\\infty, \\infty)",
            explain="Las funciones polinómicas (lineal, cuadrática, cúbica…) no tienen "
                    "restricciones: aceptan cualquier número real."))
        return reglas
    if tiene_den:
        reglas.append(_step(
            "Regla aplicable · Función racional",
            "\\text{denominador} \\neq 0",
            explain="Como la variable aparece en el denominador, la regla es: el denominador "
                    "no puede valer cero. Lo igualamos a cero, resolvemos y EXCLUIMOS esos valores."))
    if tiene_raiz:
        reglas.append(_step(
            "Regla aplicable · Función con raíz (índice par)",
            "\\text{radicando} \\geq 0",
            explain="Como hay una raíz de índice par, la regla es: lo de adentro (el radicando) "
                    "debe ser mayor o igual que cero. Planteamos y resolvemos la inecuación."))
    if tiene_log:
        reglas.append(_step(
            "Regla aplicable · Función logarítmica",
            "\\text{argumento} > 0",
            explain="Como hay un logaritmo, la regla es: su argumento debe ser estrictamente "
                    "mayor que cero. Planteamos y resolvemos la inecuación."))
    return reglas


def _tabla_valores(f, dom, n=5):
    """Genera una tabla de puntos (x, f(x)) dentro del dominio, para ilustrar el rango."""
    # elegir x's "bonitos" que estén en el dominio
    candidatos = [-3, -2, -1, 0, 1, 2, 3, 4, 5, -4, 6, -5]
    filas = []
    for xi in candidatos:
        if len(filas) >= n:
            break
        xv = sp.Integer(xi)
        try:
            if dom is not None and dom != S.Reals and xv not in dom:
                continue
            yv = simplify(f.subs(x, xv))
            if yv in (zoo, oo, -oo, nan) or yv.has(sp.I):
                continue
            filas.append((xv, yv))
        except Exception:
            continue
    return filas


def _tabla_valores_en(expr, conjunto, n=4):
    """Tabla (x, expr(x)) con x dentro de un conjunto dado (para un tramo)."""
    candidatos = [-3, -2, -1, 0, 1, 2, 3, 4, 5, -4, 6, -5, 7, -6]
    filas = []
    for xi in candidatos:
        if len(filas) >= n:
            break
        xv = sp.Integer(xi)
        try:
            if conjunto is not None and conjunto != S.Reals and xv not in conjunto:
                continue
            yv = simplify(expr.subs(x, xv))
            if yv in (zoo, oo, -oo, nan) or yv.has(sp.I):
                continue
            filas.append((xv, yv))
        except Exception:
            continue
    return filas


def _tabla_latex(filas):
    """Formatea la tabla (x,y) como un array LaTeX."""
    if not filas:
        return ""
    xs = " & ".join(latex(a) for a, _ in filas)
    ys = " & ".join(latex(b) for _, b in filas)
    return (f"\\begin{{array}}{{c|{'c' * len(filas)}}}"
            f"x & {xs} \\\\ \\hline "
            f"y & {ys} \\end{{array}}")


def _dominio_detallado(f, tipo=""):
    """Devuelve (dominio, lista_de_pasos, resumen) explicando el razonamiento del dominio."""
    pasos = []
    num, den = fraction(together(f))
    restricciones = []

    # 0) Enunciar la regla que aplica según el tipo de función
    pasos.extend(_regla_dominio(f, tipo))

    # 1) Denominador distinto de cero
    if den != 1 and den.has(x):
        pasos.append(_step(
            "Restricción 1: el denominador no puede ser cero",
            f"{latex(den)} \\neq 0",
            explain="Dividir entre cero no está definido. Buscamos qué valores de x anulan "
                    "el denominador para EXCLUIRLOS del dominio."))
        ceros = sym_solve(den, x)
        ceros_r = [c for c in ceros if getattr(c, "is_real", False)]
        if ceros_r:
            # mostrar la ecuación del denominador = 0 resuelta
            ceros_tex = ",\\; ".join(latex(c) for c in ceros_r)
            pasos.append(_step("Resolvemos denominador = 0",
                               f"{latex(den)} = 0 \\;\\Rightarrow\\; x = {ceros_tex}",
                               explain="Estos son los valores prohibidos."))
            txt = ",\\; ".join(latex(c) for c in ceros_r)
            pasos.append(_step("Valores excluidos", f"x \\neq {txt}"))
            restricciones.append(("den", ceros_r))

    # 2) Radicando de índice par >= 0  (con despeje paso a paso)
    radicandos = []
    for p in f.atoms(sp.Pow):
        if getattr(p.exp, "is_Rational", False) and p.exp.q % 2 == 0 and p.base.has(x):
            radicandos.append(p.base)
    for rad in radicandos:
        rel = sp.Ge(rad, 0, evaluate=False)
        subpasos, sol = _resolver_inecuacion_pasos(
            rel, x,
            "Restricción: el radicando debe ser ≥ 0",
            "Tip del curso: en una raíz de índice PAR, lo de adentro no puede ser negativo "
            "(no existe la raíz par de un número negativo en los reales). Planteamos la "
            "inecuación y la despejamos.")
        pasos.extend(subpasos)
        restricciones.append(("rad", sol))

    # 3) Argumento del logaritmo > 0  (con despeje paso a paso)
    for l in f.atoms(sp.log):
        arg = l.args[0]
        if arg.has(x):
            rel = sp.Gt(arg, 0, evaluate=False)
            subpasos, sol = _resolver_inecuacion_pasos(
                rel, x,
                "Restricción: el argumento del logaritmo debe ser > 0",
                "El logaritmo solo existe para números estrictamente positivos. Planteamos "
                "argumento > 0 y despejamos.")
            pasos.extend(subpasos)
            restricciones.append(("log", sol))

    try:
        dom = continuous_domain(f, x, S.Reals)
    except Exception:
        dom = S.Reals

    if not restricciones:
        pasos.append(_step(
            "Sin restricciones",
            "\\text{Dom}(f) = \\mathbb{R}",
            explain="Tip del curso: si NO hay raíces de índice par, ni cocientes, ni "
                    "logaritmos, la función acepta cualquier número real. El dominio es todo ℝ."))
    else:
        pasos.append(_step(
            "Reunimos las restricciones",
            f"\\text{{Dom}}(f) = {latex(dom)}",
            explain="El dominio es la intersección de todas las condiciones anteriores: "
                    "los x que las cumplen TODAS a la vez."))
    return dom, pasos, restricciones


def _rango_detallado(f, dom, tipo):
    """Explica cómo se obtiene el rango: tabla de valores + método según el tipo."""
    pasos = []
    try:
        rng = function_range(f, x, dom)
        rng_latex = latex(rng)
    except Exception:
        rng = None
        rng_latex = "\\text{(no se pudo calcular automáticamente)}"

    # --- Método 1: tabla de valores (siempre, para intuición) ---
    filas = _tabla_valores(f, dom, n=5)
    if filas:
        pasos.append(_step(
            "Método práctico · Tabla de valores",
            _tabla_latex(filas),
            explain="Evaluamos la función en varios x del dominio y observamos qué valores de "
                    "y van saliendo. Esto da una idea de qué alturas alcanza la gráfica."))

    # --- Método 2: razonamiento específico según el tipo ---
    if "radicales" in tipo:
        pasos.append(_step(
            "Método · Raíz de índice par",
            "\\sqrt{(\\;\\cdot\\;)} \\geq 0",
            explain="Una raíz de índice par nunca es negativa: su menor valor es 0. "
                    "Por eso el rango arranca en 0 y crece hacia +∞."))
    elif tipo.startswith("cuadrática"):
        try:
            p = Poly(f, x)
            a, b, c = p.all_coeffs()
            xv = simplify(-b / (2 * a))
            yv = simplify(f.subs(x, xv))
            # Identificar coeficientes y explicar cada letra
            pasos.append(_step(
                "Identificamos los coeficientes",
                f"a = {latex(a)}, \\quad b = {latex(b)}, \\quad c = {latex(c)}",
                explain="En f(x) = a·x² + b·x + c:  'a' marca la abertura (hacia arriba si a>0, "
                        "hacia abajo si a<0) y qué tan 'cerrada' es; 'b' desplaza el vértice de "
                        "lado; 'c' es el corte con el eje Y (el valor en x=0)."))
            pasos.append(_step(
                "Forma canónica (vértice)",
                "y = a\\,(x-h)^2 + k",
                explain="h y k son las coordenadas del vértice V(h, k): "
                        "'h' es la posición horizontal del vértice (su x) y 'k' es la altura "
                        "del vértice (su y). Desde el vértice la parábola sube o baja."))
            pasos.append(_step(
                "Calculamos h (abscisa del vértice)",
                f"h = -\\dfrac{{b}}{{2a}} = -\\dfrac{{{latex(b)}}}{{2\\cdot {latex(a)}}} = {latex(xv)}",
                explain="Fórmula del curso para la x del vértice."))
            pasos.append(_step(
                "Calculamos k (ordenada del vértice)",
                f"k = f(h) = f({latex(xv)}) = {latex(yv)}",
                explain="Evaluamos la función en h; k es el valor mínimo o máximo de la parábola."))
            if a.is_positive:
                pasos.append(_step("Abre hacia arriba (a > 0)",
                                   f"\\text{{Rang}}(f) = [{latex(yv)}, \\infty)",
                                   explain=f"Como a = {latex(a)} > 0, la parábola tiene un MÍNIMO "
                                           f"en y = {latex(yv)} y sube sin tope."))
            else:
                pasos.append(_step("Abre hacia abajo (a < 0)",
                                   f"\\text{{Rang}}(f) = (-\\infty, {latex(yv)}]",
                                   explain=f"Como a = {latex(a)} < 0, la parábola tiene un MÁXIMO "
                                           f"en y = {latex(yv)}."))
        except Exception:
            pass
    elif tipo.startswith("lineal"):
        # método de despejar x en función de y
        try:
            y = Symbol('y', real=True)
            sol = sym_solve(sp.Eq(y, f), x)
            if sol:
                pasos.append(_step(
                    "Método · Despejar x en función de y",
                    f"y = {latex(f)} \\;\\Rightarrow\\; x = {latex(sol[0])}",
                    explain="Cambiamos f(x) por y y despejamos x. Si la expresión resultante "
                            "no impone ninguna restricción sobre y, entonces y puede ser cualquier real."))
        except Exception:
            pass
        pasos.append(_step("Conclusión", "\\text{Rang}(f) = \\mathbb{R}",
                           explain="Una recta no horizontal toma todos los valores de y."))
    elif "exponencial" in tipo:
        pasos.append(_step("Método · Exponencial siempre positiva",
                           "a^x > 0",
                           explain="a^x nunca llega a 0 ni es negativa; su rango son los "
                                   "reales positivos (0, ∞)."))
    elif "logarítmica" in tipo:
        pasos.append(_step("Método · Logaritmo",
                           "\\text{Rang}(f) = \\mathbb{R}",
                           explain="El logaritmo crece sin tope y baja a −∞ al acercarse a 0 "
                                   "por la derecha; toma todos los valores reales."))
    else:
        pasos.append(_step("Método · Despejar x en función de y",
                           text="Cambia f(x) por y, despeja x y aplica al resultado las mismas "
                                "reglas del dominio: las restricciones sobre y dan el rango.",
                           explain="También puedes proyectar la gráfica sobre el eje Y para ver "
                                   "qué alturas cubre."))

    pasos.append(_step("Rango (imagen)", f"\\text{{Rang}}(f) = {rng_latex}"))
    return pasos


def analizar(expr_str):
    pasos = []
    f = _parse(expr_str)
    tipo, desc = _clasificar(f)
    pasos.append(_step("Función", f"f(x) = {latex(f)}",
                       text=f"Tipo: función {tipo}.", explain=desc,
                       geogebra=f"f(x)={_gg(f)}"))

    pasos.append(_step("Paso 1 · Hallar el dominio",
                       text="El dominio son los valores de x que la función acepta.",
                       explain="Según el TIPO de función aplicamos su regla correspondiente "
                               "(polinómica, racional, con raíz o logarítmica)."))
    dom, dpasos, restric = _dominio_detallado(f, tipo)
    pasos.extend(dpasos)
    pasos.append(_step("Dominio", f"\\text{{Dom}}(f) = {latex(dom)}",
                       geogebra=_gg_slider_dominio(f, dom)))

    pasos.append(_step("Paso 2 · Hallar el rango",
                       text="El rango son los valores de y que la función produce.",
                       explain="Analizamos el comportamiento de la función en su dominio."))
    rpasos = _rango_detallado(f, dom, tipo)
    pasos.extend(rpasos)
    try:
        rng = function_range(f, x, dom)
        rng_latex = latex(rng)
    except Exception:
        rng_latex = "\\text{(no se pudo calcular automáticamente)}"

    # Vértice si es cuadrática
    try:
        p = Poly(f, x)
        if p.degree() == 2:
            a, b, c = p.all_coeffs()
            xv = simplify(-b / (2 * a))
            yv = simplify(f.subs(x, xv))
            pasos.append(_step("Vértice de la parábola",
                               f"V(h, k) = ({latex(xv)},\\; {latex(yv)})",
                               explain="El vértice es el punto más alto o más bajo de la parábola. "
                                       "Su x es h = -b/(2a) y su y es k = f(h). Aquí a es el "
                                       "coeficiente de x², b el de x y c el término independiente."))
    except Exception:
        pass

    # cortes
    raices_r = _raices_reales(f)
    if raices_r:
        txt = ",\\; ".join(latex(r) for r in raices_r)
        pasos.append(_step("Corte con eje X", f"x = {txt}",
                           explain="Donde f(x)=0.", geogebra=f"Raiz(f)"))
    try:
        y0 = f.subs(x, 0)
        if y0 not in (zoo, oo, -oo, nan):
            pasos.append(_step("Corte con eje Y", f"f(0) = {latex(simplify(y0))}"))
    except Exception:
        pass

    # simetría
    try:
        if simplify(f.subs(x, -x) - f) == 0:
            pasos.append(_step("Simetría", text="Función PAR: f(−x)=f(x), simétrica respecto al eje Y."))
        elif simplify(f.subs(x, -x) + f) == 0:
            pasos.append(_step("Simetría", text="Función IMPAR: f(−x)=−f(x), simétrica respecto al origen."))
    except Exception:
        pass

    pasos.append(_step("RESULTADO",
                       f"\\text{{Dom}} = {latex(dom)} \\qquad \\text{{Rang}} = {rng_latex}",
                       geogebra=f"f(x)={_gg(f)}"))
    return pasos


def _raices_reales(f):
    try:
        return [r for r in sym_solve(f, x) if getattr(r, "is_real", False)]
    except Exception:
        return []


# ======================= U1: OPERACIONES ENTRE f y g =======================

def operar_fg(op, f_str, g_str):
    pasos = []
    f = _parse(f_str)
    g = _parse(g_str)
    pasos.append(_step("Funciones dadas",
                       f"f(x) = {latex(f)} \\qquad g(x) = {latex(g)}",
                       geogebra=f"f(x)={_gg(f)}\ng(x)={_gg(g)}"))

    def dom(e):
        try:
            return continuous_domain(e, x, S.Reals)
        except Exception:
            return S.Reals

    Df, Dg = dom(f), dom(g)
    pasos.append(_step("Dominios individuales",
                       f"D_f = {latex(Df)} \\qquad D_g = {latex(Dg)}",
                       explain="Primero hallamos el dominio de cada función."))

    if op == "suma":
        r = simplify(f + g)
        D = Df.intersect(Dg)
        pasos.append(_step("(f + g)(x)", f"f(x)+g(x) = {latex(r)}",
                           explain="Se suman las funciones.", geogebra=f"h(x)={_gg(r)}"))
        pasos.append(_step("Dominio", f"D_{{f+g}} = D_f \\cap D_g = {latex(D)}",
                           explain="Es la intersección de los dominios."))
        pasos.append(_step("RESULTADO", f"(f+g)(x) = {latex(r)}"))
    elif op == "resta":
        r = simplify(f - g)
        D = Df.intersect(Dg)
        pasos.append(_step("(f − g)(x)", f"f(x)-g(x) = {latex(r)}", geogebra=f"h(x)={_gg(r)}"))
        pasos.append(_step("Dominio", f"D_{{f-g}} = D_f \\cap D_g = {latex(D)}"))
        pasos.append(_step("RESULTADO", f"(f-g)(x) = {latex(r)}"))
    elif op == "producto":
        r = simplify(f * g)
        D = Df.intersect(Dg)
        pasos.append(_step("(f · g)(x)", f"f(x)\\cdot g(x) = {latex(r)}", geogebra=f"h(x)={_gg(r)}"))
        pasos.append(_step("Dominio", f"D_{{f\\cdot g}} = D_f \\cap D_g = {latex(D)}"))
        pasos.append(_step("RESULTADO", f"(f\\cdot g)(x) = {latex(r)}"))
    elif op == "cociente":
        r = simplify(f / g)
        ceros_g = [c for c in sym_solve(g, x) if getattr(c, "is_real", False)]
        D = Df.intersect(Dg)
        pasos.append(_step("(f / g)(x)", f"\\dfrac{{f(x)}}{{g(x)}} = {latex(r)}", geogebra=f"h(x)={_gg(r)}"))
        if ceros_g:
            txt = ",\\; ".join(latex(c) for c in ceros_g)
            pasos.append(_step("Excluir donde g(x)=0", f"x \\neq {txt}",
                               explain="En el cociente, g(x) no puede ser cero."))
        pasos.append(_step("Dominio",
                           f"D_{{f/g}} = D_f \\cap D_g \\setminus \\{{g(x)=0\\}} = {latex(D)}"))
        pasos.append(_step("RESULTADO", f"\\dfrac{{f}}{{g}}(x) = {latex(r)}"))
    elif op == "composicion":
        r = simplify(f.subs(x, g))
        pasos.append(_step("Composición (f ∘ g)(x) = f(g(x))",
                           f"f(g(x)) = f({latex(g)}) = {latex(r)}",
                           explain="Sustituimos g(x) dentro de f.",
                           geogebra=f"h(x)={_gg(r)}"))
        r2 = simplify(g.subs(x, f))
        pasos.append(_step("También (g ∘ f)(x) = g(f(x))",
                           f"g(f(x)) = {latex(r2)}",
                           explain="Ojo: la composición no es conmutativa."))
        pasos.append(_step("RESULTADO", f"(f\\circ g)(x) = {latex(r)}"))
    else:
        raise ValueError("Operación entre funciones desconocida")
    return pasos


# ======================= U2: LÍMITES CON TÉCNICAS =======================

def limite(expr_str, punto="0", direccion=""):
    pasos = []
    f = _parse(expr_str)
    p = _parse_point(punto)
    pasos.append(_step("Función", f"f(x) = {latex(f)}", geogebra=f"f(x)={_gg(f)}"))

    dir_latex = {"+": "^+", "-": "^-"}.get(direccion, "")
    pasos.append(_step("Planteamos el límite",
                       f"\\lim_{{x \\to {latex(p)}{dir_latex}}} {latex(f)}",
                       geogebra=(f"Limite(f,{_gg(p)})" if direccion == "" else
                                 (f"LimiteDerecho(f,{_gg(p)})" if direccion == "+"
                                  else f"LimiteIzquierdo(f,{_gg(p)})"))))

    # Intento 1: evaluación directa (si el punto es finito)
    indet = False
    if p not in (oo, -oo):
        try:
            val = f.subs(x, p)
            num, den = fraction(together(f))
            nv = num.subs(x, p) if num.has(x) or num.is_number else num
            dv = den.subs(x, p) if (den.has(x) or den.is_number) else den
            if val in (nan, zoo) or (simplify(nv) == 0 and simplify(dv) == 0):
                indet = True
                pasos.append(_step("Evaluación directa",
                                   f"\\lim_{{x\\to {latex(p)}}} {latex(f)} = \\dfrac{{0}}{{0}}",
                                   explain="Da la indeterminación 0/0. Debemos usar una técnica "
                                           "(cancelación o racionalización)."))
            else:
                pasos.append(_step("Evaluación directa",
                                   f"\\text{{Sustituimos }} x={latex(p)}: \\; {latex(simplify(val))}",
                                   explain="Como no hay indeterminación, el límite es el valor obtenido."))
        except Exception:
            pass

    # Técnica de cancelación / racionalización si hubo 0/0
    if indet:
        num, den = fraction(together(f))
        tiene_raiz = any(
            getattr(pw.exp, "is_Rational", False) and not pw.exp.is_Integer
            for pw in f.atoms(sp.Pow))
        if tiene_raiz:
            # racionalización: multiplicar por el conjugado
            pasos.append(_step("Técnica de racionalización",
                               text="Como hay raíces y da 0/0, multiplicamos numerador y "
                                    "denominador por el conjugado.",
                               explain="El conjugado de (a−√b) es (a+√b); al multiplicar se "
                                       "elimina la raíz usando (a−b)(a+b)=a²−b²."))
            simplificada = cancel(simplify(sp.radsimp(f)))
            pasos.append(_step("Tras racionalizar y simplificar",
                               f"= {latex(simplificada)}"))
        else:
            pasos.append(_step("Técnica de cancelación (factorización)",
                               text="Factorizamos numerador y denominador y cancelamos el factor común.",
                               explain="El factor (x − a) causa el 0/0; al cancelarlo desaparece "
                                       "la indeterminación."))
            fn = factor(num)
            fd = factor(den)
            pasos.append(_step("Factorizamos",
                               f"\\dfrac{{{latex(fn)}}}{{{latex(fd)}}}"))
            simplificada = cancel(f)
            pasos.append(_step("Cancelamos el factor común",
                               f"= {latex(simplificada)}"))
        try:
            val2 = simplificada.subs(x, p)
            pasos.append(_step("Ahora sí evaluamos",
                               f"\\text{{En }} x={latex(p)}: \\; {latex(simplify(val2))}"))
        except Exception:
            pass

    # Cálculo final (robusto) con laterales
    if direccion in ("+", "-"):
        L = limit(f, x, p, dir=direccion)
        pasos.append(_step("RESULTADO",
                           f"\\lim_{{x \\to {latex(p)}{dir_latex}}} {latex(f)} = {latex(L)}"))
        return pasos

    Lizq = limit(f, x, p, dir='-')
    Lder = limit(f, x, p, dir='+')
    pasos.append(_step("Límite por la izquierda", f"\\lim_{{x\\to {latex(p)}^-}} = {latex(Lizq)}"))
    pasos.append(_step("Límite por la derecha", f"\\lim_{{x\\to {latex(p)}^+}} = {latex(Lder)}"))
    if Lizq == Lder:
        pasos.append(_step("El límite existe",
                           f"\\lim_{{x\\to {latex(p)}}} {latex(f)} = {latex(Lder)}",
                           explain="Los límites laterales coinciden."))
        pasos.append(_step("RESULTADO", f"{latex(Lder)}"))
    else:
        pasos.append(_step("El límite NO existe",
                           text="Los límites laterales son distintos."))
        pasos.append(_step("RESULTADO", "\\text{No existe (laterales distintos)}"))
    return pasos


# ======================= U2: CONTINUIDAD (3 criterios) =======================

def continuidad(expr_str, punto="0"):
    pasos = []
    is_pw = _es_piecewise(expr_str)
    f = _parse_piecewise(expr_str)[0] if is_pw else _parse(expr_str)
    p = _parse_point(punto)
    pasos.append(_step("Función", f"f(x) = {latex(f)}"))
    pasos.append(_step("Estudiamos la continuidad en", f"x = {latex(p)}",
                       explain="El curso da 3 condiciones que deben cumplirse todas."))

    # Criterio 1: existe el límite
    Lizq = limit(f, x, p, dir='-')
    Lder = limit(f, x, p, dir='+')
    existe_lim = (Lizq == Lder) and Lizq not in (oo, -oo, zoo, nan)
    pasos.append(_step("Criterio 1: ¿existe el límite?",
                       f"\\lim_{{x\\to {latex(p)}^-}} = {latex(Lizq)}, \\quad "
                       f"\\lim_{{x\\to {latex(p)}^+}} = {latex(Lder)}",
                       explain=("Existe: los laterales coinciden." if existe_lim
                                else "NO existe: los laterales difieren o son infinitos.")))

    # Criterio 3 (imagen existe)
    try:
        val = f.subs(x, p)
        existe_img = val not in (zoo, oo, -oo, nan)
    except Exception:
        existe_img, val = False, nan
    pasos.append(_step("Criterio 2: ¿existe la imagen f(a)?",
                       f"f({latex(p)}) = {latex(simplify(val))}" if existe_img
                       else f"f({latex(p)}) \\text{{ no está definida}}",
                       explain=("La función está definida en el punto." if existe_img
                                else "La función no está definida en el punto.")))

    # Criterio 2 (igualdad límite = imagen)
    iguales = existe_lim and existe_img and simplify(Lder - val) == 0
    pasos.append(_step("Criterio 3: ¿límite = imagen?",
                       (f"{latex(Lder)} = {latex(simplify(val))}" if iguales
                        else f"{latex(Lder)} \\neq {latex(simplify(val)) if existe_img else '?'}"),
                       explain=("Coinciden." if iguales else "No coinciden (o falta alguno).")))

    if existe_lim and existe_img and iguales:
        pasos.append(_step("RESULTADO", f"\\text{{f es CONTINUA en }} x={latex(p)}",
                           explain="Se cumplen los 3 criterios."))
    else:
        motivo = ("el límite no existe" if not existe_lim else
                  "la función no está definida ahí" if not existe_img else
                  "el límite y la imagen no coinciden")
        pasos.append(_step("RESULTADO", f"\\text{{f es DISCONTINUA en }} x={latex(p)}",
                           explain=f"Falla porque {motivo}."))
    return pasos


# ======================= U3: DERIVADAS =======================

def _regla_derivada(f):
    """Identifica qué regla principal aplica, para explicarlo."""
    if f.is_Add:
        return ("Regla de la suma/diferencia",
                "La derivada de una suma es la suma de las derivadas: (u±v)' = u' ± v'.")
    if f.is_Mul:
        coef = [a for a in f.args if not a.has(x)]
        if coef and len(f.args) - len(coef) == 1:
            return ("Regla del múltiplo constante",
                    "Una constante que multiplica sale de la derivada: (k·u)' = k·u'.")
        return ("Regla del producto",
                "(u·v)' = u'·v + u·v'.")
    num, den = fraction(together(f))
    if den.has(x):
        return ("Regla del cociente",
                "(u/v)' = (u'·v − u·v') / v².")
    if f.is_Pow:
        return ("Regla de la potencia / cadena",
                "(xⁿ)' = n·xⁿ⁻¹. Si la base es una función, se multiplica por su derivada (cadena).")
    if f.has(sp.sin, sp.cos, sp.tan):
        return ("Derivadas trigonométricas (con cadena)",
                "(sin u)'=cos u·u', (cos u)'=−sin u·u', (tan u)'=sec²u·u'.")
    return ("Reglas de derivación", "Aplicamos las reglas básicas término a término.")


def derivar(expr_str):
    pasos = []
    is_pw = _es_piecewise(expr_str)
    f = _parse_piecewise(expr_str)[0] if is_pw else _parse(expr_str)
    pasos.append(_step("Función", f"f(x) = {latex(f)}", geogebra=f"f(x)={_gg(f)}"))

    nombre, desc = _regla_derivada(f)
    pasos.append(_step("Regla principal a usar", text=nombre, explain=desc))

    # derivar término a término si es suma
    if f.is_Add and not is_pw:
        for t in f.args:
            dt = simplify(diff(t, x))
            pasos.append(_step(f"Derivada de {latex(t)}", f"= {latex(dt)}"))

    d = diff(f, x)
    d_simpl = simplify(d)
    pasos.append(_step("Derivada", f"f'(x) = {latex(d)}",
                       geogebra=f"f'(x)={_gg(d_simpl)}   (o  Derivada(f) )"))
    if d_simpl != d:
        pasos.append(_step("Simplificada", f"f'(x) = {latex(d_simpl)}"))

    try:
        d2 = simplify(diff(f, x, 2))
        pasos.append(_step("Segunda derivada", f"f''(x) = {latex(d2)}",
                           explain="Sirve para concavidad y puntos de inflexión.",
                           geogebra="Derivada(f,2)"))
    except Exception:
        pass

    pasos.append(_step("RESULTADO", f"f'(x) = {latex(d_simpl)}"))
    return pasos


def derivada_definicion(expr_str, punto=None):
    """Derivada por el límite del cociente incremental (definición del curso)."""
    pasos = []
    f = _parse(expr_str)
    pasos.append(_step("Función", f"f(x) = {latex(f)}", geogebra=f"f(x)={_gg(f)}"))
    pasos.append(_step("Definición de derivada",
                       "f'(x) = \\lim_{h \\to 0} \\dfrac{f(x+h) - f(x)}{h}",
                       explain="Es la pendiente de la recta tangente: límite del cociente incremental."))
    fxh = f.subs(x, x + h)
    pasos.append(_step("Calculamos f(x+h)", f"f(x+h) = {latex(fxh)}",
                       explain="Sustituimos x por (x+h)."))
    cociente = (fxh - f) / h
    pasos.append(_step("Armamos el cociente incremental",
                       f"\\dfrac{{f(x+h)-f(x)}}{{h}} = \\dfrac{{{latex(fxh)} - ({latex(f)})}}{{h}}"))
    simpl = simplify(sp.expand(fxh - f) / h)
    pasos.append(_step("Simplificamos (dividimos entre h)", f"= {latex(simpl)}",
                       explain="Se cancela la h del denominador."))
    d = limit(cociente, h, 0)
    pasos.append(_step("Tomamos el límite cuando h→0",
                       f"\\lim_{{h\\to 0}} \\left({latex(simpl)}\\right) = {latex(simplify(d))}"))
    if punto not in (None, "", "ninguno"):
        a = _parse_point(punto)
        da = simplify(d.subs(x, a))
        pasos.append(_step("Evaluamos en el punto",
                           f"f'({latex(a)}) = {latex(da)}",
                           explain="Esta es la pendiente de la tangente en ese punto."))
    pasos.append(_step("RESULTADO", f"f'(x) = {latex(simplify(d))}"))
    return pasos


def tangente(expr_str, punto="0"):
    pasos = []
    f = _parse(expr_str)
    a = _parse_point(punto)
    pasos.append(_step("Función", f"f(x) = {latex(f)}", geogebra=f"f(x)={_gg(f)}"))
    pasos.append(_step("Punto de tangencia", f"x = {latex(a)}"))
    fa = simplify(f.subs(x, a))
    d = diff(f, x)
    ma = simplify(d.subs(x, a))
    pasos.append(_step("Derivada (pendiente de la tangente)", f"f'(x) = {latex(simplify(d))}",
                       explain="La derivada da la pendiente de la recta tangente en cada punto.",
                       geogebra="Derivada(f)"))
    pasos.append(_step("Pendiente en el punto", f"m = f'({latex(a)}) = {latex(ma)}"))
    pasos.append(_step("Punto de la curva", f"({latex(a)},\\; {latex(fa)})",
                       explain=f"Se obtiene evaluando f({latex(a)})."))
    recta = simplify(ma * (x - a) + fa)
    pasos.append(_step("Ecuación punto-pendiente",
                       f"y - {latex(fa)} = {latex(ma)}\\,(x - {latex(a)})",
                       explain="Fórmula del curso: y − f(a) = m (x − a)."))
    pasos.append(_step("Recta tangente", f"y = {latex(recta)}",
                       geogebra=f"Tangente(({_gg(a)},{_gg(fa)}),f)   o bien   y={_gg(recta)}"))
    pasos.append(_step("RESULTADO", f"y = {latex(recta)}"))
    return pasos


def criticos(expr_str):
    """Criterio de 1ª y 2ª derivada: crecimiento, máx/mín, concavidad, inflexión."""
    pasos = []
    f = _parse(expr_str)
    pasos.append(_step("Función", f"f(x) = {latex(f)}", geogebra=f"f(x)={_gg(f)}"))

    d = simplify(diff(f, x))
    d2 = simplify(diff(f, x, 2))
    pasos.append(_step("Primera derivada", f"f'(x) = {latex(d)}", geogebra="Derivada(f)"))
    pasos.append(_step("Igualamos f'(x)=0", f"{latex(d)} = 0",
                       explain="Los puntos críticos están donde la derivada se anula "
                               "(tangente horizontal)."))
    crit = sorted([c for c in sym_solve(d, x) if getattr(c, "is_real", False)],
                  key=lambda v: float(v) if v.is_number else 0)
    if not crit:
        pasos.append(_step("RESULTADO", text="No hay puntos críticos reales."))
        return pasos
    txt = ",\\; ".join(latex(c) for c in crit)
    pasos.append(_step("Puntos críticos", f"x = {txt}"))

    # Intervalos de crecimiento (signo de f')
    pts = crit
    muestras = _muestras_entre(pts)
    filas = []
    for (a, b, xm) in muestras:
        s = simplify(d.subs(x, xm))
        signo = "creciente ↑" if s.is_positive else ("decreciente ↓" if s.is_negative else "constante")
        filas.append(f"({_rango_txt(a, b)}): f'({latex(xm)})={latex(s)} ⇒ {signo}")
    pasos.append(_step("Signo de f' (crecimiento)",
                       text="  |  ".join(filas),
                       explain="Donde f'>0 la función crece; donde f'<0 decrece."))

    # Clasificar con 2ª derivada
    pasos.append(_step("Segunda derivada", f"f''(x) = {latex(d2)}", geogebra="Derivada(f,2)"))
    clasif = []
    for c in crit:
        y = simplify(f.subs(x, c))
        conc = simplify(d2.subs(x, c))
        if conc.is_positive:
            tipo = "MÍNIMO local (cóncava hacia arriba)"
        elif conc.is_negative:
            tipo = "MÁXIMO local (cóncava hacia abajo)"
        else:
            tipo = "no concluyente (revisar 1ª derivada)"
        clasif.append(_step(f"En x = {latex(c)}: {tipo}",
                            f"({latex(c)},\\; {latex(y)})",
                            explain=f"f''({latex(c)}) = {latex(conc)}."))
    pasos.extend(clasif)

    # Inflexión
    infl = [c for c in sym_solve(d2, x) if getattr(c, "is_real", False)]
    if infl:
        itxt = ",\\; ".join(latex(c) for c in infl)
        pasos.append(_step("Puntos de inflexión", f"x = {itxt}",
                           explain="Donde f''=0 la concavidad puede cambiar."))

    puntos = ",\\; ".join(f"({latex(c)}, {latex(simplify(f.subs(x, c)))})" for c in crit)
    pasos.append(_step("RESULTADO", f"\\text{{Críticos: }} {puntos}"))
    return pasos


def _muestras_entre(pts):
    """Devuelve tramos (a,b,x_muestra) a partir de puntos críticos ordenados."""
    out = []
    reales = [p for p in pts if p.is_number]
    if not reales:
        return [( -oo, oo, S.Zero )]
    # antes del primero
    out.append((-oo, reales[0], reales[0] - 1))
    for i in range(len(reales) - 1):
        a, b = reales[i], reales[i + 1]
        out.append((a, b, simplify((a + b) / 2)))
    out.append((reales[-1], oo, reales[-1] + 1))
    return out


def _rango_txt(a, b):
    la = "-\\infty" if a == -oo else latex(a)
    lb = "\\infty" if b == oo else latex(b)
    return f"{la},{lb}"


# ======================= U3: RAZONES DE CAMBIO (guiadas) =======================

RAZONES = {
    "globo": {
        "titulo": "Globo esférico que se infla",
        "enunciado": ("Se bombea aire a un globo esférico de modo que su volumen aumenta "
                      "a 100 cm³/s. ¿Con qué rapidez aumenta el radio cuando el diámetro es 50 cm?"),
        "pasos": [
            ("Datos", "\\dfrac{dV}{dt} = 100\\ \\text{cm}^3/s, \\quad d=50 \\Rightarrow r=25\\ \\text{cm}",
             "Nos dan la razón de cambio del volumen y nos piden la del radio."),
            ("Relación entre variables", "V = \\dfrac{4}{3}\\pi r^3",
             "Volumen de una esfera en función del radio."),
            ("Derivamos respecto al tiempo (regla de la cadena)",
             "\\dfrac{dV}{dt} = 4\\pi r^2 \\dfrac{dr}{dt}",
             "Como V y r dependen del tiempo, derivamos implícitamente respecto a t."),
            ("Despejamos dr/dt", "\\dfrac{dr}{dt} = \\dfrac{1}{4\\pi r^2}\\dfrac{dV}{dt}",
             "Aislamos la incógnita."),
            ("Sustituimos r=25 y dV/dt=100",
             "\\dfrac{dr}{dt} = \\dfrac{100}{4\\pi (25)^2} = \\dfrac{1}{25\\pi}",
             "Reemplazamos los valores conocidos."),
        ],
        "resultado": "\\dfrac{dr}{dt} = \\dfrac{1}{25\\pi}\\ \\text{cm/s} \\approx 0.0127\\ \\text{cm/s}",
        "geogebra": "V(r)=4/3 pi r^3   # deriva con Derivada(V)"
    },
    "escalera": {
        "titulo": "Escalera que resbala",
        "enunciado": ("Una escalera de 10 m se apoya en una pared. La base se aleja a 1 m/s. "
                      "¿Qué tan rápido baja la parte superior cuando la base está a 6 m?"),
        "pasos": [
            ("Datos", "x^2 + y^2 = 10^2, \\quad \\dfrac{dx}{dt}=1,\\ x=6 \\Rightarrow y=8",
             "Teorema de Pitágoras relaciona las distancias; y se halla con √(100−36)=8."),
            ("Derivamos respecto a t", "2x\\dfrac{dx}{dt} + 2y\\dfrac{dy}{dt} = 0",
             "Derivación implícita de la relación."),
            ("Despejamos dy/dt", "\\dfrac{dy}{dt} = -\\dfrac{x}{y}\\dfrac{dx}{dt}",
             "El signo negativo indica que y disminuye."),
            ("Sustituimos", "\\dfrac{dy}{dt} = -\\dfrac{6}{8}(1) = -\\dfrac{3}{4}",
             "Reemplazamos x=6, y=8, dx/dt=1."),
        ],
        "resultado": "\\dfrac{dy}{dt} = -\\dfrac{3}{4}\\ \\text{m/s}\\ (\\text{baja a }0.75\\ \\text{m/s})",
        "geogebra": "# Modela con un deslizador t y los puntos de la escalera"
    },
    "tanque": {
        "titulo": "Tanque cónico que se llena",
        "enunciado": ("Agua entra a un tanque cónico (radio 2 m, altura 4 m) a 2 m³/min. "
                      "¿Qué tan rápido sube el nivel cuando el agua tiene 3 m de altura?"),
        "pasos": [
            ("Datos y semejanza", "\\dfrac{r}{h} = \\dfrac{2}{4} \\Rightarrow r = \\dfrac{h}{2}",
             "Por triángulos semejantes, el radio es proporcional a la altura."),
            ("Volumen en función de h", "V = \\dfrac{1}{3}\\pi r^2 h = \\dfrac{\\pi}{12}h^3",
             "Sustituimos r=h/2 para dejar todo en h."),
            ("Derivamos respecto a t", "\\dfrac{dV}{dt} = \\dfrac{\\pi}{4}h^2\\dfrac{dh}{dt}",
             "Regla de la cadena."),
            ("Despejamos y sustituimos h=3, dV/dt=2",
             "\\dfrac{dh}{dt} = \\dfrac{4}{\\pi h^2}\\dfrac{dV}{dt} = \\dfrac{4\\cdot 2}{\\pi (3)^2} = \\dfrac{8}{9\\pi}",
             "Reemplazamos los valores."),
        ],
        "resultado": "\\dfrac{dh}{dt} = \\dfrac{8}{9\\pi}\\ \\text{m/min} \\approx 0.283\\ \\text{m/min}",
        "geogebra": "V(h)=pi/12 h^3   # Derivada(V) da dV/dh"
    },
}


def razon_cambio(clave):
    prob = RAZONES.get(clave)
    if not prob:
        raise ValueError("Problema de razón de cambio no encontrado")
    pasos = [_step("Problema", text=prob["titulo"], explain=prob["enunciado"])]
    for (tag, tex, exp) in prob["pasos"]:
        pasos.append(_step(tag, tex, explain=exp))
    pasos.append(_step("RESULTADO", prob["resultado"], geogebra=prob.get("geogebra", "")))
    return pasos


# ======================= GRÁFICA → ECUACIÓN (ajuste de curva) =======================

def _fit_poly(xs, ys, grado):
    """Ajuste polinómico por mínimos cuadrados (ecuaciones normales con SymPy).
    Devuelve (lista_coefs [a0..an], expr_sympy)."""
    n = grado
    m = len(xs)
    # Matriz de diseño A (m x n+1): [1, x, x^2, ...]
    A = sp.Matrix([[sp.Rational(str(xi)) ** j for j in range(n + 1)] for xi in xs])
    Y = sp.Matrix([[sp.Rational(str(yi))] for yi in ys])
    # Ecuaciones normales: (AᵀA) c = AᵀY
    AtA = A.T * A
    AtY = A.T * Y
    coefs = AtA.LUsolve(AtY)
    coefs = [sp.nsimplify(c, rational=False) for c in coefs]
    expr = sum(coefs[j] * x ** j for j in range(n + 1))
    return coefs, sp.expand(expr)


def _r2(xs, ys, expr):
    """Coeficiente de determinación R²."""
    yb = sum(ys) / len(ys)
    ss_tot = sum((yi - yb) ** 2 for yi in ys)
    ss_res = 0.0
    for xi, yi in zip(xs, ys):
        pred = float(expr.subs(x, xi))
        ss_res += (yi - pred) ** 2
    if ss_tot == 0:
        return 1.0 if ss_res < 1e-9 else 0.0
    return 1 - ss_res / ss_tot


def ajustar_curva(puntos_json, modelo="auto"):
    """Ajusta una curva a una nube de puntos.
    puntos_json: '[[x1,y1],[x2,y2],...]'
    modelo: 'recta' | 'parabola' | 'cubica' | 'auto'
    """
    pts = json.loads(puntos_json) if isinstance(puntos_json, str) else puntos_json
    pts = [(float(p[0]), float(p[1])) for p in pts]
    if len(pts) < 2:
        raise ValueError("Marca al menos 2 puntos en el plano.")
    # ordenar por x y promediar duplicados en x para estabilidad visual
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]

    pasos = []
    lista = ",\\; ".join(f"({_num(xi)},{_num(yi)})" for xi, yi in pts)
    pasos.append(_step("Puntos marcados", f"\\{{{lista}\\}}",
                       explain=f"Tienes {len(pts)} puntos. Buscamos la curva que mejor se "
                               f"ajusta por mínimos cuadrados."))

    grados = {"recta": 1, "parabola": 2, "cubica": 3}
    if modelo == "auto":
        # elige el grado que mejora R² sin exceder (nº puntos - 1)
        candidatos = [g for g in (1, 2, 3) if g <= len(pts) - 1] or [1]
        mejor = None
        for g in candidatos:
            try:
                coefs, expr = _fit_poly(xs, ys, g)
                r2 = _r2(xs, ys, expr)
                if mejor is None or r2 > mejor[2] + 1e-6:
                    mejor = (g, coefs, r2, expr)
            except Exception:
                continue
        grado, coefs, r2, expr = mejor
        nombre = {1: "recta (grado 1)", 2: "parábola (grado 2)", 3: "cúbica (grado 3)"}[grado]
        pasos.append(_step("Modelo elegido automáticamente", text=f"Mejor ajuste: {nombre}.",
                           explain="Se probó grado 1, 2 y 3 y se quedó el de mayor R²."))
    else:
        grado = grados.get(modelo, 1)
        grado = min(grado, max(1, len(pts) - 1))
        coefs, expr = _fit_poly(xs, ys, grado)
        r2 = _r2(xs, ys, expr)

    # Mostrar el modelo general
    formas = {
        1: "y = a_1 x + a_0",
        2: "y = a_2 x^2 + a_1 x + a_0",
        3: "y = a_3 x^3 + a_2 x^2 + a_1 x + a_0",
    }
    pasos.append(_step("Modelo propuesto", formas[grado],
                       explain="Buscamos los coeficientes que minimizan el error cuadrático."))
    pasos.append(_step("Método: mínimos cuadrados",
                       "(A^T A)\\,\\vec{c} = A^T \\vec{y}",
                       explain="Resolvemos las ecuaciones normales; A es la matriz de diseño "
                               "con columnas 1, x, x², …"))
    # coeficientes
    coef_txt = ",\\quad ".join(f"a_{j} = {latex(coefs[j])}" for j in range(grado + 1))
    pasos.append(_step("Coeficientes hallados", coef_txt))

    expr_s = sp.nsimplify(expr, rational=False)
    pasos.append(_step("Ecuación ajustada", f"y = {latex(expr_s)}"))
    pasos.append(_step("Bondad del ajuste",
                       f"R^2 = {r2:.4f}",
                       explain="R² cercano a 1 indica que la curva pasa muy cerca de los puntos."))
    pasos.append(_step("RESULTADO", f"y = {latex(expr_s)}",
                       geogebra=_gg_ajuste(pts, grado)))

    return pasos, str(expr).replace("**", "^"), pts


def _gg_ajuste(pts, grado):
    lista = ", ".join(f"({_num(a)},{_num(b)})" for a, b in pts)
    cmd = f"datos = {{{lista}}}\n"
    if grado == 1:
        cmd += "AjusteLineal(datos)"
    else:
        cmd += f"AjustePolinomico(datos, {grado})"
    return cmd


def _num(v):
    """Formatea un número para texto (sin .0 innecesario)."""
    f = float(v)
    if abs(f - round(f)) < 1e-9:
        return str(int(round(f)))
    return f"{f:g}"


# ======================= RESTO DE OPERACIONES =======================

def simplificar(expr_str):
    pasos = []
    f = _parse(expr_str)
    pasos.append(_step("Expresión original", f"{latex(f)}", geogebra=f"f(x)={_gg(f)}"))
    s = simplify(f)
    pasos.append(_step("Simplificada", f"{latex(s)}", geogebra="Simplifica(f)"))
    try:
        fac = factor(f)
        if fac != s:
            pasos.append(_step("Factorizada", f"{latex(fac)}", geogebra="Factoriza(f)"))
    except Exception:
        pass
    try:
        exp = expand(f)
        if exp != s and exp != f:
            pasos.append(_step("Expandida", f"{latex(exp)}", geogebra="Expande(f)"))
    except Exception:
        pass
    pasos.append(_step("RESULTADO", f"{latex(s)}"))
    return pasos


def raices(expr_str):
    pasos = []
    f = _parse(expr_str)
    pasos.append(_step("Función", f"f(x) = {latex(f)}", geogebra=f"f(x)={_gg(f)}"))
    pasos.append(_step("Planteamos f(x)=0", f"{latex(f)} = 0",
                       explain="Las raíces son los cortes con el eje X."))
    try:
        fac = factor(f)
        if fac != f:
            pasos.append(_step("Factorizamos", f"{latex(fac)} = 0",
                               explain="Factorizar revela las soluciones."))
    except Exception:
        pass
    sol = sym_solve(f, x)
    if sol:
        txt = ",\\; ".join(latex(s) for s in sol)
        pasos.append(_step("Soluciones", f"x = {txt}"))
        pasos.append(_step("RESULTADO", f"x = {txt}", geogebra="Raiz(f)"))
    else:
        pasos.append(_step("RESULTADO", "\\text{No tiene raíces reales}"))
    return pasos


def resolver_ecuacion(expr_str):
    pasos = []
    if "=" in expr_str:
        izq_s, der_s = expr_str.split("=", 1)
        izq, der = _parse(izq_s), _parse(der_s)
    else:
        izq, der = _parse(expr_str), S.Zero
    pasos.append(_step("Ecuación", f"{latex(sp.Eq(izq, der))}"))
    movido = simplify(izq - der)
    pasos.append(_step("Pasamos todo a un lado", f"{latex(movido)} = 0"))
    try:
        fac = factor(movido)
        if fac != movido:
            pasos.append(_step("Factorizamos", f"{latex(fac)} = 0"))
    except Exception:
        pass
    sol = sym_solve(sp.Eq(izq, der), x)
    if sol:
        txt = ",\\; ".join(latex(s) for s in sol)
        pasos.append(_step("Soluciones", f"x = {txt}"))
        pasos.append(_step("RESULTADO", f"x = {txt}",
                           geogebra=f"Resuelve({_gg(izq)}={_gg(der)})"))
    else:
        pasos.append(_step("RESULTADO", "\\text{Sin solución real}"))
    return pasos


def asintotas(expr_str):
    pasos = []
    f = _parse(expr_str)
    pasos.append(_step("Función", f"f(x) = {latex(f)}", geogebra=f"f(x)={_gg(f)}"))
    verticales = []
    try:
        sing = singularities(f, x, S.Reals)
        if sing not in (EmptySet, S.EmptySet):
            verticales = list(sing)
    except Exception:
        pass
    if verticales:
        txt = ",\\; ".join(latex(v) for v in verticales)
        pasos.append(_step("Asíntotas verticales", f"x = {txt}",
                           explain="Donde el denominador se anula y la función diverge.",
                           geogebra="Asintota(f)"))
    else:
        pasos.append(_step("Asíntotas verticales", text="No se detectaron."))
    Lpos = limit(f, x, oo)
    Lneg = limit(f, x, -oo)
    if Lpos.is_finite:
        pasos.append(_step("Asíntota horizontal (x→+∞)", f"y = {latex(Lpos)}",
                           explain="Límite de f cuando x tiende a +∞."))
    if Lneg.is_finite and Lneg != Lpos:
        pasos.append(_step("Asíntota horizontal (x→−∞)", f"y = {latex(Lneg)}"))
    try:
        m = limit(f / x, x, oo)
        if m.is_finite and m != 0:
            b = limit(f - m * x, x, oo)
            if b.is_finite:
                pasos.append(_step("Asíntota oblicua", f"y = {latex(m)}x + {latex(b)}",
                                   explain="m = lim f/x, b = lim (f − m·x)."))
    except Exception:
        pass
    pasos.append(_step("RESULTADO", text="Análisis de asíntotas completado."))
    return pasos


def taylor(expr_str, punto="0", orden="4"):
    pasos = []
    f = _parse(expr_str)
    a = _parse_point(punto)
    try:
        n = int(orden)
    except Exception:
        n = 4
    pasos.append(_step("Función", f"f(x) = {latex(f)}"))
    pasos.append(_step("Centro y orden", f"a = {latex(a)},\\quad n = {n}"))
    ser = series(f, x, a, n + 1).removeO()
    pasos.append(_step("Polinomio de Taylor", f"P_{{{n}}}(x) = {latex(ser)}",
                       explain="Aproximación polinómica cerca del centro."))
    pasos.append(_step("RESULTADO", f"{latex(ser)}", geogebra=f"PolinomioTaylor(f,{_gg(a)},{n})"))
    return pasos


# ======================= PIECEWISE (análisis) =======================

def analizar_piecewise(expr_str, op="analizar", punto="0"):
    pw, tramos = _parse_piecewise(expr_str)
    pasos = [_step("Función por tramos", f"f(x) = {latex(pw)}",
                   explain="Interpretamos cada tramo con su condición.")]
    for (e, c, vtxt, ctxt) in tramos:
        cond_leg = "en otro caso" if c is True else ctxt
        pasos.append(_step("Tramo", f"f(x) = {latex(e)} \\quad \\text{{si }} {cond_leg}"))

    if op == "derivar":
        pasos.append(_step("Derivamos cada tramo por separado",
                           text="En una función por tramos, la derivada se calcula tramo a tramo "
                                "con las reglas usuales.",
                           explain="En los puntos de unión la derivada puede no existir si hay "
                                   "un pico o un salto."))
        for (e, c, vtxt, ctxt) in tramos:
            cond_leg = "en otro caso" if c is True else ctxt
            de = simplify(diff(e, x))
            pasos.append(_step(f"Derivada del tramo ({cond_leg})",
                               f"\\dfrac{{d}}{{dx}}\\left[{latex(e)}\\right] = {latex(de)}"))
        d = diff(pw, x)
        pasos.append(_step("RESULTADO", f"f'(x) = {latex(simplify(d))}"))
        return pasos

    if op in ("limite", "continuidad"):
        return continuidad(expr_str, punto)

    # ---------- op == "analizar": análisis COMPLETO y detallado ----------
    return _analizar_piecewise_completo(expr_str, pw, tramos, pasos)


def _analizar_piecewise_completo(expr_str, pw, tramos, pasos):
    fronteras = _fronteras_tramos(tramos)

    # 1) DOMINIO: unión de los dominios de cada tramo según su condición
    pasos.append(_step("Paso 1 · Dominio",
                       text="El dominio de una función por tramos es la unión de los intervalos "
                            "donde está definida cada parte.",
                       explain="Para cada tramo miramos su condición Y la regla de su tipo de "
                               "función (polinómica, racional, con raíz o logarítmica)."))
    for (e, c, vtxt, ctxt) in tramos:
        cond_leg = "en otro caso (todos los x restantes)" if c is True else _cond_tex(c)
        tipo_e, _ = _clasificar(e)
        pasos.append(_step(f"Tramo: f(x) = {latex(e)}",
                           f"\\text{{condición: }} {cond_leg}",
                           explain=f"Es una función {tipo_e} válida en ese conjunto de x."))
        # regla de dominio propia de la fórmula del tramo
        for r in _regla_dominio(e, tipo_e):
            pasos.append(r)
        try:
            dtr = continuous_domain(e, x, S.Reals)
            if dtr != S.Reals:
                pasos.append(_step("Restricción propia de la fórmula",
                                   f"\\text{{esta parte exige }} x \\in {latex(dtr)}",
                                   explain="Se combina con la condición del tramo."))
        except Exception:
            pass
    try:
        dom = continuous_domain(pw, x, S.Reals)
    except Exception:
        dom = S.Reals
    pasos.append(_step("Dominio de f", f"\\text{{Dom}}(f) = {latex(dom)}",
                       geogebra=_gg_slider_dominio(pw, dom)))

    # 2) CONTINUIDAD detallada en cada frontera (3 criterios)
    pasos.append(_step("Paso 2 · Continuidad en los puntos de unión",
                       text="Donde cambia la fórmula aplicamos los 3 criterios de continuidad.",
                       explain="1) que exista el límite, 2) que exista f(a), 3) que coincidan."))
    discontinuidades = []
    for p in fronteras:
        Lizq = limit(pw, x, p, dir='-')
        Lder = limit(pw, x, p, dir='+')
        try:
            val = pw.subs(x, p)
            existe_img = val not in (zoo, oo, -oo, nan)
        except Exception:
            existe_img, val = False, nan
        existe_lim = (Lizq == Lder) and Lizq not in (oo, -oo, zoo, nan)
        pasos.append(_step(f"En x = {latex(p)} · Criterio 1 (límite)",
                           f"\\lim_{{x\\to {latex(p)}^-}} = {latex(Lizq)}, \\quad "
                           f"\\lim_{{x\\to {latex(p)}^+}} = {latex(Lder)}",
                           explain=("Los laterales coinciden: el límite existe." if existe_lim
                                    else "Los laterales NO coinciden: el límite no existe (hay salto).")))
        pasos.append(_step(f"En x = {latex(p)} · Criterio 2 (imagen)",
                           (f"f({latex(p)}) = {latex(simplify(val))}" if existe_img
                            else f"f({latex(p)}) \\text{{ no está definida}}"),
                           explain=("La función está definida en el punto." if existe_img
                                    else "La función no toma valor en el punto.")))
        iguales = existe_lim and existe_img and simplify(Lder - val) == 0
        if existe_lim and existe_img:
            pasos.append(_step(f"En x = {latex(p)} · Criterio 3 (igualdad)",
                               (f"{latex(Lder)} = {latex(simplify(val))}" if iguales
                                else f"{latex(Lder)} \\neq {latex(simplify(val))}"),
                               explain=("Coinciden límite e imagen." if iguales
                                        else "Límite e imagen difieren.")))
        if existe_lim and existe_img and iguales:
            pasos.append(_step(f"Conclusión en x = {latex(p)}",
                               f"\\text{{CONTINUA en }} x={latex(p)}",
                               explain="Se cumplen los 3 criterios."))
        else:
            discontinuidades.append(p)
            tipo = ("salto" if existe_lim is False and (Lizq not in (oo,-oo,zoo,nan))
                    and (Lder not in (oo,-oo,zoo,nan)) and Lizq != Lder
                    else ("evitable" if existe_lim and not iguales else "esencial/infinita"))
            pasos.append(_step(f"Conclusión en x = {latex(p)}",
                               f"\\text{{DISCONTINUA en }} x={latex(p)} \\;(\\text{{{tipo}}})",
                               explain="No se cumplen los 3 criterios."))
    if not fronteras:
        pasos.append(_step("Continuidad", text="No hay puntos de unión que revisar."))

    # 3) RANGO (unión de imágenes de cada tramo) con TABLA DE VALORES por tramo
    pasos.append(_step("Paso 3 · Rango (imagen)",
                       text="El rango es la unión de los valores que produce cada tramo en su intervalo.",
                       explain="Para cada parte evaluamos algunos x (tabla de valores) y hallamos su imagen."))
    rng_total = None
    for (e, c, vtxt, ctxt) in tramos:
        sub = _dominio_de_cond(c, dom)
        if sub in (EmptySet, S.EmptySet) or sub == sp.EmptySet:
            continue  # este tramo quedó fuera del dominio real de f
        cond_leg = "en otro caso" if c is True else _cond_tex(c)
        # tabla de valores del tramo
        filas = _tabla_valores_en(e, sub, n=4)
        if filas:
            pasos.append(_step(
                f"Tabla del tramo {latex(e)}  ({cond_leg})",
                _tabla_latex(filas),
                explain="Evaluamos la fórmula de este tramo en x dentro de su condición."))
        try:
            r = function_range(e, x, sub)
        except Exception:
            r = None
        if r is not None:
            pasos.append(_step(f"Imagen del tramo {latex(e)}",
                               f"\\text{{sobre }} {latex(sub)}: \\; {latex(r)}",
                               explain="Estos son los valores de y que alcanza este tramo."))
            rng_total = r if rng_total is None else Union(rng_total, r)
    if rng_total is not None:
        pasos.append(_step("Rango de f", f"\\text{{Rang}}(f) = {latex(rng_total)}",
                           explain="Unimos las imágenes de todos los tramos."))

    # 4) CORTES con los ejes
    try:
        raices_pw = [r for r in sym_solve(pw, x) if getattr(r, "is_real", False)]
        if raices_pw:
            txt = ",\\; ".join(latex(r) for r in raices_pw)
            pasos.append(_step("Corte con eje X", f"x = {txt}", explain="Donde f(x)=0."))
    except Exception:
        pass
    try:
        y0 = pw.subs(x, 0)
        if y0 not in (zoo, oo, -oo, nan):
            pasos.append(_step("Corte con eje Y", f"f(0) = {latex(simplify(y0))}"))
    except Exception:
        pass

    # Resumen final
    resumen = f"\\text{{Dom}} = {latex(dom)}"
    if rng_total is not None:
        resumen += f" \\qquad \\text{{Rang}} = {latex(rng_total)}"
    if discontinuidades:
        dtxt = ",\\; ".join(latex(p) for p in discontinuidades)
        resumen += f" \\qquad \\text{{Discontinua en }} x={dtxt}"
    else:
        resumen += " \\qquad \\text{(continua en todo su dominio)}"
    pasos.append(_step("RESULTADO", resumen, geogebra=_gg_piecewise(tramos)))
    return pasos


def _cond_tex(c):
    """LaTeX legible de una condición (relación o conjunción)."""
    try:
        return latex(c)
    except Exception:
        return str(c)


def _dominio_de_cond(cond, dom_global):
    """Convierte una condición de tramo en el subconjunto de x correspondiente."""
    if cond is True:
        return dom_global
    try:
        s = sp.solve_univariate_inequality(cond, x, relational=False)
        return s.intersect(dom_global)
    except Exception:
        try:
            return sp.ConditionSet(x, cond, dom_global)
        except Exception:
            return dom_global


def _gg_piecewise(tramos):
    """Comando GeoGebra para una función por tramos con Si(...)."""
    # GeoGebra: f(x)=Si(cond1, val1, cond2, val2, ..., valorPorDefecto)
    partes = []
    defecto = None
    for (e, c, vtxt, ctxt) in tramos:
        if c is True:
            defecto = _gg(e)
        else:
            partes.append((_cond_gg(c), _gg(e)))
    args = []
    for (cg, eg) in partes:
        args.append(cg)
        args.append(eg)
    if defecto is not None:
        args.append(defecto)
    return "f(x)=Si(" + ", ".join(args) + ")"


def _cond_gg(cond):
    """Condición en sintaxis GeoGebra (x > 1, x <= 1, etc.)."""
    s = str(cond)
    s = s.replace(">=", "≥").replace("<=", "≤")  # GeoGebra acepta ambos; dejamos legible
    return s.replace("≥", ">=").replace("≤", "<=")


def _fronteras_tramos(tramos):
    pts = set()
    for (_, c, _, _) in tramos:
        if c is True:
            continue
        for rel in _iter_rels(c):
            try:
                if rel.lhs == x:
                    pts.add(rel.rhs)
                elif rel.rhs == x:
                    pts.add(rel.lhs)
            except Exception:
                pass
    try:
        return sorted(pts, key=lambda v: float(v))
    except Exception:
        return list(pts)


def _iter_rels(cond):
    if isinstance(cond, (sp.And, sp.Or)):
        res = []
        for a in cond.args:
            res += _iter_rels(a)
        return res
    if isinstance(cond, sp.Rel):
        return [cond]
    return []


# ======================= RECTA POR PUNTOS =======================

def recta_puntos(texto):
    pasos = []
    nums = re.findall(r"-?\d+\.?\d*", texto)
    if len(nums) < 4:
        raise ValueError("Necesito dos puntos: p. ej. (1,2) y (3,8)")
    x1, y1, x2, y2 = (nsimplify(nums[0]), nsimplify(nums[1]),
                      nsimplify(nums[2]), nsimplify(nums[3]))
    pasos.append(_step("Puntos dados",
                       f"P_1=({latex(x1)},{latex(y1)}),\\quad P_2=({latex(x2)},{latex(y2)})",
                       geogebra=f"A=({_gg(x1)},{_gg(y1)})\nB=({_gg(x2)},{_gg(y2)})"))
    if x2 == x1:
        pasos.append(_step("Recta vertical", f"x = {latex(x1)}",
                           explain="Ambos puntos tienen la misma x."))
        pasos.append(_step("RESULTADO", f"x = {latex(x1)}"))
        return pasos, None
    m = nsimplify((y2 - y1) / (x2 - x1))
    pasos.append(_step("Pendiente",
                       f"m = \\dfrac{{y_2-y_1}}{{x_2-x_1}} = "
                       f"\\dfrac{{{latex(y2)}-{latex(y1)}}}{{{latex(x2)}-{latex(x1)}}} = {latex(m)}",
                       explain="La pendiente mide la inclinación de la recta."))
    y = simplify(m * (x - x1) + y1)
    pasos.append(_step("Punto-pendiente", f"y - {latex(y1)} = {latex(m)}(x - {latex(x1)})"))
    pasos.append(_step("Forma pendiente-intercepto", f"y = {latex(y)}"))
    b = simplify(y.subs(x, 0))
    pasos.append(_step("Intercepto con eje Y", f"b = {latex(b)}"))
    pasos.append(_step("RESULTADO", f"y = {latex(y)}",
                       geogebra=f"Recta(A,B)   o bien   f(x)={_gg(y)}"))
    expr_txt = str(y).replace("**", "^")
    return pasos, expr_txt


# ======================= PUNTO DE ENTRADA =======================

def _es_piecewise(expr_str):
    s = str(expr_str).lower()
    return (" si " in s or " if " in s or " cuando " in s
            or (("{" in s or "[" in s) and ("si" in s or "if" in s)))


def resolver(op, expr_str, punto="0", extra1="", extra2=""):
    try:
        if op == "recta_puntos":
            pasos, expr_txt = recta_puntos(expr_str)
            return json.dumps({"ok": True, "pasos": pasos, "plot": expr_txt})

        if op == "razon_cambio":
            pasos = razon_cambio(expr_str.strip().lower() or "globo")
            return json.dumps({"ok": True, "pasos": pasos, "noplot": True})

        if op == "ajustar_curva":
            # expr_str = JSON de puntos, extra1 = modelo
            pasos, expr_txt, pts = ajustar_curva(expr_str, extra1 or "auto")
            return json.dumps({"ok": True, "pasos": pasos, "fit": expr_txt, "puntos": pts})

        if op.startswith("fg_"):
            sub = op[3:]  # suma, resta, producto, cociente, composicion
            pasos = operar_fg(sub, expr_str, extra1)
            return json.dumps({"ok": True, "pasos": pasos, "fg": True})

        if _es_piecewise(expr_str) and op in ("analizar", "derivar", "limite", "continuidad"):
            pasos = analizar_piecewise(expr_str, op, punto)
            return json.dumps({"ok": True, "pasos": pasos, "piecewise": True})

        if op == "analizar":
            pasos = analizar(expr_str)
        elif op == "derivar":
            pasos = derivar(expr_str)
        elif op == "derivada_definicion":
            pasos = derivada_definicion(expr_str, extra1)
        elif op == "limite":
            pasos = limite(expr_str, punto, extra1)
        elif op == "continuidad":
            pasos = continuidad(expr_str, punto)
        elif op == "asintotas":
            pasos = asintotas(expr_str)
        elif op == "tangente":
            pasos = tangente(expr_str, punto)
        elif op == "criticos":
            pasos = criticos(expr_str)
        elif op == "taylor":
            pasos = taylor(expr_str, punto, extra1 or "4")
        elif op == "simplificar":
            pasos = simplificar(expr_str)
        elif op == "raices":
            pasos = raices(expr_str)
        elif op == "resolver_ecuacion":
            pasos = resolver_ecuacion(expr_str)
        else:
            return json.dumps({"ok": False, "error": "Operación desconocida"})
        return json.dumps({"ok": True, "pasos": pasos})
    except Exception as e:
        return json.dumps({"ok": False, "error": f"No pude procesar: {e}"})


def preview_latex(expr_str):
    try:
        if _es_piecewise(expr_str):
            pw, _ = _parse_piecewise(expr_str)
            return latex(pw)
        if "=" in expr_str and expr_str.count("=") == 1:
            izq, der = expr_str.split("=", 1)
            return latex(sp.Eq(_parse(izq), _parse(der)))
        return latex(_parse(expr_str))
    except Exception:
        return ""


def plot_expr(expr_str):
    try:
        if _es_piecewise(expr_str):
            pw, tramos = _parse_piecewise(expr_str)
            data = [{"fn": str(e).replace("**", "^")} for (e, c, vtxt, ctxt) in tramos]
            return json.dumps({"piecewise": True, "tramos": data})
        return json.dumps({"piecewise": False,
                           "fn": str(_parse(expr_str)).replace("**", "^")})
    except Exception:
        return json.dumps({"piecewise": False, "fn": expr_str})
