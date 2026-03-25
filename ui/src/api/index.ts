export type {
	TimeWindow,
	DataLayer,
	EarthquakeProperties,
	EarthquakeFeature,
	EarthquakeCollection,
	TornadoProperties,
	TornadoFeature,
	TornadoCollection,
	StormProperties,
	StormFeature,
	CycloneCollection,
	FireProperties,
	FireFeature,
	FireCollection,
} from "./types";

const base = import.meta.env.VITE_API_URL ?? "";

async function get<T>(
	path: string,
	params?: Record<string, string>,
): Promise<T> {
	const url = new URL(`${base}${path}`, window.location.href);
	if (params) {
		for (const [k, v] of Object.entries(params)) url.searchParams.set(k, v);
	}
	const res = await fetch(url.toString());
	if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
	return res.json() as Promise<T>;
}

export { get };

// ── Earthquakes ──────────────────────────────────────────────────────────────
import type { TimeWindow, EarthquakeCollection } from "./types";

export function fetchEarthquakes(
	window: TimeWindow,
	minMag: number,
): Promise<EarthquakeCollection> {
	return get("/api/earthquakes/earthquakes", {
		window,
		...(minMag > 0 && { min_mag: String(minMag) }),
	});
}

// ── Tornadoes ────────────────────────────────────────────────────────────────
import type { TornadoCollection } from "./types";

export function fetchTornadoes(window: TimeWindow): Promise<TornadoCollection> {
	return get("/api/tornadoes/tornadoes", { window });
}

// ── Cyclones ──────────────────────────────────────────────────────────────────
import type { CycloneCollection } from "./types";

export function fetchCyclones(): Promise<CycloneCollection> {
	return get("/api/cyclones/cyclones");
}

// ── Fires ────────────────────────────────────────────────────────────────────
import type { FireCollection } from "./types";

export type DayRange = "1" | "2" | "3" | "7";

export function fetchFires(days: DayRange = "1"): Promise<FireCollection> {
	return get("/api/fires/fires", { days });
}
