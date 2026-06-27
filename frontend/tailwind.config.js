/** @type {import('tailwindcss').Config} */
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
      },
      colors: {
        accent: "#1F4BFF",
        ink: "#0A0A0A",
        line: "#E5E5E5",
      },
      borderRadius: {
        none: "0",
        sm: "2px",
        DEFAULT: "2px",
      },
    },
  },
  plugins: [],
};
