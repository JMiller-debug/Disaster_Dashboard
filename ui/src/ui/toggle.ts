import type { MapMode } from "../map";

const LABELS: Record<MapMode, string> = {
	heatmap: "🌡 Heatmap",
	points: "● Points",
};

export function createToggle(
	mapEl: HTMLElement,
	initial: MapMode,
	onChange: (mode: MapMode) => void,
) {
	const btn = document.createElement("button");
	btn.className = [
		"absolute bottom-6 right-6 z-10",
		"px-4 py-2 rounded-xl text-sm font-medium",
		"bg-surface border border-border text-slate-200",
		"hover:border-accent hover:text-accent",
		"shadow-lg transition-colors cursor-pointer",
	].join(" ");

	let current: MapMode = initial;
	btn.textContent = LABELS[current];

	btn.addEventListener("click", () => {
		current = current === "heatmap" ? "points" : "heatmap";
		btn.textContent = LABELS[current];
		onChange(current);
	});

	mapEl.style.position = "relative";
	mapEl.appendChild(btn);

	return btn;
}
