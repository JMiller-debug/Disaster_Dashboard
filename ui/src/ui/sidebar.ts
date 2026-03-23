import type { EarthquakeFeature } from "../api";

const listEl = document.getElementById("quake-list") as HTMLUListElement;
const countEl = document.getElementById("quake-count") as HTMLParagraphElement;
const tabEls = document.querySelectorAll<HTMLButtonElement>(".tab");

export function setActiveTab(window: string) {
	tabEls.forEach((t) =>
		t.classList.toggle("active", t.dataset.window === window),
	);
}

function formatTime(epochMs: number): string {
	const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
	const diffMs = epochMs - Date.now();
	const diffMins = Math.round(diffMs / 60_000);
	const diffHours = Math.round(diffMs / 3_600_000);
	const diffDays = Math.round(diffMs / 86_400_000);

	if (Math.abs(diffMins) < 60) return rtf.format(diffMins, "minute");
	if (Math.abs(diffHours) < 24) return rtf.format(diffHours, "hour");
	return rtf.format(diffDays, "day");
}

function magColor(mag: number): string {
	if (mag >= 6) return "text-red-500";
	if (mag >= 4) return "text-orange-400";
	if (mag >= 2) return "text-yellow-400";
	return "text-green-400";
}

export function renderList(
	features: EarthquakeFeature[],
	onSelect: (f: EarthquakeFeature) => void,
) {
	const sorted = [...features].sort(
		(a, b) => (b.properties.mag ?? 0) - (a.properties.mag ?? 0),
	);

	countEl.textContent = `${sorted.length} earthquakes`;
	listEl.innerHTML = "";

	for (const f of sorted.slice(0, 50)) {
		const { mag, place, time } = f.properties;
		const li = document.createElement("li");
		li.className =
			"p-3 bg-[#0f1117] border border-border rounded-lg cursor-pointer hover:border-accent transition-colors";
		li.innerHTML = `
      <div class="text-base font-bold ${magColor(mag ?? 0)}">${mag?.toFixed(1) ?? "?"}</div>
      <div class="text-sm text-slate-200 truncate mt-0.5">${place ?? "Unknown location"}</div>
      <div class="text-xs text-slate-500 mt-1">${formatTime(time)}</div>
    `;
		li.addEventListener("click", () => onSelect(f));
		listEl.appendChild(li);
	}
}
