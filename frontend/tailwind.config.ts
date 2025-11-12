import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        "background-soft": "var(--background-soft)",
        "background-muted": "var(--background-muted)",
        foreground: "var(--foreground)",
        "foreground-muted": "var(--foreground-muted)",
        "foreground-subtle": "var(--foreground-subtle)",
        text: {
          primary: "var(--text-primary)",
          muted: "var(--text-muted)",
          subtle: "var(--text-subtle)",
        },
        accent: {
          cyan: "#3dd9ff",
          "cyan-hover": "#4de5ff",
          lime: "#a6f573",
          green: "#6ef5b8",
          purple: "#8b6eff",
          "purple-hover": "#9d7fff",
          yellow: "#ffd43b",
          pink: "#ff75e0",
          info: "#5b9fff",
        },
        brand: {
          primary: "var(--accent-primary)",
          "primary-hover": "var(--accent-primary-hover)",
          secondary: "var(--accent-secondary)",
          "secondary-hover": "var(--accent-secondary-hover)",
          tertiary: "var(--accent-tertiary)",
        },
        surface: {
          DEFAULT: "var(--surface)",
          hover: "var(--surface-hover)",
          elevated: "var(--surface-elevated)",
          outline: "var(--surface-outline)",
          "outline-strong": "var(--surface-outline-strong)",
          "outline-focus": "var(--surface-outline-focus)",
        },
        danger: {
          DEFAULT: "var(--accent-danger)",
          bg: "var(--danger-bg)",
          border: "var(--danger-border)",
        },
        success: {
          DEFAULT: "var(--accent-success)",
          bg: "var(--success-bg)",
          border: "var(--success-border)",
        },
        warning: {
          DEFAULT: "var(--accent-warning)",
          bg: "var(--warning-bg)",
          border: "var(--warning-border)",
        },
        info: {
          DEFAULT: "var(--accent-info)",
          bg: "var(--info-bg)",
          border: "var(--info-border)",
        },
      },
      fontFamily: {
        sans: ['"Inter"', '"SF Pro Display"', "system-ui", "-apple-system", "sans-serif"],
        mono: ['"JetBrains Mono"', '"SF Mono"', "Menlo", "Monaco", "monospace"],
        serif: ["Instrument Serif", "serif"],
      },
      spacing: {
        "18": "4.5rem",
        "88": "22rem",
        "100": "25rem",
        "112": "28rem",
        "128": "32rem",
      },
      backdropBlur: {
        glass: "14px",
        "glass-sm": "14px",
        "glass-md": "20px",
        "glass-lg": "32px",
      },
      backgroundColor: {
        glass: "rgba(18, 18, 18, 0.82)",
        "glass-hover": "rgba(26, 26, 26, 0.9)",
        "glass-elevated": "rgba(26, 26, 26, 0.95)",
        "glass-assistant": "rgba(255, 255, 255, 0.04)",
        "glass-user": "rgba(255, 255, 255, 0.02)",
      },
      borderColor: {
        glass: "rgba(255, 255, 255, 0.1)",
        "glass-strong": "rgba(255, 255, 255, 0.2)",
        "glass-focus": "rgba(99, 102, 241, 0.5)",
      },
      boxShadow: {
        soft: "0 4px 6px -1px rgba(0, 0, 0, 0.3)",
        medium: "0 10px 15px -3px rgba(0, 0, 0, 0.35)",
        elevated: "0 20px 60px rgba(0, 0, 0, 0.35)",
        floating: "0 10px 15px -3px rgba(0, 0, 0, 0.35)",
        "inset-top": "inset 0 1px 0 rgba(255,255,255,0.1)",
        "inset-border": "inset 0 0 0 1px rgba(255,255,255,0.05)",
        "glow-primary": "0 0 20px rgba(99, 102, 241, 0.3)",
        "glow-secondary": "0 0 20px rgba(61, 217, 255, 0.3)",
      },
      borderRadius: {
        card: "1rem",
        "card-lg": "1.5rem",
      },
      backgroundImage: {
        "glow-primary":
          "radial-gradient(circle at 0% 0%, rgba(124, 92, 255, 0.35), transparent 55%), radial-gradient(circle at 100% 0%, rgba(56, 214, 255, 0.35), transparent 52%)",
      },
      transitionTimingFunction: {
        "out-expo": "cubic-bezier(0.19, 1, 0.22, 1)",
        "smooth": "cubic-bezier(0.4, 0, 0.2, 1)",
        "bounce-soft": "cubic-bezier(0.68, -0.55, 0.265, 1.55)",
      },
      animation: {
        "fade-in": "fadeIn 0.15s cubic-bezier(0.25, 0.1, 0.25, 1)",
        "slide-up": "slideUp 0.2s cubic-bezier(0.25, 0.1, 0.25, 1)",
        "slide-down": "slideDown 0.2s cubic-bezier(0.25, 0.1, 0.25, 1)",
        "scale-in": "scaleIn 0.15s cubic-bezier(0.25, 0.1, 0.25, 1)",
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "glow": "glow 2s ease-in-out infinite alternate",
        "gradient-shift": "gradientShift 8s ease infinite",
        shimmer: "shimmer 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "bounce-dots": "bounceDots 1.4s cubic-bezier(0.68, -0.55, 0.265, 1.55) infinite",
        "caret-blink": "caretBlink 1s step-end infinite",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideUp: {
          "0%": { transform: "translateY(4px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
        slideDown: {
          "0%": { transform: "translateY(-20px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
        scaleIn: {
          "0%": { transform: "scale(0.95)", opacity: "0" },
          "100%": { transform: "scale(1)", opacity: "1" },
        },
        glow: {
          "0%": { boxShadow: "0 0 10px rgba(139, 110, 255, 0.3)" },
          "100%": { boxShadow: "0 0 20px rgba(139, 110, 255, 0.5)" },
        },
        gradientShift: {
          "0%, 100%": { backgroundPosition: "0% 50%" },
          "50%": { backgroundPosition: "100% 50%" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        bounceDots: {
          "0%, 80%, 100%": { transform: "scale(0)", opacity: "0.5" },
          "40%": { transform: "scale(1)", opacity: "1" },
        },
        caretBlink: {
          "0%, 50%": { opacity: "1" },
          "51%, 100%": { opacity: "0" },
        },
      },
    },
  },
  plugins: [],
};
export default config;
