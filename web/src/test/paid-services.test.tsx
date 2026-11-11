import { screen, within } from "@testing-library/react";
import { InfoPage } from "../pages/info/InfoPages";
import { mockFetch, renderAt } from "./utils";

const tr = { requested_lang: "ru", lang: "ru", status: "original", is_fallback: false };
const page = {
  slug: "services-paid", section: "services", title: "Платные услуги", body: "<p>Прейскурант утверждён.</p>",
  meta_description: null, actualized_at: "2026-11-11T00:00:00Z", is_demo: false, translation: tr,
  attachments: [
    { title: "Постановление № 289 (PDF, рус.)", url: "/api/public-docs/price-list-ru", kind: "pdf", external: false, lang: "ru", verified: true },
    { title: "Әділет", url: "https://adilet.zan.kz/rus/docs/V1800017446", kind: "link", external: true, lang: null, verified: false },
  ],
  data: {
    act: { title: "Об утверждении прейскуранта", issuer: "Восточно-Казахстанский областной акимат", kind: "Постановление", number: "289", date: "2023-12-15", basis: "…", in_force: "…" },
    transcription_note: "Набрано по скану — сверяйте с PDF.",
    currency: "тенге",
    sections: [{ no: "8", title: "Изготовление копий", rows: [{ index: "8.1.1.1.5.", name: "документа 1991 г. — до сегодняшнего дня", unit: "лист", price: "219,0" }] }],
    other_sections: [{ no: "1", title: "Курсы", pages: "2–3" }],
  },
};

test("«Платные услуги»: баннер, прейскурант, PDF и внешняя ссылка; никаких кнопок заказа", async () => {
  mockFetch((url) => (url.includes("/pages/services-paid") ? page : url.includes("/pages?") ? [] : undefined));
  renderAt("/ru/services/paid", "/:lang/services/:sub", <InfoPage section="services" />);
  expect(await screen.findByRole("heading", { level: 1, name: "Платные услуги" })).toBeInTheDocument();
  expect(screen.getByText("Оформление и оплата на этом сайте не производятся")).toBeInTheDocument();
  const table = screen.getByRole("table");
  expect(within(table).getByText("219,0")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Постановление № 289/ })).toHaveAttribute("href", "/api/public-docs/price-list-ru");
  const ext = screen.getByRole("link", { name: /Әділет/ });
  expect(ext).toHaveAttribute("target", "_blank");
  expect(ext).toHaveAttribute("rel", expect.stringContaining("noopener"));
  expect(screen.getByText(/ссылка не подтверждена/)).toBeInTheDocument();
  // на странице нет ни форм, ни кнопок действий
  expect(document.querySelector("form")).toBeNull();
  expect(screen.queryByRole("button")).toBeNull();
});
