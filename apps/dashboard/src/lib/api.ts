import axios from 'axios';

/**
 * Production-grade Axios instance for the BewerbLens Orchestrator API.
 * 
 * In development, it points to the local FastAPI service on port 8000.
 * In production, it should point to your hosted orchestrator URL.
 */
const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_ORCHESTRATOR_URL || 'http://localhost:8000',
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
