import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'

// Vuetify
import 'vuetify/styles'
import { createVuetify } from 'vuetify'
import '@mdi/font/css/materialdesignicons.css'
import { vMaska } from 'maska/vue'

const vuetify = createVuetify({
  theme: {
    defaultTheme: 'light',
    themes: {
      light: {
        colors: {
          // Paleta Institucional Mogi das Cruzes
          primary: '#213a8f',   // Azul Marinho Institucional
          secondary: '#0bbbef', // Azul Claro (Cyan)
          warning: '#f59d24',   // Laranja Alerta
          error: '#e9426d',     // Vermelho/Rosa Erro
          success: '#2E7D32',   // Verde Padrão (Mantivemos um verde floresta para aprovações)
          info: '#0bbbef',      // Usando o secundário para infos
          background: '#F5F7FA' // Fundo gelo suave
        }
      }
    }
  }
})

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(vuetify)
app.directive('maska', vMaska)

app.mount('#app')