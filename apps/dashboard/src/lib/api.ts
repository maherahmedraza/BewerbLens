import axios from 'axios';
import { dashboardEnv } from './env';

/**
 * Production-grade Axios instance for the BewerbLens Orchestrator API.
 * 
 * In development, it points to the local FastAPI service on port 8000.
 * In production, it should point to your hosted orchestrator URL.
 */
const api = axios.create({
  baseURL: dashboardEnv.orchestratorUrl,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 10000,
});

// Add response interceptors for global error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const errorData = error.response?.data;
    const errorMessage = error.message;
    const url = error.config?.url;
    console.error('API Error:', {
      url,
      status: error.response?.status,
      data: errorData,
      message: errorMessage,
      error
    });
    return Promise.reject(error);
  }
);

export default api;
