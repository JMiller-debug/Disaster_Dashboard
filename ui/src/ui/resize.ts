const STORAGE_KEY = "sidebar-width";
const DEFAULT_WIDTH = 280;

export function initResize(onResize?: () => void) {
	const sidebar = document.getElementById("sidebar") as HTMLElement;
	const handle = document.getElementById("resize-handle") as HTMLElement;

	// Restore persisted width
	const saved = localStorage.getItem(STORAGE_KEY);
	if (saved) sidebar.style.width = `${saved}px`;

	let startX = 0;
	let startWidth = 0;

	function onPointerMove(e: PointerEvent) {
		const delta = e.clientX - startX;
		const next = Math.min(
			Math.max(startWidth + delta, parseInt(sidebar.style.minWidth)),
			parseInt(sidebar.style.maxWidth),
		);
		sidebar.style.width = `${next}px`;
		onResize?.();
	}

	function onPointerUp(e: PointerEvent) {
		handle.releasePointerCapture(e.pointerId);
		handle.removeEventListener("pointermove", onPointerMove);
		handle.removeEventListener("pointerup", onPointerUp);
		localStorage.setItem(STORAGE_KEY, parseInt(sidebar.style.width).toString());
	}

	handle.addEventListener("pointerdown", (e) => {
		startX = e.clientX;
		startWidth = sidebar.offsetWidth;
		handle.setPointerCapture(e.pointerId);
		handle.addEventListener("pointermove", onPointerMove);
		handle.addEventListener("pointerup", onPointerUp);
	});

	// Double-click to reset
	handle.addEventListener("dblclick", () => {
		sidebar.style.width = `${DEFAULT_WIDTH}px`;
		localStorage.setItem(STORAGE_KEY, String(DEFAULT_WIDTH));
		onResize?.();
	});
}
