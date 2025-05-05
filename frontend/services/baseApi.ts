import axios from 'axios';

/**
 * Base API configuration for all service requests.
 * Points to the FastAPI backend server with appropriate defaults.
 */
export const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  timeout: 60000, // 60 second timeout
  headers: {
    'Content-Type': 'application/json',
  }
});

// Request interceptor for API calls
api.interceptors.request.use(
  (config) => {
    // You can add auth headers or other request transformations here
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for API calls
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    // Standardize error handling
    const customError = {
      message: error.response?.data?.detail || error.message || 'An unknown error occurred',
      status: error.response?.status || 500,
      data: error.response?.data || null
    };
    
    // Log errors in development
    if (process.env.NODE_ENV !== 'production') {
      console.error('API Error:', customError);
    }
    
    return Promise.reject(customError);
  }
);