import type {
	EarthquakeFeature,
	TornadoFeature,
	StormFeature,
	FireFeature,
} from "../api";

const listEl = document.getElementById("quake-list") as HTMLUListElement;
const tabEls = document.querySelectorAll<HTMLButtonElement>(".tab");

export function setActiveTab(window: string) {
	tabEls.forEach((t) =>
		t.classList.toggle("active", t.dataset.window === window),
	);
}

export function setActiveTwTab(window: string) {
	document
		.querySelectorAll<HTMLButtonElement>(".tw-tab")
		.forEach((t) => t.classList.toggle("active", t.dataset.window === window));
}

export function setActiveFireTab(days: string) {
	document
		.querySelectorAll<HTMLButtonElement>(".fire-tab")
		.forEach((t) => t.classList.toggle("active", t.dataset.days === days));
}

function relTime(isoOrMs: string | number): string {
	const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
	const ms = typeof isoOrMs === "number" ? isoOrMs : Date.parse(isoOrMs);
	const diffMs = ms - Date.now();
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

function li(inner: string, onClick?: () => void): HTMLLIElement {
	const el = document.createElement("li");
	el.className =
		"p-3 bg-[#0f1117] border border-border rounded-lg transition-colors" +
		(onClick ? " cursor-pointer hover:border-accent" : "");
	el.innerHTML = inner;
	if (onClick) el.addEventListener("click", onClick);
	return el;
}

// ── Earthquakes ──────────────────────────────────────────────────────────────
export function renderList(
	features: EarthquakeFeature[],
	onSelect: (f: EarthquakeFeature) => void,
) {
	const sorted = [...features].sort(
		(a, b) => (b.properties.mag ?? 0) - (a.properties.mag ?? 0),
	);
	listEl.innerHTML = "";
	for (const f of sorted.slice(0, 50)) {
		const { mag, place, time } = f.properties;
		listEl.appendChild(
			li(
				`<div class="text-base font-bold ${magColor(mag ?? 0)}">${mag?.toFixed(1) ?? "?"}</div>
         <div class="text-sm text-slate-200 truncate mt-0.5">${place ?? "Unknown location"}</div>
         <div class="text-xs text-slate-500 mt-1">${relTime(time)}</div>`,
				() => onSelect(f),
			),
		);
	}
}

// ── Tornadoes ────────────────────────────────────────────────────────────────
export function renderTornadoList(
	features: TornadoFeature[],
	onSelect: (f: TornadoFeature) => void,
) {
	listEl.innerHTML = "";
	for (const f of features.slice(0, 50)) {
		const { type, headline, severity, issued } = f.properties;
		const color =
			type === "warning"
				? "text-red-500"
				: type === "watch"
					? "text-orange-400"
					: "text-purple-400";

		// Only attach click if geometry is a selectable point-like type
		const geomType = f.geometry?.type;
		const clickable =
			geomType === "Point" ||
			geomType === "LineString" ||
			geomType === "Polygon";

		listEl.appendChild(
			li(
				`<div class="text-xs font-bold uppercase ${color}">${type}</div>
         <div class="text-sm text-slate-200 truncate mt-0.5">${headline ?? "Tornado event"}</div>
         <div class="text-xs text-slate-500 mt-1">${severity ?? ""} · ${issued ? relTime(issued) : ""}`,
				clickable ? () => onSelect(f) : undefined,
			),
		);
	}
}

// ── Cyclones ──────────────────────────────────────────────────────────────────
export function renderCycloneList(
	features: StormFeature[],
	onSelect: (f: StormFeature) => void,
) {
	listEl.innerHTML = "";
	if (features.length === 0) {
		const empty = document.createElement("li");
		empty.className = "text-xs text-slate-500 text-center py-4";
		empty.textContent = "No active cyclones";
		listEl.appendChild(empty);
		return;
	}
	for (const f of features) {
		const { name, classification, basin, intensity, timestamp } = f.properties;
		const color =
			(intensity ?? 0) >= 96
				? "text-red-500"
				: (intensity ?? 0) >= 64
					? "text-orange-400"
					: "text-yellow-400";
		listEl.appendChild(
			li(
				`<div class="text-sm font-bold ${color}">${classification ?? "TC"} ${name ?? f.id}</div>
         <div class="text-xs text-slate-400 mt-0.5">${basin ?? ""} · ${intensity ? `${intensity} kt` : ""}</div>
         <div class="text-xs text-slate-500 mt-1">${timestamp ? relTime(timestamp) : ""}`,
				() => onSelect(f),
			),
		);
	}
}

// ── Fires ─────────────────────────────────────────────────────────────────────
export function renderFireList(
	features: FireFeature[],
	onSelect: (f: FireFeature) => void,
) {
	listEl.innerHTML = "";
	// Sort by FRP descending (most intense fires first)
	const sorted = [...features].sort(
		(a, b) => (b.properties.frp ?? 0) - (a.properties.frp ?? 0),
	);
	for (const f of sorted.slice(0, 50)) {
		const { frp, confidence, acquired, satellite, day_night } = f.properties;
		listEl.appendChild(
			li(
				`<div class="text-sm font-bold text-orange-400">${frp ? `${frp.toFixed(0)} MW` : "Fire"}</div>
         <div class="text-xs text-slate-400 mt-0.5">${satellite ?? ""} · ${confidence ?? ""} confidence · ${day_night === "D" ? "☀ Day" : "🌙 Night"}</div>
         <div class="text-xs text-slate-500 mt-1">${acquired ? relTime(acquired) : ""}`,
				() => onSelect(f),
			),
		);
	}
}
