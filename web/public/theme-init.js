// Применяет тему до отрисовки (без мерцания). Внешний файл — совместимо с CSP script-src 'self'.
(function () {
  var t = null;
  try { t = window.localStorage.getItem("theme"); } catch (e) { t = null; }
  if (t !== "light" && t !== "dark") {
    t = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  document.documentElement.setAttribute("data-theme", t);
})();
