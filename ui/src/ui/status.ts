const statusEl = document.getElementById("refresh-status") as HTMLSpanElement;
const iconEl = document.getElementById("refresh-icon") as HTMLSpanElement;
const refreshBtn = document.getElementById("refresh-btn") as HTMLButtonElement;

let lastRefreshed: Date | null = null;
let tickInterval: ReturnType<typeof setInterval> | null = null;

function formatAgo(date: Date): string {
	const diffMs = Date.now() - date.getTime();
	const diffMins = Math.floor(diffMs / 60_000);
	if (diffMins < 1) return "just now";
	if (diffMins < 60) return `${diffMins}m ago`;
	const diffHours = Math.floor(diffMins / 60);
	if (diffHours < 24) return `${diffHours}h ago`;
	return `${Math.floor(diffHours / 24)}d ago`;
}

function tick() {
	if (!lastRefreshed) return;
	statusEl.textContent = `Refreshed ${formatAgo(lastRefreshed)}`;
}

export function setLoading(loading: boolean) {
	iconEl.style.display = loading ? "none" : "";
	refreshBtn.disabled = loading;

	if (loading) {
		// Insert spinner if not already present
		if (!document.getElementById("refresh-spinner")) {
			const spinner = document.createElement("span");
			spinner.id = "refresh-spinner";
			spinner.className =
				"inline-block w-3 h-3 border-2 border-slate-600 border-t-accent rounded-full animate-spin";
			iconEl.insertAdjacentElement("afterend", spinner);
		}
		statusEl.textContent = "Refreshing…";
	} else {
		document.getElementById("refresh-spinner")?.remove();
		lastRefreshed = new Date();
		tick();

		// Update the "x mins ago" text every 30s
		if (tickInterval) clearInterval(tickInterval);
		tickInterval = setInterval(tick, 30_000);
	}
}

export function initRefreshBtn(onRefresh: () => void) {
	refreshBtn.addEventListener("click", onRefresh);
}
