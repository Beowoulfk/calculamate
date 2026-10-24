// Anti-clickjacking: si la página se carga dentro de un iframe de otro sitio,
// rompe el marco (o bloquea el contenido si no puede). Protege al usuario de
// que un tercero embeba CalculaMate para engañarlo.
(function () {
  if (window.top !== window.self) {
    try {
      window.top.location = window.self.location;
    } catch (e) {
      document.documentElement.innerHTML =
        '<p style="color:#fff;font-family:sans-serif;padding:2rem">' +
        'Esta página no puede mostrarse dentro de otro sitio.</p>';
    }
  }
})();
