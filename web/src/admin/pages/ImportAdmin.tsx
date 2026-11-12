import { useMutation } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { admin } from "../api";
import { useAuth } from "../auth";
import { Alert, PageHeader } from "../ui";

interface Preview {
  headers: string[];
  rows: string[][];
  total: number;
  fields: Record<string, { label: string; required: boolean }>;
  suggested: Record<string, string | null>;
}
interface Result {
  created: number;
  duplicates: number;
  errors: number;
  rows: { row: number; status: string; cipher: string | null; message: string | null }[];
}

const STATUS = { created: "создано", duplicate: "дубль", error: "ошибка" } as Record<string, string>;

export function ImportAdmin() {
  const { can } = useAuth();
  const [file, setFile] = useState<File | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  useEffect(() => {
    document.title = "Импорт — админ-панель ГА ВКО";
  }, []);
  const form = () => {
    const fd = new FormData();
    if (file) fd.append("file", file);
    return fd;
  };
  const preview = useMutation({
    mutationFn: () => admin.upload<Preview>("/admin/catalog/import/preview", form()),
    onSuccess: (p) => setMapping(Object.fromEntries(Object.entries(p.suggested).filter(([, v]) => v).map(([k, v]) => [k, v as string]))),
  });
  const run = useMutation({
    mutationFn: () => {
      const fd = form();
      fd.append("mapping", JSON.stringify(mapping));
      return admin.upload<Result>("/admin/catalog/import", fd);
    },
  });
  const p = preview.data;
  const missing = p ? Object.entries(p.fields).filter(([k, f]) => f.required && !mapping[k]) : [];
  return (
    <>
      <PageHeader title="Импорт и экспорт каталога">
        {can("catalog.export") && <a className="btn-ghost" href="/api/admin/catalog/export.csv">Экспорт опубликованного (CSV)</a>}
      </PageHeader>
      <Alert kind="info">
        CSV (разделитель «;» или «,», UTF-8) или XLSX, до 5000 строк. Каждая строка импортируется отдельно: ошибка в строке не
        отменяет остальные. Дубли определяются по шифру. Фонды, описи и дела создаются по номерам. Новые записи — черновики,
        закрытые по умолчанию. Категории: historical, photo, map, written, organization, personal, audiovisual.
      </Alert>
      <form
        data-form="admin"
        className="card flex flex-wrap items-end gap-3 p-4"
        onSubmit={(e) => {
          e.preventDefault();
          run.reset();
          preview.mutate();
        }}
      >
        <label className="text-sm">
          Файл
          <input type="file" required accept=".csv,.xlsx" className="mt-1 block text-sm" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </label>
        <button type="submit" className="btn-primary" disabled={!file || preview.isPending}>Предпросмотр</button>
      </form>
      {preview.isError && <Alert kind="error">{(preview.error as Error).message}</Alert>}
      {p && (
        <section className="mt-6 space-y-4">
          <h2 className="text-xl">Сопоставление колонок (строк в файле: {p.total})</h2>
          <div className="grid gap-3 md:grid-cols-3">
            {Object.entries(p.fields).map(([k, f]) => (
              <label key={k} className="text-sm">
                {f.label} {f.required && <span className="text-danger">*</span>}
                <select className="input mt-1" value={mapping[k] ?? ""} onChange={(e) => setMapping((m) => ({ ...m, [k]: e.target.value }))}>
                  <option value="">— не импортировать —</option>
                  {p.headers.map((h) => <option key={h} value={h}>{h}</option>)}
                </select>
              </label>
            ))}
          </div>
          <h3 className="font-semibold">Первые строки</h3>
          <div className="overflow-x-auto rounded-xl border border-line">
            <table className="w-full text-xs">
              <thead className="bg-surface-2"><tr>{p.headers.map((h) => <th key={h} scope="col" className="px-2 py-1 text-left">{h}</th>)}</tr></thead>
              <tbody>{p.rows.map((r, i) => <tr key={i} className="border-t border-line">{r.map((c, j) => <td key={j} className="px-2 py-1">{c}</td>)}</tr>)}</tbody>
            </table>
          </div>
          {missing.length > 0 && <Alert kind="warn">Не сопоставлены обязательные поля: {missing.map(([, f]) => f.label).join(", ")}</Alert>}
          <button type="button" className="btn-primary" disabled={missing.length > 0 || run.isPending} onClick={() => run.mutate()}>
            {run.isPending ? "Импорт…" : `Импортировать ${p.total} строк`}
          </button>
        </section>
      )}
      {run.isError && <Alert kind="error">{(run.error as Error).message}</Alert>}
      {run.data && (
        <section className="mt-6">
          <h2 className="text-xl">Протокол импорта</h2>
          <p className="mt-1">Создано: <b>{run.data.created}</b> · Дубли: <b>{run.data.duplicates}</b> · Ошибки: <b>{run.data.errors}</b></p>
          <div className="mt-3 overflow-x-auto rounded-xl border border-line">
            <table className="w-full text-sm">
              <thead className="bg-surface-2 text-left"><tr><th scope="col" className="px-3 py-2">Строка</th><th scope="col" className="px-3 py-2">Результат</th><th scope="col" className="px-3 py-2">Шифр / причина</th></tr></thead>
              <tbody>
                {run.data.rows.map((r) => (
                  <tr key={r.row} className={`border-t border-line ${r.status === "error" ? "bg-danger/5" : ""}`}>
                    <td className="px-3 py-1">{r.row}</td>
                    <td className="px-3 py-1">{STATUS[r.status] ?? r.status}</td>
                    <td className="px-3 py-1 text-xs">{r.cipher ?? ""} {r.message ?? ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </>
  );
}
