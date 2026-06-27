/** @type {import('tailwindcss').Config} */
// Дизайн система v2 (Фаза 0.1). Токены — единый источник правды для лендинга,
// продукт переодевается под v2 постепенно. Светлая база сохранена, добавлены
// тёмные секции, фирменный фиолет-индиго акцент и скруглённая геометрия.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "Space Grotesk",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Helvetica",
          "Arial",
          "sans-serif",
        ],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      colors: {
        // Фирменный акцент v2 (один цвет, три тона).
        accent: "#6D5EF6",
        "accent-light": "#9A8CFF",
        "accent-dark": "#4B3FD6",
        // Нейтрали.
        ink: "#0A0A0B",
        surface: "#121214",
        "surface-line": "#26262B",
        paper: "#FFFFFF",
        mist: "#F4F5F8",
        line: "#E5E5E5",
        // shadcn совместимые токены (для вставленных шаблонов). Маппятся на палитру v2.
        // Фирменный accent оставлен плоским выше, поэтому shadcn accent сюда не добавляем.
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        // muted остаётся плоским вторичным текстом v2 (#6B7280, используется лендингом),
        // а muted-foreground добавлен отдельно для вставленных shadcn шаблонов.
        muted: "#6B7280",
        "muted-foreground": "hsl(var(--muted-foreground))",
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
      },
      borderRadius: {
        // Сохраняем острые продуктовые радиусы и добавляем v2 скругления.
        none: "0",
        sm: "2px",
        DEFAULT: "2px",
        card: "22px",
        panel: "24px",
        pill: "9999px",
      },
      boxShadow: {
        soft: "0 1px 2px rgba(10,10,11,.06), 0 12px 32px rgba(10,10,11,.08)",
        lift: "0 2px 6px rgba(10,10,11,.08), 0 24px 60px rgba(10,10,11,.12)",
        glow: "0 0 0 1px rgba(109,94,246,.18), 0 24px 80px rgba(109,94,246,.30)",
      },
      maxWidth: {
        content: "1200px",
      },
      fontSize: {
        eyebrow: ["13px", { lineHeight: "1.4", letterSpacing: "0.16em" }],
        display: ["clamp(2.75rem, 6vw, 4.5rem)", { lineHeight: "1.04", letterSpacing: "-0.02em" }],
        h2: ["clamp(2rem, 4vw, 3rem)", { lineHeight: "1.1", letterSpacing: "-0.01em" }],
      },
      transitionTimingFunction: {
        out2: "cubic-bezier(.16,1,.3,1)",
      },
      keyframes: {
        drift: {
          "0%, 100%": { transform: "translate3d(0,0,0) scale(1)" },
          "50%": { transform: "translate3d(2%,-3%,0) scale(1.08)" },
        },
        marquee: {
          "0%": { transform: "translateX(0)" },
          "100%": { transform: "translateX(-50%)" },
        },
      },
      animation: {
        drift: "drift 11s ease-in-out infinite",
        marquee: "marquee 38s linear infinite",
      },
    },
  },
  plugins: [],
};
