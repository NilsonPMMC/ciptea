import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'
import vuetify from 'vite-plugin-vuetify' // <--- Plugin do Vuetify
import { VitePWA } from 'vite-plugin-pwa' // <--- Plugin do PWA

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    vueDevTools(),
    // Configura o Vuetify para importar componentes sob demanda (mais leve)
    vuetify({ autoImport: true }), 
    
    // Configuração do PWA (Progressive Web App)
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.ico', 'apple-touch-icon.png', 'masked-icon.svg'],
      manifest: {
        name: 'CIPTEA Mogi',
        short_name: 'CIPTEA',
        description: 'Carteira de Identificação da Pessoa com TEA - Mogi das Cruzes',
        theme_color: '#ffffff',
        display: 'standalone', // Faz parecer um app nativo (sem barra de URL)
        icons: [
          {
            src: 'pwa-192x192.png',
            sizes: '192x192',
            type: 'image/png'
          },
          {
            src: 'pwa-512x512.png',
            sizes: '512x512',
            type: 'image/png'
          }
        ]
      }
    })
  ],
  // Libera o acesso pelo IP do servidor (essencial para testarmos)
  server: {
    host: true, 
    port: 5173
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
  },
})