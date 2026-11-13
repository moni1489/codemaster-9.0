import { expect, test } from "vitest";
import { isYes, parseUi } from "../features/assistant/Assistant";

test("команды оформления", () => {
  expect(parseUi("Мне не видно")).toBe("lv_on");
  expect(parseUi("плохо вижу, сделай крупнее")).toBe("lv_on");
  expect(parseUi("включи версию для слабовидящих")).toBe("lv_on");
  expect(parseUi("выключи режим для слабовидящих")).toBe("lv_off");
  expect(parseUi("верни обычную версию")).toBe("lv_off");
  expect(parseUi("Включи тёмную тему")).toBe("dark");
  expect(parseUi("слишком ярко")).toBe("dark");
  expect(parseUi("выключи тёмную тему")).toBe("light");
  expect(parseUi("светлая тема")).toBe("light");
  expect(parseUi("көрмеймін")).toBe("lv_on");
  expect(parseUi("қараңғы тақырып")).toBe("dark");
  expect(parseUi("dark mode")).toBe("dark");
  expect(parseUi("I can't see")).toBe("lv_on");
  // обычные вопросы к каталогу не перехватываем
  expect(parseUi("фотографии Усть-Каменогорска 1960-х")).toBeNull();
  expect(parseUi("покажи газеты 1945 года")).toBeNull();
  expect(parseUi("как увеличить сроки хранения документов о стаже работы на предприятии в 1980-х")).toBeNull();
});

test("согласие: позвонить / открыть 2ГИС", () => {
  for (const s of ["да", "Да.", "да, пожалуйста", "давай", "открой", "иә", "ашыңыз", "yes", "ok"]) expect(isYes(s)).toBe(true);
  for (const s of ["нет", "адрес Риддерского филиала", "да нет, телефон", "открой газеты 1945"]) expect(isYes(s)).toBe(false);
});
