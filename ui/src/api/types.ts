// ── Shared ─────────────────────────────────────────────────────────────────
export type TimeWindow = "hour" | "day" | "week" | "month";
export type DataLayer = "earthquakes" | "tornadoes" | "cyclones" | "fires";

// ── Earthquakes ─────────────────────────────────────────────────────────────
export interface EarthquakeProperties {
	mag: number | null;
	place: string | null;
	time: number;
	updated: number;
	url: string;
	title: string;
	alert: string | null;
	tsunami: number;
	sig: number;
	depth?: number;
}

export interface EarthquakeFeature {
	type: "Feature";
	id: string;
	properties: EarthquakeProperties;
	geometry: { type: "Point"; coordinates: [number, number, number] };
}

export interface EarthquakeCollection {
	type: "FeatureCollection";
	features: EarthquakeFeature[];
	count: number;
}

// ── Tornadoes ───────────────────────────────────────────────────────────────
export interface TornadoProperties {
	event: string | null;
	severity: string | null;
	certainty: string | null;
	urgency: string | null;
	headline: string | null;
	issued: string | null;
	expires: string | null;
	status: string | null;
	type: "watch" | "warning" | "confirmed";
	mag: number | null;
	injuries: number | null;
	fatalities: number | null;
	state: string | null;
	length_mi: number | null;
	width_yd: number | null;
}

export interface TornadoFeature {
	type: "Feature";
	id: string;
	properties: TornadoProperties;
	geometry: { type: string; coordinates: unknown };
}

export interface TornadoCollection {
	type: "FeatureCollection";
	features: TornadoFeature[];
	count: number;
	source: string;
	window: TimeWindow;
}

// ── Cyclones ─────────────────────────────────────────────────────────────────
export interface StormProperties {
	name: string | null;
	basin: string | null;
	classification: string | null;
	intensity: number | null;
	pressure: number | null;
	timestamp: string | null;
	source: string | null;
}

export interface StormFeature {
	type: "Feature";
	id: string;
	properties: StormProperties;
	geometry: { type: "Point"; coordinates: [number, number] };
}

export interface CycloneCollection {
	type: "FeatureCollection";
	features: StormFeature[];
	count: number;
}

// ── Fires ────────────────────────────────────────────────────────────────────
export interface FireProperties {
	brightness: number | null;
	frp: number | null;
	confidence: string | null;
	acquired: string | null;
	sensor: string | null;
	satellite: string | null;
	day_night: string | null;
}

export interface FireFeature {
	type: "Feature";
	id: string;
	properties: FireProperties;
	geometry: { type: "Point"; coordinates: [number, number] };
}

export interface FireCollection {
	type: "FeatureCollection";
	features: FireFeature[];
	count: number;
	sensor: string;
	days: string;
}
