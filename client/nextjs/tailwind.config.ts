import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#FAFBFF",
        surface: "#FFFFFF",
        "soft-surface": "#F6F7FB",
        border: "#E8EBF4",
        foreground: "#111827",
        "text-primary": "#111827",
        "text-secondary": "#6B7280",
        "text-muted": "#9CA3AF",
        primary: "#5B21B6",
        "primary-hover": "#4C1D95",
        "primary-light": "#EEF2FF",
        success: "#059669",
        warning: "#D97706",
        error: "#DC2626",
      },
      fontFamily: {
        sans: ["var(--font-inter)"],
        display: ["var(--font-plus-jakarta)"],
      },
    },
  },
  plugins: [],
};
export default config;
