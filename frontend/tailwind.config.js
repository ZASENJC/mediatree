/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        jelly: '#00a4dc',
        apple: {
          blue: '#0A84FF',
          purple: '#BF5AF2',
          pink: '#FF375F',
          mint: '#32D74B',
          yellow: '#FFD60A',
        },
        glass: {
          surface: 'rgba(255,255,255,0.08)',
          elevated: 'rgba(255,255,255,0.12)',
          border: 'rgba(255,255,255,0.16)',
          muted: 'rgba(255,255,255,0.06)',
        },
        dark: {
          50: '#f5f5f5',
          100: '#e0e0e0',
          200: '#b0b0b0',
          300: '#808080',
          400: '#606060',
          500: '#404040',
          600: '#303030',
          700: '#202020',
          800: '#181818',
          900: '#101010',
          950: '#080808',
        },
      },
      boxShadow: {
        glass: 'var(--mt-shadow-glass)',
        glow: 'var(--mt-shadow-glow)',
        card: 'var(--mt-shadow-card)',
      },
      backgroundImage: {
        aurora: 'radial-gradient(circle at 18% 8%, var(--mt-color-bg-glow), transparent 32%), linear-gradient(135deg, var(--mt-color-bg-start) 0%, var(--mt-color-bg-mid) 42%, var(--mt-color-bg-end) 100%)',
      },
    },
  },
  plugins: [],
}
