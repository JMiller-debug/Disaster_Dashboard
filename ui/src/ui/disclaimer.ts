const STORAGE_KEY = "disclaimer-acknowledged";

export function initDisclaimer(): void {
	if (localStorage.getItem(STORAGE_KEY) === "true") return;

	// ── Backdrop ──────────────────────────────────────────────────────────────
	const backdrop = document.createElement("div");
	backdrop.className = [
		"fixed inset-0 z-50",
		"bg-black/60 backdrop-blur-sm",
		"flex items-center justify-center p-4",
	].join(" ");

	// ── Modal ─────────────────────────────────────────────────────────────────
	const modal = document.createElement("div");
	modal.className = [
		"relative w-full max-w-md rounded-2xl",
		"bg-surface border border-border shadow-2xl",
		"p-6 flex flex-col gap-4",
		"text-slate-200",
	].join(" ");

	modal.innerHTML = `
		<div class="flex items-start gap-3">
			<span class="text-2xl mt-0.5" aria-hidden="true">⚠️</span>
			<div>
				<h2 class="text-base font-semibold text-accent">Disclaimer</h2>
				<p class="text-xs text-slate-500 mt-0.5">Please read before continuing</p>
			</div>
		</div>

		<div class="flex flex-col gap-3 text-sm text-slate-300 leading-relaxed border-t border-border pt-4">
			<p>
				This is a <span class="text-slate-100 font-medium">personal hobby project</span>
				built for fun and learning. It visualises publicly available data from
				sources such as USGS, NOAA, NASA FIRMS, and NHC.
			</p>
			<p>
				<span class="text-red-400 font-medium">Do not rely on this dashboard</span>
				for emergency planning, evacuation decisions, or any safety-critical
				purpose. Data may be delayed, incomplete, or inaccurate.
			</p>
			<p>
				For authoritative information please consult official sources:
				<a href="https://earthquake.usgs.gov" target="_blank" rel="noopener"
					class="text-accent hover:underline">USGS</a>,
				<a href="https://www.nhc.noaa.gov" target="_blank" rel="noopener"
					class="text-accent hover:underline">NHC</a>,
				<a href="https://www.weather.gov" target="_blank" rel="noopener"
					class="text-accent hover:underline">NWS</a>, or your
				local emergency management agency.
			</p>
		</div>

		<label class="flex items-center gap-2.5 cursor-pointer select-none text-xs text-slate-400 hover:text-slate-200 transition-colors">
			<input
				id="disclaimer-dont-show"
				type="checkbox"
				class="w-3.5 h-3.5 rounded accent-accent cursor-pointer"
			/>
			Don't show this again
		</label>

		<button
			id="disclaimer-acknowledge"
			class="w-full py-2.5 rounded-xl text-sm font-medium
				bg-accent text-white
				hover:brightness-110 active:brightness-95
				transition-all cursor-pointer"
		>
			I understand — take me to the dashboard
		</button>
	`;

	backdrop.appendChild(modal);
	document.body.appendChild(backdrop);

	// ── Focus trap ────────────────────────────────────────────────────────────
	const btn = modal.querySelector<HTMLButtonElement>(
		"#disclaimer-acknowledge",
	)!;
	btn.focus();

	// ── Dismiss ───────────────────────────────────────────────────────────────
	function dismiss() {
		const dontShow = modal.querySelector<HTMLInputElement>(
			"#disclaimer-dont-show",
		)!.checked;

		if (dontShow) {
			localStorage.setItem(STORAGE_KEY, "true");
		}

		backdrop.classList.add("opacity-0", "transition-opacity", "duration-200");
		setTimeout(() => backdrop.remove(), 200);
	}

	btn.addEventListener("click", dismiss);

	// Close on backdrop click (outside the modal card)
	backdrop.addEventListener("click", (e) => {
		if (e.target === backdrop) dismiss();
	});

	// Close on Escape
	document.addEventListener(
		"keydown",
		(e) => {
			if (e.key === "Escape") dismiss();
		},
		{ once: true },
	);
}
