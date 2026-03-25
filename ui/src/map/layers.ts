import Map from "ol/Map";
import View from "ol/View";
import TileLayer from "ol/layer/Tile";
import Heatmap from "ol/layer/Heatmap";
import VectorLayer from "ol/layer/Vector";
import VectorSource from "ol/source/Vector";
import OSM from "ol/source/OSM";
import GeoJSON from "ol/format/GeoJSON";
import { fromLonLat } from "ol/proj";
import Style from "ol/style/Style";
import Circle from "ol/style/Circle";
import Fill from "ol/style/Fill";
import Stroke from "ol/style/Stroke";
import type {
	EarthquakeCollection,
	TornadoCollection,
	CycloneCollection,
	FireCollection,
} from "../api";
import { makePointStyle } from "./points";

export type MapMode = "heatmap" | "points";

const geojsonFormat = new GeoJSON({ featureProjection: "EPSG:3857" });

// ── Layer sources ─────────────────────────────────────────────────────────────
const sources: Record<string, VectorSource> = {
	earthquakes: new VectorSource(),
	tornadoes: new VectorSource(),
	cyclones: new VectorSource(),
	fires: new VectorSource(),
};

// ── Tornado style ─────────────────────────────────────────────────────────────
function makeTornadoStyle(type: string): Style {
	const color =
		type === "warning" ? "#ef4444" : type === "watch" ? "#f97316" : "#a78bfa";
	return new Style({
		image: new Circle({
			radius: 6,
			fill: new Fill({ color: `${color}cc` }),
			stroke: new Stroke({ color, width: 1.5 }),
		}),
	});
}

// ── Cyclone style ─────────────────────────────────────────────────────────────
function makeCycloneStyle(intensity: number | null): Style {
	const kt = intensity ?? 0;
	const color = kt >= 96 ? "#ef4444" : kt >= 64 ? "#f97316" : "#eab308";
	const radius = 6 + Math.min(kt / 20, 8);
	return new Style({
		image: new Circle({
			radius,
			fill: new Fill({ color: `${color}99` }),
			stroke: new Stroke({ color, width: 2 }),
		}),
	});
}

// ── Fire style ────────────────────────────────────────────────────────────────
function makeFireStyle(frp: number | null): Style {
	const power = frp ?? 0;
	const radius = 3 + Math.min(Math.log1p(power) * 1.5, 10);
	return new Style({
		image: new Circle({
			radius,
			fill: new Fill({ color: "#f9731699" }),
			stroke: new Stroke({ color: "#ef4444", width: 1 }),
		}),
	});
}

export function createMap(target: string) {
	const earthquakeHeatmap = new Heatmap({
		source: sources.earthquakes,
		blur: 24,
		radius: 16,
		weight: (f) => Math.min((f.get("mag") ?? 0) / 9, 1),
		visible: false,
	});

	const earthquakePoints = new VectorLayer({
		source: sources.earthquakes,
		style: (f) => makePointStyle(f.get("mag") ?? 0, f.get("time") ?? 0),
		visible: true,
	});

	const tornadoLayer = new VectorLayer({
		source: sources.tornadoes,
		style: (f) => makeTornadoStyle(f.get("type") ?? ""),
		visible: false,
	});

	const cycloneLayer = new VectorLayer({
		source: sources.cyclones,
		style: (f) => makeCycloneStyle(f.get("intensity")),
		visible: false,
	});

	const fireLayer = new VectorLayer({
		source: sources.fires,
		style: (f) => makeFireStyle(f.get("frp")),
		visible: false,
	});

	const map = new Map({
		target,
		layers: [
			new TileLayer({ source: new OSM() }),
			earthquakeHeatmap,
			earthquakePoints,
			tornadoLayer,
			cycloneLayer,
			fireLayer,
		],
		view: new View({ center: fromLonLat([0, 20]), zoom: 2 }),
	});

	return {
		map,
		sources,
		earthquakeHeatmap,
		earthquakePoints,
		tornadoLayer,
		cycloneLayer,
		fireLayer,
	};
}

export function updateEarthquakes(data: EarthquakeCollection) {
	sources.earthquakes.clear();
	sources.earthquakes.addFeatures(geojsonFormat.readFeatures(data));
}

export function updateTornadoes(data: TornadoCollection) {
	sources.tornadoes.clear();
	// Normalize: ensure each feature has geometry (skip nulls)
	const valid = { ...data, features: data.features.filter((f) => f.geometry) };
	sources.tornadoes.addFeatures(geojsonFormat.readFeatures(valid));
}

export function updateCyclones(data: CycloneCollection) {
	sources.cyclones.clear();
	sources.cyclones.addFeatures(geojsonFormat.readFeatures(data));
}

export function updateFires(data: FireCollection) {
	sources.fires.clear();
	sources.fires.addFeatures(geojsonFormat.readFeatures(data));
}

export function setMode(
	earthquakeHeatmap: Heatmap,
	earthquakePoints: VectorLayer,
	mode: MapMode,
) {
	earthquakeHeatmap.setVisible(mode === "heatmap");
	earthquakePoints.setVisible(mode === "points");
}
