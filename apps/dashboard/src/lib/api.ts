import axios from 'axios';

/**
 * Production-grade Axios instance for the BewerbLens Orchestrator API.
 * 
 * It targets the dashboard's server-side orchestrator proxy so browser code
 * never talks to the FastAPI service directly.
 */
const api = axios.create({
  baseURL: '/api/orchestrator',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 10000,
});

// Add response interceptors for global error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

export default api;
