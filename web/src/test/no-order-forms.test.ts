/// <reference types="node" />
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

// Д §1, §9: на сайте нет форм заявлений/заказов/оплаты. Разрешены: поиск (role="search"),
// отзыв о сайте (data-form="feedback", с дисклеймером), вход в админку (data-form="login").
const SRC = join(__dirname, "..");

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) return name === "test" ? [] : files(p);
    return /\.(tsx|ts)$/.test(name) ? [p] : [];
  });
}

test("каждая <form> — поиск, отзыв или вход в админку", () => {
  const offenders: string[] = [];
  for (const f of files(SRC)) {
    const text: string = readFileSync(f, "utf-8");
    for (const m of text.matchAll(/<form\b[^>]*>/g)) {
      const tag = m[0];
      if (!/role="search"|data-form="feedback"|data-form="login"/.test(tag)) offenders.push(`${f}: ${tag}`);
    }
  }
  expect(offenders).toEqual([]);
});

test("в интерфейсе нет призывов заказать или оплатить", () => {
  const forbidden = /(оформить заказ|оплатить|корзин|add to cart|checkout|pay now|тапсырыс беру(?!ші| және төлем жүргізілмейді)|төлеу)/i;
  // «тапсырыс беруші» (каз.) = «заказчик» — не призыв к заказу
  const hits: string[] = [];
  for (const f of files(SRC)) {
    const text: string = readFileSync(f, "utf-8");
    text.split("\n").forEach((line: string, i: number) => {
      if (forbidden.test(line)) hits.push(`${f}:${i + 1}: ${line.trim()}`);
    });
  }
  expect(hits).toEqual([]);
});
