import Overlay from "ol/Overlay";
import type Map from "ol/Map";
import type { EarthquakeProperties } from "../api";

const ALERT_COLORS: Record<string, string> = {
	green: "text-green-400",
	yellow: "text-yellow-400",
	orange: "text-orange-400",
	red: "text-red-500",
};

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

function magColorClass(mag: number): string {
	if (mag >= 6) return "text-red-500";
	if (mag >= 4) return "text-orange-400";
	if (mag >= 2) return "text-yellow-400";
	return "text-green-400";
}

function renderMinimal(p: EarthquakeProperties): string {
	const mag = p.mag ?? 0;
	return `
    <div class="flex items-start justify-between gap-4">
      <div>
        <div class="text-2xl font-bold ${magColorClass(mag)}">${mag.toFixed(1)}</div>
        <div class="text-sm text-slate-200 mt-0.5">${p.place ?? "Unknown location"}</div>
        <div class="text-xs text-slate-500 mt-1">${formatTime(p.time)}</div>
      </div>
      <button id="popup-close" class="text-slate-500 hover:text-slate-200 transition-colors text-lg leading-none">✕</button>
    </div>
    <button id="popup-expand"
      class="mt-3 w-full text-xs text-slate-400 hover:text-accent border border-border rounded-md py-1.5 transition-colors">
      Show more
    </button>
  `;
}

function renderFull(p: EarthquakeProperties): string {
	const mag = p.mag ?? 0;
	const depth = p.depth ?? "N/A";
	const alertClass = p.alert
		? (ALERT_COLORS[p.alert] ?? "text-slate-400")
		: "text-slate-500";
	return `
    <div class="flex items-start justify-between gap-4">
      <div>
        <div class="text-2xl font-bold ${magColorClass(mag)}">${mag.toFixed(1)}</div>
        <div class="text-sm text-slate-200 mt-0.5">${p.place ?? "Unknown location"}</div>
        <div class="text-xs text-slate-500 mt-1">${formatTime(p.time)}</div>
      </div>
      <button id="popup-close" class="text-slate-500 hover:text-slate-200 transition-colors text-lg leading-none">✕</button>
    </div>
    <div class="mt-3 flex flex-col gap-1.5 text-xs text-slate-400 border-t border-border pt-3">
      <div class="flex justify-between"><span>Depth</span><span class="text-slate-200">${depth} km</span></div>
      <div class="flex justify-between"><span>Tsunami</span><span class="text-slate-200">${p.tsunami ? "⚠ Yes" : "No"}</span></div>
      <div class="flex justify-between"><span>Alert</span><span class="${alertClass}">${p.alert ?? "none"}</span></div>
      <div class="flex justify-between"><span>Significance</span><span class="text-slate-200">${p.sig}</span></div>
    </div>
    <a href="${p.url}" target="_blank" rel="noopener"
      class="mt-3 block w-full text-center text-xs text-accent hover:underline border border-border rounded-md py-1.5 transition-colors">
      View on USGS ↗
    </a>
    <button id="popup-collapse"
      class="mt-1.5 w-full text-xs text-slate-500 hover:text-slate-200 border border-border rounded-md py-1.5 transition-colors">
      Show less
    </button>
  `;
}

type PopupItem = { coords: number[]; props: EarthquakeProperties };

function renderPickerList(items: PopupItem[]): string {
	// items are pre-sorted by the caller
	return `
    <div class="flex items-center justify-between mb-2">
      <span class="text-xs text-slate-400">${items.length} earthquakes here</span>
      <button id="popup-close" class="text-slate-500 hover:text-slate-200 transition-colors text-lg leading-none">✕</button>
    </div>
    <ul class="flex flex-col gap-1">
      ${items
				.map(
					(item, i) => `
        <li data-index="${i}"
          class="flex items-center justify-between px-3 py-2 rounded-lg bg-[#0f1117] border border-border cursor-pointer hover:border-accent transition-colors">
          <span class="font-bold ${magColorClass(item.props.mag ?? 0)}">${(item.props.mag ?? 0).toFixed(1)}</span>
          <span class="text-xs text-slate-300 truncate mx-2 flex-1">${item.props.place ?? "Unknown"}</span>
          <span class="text-xs text-slate-500 shrink-0">${formatTime(item.props.time)}</span>
        </li>
      `,
				)
				.join("")}
    </ul>
  `;
}
export function createPopup(map: Map) {
	const el = document.createElement("div");
	el.className = [
		"hidden absolute z-10 w-64 rounded-xl p-4",
		"bg-surface border border-border shadow-xl",
		"text-slate-200 text-sm",
	].join(" ");

	document.getElementById("map")!.appendChild(el);

	const overlay = new Overlay({
		element: el,
		positioning: "bottom-center",
		offset: [0, -12],
		stopEvent: true,
	});
	map.addOverlay(overlay);

	function hide() {
		el.classList.add("hidden");
		overlay.setPosition(undefined);
	}

	function showSingle(coords: number[], props: EarthquakeProperties) {
		el.classList.remove("hidden");
		overlay.setPosition(coords);
		el.innerHTML = renderMinimal(props);
		bindButtons(coords, props);
	}

	function showMulti(items: PopupItem[]) {
		const safe = items
			.filter((item) => item?.props?.mag !== undefined)
			.sort((a, b) => (b.props.mag ?? 0) - (a.props.mag ?? 0));

		if (safe.length === 0) return;
		if (safe.length === 1) {
			showSingle(safe[0].coords, safe[0].props);
			return;
		}

		el.classList.remove("hidden");
		overlay.setPosition(safe[0].coords);
		el.innerHTML = renderPickerList(safe);

		el.querySelector("#popup-close")?.addEventListener("click", hide);
		el.querySelectorAll<HTMLLIElement>("li[data-index]").forEach((li) => {
			li.addEventListener("click", () => {
				const i = Number(li.dataset.index);
				showSingle(safe[i].coords, safe[i].props);
			});
		});
	}

	function show(items: PopupItem[]) {
		if (items.length === 0) return;
		if (items.length === 1) showSingle(items[0].coords, items[0].props);
		else showMulti(items);
	}

	function bindButtons(coords: number[], props: EarthquakeProperties) {
		el.querySelector("#popup-close")?.addEventListener("click", hide);
		el.querySelector("#popup-expand")?.addEventListener("click", () => {
			el.innerHTML = renderFull(props);
			overlay.setPosition(coords);
			bindButtons(coords, props);
		});
		el.querySelector("#popup-collapse")?.addEventListener("click", () => {
			el.innerHTML = renderMinimal(props);
			overlay.setPosition(coords);
			bindButtons(coords, props);
		});
	}

	return { show, hide };
}
