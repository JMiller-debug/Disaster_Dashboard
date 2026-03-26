import { fromLonLat } from "ol/proj";
import {
	fetchEarthquakes,
	fetchTornadoes,
	fetchCyclones,
	fetchFires,
	type TimeWindow,
	type DataLayer,
	type DayRange,
	type EarthquakeFeature,
	type TornadoFeature,
	type StormFeature,
	type FireFeature,
} from "./api";
import {
	createMap,
	updateEarthquakes,
	updateTornadoes,
	updateCyclones,
	updateFires,
	setMode,
	type MapMode,
} from "./map";
import {
	renderList,
	renderTornadoList,
	renderCycloneList,
	renderFireList,
	initResize,
	createToggle,
	setActiveTab,
	setActiveTwTab,
	setActiveFireTab,
	setLoading,
	initRefreshBtn,
	initDisclaimer,
} from "./ui";
import { createPopup } from "./map/popup";

// ── State ──────────────────────────────────────────────────────────────────
let activeLayer: DataLayer = "earthquakes";
let timeWindow: TimeWindow = "day";
let twWindow: TimeWindow = "day";
let fireDays: DayRange = "1";
let minMag = 0;
let mapMode: MapMode = "points";

// ── Map ────────────────────────────────────────────────────────────────────
const {
	map,
	earthquakeHeatmap,
	earthquakePoints,
	tornadoLayer,
	cycloneLayer,
	fireLayer,
} = createMap("map");

const popup = createPopup(map);

// ── Pulse animation ────────────────────────────────────────────────────────
let animFrameId: number;
function animatePoints() {
	earthquakePoints.changed();
	animFrameId = requestAnimationFrame(animatePoints);
}

// ── Layer visibility ───────────────────────────────────────────────────────
function applyLayerVisibility() {
	const isEq = activeLayer === "earthquakes";
	const isTornado = activeLayer === "tornadoes";
	const isCyclone = activeLayer === "cyclones";
	const isFire = activeLayer === "fires";

	earthquakeHeatmap.setVisible(isEq && mapMode === "heatmap");
	earthquakePoints.setVisible(isEq && mapMode === "points");
	tornadoLayer.setVisible(isTornado);
	cycloneLayer.setVisible(isCyclone);
	fireLayer.setVisible(isFire);

	document.getElementById("eq-controls")!.classList.toggle("hidden", !isEq);
	document
		.getElementById("tw-controls")!
		.classList.toggle("hidden", !isTornado);
	document.getElementById("fire-controls")!.classList.toggle("hidden", !isFire);

	const toggleBtn =
		document.querySelector<HTMLButtonElement>(".map-mode-toggle");
	if (toggleBtn) toggleBtn.style.display = isEq ? "" : "none";

	if (isEq) {
		animatePoints();
	} else {
		cancelAnimationFrame(animFrameId);
	}
}

// ── Fly-to helpers ─────────────────────────────────────────────────────────
function flyToCoords(coords: [number, number], zoom = 6) {
	map.getView().animate({ center: fromLonLat(coords), zoom, duration: 600 });
}

function flyToEarthquake(feature: EarthquakeFeature) {
	const [lng, lat] = feature.geometry.coordinates;
	const dest = fromLonLat([lng, lat]);
	if (mapMode !== "points") {
		mapMode = "points";
		setMode(earthquakeHeatmap, earthquakePoints, mapMode);
	}
	map.getView().animate({ center: dest, zoom: 6, duration: 600 }, () => {
		popup.show([{ coords: dest, props: feature.properties }]);
	});
}

function flyToTornado(feature: TornadoFeature) {
	const geom = feature.geometry;
	let coords: [number, number] | null = null;
	if (geom.type === "Point") {
		const c = geom.coordinates as [number, number];
		coords = c;
	} else if (geom.type === "LineString") {
		const c = geom.coordinates as [number, number][];
		coords = c[0];
	}
	if (!coords) return;
	const dest = fromLonLat(coords);
	map.getView().animate({ center: dest, zoom: 7, duration: 600 }, () => {
		popup.showTornado(dest, feature.properties);
	});
}

function flyToCyclone(feature: StormFeature) {
	const [lng, lat] = feature.geometry.coordinates;
	const dest = fromLonLat([lng, lat]);
	map.getView().animate({ center: dest, zoom: 5, duration: 600 }, () => {
		popup.showCyclone(dest, feature.properties, feature.id);
	});
}

function flyToFire(feature: FireFeature) {
	const [lng, lat] = feature.geometry.coordinates;
	const dest = fromLonLat([lng, lat]);
	map.getView().animate({ center: dest, zoom: 8, duration: 600 }, () => {
		popup.showFire(dest, feature.properties);
	});
}

// ── Map click interaction ──────────────────────────────────────────────────
map.on("click", (e) => {
	popup.hide();

	if (activeLayer === "earthquakes" && mapMode === "points") {
		// Collect ALL features at this pixel so the picker list works for clusters
		const items: {
			coords: number[];
			props: EarthquakeFeature["properties"];
		}[] = [];
		map.forEachFeatureAtPixel(e.pixel, (feat) => {
			const props = feat.getProperties() as EarthquakeFeature["properties"];
			if (props.mag !== undefined) items.push({ coords: e.coordinate, props });
		});
		if (items.length > 0) popup.show(items);
		return;
	}

	// For all other layers just grab the first feature hit
	map.forEachFeatureAtPixel(e.pixel, (feat) => {
		const props = feat.getProperties();

		if (activeLayer === "tornadoes") {
			popup.showTornado(e.coordinate, props as TornadoFeature["properties"]);
			return true;
		}
		if (activeLayer === "cyclones") {
			popup.showCyclone(
				e.coordinate,
				props as StormFeature["properties"],
				String(feat.getId() ?? ""),
			);
			return true;
		}
		if (activeLayer === "fires") {
			popup.showFire(e.coordinate, props as FireFeature["properties"]);
			return true;
		}
	});
});

map.on("pointermove", (e) => {
	const hit = map.hasFeatureAtPixel(e.pixel);
	map.getTargetElement().style.cursor = hit ? "pointer" : "";
});

// ── Map mode toggle (earthquakes only) ────────────────────────────────────
const mapEl = document.getElementById("map")!;
createToggle(mapEl, mapMode, (next) => {
	mapMode = next;
	setMode(earthquakeHeatmap, earthquakePoints, mapMode);
	popup.hide();
	if (mapMode === "points") animatePoints();
	else cancelAnimationFrame(animFrameId);
});

// ── Layer tab switching ────────────────────────────────────────────────────
document.getElementById("layer-tabs")!.addEventListener("click", (e) => {
	const btn = (e.target as HTMLElement).closest<HTMLButtonElement>(
		".layer-tab",
	);
	if (!btn?.dataset.layer) return;
	activeLayer = btn.dataset.layer as DataLayer;

	document
		.querySelectorAll<HTMLButtonElement>(".layer-tab")
		.forEach((t) =>
			t.classList.toggle("active", t.dataset.layer === activeLayer),
		);

	// Sync time-range tab highlights to current state
	setActiveTwTab(twWindow);
	setActiveFireTab(fireDays);

	applyLayerVisibility();
	popup.hide();
	load();
});

// ── Earthquake controls ────────────────────────────────────────────────────
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

// ── Tornado time window ────────────────────────────────────────────────────
document.getElementById("tw-tabs")!.addEventListener("click", (e) => {
	const tab = (e.target as HTMLElement).closest<HTMLButtonElement>(".tw-tab");
	if (!tab?.dataset.window) return;
	twWindow = tab.dataset.window as TimeWindow;
	setActiveTwTab(twWindow);
	load();
});

// ── Fires day range ────────────────────────────────────────────────────────
document.getElementById("fire-tabs")!.addEventListener("click", (e) => {
	const tab = (e.target as HTMLElement).closest<HTMLButtonElement>(".fire-tab");
	if (!tab?.dataset.days) return;
	fireDays = tab.dataset.days as DayRange;
	setActiveFireTab(fireDays);
	load();
});

// ── Load ───────────────────────────────────────────────────────────────────
async function load() {
	try {
		setLoading(true);
		switch (activeLayer) {
			case "earthquakes": {
				const data = await fetchEarthquakes(timeWindow, minMag);
				updateEarthquakes(data);
				renderList(data.features, flyToEarthquake);
				document.getElementById("quake-count")!.textContent =
					`${data.count} earthquakes`;
				break;
			}
			case "tornadoes": {
				const data = await fetchTornadoes(twWindow);
				updateTornadoes(data);
				renderTornadoList(data.features, flyToTornado);
				document.getElementById("quake-count")!.textContent =
					`${data.count} tornado events`;
				break;
			}
			case "cyclones": {
				const data = await fetchCyclones();
				updateCyclones(data);
				renderCycloneList(data.features, flyToCyclone);
				document.getElementById("quake-count")!.textContent =
					`${data.count} active cyclones`;
				break;
			}
			case "fires": {
				const data = await fetchFires(fireDays);
				updateFires(data, map);
				renderFireList(data.features, flyToFire);
				document.getElementById("quake-count")!.textContent =
					`${data.count} fire detections`;
				break;
			}
		}
	} catch (err) {
		console.error("Failed to load data:", err);
	} finally {
		setLoading(false);
	}
}

// ── Init ───────────────────────────────────────────────────────────────────
initDisclaimer();
initResize(() => map.updateSize());
initRefreshBtn(load);
setActiveTab(timeWindow);
setActiveTwTab(twWindow); // already present ✓
setActiveFireTab(fireDays); // already present ✓

document
	.querySelector<HTMLButtonElement>('.layer-tab[data-layer="earthquakes"]')
	?.classList.add("active");
document
	.querySelector<HTMLButtonElement>('.tab[data-window="day"]')
	?.classList.add("active");
document
	.querySelector<HTMLButtonElement>('.tw-tab[data-window="day"]')
	?.classList.add("active");
document
	.querySelector<HTMLButtonElement>('.fire-tab[data-days="1"]')
	?.classList.add("active");

applyLayerVisibility();
load();
setInterval(load, 2 * 60 * 1000);
