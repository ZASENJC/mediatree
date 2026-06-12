import DefaultTheme from 'vitepress/theme'
import MediaTreeHome from './components/MediaTreeHome.vue'
import './style.css'

export default {
  extends: DefaultTheme,
  enhanceApp({ app }) {
    app.component('MediaTreeHome', MediaTreeHome)
  }
}
