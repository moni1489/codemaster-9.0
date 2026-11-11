import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "../locales/en";
import kk from "../locales/kk";
import ru from "../locales/ru";

function initialLang(): string {
  const seg = typeof window !== "undefined" ? window.location.pathname.split("/")[1] : "";
  return seg === "kk" || seg === "en" || seg === "ru" ? seg : "ru";
}

// Язык задаётся URL-префиксом (/kk, /ru, /en); здесь только словари интерфейса.
void i18n.use(initReactI18next).init({
  resources: { ru: { translation: ru }, kk: { translation: kk }, en: { translation: en } },
  // стартовый язык — из URL, чтобы первый рендер уже был на нужном языке
  lng: initialLang(),
  fallbackLng: "ru",
  interpolation: { escapeValue: false }, // React сам экранирует вывод
  returnNull: false,
});

export default i18n;
