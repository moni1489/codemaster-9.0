import "leaflet/dist/leaflet.css";
import { CircleMarker, MapContainer, TileLayer, Tooltip } from "react-leaflet";
import type { Branch } from "../lib/types";

/** Мини-карта филиалов для главной (отдельный чанк). */
export default function MiniMap({ branches }: { branches: Branch[] }) {
  return (
    <MapContainer center={[49.4, 83.4]} zoom={5} scrollWheelZoom={false} dragging={false} zoomControl={false} className="h-40 w-full rounded-lg">
      <TileLayer attribution="&copy; OpenStreetMap" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      {branches.filter((b) => b.lat !== null && b.lon !== null).map((b) => (
        <CircleMarker key={b.slug} center={[b.lat as number, b.lon as number]} radius={b.type === "main" ? 7 : 5} pathOptions={{ color: "#0e4c5c", fillOpacity: 0.8 }}>
          <Tooltip>{b.short_name}</Tooltip>
        </CircleMarker>
      ))}
    </MapContainer>
  );
}
