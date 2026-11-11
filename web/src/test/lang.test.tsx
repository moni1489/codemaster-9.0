import { screen } from "@testing-library/react";
import { useLang, useSwitchLangHref } from "../app/lang";
import { renderAt } from "./utils";

function Probe() {
  const href = useSwitchLangHref();
  const lang = useLang();
  return (
    <div>
      <span data-testid="lang">{lang}</span>
      <span data-testid="kk">{href("kk")}</span>
      <span data-testid="en">{href("en")}</span>
    </div>
  );
}

test("смена языка сохраняет маршрут и параметры фильтров (Д §3.3)", () => {
  renderAt("/ru/catalog?q=%D1%84%D0%BE%D1%82%D0%BE&category=photo&page=2", "/:lang/*", <Probe />);
  expect(screen.getByTestId("lang")).toHaveTextContent("ru");
  expect(screen.getByTestId("kk")).toHaveTextContent("/kk/catalog?q=%D1%84%D0%BE%D1%82%D0%BE&category=photo&page=2");
  expect(screen.getByTestId("en")).toHaveTextContent("/en/catalog?q=");
});

test("смена языка на карточке документа сохраняет id", () => {
  renderAt("/en/catalog/documents/abc-123", "/:lang/*", <Probe />);
  expect(screen.getByTestId("kk")).toHaveTextContent("/kk/catalog/documents/abc-123");
});
