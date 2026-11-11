import { render, screen } from "@testing-library/react";
import "../app/i18n";
import { AccessBadge, TranslationNotice } from "../components/ui/Badges";
import type { FileAccess } from "../lib/types";

test("неизвестный статус доступа отображается как закрытый", () => {
  render(<AccessBadge access={"weird" as FileAccess} />);
  expect(screen.getByText("Доступ закрыт")).toBeInTheDocument();
});

test("при отсутствии перевода показывается уведомление об оригинале", () => {
  render(<TranslationNotice info={{ requested_lang: "kk", lang: "ru", status: "missing", is_fallback: true }} />);
  expect(screen.getByRole("note")).toHaveTextContent("показан оригинал");
});
