// Применяет тему и версию для слабовидящих до отрисовки (без мерцания). Внешний файл — совместимо с CSP script-src 'self'.
(function () {
  var t = null;
  try { t = window.localStorage.getItem("theme"); } catch (e) { t = null; }
  if (t !== "light" && t !== "dark") {
    t = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  var el = document.documentElement;
  el.setAttribute("data-theme", t);
  // формат совпадает с src/app/lowVision.ts
  try {
    var v = JSON.parse(window.localStorage.getItem("lowvision") || "null");
    if (v && v.on) {
      el.setAttribute("data-lv", "on");
      el.setAttribute("data-lv-fs", String(v.fs || 2));
      el.setAttribute("data-lv-scheme", v.scheme || "bw");
      if (v.img === false) el.setAttribute("data-lv-img", "off");
      if (v.wide) el.setAttribute("data-lv-ls", "wide");
    }
  } catch (e) { /* нет хранилища — обычная версия */ }
})();
