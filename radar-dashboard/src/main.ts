import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './assets/tokens.css'
import App from './App.vue'
import router from './router'
import { initErrorTracking } from './observability'

const app = createApp(App)

initErrorTracking(app)

app.use(createPinia())
app.use(router)

app.mount('#app')
