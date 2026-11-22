import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './assets/tokens.css'
import App from './App.vue'
import { isOnlineMode } from './mode'
import { initErrorTracking } from './observability'

const app = createApp(App)

initErrorTracking(app)

app.use(createPinia())
// Compared inline, not through isOnlineMode(): Vite replaces the variable at build time, so
// the bundler drops the other branch and the public build ships no local view at all.
const { default: router } =
  import.meta.env.VITE_RADAR_MODE === 'online'
    ? await import('./router/online').then(({ createOnlineRouter }) => ({
        default: createOnlineRouter(),
      }))
    : await import('./router')
app.use(router)
if (isOnlineMode()) {
  document.title = 'Engineering-Radar reports'
}

app.mount('#app')
