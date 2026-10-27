/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        leaf: 'var(--leaf)',
        forest: 'var(--forest)',
        soil: 'var(--soil)',
        'cherry-deep': 'var(--cherry-deep)',
        cherry: 'var(--cherry)',
        paper: 'var(--paper)',
      },
      fontFamily: {
        ui: ['Poppins', 'sans-serif'],
        display: ['Fraunces', 'serif'],
        mono: ['IBM Plex Mono', 'monospace'],
      },
      boxShadow: {
        soft: '0 10px 30px rgba(23, 20, 10, 0.12)',
      },
    },
  },
  plugins: [],
}
