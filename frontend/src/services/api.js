import axios from 'axios';

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || `${window.location.origin}/api/`;

const api = axios.create({
    baseURL: apiBaseUrl,
    headers: { 'Content-Type': 'application/json' }
});

const getToken = () => {
    return sessionStorage.getItem('access_token') || localStorage.getItem('access_token');
};

// Interceptor para injetar o Token
api.interceptors.request.use(config => {
    const token = getToken();
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
        
        const token = getToken();
        
        if (token) {
            sessionStorage.removeItem('access_token');
            sessionStorage.removeItem('refresh_token');
            localStorage.removeItem('access_token');
            localStorage.removeItem('refresh_token');
            window.location.href = '/login';
        }
    }
    return Promise.reject(error);
  }
);

export default api;