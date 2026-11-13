import "leaflet/dist/leaflet.css";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState, useSyncExternalStore } from "react";
import { CircleMarker, MapContainer, TileLayer, Tooltip, useMap } from "react-leaflet";
import { useLang } from "../app/lang";
import { useT } from "../app/useT";
import { useTitle } from "../app/useTitle";
import { TranslationNotice } from "../components/ui/Badges";
import { Breadcrumbs } from "../components/ui/Breadcrumbs";
import { ExternalLink } from "../components/ui/ExternalLink";
import { Icon } from "../components/ui/Icon";
import { ErrorState, Loading } from "../components/ui/States";
import { apiGet } from "../lib/api";
import type { Branch } from "../lib/types";

// Справочник населённых пунктов для ручного ввода начальной точки (без внешнего геокодера).
// Координаты приблизительные — для оценки расстояния по прямой.
const PLACES: { names: string[]; lat: number; lon: number }[] = [
  { names: ["Усть-Каменогорск", "Өскемен", "Oskemen", "Ust-Kamenogorsk"], lat: 49.948, lon: 82.628 },
  { names: ["Риддер", "Ridder", "Лениногорск"], lat: 50.345, lon: 83.513 },
  { names: ["Алтай", "Зыряновск", "Altai"], lat: 49.727, lon: 84.273 },
  { names: ["Зайсан", "Zaisan"], lat: 47.469, lon: 84.871 },
  { names: ["Шемонаиха", "Shemonaikha"], lat: 50.628, lon: 81.911 },
  { names: ["Глубокое", "Glubokoe"], lat: 50.139, lon: 82.312 },
  { names: ["Семей", "Semey", "Семипалатинск"], lat: 50.411, lon: 80.227 },
  { names: ["Астана", "Astana"], lat: 51.169, lon: 71.449 },
  { names: ["Алматы", "Almaty"], lat: 43.238, lon: 76.946 },
  { names: ["Катон-Карагай", "Katon-Karagai"], lat: 49.177, lon: 85.61 },
  { names: ["Курчум", "Kurchum", "Күршім"], lat: 48.566, lon: 83.656 },
];

export function haversineKm(a: [number, number], b: [number, number]): number {
  const R = 6371;
  const rad = (d: number) => (d * Math.PI) / 180;
  const dLat = rad(b[0] - a[0]);
  const dLon = rad(b[1] - a[1]);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a[0])) * Math.cos(rad(b[0])) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

function findPlace(text: string): [number, number] | null {
  const m = text.trim().match(/^(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)$/);
  if (m) return [Number(m[1]), Number(m[2])];
  const low = text.toLowerCase();
  const p = PLACES.find((x) => x.names.some((n) => low.includes(n.toLowerCase())));
  return p ? [p.lat, p.lon] : null;
}

function FlyTo({ pos }: { pos: [number, number] | null }) {
  const map = useMap();
  if (pos) map.flyTo(pos, 10, { duration: 0.6 });
  return null;
}

// https-ссылка 2ГИС: на телефоне с установленным приложением открывается само приложение (universal/app link)
const twoGisUrl = (b: Branch) =>
  b.lat !== null && b.lon !== null
    ? `https://2gis.kz/directions/points/%7C${b.lon}%2C${b.lat}`
    : `https://2gis.kz/search/${encodeURIComponent(`${b.address}, ${b.locality}`)}`;

function RoutePanel({ b }: { b: Branch }) {
  const { t } = useT();
  const [from, setFrom] = useState("");
  const [geo, setGeo] = useState<[number, number] | null>(null);
  const [geoError, setGeoError] = useState(false);
  const origin = geo ?? (from ? findPlace(from) : null);
  const dest: [number, number] | null = b.lat !== null && b.lon !== null ? [b.lat, b.lon] : null;
  const km = origin && dest ? haversineKm(origin, dest) : null;
  const destText = encodeURIComponent(`${b.address}, ${b.locality}`);
  const originText = geo ? `${geo[0]},${geo[1]}` : from;
  const links = [
    { name: "2GIS", url: twoGisUrl(b) },
    { name: "Google Maps", url: `https://www.google.com/maps/dir/?api=1${originText ? `&origin=${encodeURIComponent(originText)}` : ""}&destination=${dest ? `${dest[0]},${dest[1]}` : destText}` },
    { name: "Яндекс Карты", url: dest ? `https://yandex.kz/maps/?rtext=${geo ? `${geo[0]},${geo[1]}` : ""}~${dest[0]},${dest[1]}` : `https://yandex.kz/maps/?text=${destText}` },
  ];
  const locate = () => {
    setGeoError(false);
    if (!("geolocation" in navigator)) return setGeoError(true);
    navigator.geolocation.getCurrentPosition(
      (p) => setGeo([p.coords.latitude, p.coords.longitude]),
      () => setGeoError(true),
      { timeout: 8000 },
    );
  };
  return (
    <section className="mt-4 border-t border-line pt-4" aria-labelledby="route-h">
      <h3 id="route-h" className="font-semibold">{t("map.route")}</h3>
      <label className="mt-2 block text-sm" htmlFor="route-from">{t("map.from")}</label>
      <input id="route-from" className="input mt-1" list="places" value={from} placeholder={t("map.fromPlaceholder")} onChange={(e) => { setGeo(null); setFrom(e.target.value); }} />
      <datalist id="places">{PLACES.map((p) => <option key={p.names[0]} value={p.names[0]} />)}</datalist>
      <button type="button" className="btn-ghost mt-3 w-full" onClick={locate}>
        <Icon name="pin" size={18} /> {t("map.myLocation")}
      </button>
      <p className="mt-1 text-xs text-muted">{t("map.geoConsent")}</p>
      {geoError && <p className="mt-2 text-sm text-warn" role="alert">{t("map.geoDenied")}</p>}
      {km !== null && <p className="mt-2 text-sm font-medium" aria-live="polite">{t("map.distance", { km: km.toFixed(0) })}</p>}
      {(from || geo) && km === null && <p className="mt-2 text-sm text-muted">{t("map.distanceUnknown")}</p>}
      <p className="mt-3 text-sm">{t("map.openIn")}:</p>
      <ul className="mt-1 flex flex-wrap gap-2">
        {links.map((l) => (
          <li key={l.name}><ExternalLink href={l.url} className="btn-ghost">{l.name}</ExternalLink></li>
        ))}
      </ul>
    </section>
  );
}

// Широкий экран: подробности филиала — в боковой колонке; телефон/планшет — прямо под выбранной карточкой.
const WIDE = "(min-width: 1024px)";
const subscribeWide = (cb: () => void) => {
  const m = window.matchMedia(WIDE);
  m.addEventListener("change", cb);
  return () => m.removeEventListener("change", cb);
};
const useWide = () => useSyncExternalStore(subscribeWide, () => window.matchMedia(WIDE).matches, () => true);

export function BranchesPage() {
  const { t } = useT();
  const lang = useLang();
  useTitle(t("map.title"), t("map.lead"));
  const q = useQuery({ queryKey: ["branches", lang], queryFn: () => apiGet<Branch[]>("/branches", lang) });
  const [search, setSearch] = useState("");
  const [type, setType] = useState<"" | "main" | "branch">("");
  const [selected, setSelected] = useState<string | null>(null);
  const [tilesFailed, setTilesFailed] = useState(false);
  const list = useMemo(
    () =>
      (q.data ?? []).filter(
        (b) => (!type || b.type === type) && (!search || `${b.name} ${b.short_name} ${b.locality} ${b.address}`.toLowerCase().includes(search.toLowerCase())),
      ),
    [q.data, search, type],
  );
  const sel = list.find((b) => b.slug === selected) ?? null;
  const wide = useWide();
  const details = sel && (
    <section className="card border-2 border-primary p-4 sm:p-5" aria-labelledby="sel-h">
      <p className="text-sm text-muted">{t("map.selected")}</p>
      <h2 id="sel-h" className="text-[1.25rem]">{sel.name}</h2>
      <TranslationNotice info={sel.translation} />
      <ul className="mt-3 space-y-3">
        <li className="flex gap-2"><Icon name="pin" size={20} className="mt-1 shrink-0 text-primary" /><ExternalLink href={twoGisUrl(sel)} className="inline">{sel.address}, {sel.locality}</ExternalLink></li>
        {sel.phone && <li className="flex gap-2"><Icon name="phone" size={20} className="mt-1 shrink-0 text-primary" /><a href={`tel:${sel.phone.replace(/[^\d+]/g, "")}`}>{sel.phone}</a></li>}
        {sel.email && <li className="flex gap-2"><Icon name="mail" size={20} className="mt-1 shrink-0 text-primary" /><a href={`mailto:${sel.email}`}>{sel.email}</a></li>}
        {sel.hours && <li className="flex gap-2"><Icon name="clock" size={20} className="mt-1 shrink-0 text-primary" />{sel.hours}</li>}
        {sel.director && <li>{t("map.director")}: {sel.director}</li>}
      </ul>
      <RoutePanel key={sel.slug} b={sel} />
    </section>
  );
  return (
    <div className="container-page py-8 sm:py-10">
      <Breadcrumbs items={[{ label: t("map.title") }]} />
      <h1>{t("map.title")}</h1>
      <p className="lead mt-2">{t("map.lead")}</p>
      <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
        <label className="sr-only" htmlFor="br-q">{t("map.search")}</label>
        <input id="br-q" type="search" className="input sm:max-w-sm" placeholder={t("map.search")} value={search} onChange={(e) => setSearch(e.target.value)} />
        <div role="group" aria-label={t("catalog.fields.branch")} className="grid grid-cols-3 gap-2 sm:flex">
          {(["", "main", "branch"] as const).map((v) => (
            <button key={v || "all"} type="button" aria-pressed={type === v} className={`${type === v ? "btn-primary" : "btn-ghost"} px-3 sm:px-6`} onClick={() => setType(v)}>
              {v === "" ? t("map.all") : t(`map.${v}`)}
            </button>
          ))}
        </div>
      </div>
      {q.isLoading && <Loading />}
      {q.isError && <ErrorState error={q.error} onRetry={() => void q.refetch()} />}
      {q.data && (
        <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-[1fr_24rem]">
          <div className="space-y-3">
            <div className="h-[320px] overflow-hidden rounded-xl border border-line sm:h-[420px]" aria-label={t("map.title")}>
              <MapContainer center={[49.6, 83.2]} zoom={6} scrollWheelZoom={false} className="h-full w-full">
                <TileLayer
                  attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                  eventHandlers={{ tileerror: () => setTilesFailed(true) }}
                />
                {list.filter((b) => b.lat !== null && b.lon !== null).map((b) => (
                  <CircleMarker
                    key={b.slug}
                    center={[b.lat as number, b.lon as number]}
                    radius={b.type === "main" ? 11 : 8}
                    pathOptions={{ color: b.slug === selected ? "#b45309" : "#1a4be0", fillOpacity: 0.8 }}
                    eventHandlers={{ click: () => setSelected(b.slug) }}
                  >
                    <Tooltip>{b.short_name}</Tooltip>
                  </CircleMarker>
                ))}
                <FlyTo pos={sel && sel.lat !== null && sel.lon !== null ? [sel.lat, sel.lon] : null} />
              </MapContainer>
            </div>
            {tilesFailed && <p className="text-sm text-warn" role="status">{t("map.tilesFailed")}</p>}
            {list.length === 0 && <p>{t("map.nothing")}</p>}
            <ul className="grid gap-2 md:grid-cols-2">
              {list.map((b) => (
                <li key={b.slug} className={!wide && b.slug === selected ? "space-y-2 md:col-span-2" : undefined}>
                  <button type="button" onClick={() => setSelected(b.slug === selected ? null : b.slug)} aria-pressed={b.slug === selected} className={`card block min-h-[4.5rem] w-full p-4 text-left transition-colors hover:border-ink ${b.slug === selected ? "border-2 border-primary" : ""}`}>
                    <span className="font-semibold">{b.short_name}</span>
                    <span className="mt-1 block text-muted">{b.address}</span>
                  </button>
                  {!wide && b.slug === selected && details}
                </li>
              ))}
            </ul>
          </div>
          {wide && (
            <aside className="sticky top-4 self-start">
              {details ?? <p className="card p-4 text-muted">{t("map.search")} ↑</p>}
            </aside>
          )}
        </div>
      )}
    </div>
  );
}
