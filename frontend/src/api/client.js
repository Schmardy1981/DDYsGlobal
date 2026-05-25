import axios from 'axios';

const API_URL = `${process.env.REACT_APP_BACKEND_URL}/api`;

const api = axios.create({ baseURL: API_URL });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('ddys_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401 && !err.config?.url?.includes('/auth/login')) {
      localStorage.removeItem('ddys_token');
      localStorage.removeItem('ddys_user');
      // Route end-customer flows back to /portal rather than the staff
      // login page so they get the right entry point.
      const isCustomerFlow = window.location.pathname.startsWith('/portal');
      window.location.href = isCustomerFlow ? '/portal' : '/login';
    }
    return Promise.reject(err);
  }
);

export default api;
