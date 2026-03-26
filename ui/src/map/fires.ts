/**
 * Fire rendering — resolution-accurate squares with grid-based aggregation.
 *
 * Each FIRMS detection is a ground pixel of known size:
 *   VIIRS (SNPP / NOAA-20 / NOAA-21) → 375 m
 *   MODIS                             → 1 000 m
 *
 * At low zoom levels thousands of points overlap into an unreadable mass.
 * We bin detections into a geographic grid whose cell size matches the
 * current map resolution, then render one representative square per cell,
 * colour-scaled by the maximum FRP and size-scaled by detection count.
 */

// Alias the native Map before any OL imports shadow the global
const NativeMap = Map;

import Feature from "ol/Feature";
import { Polygon } from "ol/geom";
import { fromLonLat } from "ol/proj";
import Style from "ol/style/Style";
import Fill from "ol/style/Fill";
import Stroke from "ol/style/Stroke";
import Text from "ol/style/Text";
import type VectorSource from "ol/source/Vector";
import type OlMap from "ol/Map";
import type { FireFeature } from "../api";

// ── Sensor ground resolution (metres) ────────────────────────────────────────
const SENSOR_RESOLUTION: Record<string, number> = {
	VIIRS: 375,
	MODIS: 1000,
};
const DEFAULT_RESOLUTION = 375;

export function sensorResolutionM(sensor: string | null | undefined): number {
	if (!sensor) return DEFAULT_RESOLUTION;
	const key = sensor.trim().toUpperCase();
	for (const [prefix, res] of Object.entries(SENSOR_RESOLUTION)) {
		if (key.startsWith(prefix)) return res;
	}
	return DEFAULT_RESOLUTION;
}

// ── FRP colour ramp (low → high intensity) ───────────────────────────────────
function frpColor(frp: number, alpha = 1): string {
	// Low  < 50 MW  : amber
	// Mid  < 300 MW : orange
	// High ≥ 300 MW : deep red
	if (frp < 50) return `rgba(251, 191, 36, ${alpha})`; // amber-400
	if (frp < 300) return `rgba(249, 115, 22, ${alpha})`; // orange-500
	return `rgba(220, 38, 38, ${alpha})`; // red-600
}

// ── Build a ground-pixel square in EPSG:3857 ─────────────────────────────────
/**
 * Returns an OL Polygon feature that represents one FIRMS detection pixel
 * as a rectangle on the map.
 *
 * @param lon      WGS-84 longitude
 * @param lat      WGS-84 latitude
 * @param sizeM    Square side length in metres
 * @param props    Original fire properties (forwarded for popup use)
 */
export function makeFireSquare(
	lon: number,
	lat: number,
	sizeM: number,
	props: FireFeature["properties"],
): Feature<Polygon> {
	const centre = fromLonLat([lon, lat]);
	const half = sizeM / 2;
	const [cx, cy] = centre;

	const ring = [
		[cx - half, cy - half],
		[cx + half, cy - half],
		[cx + half, cy + half],
		[cx - half, cy + half],
		[cx - half, cy - half],
	];

	const feat = new Feature<Polygon>({ geometry: new Polygon([ring]) });

	// Forward all original properties so popups keep working
	feat.setProperties({ ...props, _sizeM: sizeM });
	return feat;
}

// ── Style factory for a single (possibly aggregated) square ──────────────────
export function makeFireSquareStyle(
	frp: number,
	count: number,
	sizeM: number,
	mapResolution: number, // metres per pixel on screen
): Style {
	const fill = frpColor(frp, 0.75);
	const stroke = frpColor(frp, 1);

	// Only render a count label when several detections are merged and the
	// square is large enough on screen to be readable (> ~20 px wide).
	const pixelWidth = sizeM / mapResolution;
	const showLabel = count > 1 && pixelWidth > 22;

	return new Style({
		fill: new Fill({ color: fill }),
		stroke: new Stroke({ color: stroke, width: 1 }),
		...(showLabel && {
			text: new Text({
				text: count > 99 ? "99+" : String(count),
				font: "bold 10px sans-serif",
				fill: new Fill({ color: "#fff" }),
				stroke: new Stroke({ color: "rgba(0,0,0,0.6)", width: 2 }),
			}),
		}),
	});
}

// ── Grid aggregation ─────────────────────────────────────────────────────────

interface Cell {
	lon: number;
	lat: number;
	maxFrp: number;
	count: number;
	sensor: string | null | undefined;
	// Keep one full props object for the popup
	representative: FireFeature["properties"];
}

/**
 * Bin fire detections into a grid whose cell size adapts to the map zoom.
 *
 * At high zoom (close in) the grid is fine — each cell ≈ sensor pixel size,
 * so individual detections render as accurate ground squares.
 * At low zoom the grid coarsens, merging nearby detections into one cell
 * that renders as a larger, brighter square.
 *
 * @param features     Raw fire features from the API
 * @param mapResM      Current map resolution in metres-per-pixel
 * @param targetPixels Target cell side in *screen* pixels (tune feel here)
 */
export function aggregateFireFeatures(
	features: FireFeature[],
	mapResM: number,
	targetPixels = 6,
): Cell[] {
	// Cell side in metres — at least as large as the coarsest sensor pixel,
	// but grows as you zoom out so cells never shrink below targetPixels on screen.
	const minCellM = 1000; // MODIS pixel — never aggregate finer than this
	const cellM = Math.max(minCellM, mapResM * targetPixels);

	const grid = new NativeMap<string, Cell>();

	for (const f of features) {
		const [lon, lat] = f.geometry.coordinates as [number, number];
		// Snap to grid cell centre in degrees (approximate — good enough for binning)
		const degreesPerMetre = 1 / 111_320;
		const cellDeg = cellM * degreesPerMetre;
		const cellLon = Math.round(lon / cellDeg) * cellDeg;
		const cellLat = Math.round(lat / cellDeg) * cellDeg;
		const key = `${cellLon.toFixed(5)},${cellLat.toFixed(5)}`;

		const frp = f.properties.frp ?? 0;
		const existing = grid.get(key);

		if (!existing) {
			grid.set(key, {
				lon: cellLon,
				lat: cellLat,
				maxFrp: frp,
				count: 1,
				sensor: f.properties.sensor,
				representative: f.properties,
			});
		} else {
			existing.count++;
			if (frp > existing.maxFrp) {
				existing.maxFrp = frp;
				existing.representative = f.properties;
				existing.sensor = f.properties.sensor;
			}
		}
	}

	return Array.from(grid.values());
}

// ── High-level update function called from layers.ts ─────────────────────────
/**
 * Rebuild the fire vector source from raw features.
 * Called both on initial load and whenever the map view changes resolution.
 */
export function rebuildFireFeatures(
	rawFeatures: FireFeature[],
	source: VectorSource,
	map: OlMap,
): void {
	const mapResM = map.getView().getResolution() ?? 100;
	const cells = aggregateFireFeatures(rawFeatures, mapResM);

	const olFeatures = cells.map((cell) => {
		const resM = sensorResolutionM(cell.sensor);
		// Square size: at least the sensor pixel, but grow with cell size
		// so merged detections are visually larger than singletons.
		const sizeM =
			cell.count === 1
				? resM
				: Math.max(resM, Math.sqrt(cell.count) * resM * 0.8);

		const feat = makeFireSquare(cell.lon, cell.lat, sizeM, cell.representative);

		feat.setStyle(makeFireSquareStyle(cell.maxFrp, cell.count, sizeM, mapResM));

		// Store aggregation metadata for potential tooltip use
		feat.set("_count", cell.count);
		feat.set("_maxFrp", cell.maxFrp);

		return feat;
	});

	source.clear();
	source.addFeatures(olFeatures);
}
