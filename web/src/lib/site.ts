// Статичные сведения об учреждении. Источник: docs/source/Контакты.docx (материалы заказчика).

export const SITE = {
  phoneReception: "8 (7232) 25-59-76",
  phoneDirector: "8 (7232) 25-13-22",
  email: "arhiv-ukg@yandex.kz",
  social: {
    instagram: { handle: "@arhiv_vko", url: "https://www.instagram.com/arhiv_vko/" },
    facebook: { handle: "vkoarhiv", url: "https://www.facebook.com/vkoarhiv" },
  },
  gov: [
    { label: "Akorda.kz", url: "https://www.akorda.kz" },
    { label: "eGov.kz", url: "https://egov.kz" },
    { label: "Әділет (adilet.zan.kz)", url: "https://adilet.zan.kz" },
    { label: "e-Otinish", url: "https://eotinish.kz" },
    { label: "Акимат ВКО / ШҚО әкімдігі", url: "https://www.gov.kz/memleket/entities/akimvko" },
  ],
} as const;

export const NAV = [
  { key: "about", to: "/about" },
  { key: "catalog", to: "/catalog" },
  { key: "visitors", to: "/visitors" },
  { key: "services", to: "/services" },
  { key: "history", to: "/history" },
  { key: "exhibitions", to: "/exhibitions" },
  { key: "news", to: "/news" },
  { key: "branches", to: "/branches" },
  { key: "faq", to: "/faq" },
] as const;
