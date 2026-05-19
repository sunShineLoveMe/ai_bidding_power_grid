import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: '#3267ff',
        ink: '#111a33',
      },
      boxShadow: {
        panel: '0 12px 28px rgba(23, 42, 88, 0.08)',
        soft: '0 6px 18px rgba(23, 42, 88, 0.06)',
      },
    },
  },
  plugins: [],
} satisfies Config;
