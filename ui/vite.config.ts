import { defineConfig } from "vite";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
	plugins: [tailwindcss()],
	server: {
		proxy: {
			"/api": process.env.VITE_API_PROXY ?? "http://localhost:8000",
		},
	},
});
