import { expect, test } from "vitest";
import { parseShow } from "../features/assistant/Assistant";

test("«покажи мне …» распознаётся как команда показать", () => {
  expect(parseShow("Покажи мне фотографии Усть-Каменогорска 1960-х")).toEqual({
    show: true,
    all: false,
    rest: "фотографии Усть-Каменогорска 1960-х",
  });
  expect(parseShow("покажи")).toEqual({ show: true, all: false, rest: "" });
  expect(parseShow("Открой его.")).toEqual({ show: true, all: false, rest: "" });
  expect(parseShow("покажи все")).toEqual({ show: true, all: true, rest: "" });
  expect(parseShow("покажи все газеты 1945")).toEqual({ show: true, all: true, rest: "газеты 1945" });
  expect(parseShow("Өскемен фотосуреттерін көрсет")).toEqual({ show: true, all: false, rest: "Өскемен фотосуреттерін" });
  expect(parseShow("көрсетіңіз").rest).toBe("");
  expect(parseShow("Show me photos of Oskemen").rest).toBe("photos of Oskemen");
  expect(parseShow("показания свидетелей").show).toBe(false);
});
