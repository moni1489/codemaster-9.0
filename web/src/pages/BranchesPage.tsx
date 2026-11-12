import "leaflet/dist/leaflet.css";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
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
    { name: "2GIS", url: dest ? `https://2gis.kz/directions/points/%7C${dest[1]}%2C${dest[0]}` : `https://2gis.kz/search/${destText}` },
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
      <button type="button" className="btn-ghost mt-2 text-xs" onClick={locate}>
        <Icon name="pin" size={14} /> {t("map.myLocation")}
      </button>
      <p className="mt-1 text-xs text-muted">{t("map.geoConsent")}</p>
      {geoError && <p className="mt-2 text-sm text-warn" role="alert">{t("map.geoDenied")}</p>}
      {km !== null && <p className="mt-2 text-sm font-medium" aria-live="polite">{t("map.distance", { km: km.toFixed(0) })}</p>}
      {(from || geo) && km === null && <p className="mt-2 text-sm text-muted">{t("map.distanceUnknown")}</p>}
      <p className="mt-3 text-sm">{t("map.openIn")}:</p>
      <ul className="mt-1 flex flex-wrap gap-2">
        {links.map((l) => (
          <li key={l.name}><ExternalLink href={l.url} className="btn-ghost text-sm">{l.name}</ExternalLink></li>
        ))}
      </ul>
    </section>
  );
}

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
  return (
    <div className="container-page py-6">
      <Breadcrumbs items={[{ label: t("map.title") }]} />
      <h1 className="text-3xl">{t("map.title")}</h1>
      <p className="mt-1 text-muted">{t("map.lead")}</p>
      <div className="mt-4 flex flex-wrap gap-2">
        <label className="sr-only" htmlFor="br-q">{t("map.search")}</label>
        <input id="br-q" type="search" className="input max-w-sm" placeholder={t("map.search")} value={search} onChange={(e) => setSearch(e.target.value)} />
        <div role="group" aria-label={t("catalog.fields.branch")} className="flex gap-1">
          {(["", "main", "branch"] as const).map((v) => (
            <button key={v || "all"} type="button" aria-pressed={type === v} className={type === v ? "btn-primary" : "btn-ghost"} onClick={() => setType(v)}>
              {v === "" ? t("map.all") : t(`map.${v}`)}
            </button>
          ))}
        </div>
      </div>
      {q.isLoading && <Loading />}
      {q.isError && <ErrorState error={q.error} onRetry={() => void q.refetch()} />}
      {q.data && (
        <div className="mt-4 grid gap-6 lg:grid-cols-[1fr_24rem]">
          <div className="space-y-3">
            <div className="h-[420px] overflow-hidden rounded-xl border border-line" aria-label={t("map.title")}>
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
                    pathOptions={{ color: b.slug === selected ? "#965014" : "#0e4c5c", fillOpacity: 0.8, dashArray: b.coords_verified ? undefined : "4" }}
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
                <li key={b.slug}>
                  <button type="button" onClick={() => setSelected(b.slug)} aria-pressed={b.slug === selected} className={`card block w-full p-3 text-left ${b.slug === selected ? "border-primary" : ""}`}>
                    <span className="font-medium">{b.short_name}</span>
                    <span className="block text-sm text-muted">{b.address}</span>
                    {b.lat === null && <span className="block text-xs text-warn">{t("map.noCoords")}</span>}
                  </button>
                </li>
              ))}
            </ul>
          </div>
          <aside className="lg:sticky lg:top-4 lg:self-start">
            {sel ? (
              <section className="card p-4" aria-labelledby="sel-h">
                <p className="text-xs uppercase text-muted">{t("map.selected")}</p>
                <h2 id="sel-h" className="text-xl">{sel.name}</h2>
                {!sel.coords_verified && <p className="badge mt-2 border-warn/60 text-warn">⚠ {t("map.unverified")}</p>}
                <TranslationNotice info={sel.translation} />
                <ul className="mt-3 space-y-2 text-sm">
                  <li className="flex gap-2"><Icon name="pin" size={16} className="mt-0.5 shrink-0" />{sel.address}, {sel.locality}</li>
                  {sel.phone && <li className="flex gap-2"><Icon name="phone" size={16} className="mt-0.5 shrink-0" /><a href={`tel:${sel.phone.replace(/[^\d+]/g, "")}`}>{sel.phone}</a></li>}
                  {sel.email && <li className="flex gap-2"><Icon name="mail" size={16} className="mt-0.5 shrink-0" /><a href={`mailto:${sel.email}`}>{sel.email}</a></li>}
                  {sel.hours && <li className="flex gap-2"><Icon name="clock" size={16} className="mt-0.5 shrink-0" />{sel.hours}</li>}
                  {sel.director && <li>{t("map.director")}: {sel.director}</li>}
                  {sel.lat !== null && <li className="text-xs text-muted">{sel.lat.toFixed(3)}, {sel.lon?.toFixed(3)}</li>}
                </ul>
                <RoutePanel key={sel.slug} b={sel} />
              </section>
            ) : (
              <p className="card p-4 text-sm text-muted">{t("map.search")} ↑</p>
            )}
          </aside>
        </div>
      )}
    </div>
  );
}
