/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./frontend/templates/**/*.html"],
  theme: {
    extend: {
      colors: {
        pulse: {
          navy: "#0f172a",
        },
      },
    },
  },
  plugins: [],
};
