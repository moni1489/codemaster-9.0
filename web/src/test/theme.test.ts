import { setTheme } from "../app/theme";

test("тема меняется без перезагрузки и сохраняется", () => {
  setTheme("dark");
  expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
  expect(window.localStorage.getItem("theme")).toBe("dark");
  setTheme("light");
  expect(document.documentElement.getAttribute("data-theme")).toBe("light");
});

test("запрет localStorage не ломает переключение темы", () => {
  const spy = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new Error("SecurityError");
  });
  expect(() => setTheme("dark")).not.toThrow();
  expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
  spy.mockRestore();
});
