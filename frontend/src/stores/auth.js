import { defineStore } from 'pinia';
import api from '@/services/api';
import router from '@/router'; // Importe o roteador para redirecionar

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: sessionStorage.getItem('access_token') || localStorage.getItem('access_token') || null,
    user: null
  }),

  getters: {
    isAuthenticated: (state) => !!state.token
  },

  actions: {
    async login(username, password) {
      const { data } = await api.post('token/', { username, password });
      
      this.token = data.access;
      sessionStorage.setItem('access_token', data.access);
      sessionStorage.setItem('refresh_token', data.refresh);
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      
      // Configura o header padrão imediatamente
      api.defaults.headers.common['Authorization'] = `Bearer ${data.access}`;
    },

    logout() {
      // 1. Limpa o Estado
      this.token = null;
      this.user = null;

      // 2. Limpa o LocalStorage
      sessionStorage.removeItem('access_token');
      sessionStorage.removeItem('refresh_token');
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      
      // 3. Remove o Header do Axios para futuras requisições não irem com token velho
      delete api.defaults.headers.common['Authorization'];
      
      // 4. Redireciona para a tela de Login
      router.push('/login');
    }
  }
});