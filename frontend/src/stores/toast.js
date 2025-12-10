import { defineStore } from 'pinia';

export const useToastStore = defineStore('toast', {
  state: () => ({
    show: false,
    message: '',
    color: 'info', // success, error, warning, info
    timeout: 3000
  }),
  
  actions: {
    notify(message, color = 'info', timeout = 3000) {
      this.message = message;
      this.color = color;
      this.timeout = timeout;
      this.show = true;
    },
    
    // Atalhos práticos
    success(msg) {
      this.notify(msg, 'success');
    },
    error(msg) {
      this.notify(msg, 'error', 5000); // Erros ficam mais tempo
    },
    warning(msg) {
      this.notify(msg, 'warning');
    },
    info(msg) {
      this.notify(msg, 'info');
    }
  }
});