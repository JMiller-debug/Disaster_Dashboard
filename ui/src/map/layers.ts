import Map from "ol/Map";
import View from "ol/View";
import TileLayer from "ol/layer/Tile";
import Heatmap from "ol/layer/Heatmap";
import VectorLayer from "ol/layer/Vector";
import VectorSource from "ol/source/Vector";
import OSM from "ol/source/OSM";
import GeoJSON from "ol/format/GeoJSON";
import { fromLonLat } from "ol/proj";
import type { EarthquakeCollection } from "../api";
import { makePointStyle } from "./points";

export type MapMode = "heatmap" | "points";

const geojsonFormat = new GeoJSON({ featureProjection: "EPSG:3857" });

export function createMap(target: string) {
	const source = new VectorSource();

	const heatmap = new Heatmap({
		source,
		blur: 24,
		radius: 16,
		weight: (f) => Math.min((f.get("mag") ?? 0) / 9, 1),
	});

	const points = new VectorLayer({
		source,
		style: (f) => makePointStyle(f.get("mag") ?? 0, f.get("time") ?? 0),
		visible: false,
	});

	const map = new Map({
		target,
		layers: [new TileLayer({ source: new OSM() }), heatmap, points],
		view: new View({ center: fromLonLat([0, 20]), zoom: 2 }),
	});

	return { map, source, heatmap, points };
}

export function updateSource(
	source: VectorSource,
	collection: EarthquakeCollection,
) {
	source.clear();
	source.addFeatures(geojsonFormat.readFeatures(collection));
}

export function setMode(heatmap: Heatmap, points: VectorLayer, mode: MapMode) {
	heatmap.setVisible(mode === "heatmap");
	points.setVisible(mode === "points");
}
