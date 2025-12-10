import axios from 'axios';

const api = axios.create({
    baseURL: 'http://192.168.10.50:8010/api/',
    headers: { 'Content-Type': 'application/json' }
});

// Interceptor para injetar o Token
api.interceptors.request.use(config => {
    const token = localStorage.getItem('access_token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

// Interceptor para tratar erro 401 (Token Expirado)
api.interceptors.response.use(
  response => response,
  error => {
    if (error.response && error.response.status === 401) {
        
        const token = localStorage.getItem('access_token');
        
        if (token) {
            localStorage.removeItem('access_token');
            window.location.href = '/login';
        }
    }
    return Promise.reject(error);
  }
);

export default api;