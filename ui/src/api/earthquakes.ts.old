export type TimeWindow = "hour" | "day" | "week" | "month";

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
	geometry: {
		type: "Point";
		coordinates: [number, number, number]; // [lng, lat, depth]
	};
}

export interface EarthquakeCollection {
	type: "FeatureCollection";
	features: EarthquakeFeature[];
	count: number;
}

const base = import.meta.env.VITE_API_URL ?? "";

export async function fetchEarthquakes(
	window: TimeWindow,
	minMag: number,
): Promise<EarthquakeCollection> {
	const params = new URLSearchParams({
		window,
		...(minMag > 0 && { min_mag: String(minMag) }),
	});
	const res = await fetch(`${base}/api/earthquakes?${params}`);
	if (!res.ok) throw new Error(`API error ${res.status}`);
	return res.json();
}
