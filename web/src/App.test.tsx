import { render, screen } from "@testing-library/react";
import { App } from "./App";

test("renders title", () => {
  vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
  render(<App />);
  expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Государственный архив ВКО");
});
