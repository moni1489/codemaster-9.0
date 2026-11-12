import { expect, test } from "vitest";
import { parseShow } from "../features/assistant/Assistant";

test("«покажи мне …» распознаётся как команда показать", () => {
  expect(parseShow("Покажи мне фотографии Усть-Каменогорска 1960-х")).toEqual({
    show: true,
    all: false,
    rest: "фотографии Усть-Каменогорска 1960-х",
    idx: 0,
  });
  expect(parseShow("покажи")).toEqual({ show: true, all: false, rest: "", idx: 0 });
  expect(parseShow("Открой его.")).toEqual({ show: true, all: false, rest: "", idx: 0 });
  expect(parseShow("покажи все")).toEqual({ show: true, all: true, rest: "", idx: 0 });
  expect(parseShow("покажи все газеты 1945")).toEqual({ show: true, all: true, rest: "газеты 1945", idx: 0 });
  expect(parseShow("Өскемен фотосуреттерін көрсет")).toEqual({ show: true, all: false, rest: "Өскемен фотосуреттерін", idx: 0 });
  expect(parseShow("көрсетіңіз").rest).toBe("");
  expect(parseShow("Show me photos of Oskemen").rest).toBe("photos of Oskemen");
  expect(parseShow("показания свидетелей").show).toBe(false);
  expect(parseShow("покажи второй").idx).toBe(1);
  expect(parseShow("Открой третью фотографию.")).toEqual({ show: true, all: false, rest: "", idx: 2 });
  expect(parseShow("екіншісін көрсет").idx).toBe(1);
  expect(parseShow("покажи второй корпус завода").rest).toBe("второй корпус завода");
});
