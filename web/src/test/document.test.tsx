import { screen } from "@testing-library/react";
import { DocumentPage } from "../pages/catalog/DocumentPage";
import { mockFetch, renderAt } from "./utils";

const base = {
  id: "d1", cipher: "ГА ВКО Ф. Р-245 Оп. 1 Д. 30 л. 1–205", title: "Личные дела", summary: null,
  historical_note: null, period_label: "1950–1955", date_from: null, date_to: null, year_from: 1950, year_to: 1955,
  date_verified: true, category: "personal", doc_type: "certificate", language: "русский", sheets: "л. 1–205",
  sheets_count: 205, storage_location: "x", author_org: null, place: null, topic: null, tags: [],
  access_conditions: "Документы содержат персональные данные.", has_digital_copy: true,
  fund: { id: "f", number: "Р-245", cipher: "c", title: "Комбинат" },
  inventory: { id: "i", number: "1", cipher: "c", title: "Опись" },
  case: { id: "c", number: "30", cipher: "c", title: "Дело" },
  branch: null, is_personal_fund: false, is_demo: true,
  translation: { requested_lang: "ru", lang: "ru", status: "original", is_fallback: false },
};

test("закрытый документ: карточка без просмотрщика, с условиями доступа", async () => {
  mockFetch((url) => (url.includes("/catalog/documents/d1") ? { ...base, file_access: "closed", pages: [] } : undefined));
  renderAt("/ru/catalog/documents/d1", "/:lang/catalog/documents/:id", <DocumentPage />);
  expect(await screen.findByRole("heading", { level: 1, name: "Личные дела" })).toBeInTheDocument();
  expect(screen.getByText("Цифровая копия не публикуется")).toBeInTheDocument();
  expect(screen.getByText("Документы содержат персональные данные.")).toBeInTheDocument();
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
  expect(screen.getByText("Демонстрационная запись")).toBeInTheDocument();
});

test("несуществующий или скрытый документ → «Материал недоступен»", async () => {
  mockFetch(() => undefined);
  renderAt("/ru/catalog/documents/zzz", "/:lang/catalog/documents/:id", <DocumentPage />);
  expect(await screen.findByText("Материал недоступен")).toBeInTheDocument();
});
