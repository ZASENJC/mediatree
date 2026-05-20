/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        jelly: '#00a4dc',
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
    },
  },
  plugins: [],
}
