import { fromLonLat } from "ol/proj";
import type { MapBrowserEvent } from "ol";
import type { ObjectEvent } from "ol/Object";
import {
	fetchEarthquakes,
	type EarthquakeFeature,
	type TimeWindow,
} from "./api";
import {
	createMap,
	updateSource,
	setMode,
	createPopup,
	type MapMode,
} from "./map";
import {
	renderList,
	initResize,
	createToggle,
	setActiveTab,
	setLoading,
	initRefreshBtn,
} from "./ui";

// ── State ──────────────────────────────────────────────────────────────────
let timeWindow: TimeWindow = "day";
let minMag = 0;
let mode: MapMode = "points";

// ── Map ────────────────────────────────────────────────────────────────────
const { map, source, heatmap, points } = createMap("map");
const popup = createPopup(map);

// Animate pulse rings on recent quakes by nudging the points layer each frame
let animFrameId: number;
function animatePoints() {
	points.changed();
	animFrameId = requestAnimationFrame(animatePoints);
}

// ── Click interaction ──────────────────────────────────────────────────────
map.on("click", (e) => {
	if (mode !== "points") return;
	popup.hide();

	const items: { coords: number[]; props: EarthquakeFeature["properties"] }[] =
		[];

	map.forEachFeatureAtPixel(e.pixel, (feat) => {
		const props = feat.getProperties() as EarthquakeFeature["properties"];
		if (!feat.getGeometry()) return;
		items.push({ coords: e.coordinate, props }); // use click coord, not feature coord
	});

	if (items.length > 0) popup.show(items);
});

map.on("pointermove", (e) => {
	if (mode !== "points") return;
	const hit = map.hasFeatureAtPixel(e.pixel);
	map.getTargetElement().style.cursor = hit ? "pointer" : "";
});

// ── Toggle ─────────────────────────────────────────────────────────────────
const mapEl = document.getElementById("map")!;
createToggle(mapEl, mode, (next) => {
	mode = next;
	setMode(heatmap, points, mode);
	popup.hide();

	if (mode === "points") {
		animatePoints();
	} else {
		cancelAnimationFrame(animFrameId);
	}
});

// ── Controls ───────────────────────────────────────────────────────────────
const magSlider = document.getElementById("min-mag") as HTMLInputElement;
const magValue = document.getElementById("min-mag-value") as HTMLSpanElement;
const windowTabs = document.getElementById("window-tabs") as HTMLDivElement;

magSlider.addEventListener("input", () => {
	minMag = Number(magSlider.value);
	magValue.textContent = String(minMag);
	load();
});

windowTabs.addEventListener("click", (e) => {
	const tab = (e.target as HTMLElement).closest<HTMLButtonElement>(".tab");
	if (!tab?.dataset.window) return;
	timeWindow = tab.dataset.window as TimeWindow;
	setActiveTab(timeWindow);
	load();
});

// ── Data ───────────────────────────────────────────────────────────────────
async function load() {
	try {
		setLoading(true);
		const data = await fetchEarthquakes(timeWindow, minMag);
		updateSource(source, data);
		renderList(data.features, flyTo);
	} catch (err) {
		console.error("Failed to load earthquakes:", err);
	} finally {
		setLoading(false);
	}
}

function flyTo(feature: EarthquakeFeature) {
	const [lng, lat] = feature.geometry.coordinates;
	const dest = fromLonLat([lng, lat]);

	// switch to points mode so the popup is visible
	if (mode !== "points") {
		mode = "points";
		setMode(heatmap, points, mode);
	}

	map.getView().animate({ center: dest, zoom: 6, duration: 600 }, () => {
		popup.show([{ coords: dest, props: feature.properties }]);
	});
}

// ── Init ───────────────────────────────────────────────────────────────────
initResize(() => map.updateSize());
initRefreshBtn(load);
setActiveTab(timeWindow);
setMode(heatmap, points, mode);
animatePoints();
load();
setInterval(load, 2 * 60 * 1000);
