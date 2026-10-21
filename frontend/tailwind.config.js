/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Rubick Dark Navy Palette
        rubick: {
          dark: '#0f172a',    // Deep slate for sidebar
          nav: '#1e293b',     // Sidebar hover / active
          accent: '#2563eb',  // Vibrant primary blue
          accentHover: '#1d4ed8',
          bg: '#f8fafc',      // Workspace background
          card: '#ffffff',
          border: '#e2e8f0',
          textMuted: '#64748b',
          textDark: '#1e293b',
        }
      },
      boxShadow: {
        'soft': '0 2px 10px 0 rgba(0, 0, 0, 0.04)',
        'card': '0 4px 20px -2px rgba(0, 0, 0, 0.05)',
      }
    },
  },
  plugins: [],
}

