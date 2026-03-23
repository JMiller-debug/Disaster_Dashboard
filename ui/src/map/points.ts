import Style from "ol/style/Style";
import Circle from "ol/style/Circle";
import Fill from "ol/style/Fill";
import Stroke from "ol/style/Stroke";

const RECENT_MS = 60 * 60 * 1000; // 1 hour

function magToColor(mag: number): string {
	if (mag >= 6) return "#ef4444";
	if (mag >= 4) return "#f97316";
	if (mag >= 2) return "#eab308";
	return "#22c55e";
}

function magToRadius(mag: number): number {
	// Logarithmic scale: small quakes ~4px, M6+ up to ~18px
	return 4 + Math.log1p(Math.max(mag, 0)) * 5;
}

export function makePointStyle(mag: number, time: number): Style[] {
	const color = magToColor(mag);
	const radius = magToRadius(mag);
	const isRecent = Date.now() - time < RECENT_MS;

	const styles: Style[] = [
		new Style({
			image: new Circle({
				radius,
				fill: new Fill({ color: `${color}cc` }), // slight transparency
				stroke: new Stroke({ color, width: 1.5 }),
			}),
		}),
	];

	// Pulse ring for recent earthquakes — rendered as a larger fading stroke circle
	if (isRecent) {
		const pulse = getPulseRadius(radius);
		styles.unshift(
			new Style({
				image: new Circle({
					radius: pulse,
					fill: new Fill({ color: "transparent" }),
					stroke: new Stroke({ color: `${color}55`, width: 2 }),
				}),
			}),
		);
	}

	return styles;
}

// Animates pulse radius using a sine wave keyed to wall clock
function getPulseRadius(base: number): number {
	const t = (Date.now() % 2000) / 2000; // 0–1 over 2s
	const scale = 1.4 + Math.sin(t * Math.PI * 2) * 0.4; // 1.0–1.8x
	return base * scale;
}
