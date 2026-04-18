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
    const isAxiosError = axios.isAxiosError(error);
    const errorData = isAxiosError ? error.response?.data : undefined;
    const errorMessage = error instanceof Error ? error.message : String(error);
    const url = isAxiosError ? error.config?.url : undefined;
    console.error('API Error:', {
      baseURL: isAxiosError ? error.config?.baseURL : undefined,
      code: isAxiosError ? error.code : undefined,
      method: isAxiosError ? error.config?.method : undefined,
      url,
      status: isAxiosError ? error.response?.status : undefined,
      data: errorData,
      message: errorMessage,
      isAxiosError,
    });
    return Promise.reject(error);
  }
);

export default api;
