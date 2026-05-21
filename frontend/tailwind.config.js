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
        glass: '0 24px 80px rgba(0, 0, 0, 0.38), inset 0 1px 0 rgba(255, 255, 255, 0.12)',
        glow: '0 18px 48px rgba(10, 132, 255, 0.22)',
        card: '0 18px 50px rgba(0, 0, 0, 0.34)',
      },
      backgroundImage: {
        aurora: 'radial-gradient(circle at 18% 8%, rgba(10,132,255,0.22), transparent 32%), linear-gradient(135deg, #03040a 0%, #070911 42%, #0c0f17 100%)',
      },
    },
  },
  plugins: [],
}
