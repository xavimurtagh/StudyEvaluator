import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0c0a09",
        paper: "#fafaf9",
        muted: "#78716c",
        line: "#e7e5e4",
        accent: "#2563eb",
        strong: "#15803d",
        moderate: "#65a30d",
        weak: "#ca8a04",
        insufficient: "#78716c",
        contradicted: "#dc2626",
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Inter",
          "Helvetica",
          "Arial",
          "sans-serif",
        ],
        serif: ["Georgia", "Cambria", "Times", "serif"],
      },
    },
  },
  plugins: [],
};
export default config;
