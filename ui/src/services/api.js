import axios from 'axios';
import { checkBackendHealth as healthCheckService } from './healthCheck';

// API base URL - adjust this based on your backend configuration
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';
const BACKEND_BASE_URL = import.meta.env.VITE_API_BASE_URL?.replace('/api/v1', '') || 'http://localhost:8000';

console.log('API Base URL:', API_BASE_URL);
console.log('Backend Base URL:', BACKEND_BASE_URL);

// Create axios instance with default config
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 90000, // 90 second default timeout (individual endpoints can override)
});

// Request interceptor for adding auth tokens if needed
api.interceptors.request.use(
  (config) => {
    // If the data is FormData, remove Content-Type header to let axios set it with boundary
    if (config.data instanceof FormData) {
      delete config.headers['Content-Type'];
      // Only log in development mode to reduce console noise
      if (import.meta.env.DEV) {
        console.log('[API] FormData detected, Content-Type will be set automatically by axios');
      }
    }
    
    // Add auth token if available
    const token = localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    // Only log in development mode to reduce console noise
    if (import.meta.env.DEV) {
      console.log(`[API] ${config.method.toUpperCase()} ${config.url}`);
    }
    return config;
  },
  (error) => {
    console.error('[API] Request Error:', error);
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => {
    // Only log in development mode to reduce console noise
    if (import.meta.env.DEV) {
      console.log(`[API] Success: ${response.config.method.toUpperCase()} ${response.config.url}`, response.status);
    }
    return response;
  },
  (error) => {
    if (error.response) {
      // Server responded with error
      const errorMessage = error.response.data?.detail || error.response.data?.message || JSON.stringify(error.response.data);
      console.error(`[API] Error ${error.response.status}:`, errorMessage);
      // Only log full error in development mode
      if (import.meta.env.DEV) {
        console.error('[API] Full error:', error.response);
      }
    } else if (error.request) {
      // Request made but no response - only log critical network errors
      if (error.code !== 'ECONNABORTED') {
        // Don't log timeout errors here as they're handled by individual endpoints
        console.error('[API] Network Error: No response from server');
        if (import.meta.env.DEV) {
          console.error('[API] Request:', error.request);
          console.error('[API] Backend URL:', BACKEND_BASE_URL);
          console.error('[API] Please ensure the backend is running on', BACKEND_BASE_URL);
        }
      }
    } else {
      // Something else happened
      console.error('[API] Error:', error.message);
    }
    return Promise.reject(error);
  }
);

// Re-export health check function for backward compatibility
export const checkBackendHealth = healthCheckService;

// Document APIs
export const documentAPI = {
  // Upload a document
  upload: async (file, user_id = null, application_id = null, expected_document_type = null) => {
    const formData = new FormData();
    formData.append('file', file);
    if (user_id) {
      formData.append('user_id', user_id);
    }
    if (application_id) {
      formData.append('application_id', application_id);
    }
    if (expected_document_type) {
      formData.append('expected_document_type', expected_document_type);
    }
    // Don't set Content-Type manually - let axios set it with the correct boundary
    // Increased timeout to 5 minutes to handle very large files and slow connections
    const response = await api.post('/documents/upload', formData, {
      timeout: 300000, // 5 minutes for large file uploads
    });
    return response.data;
  },

  // Get document by ID
  getById: async (document_id) => {
    const response = await api.get(`/documents/${document_id}`);
    return response.data;
  },

  // List documents
  list: async (params = {}) => {
    const response = await api.get('/documents/', { params });
    return response.data;
  },

  // Get all documents for a user
  getUserDocuments: async (user_id) => {
    const response = await api.get(`/documents/user/${user_id}/all`);
    return response.data;
  },

  // Get all documents for an application
  getApplicationDocuments: async (application_id) => {
    const response = await api.get(`/documents/application/${application_id}/all`);
    return response.data;
  },

  // Get document status
  getStatus: async (document_id) => {
    const response = await api.get(`/documents/${document_id}/status`);
    return response.data;
  },

  // Delete document
  delete: async (document_id) => {
    const response = await api.delete(`/documents/${document_id}`);
    return response.data;
  },
};

// OCR and Extraction APIs
export const ocrAPI = {
  // Perform OCR and extraction
  extract: async (document_id, document_type = null, skip_classification = false) => {
    // OCR extraction is a long-running operation that can take 2-5 minutes
    // for complex documents with classification, OCR, extraction, validation, and risk analysis
    const response = await api.post('/ocr-extract/', {
      document_id,
      document_type,
      skip_classification,
    }, {
      timeout: 300000, // 5 minutes timeout for OCR extraction
    });
    return response.data;
  },

  // Get extracted data for a document
  getExtractedData: async (document_id) => {
    const response = await api.get(`/ocr-extract/${document_id}`);
    return response.data;
  },

  // Get all extractions for a user
  getUserExtractions: async (user_id) => {
    const response = await api.get(`/ocr-extract/user/${user_id}/all`);
    return response.data;
  },

  // Get all extractions for an application
  getApplicationExtractions: async (application_id) => {
    const response = await api.get(`/ocr-extract/application/${application_id}/all`);
    return response.data;
  },

  // Get user document aggregation
  getUserAggregation: async (user_id) => {
    const response = await api.get(`/ocr-extract/user/${user_id}/aggregation`);
    return response.data;
  },
};

// Classification APIs
export const classifyAPI = {
  // Classify a document
  classify: async (document_id, ocr_text = null) => {
    const response = await api.post('/classify/', {
      document_id,
      ocr_text,
    });
    return response.data;
  },
};

// Cross-Validation APIs
export const crossValidationAPI = {
  // Cross-validate a document
  validateDocument: async (document_id) => {
    const response = await api.post(`/cross-validate/document/${document_id}`);
    return response.data;
  },

  // Cross-validate all documents for a user
  validateUser: async (user_id) => {
    const response = await api.get(`/cross-validate/user/${user_id}`);
    return response.data;
  },

  // Cross-validate all documents for an application
  validateApplication: async (application_id) => {
    const response = await api.get(`/cross-validate/application/${application_id}`);
    return response.data;
  },
};

// User APIs
export const userAPI = {
  // Create a user
  create: async (userData) => {
    const response = await api.post('/users/', userData);
    return response.data;
  },

  // Get user by ID
  getById: async (user_id) => {
    const response = await api.get(`/users/${user_id}`);
    return response.data;
  },

  // List users
  list: async () => {
    const response = await api.get('/users/');
    return response.data;
  },

  // Update case status
  updateCaseStatus: async (user_id, caseStatusData) => {
    const response = await api.put(`/users/${user_id}/case-status`, caseStatusData);
    return response.data;
  },
};

// Application APIs
export const applicationAPI = {
  // Create an application
  create: async (applicationData) => {
    const response = await api.post('/applications/', applicationData);
    return response.data;
  },

  // Get application by ID
  getById: async (application_id) => {
    const response = await api.get(`/applications/${application_id}`);
    return response.data;
  },

  // List applications
  list: async (params = {}) => {
    const response = await api.get('/applications/', { params });
    return response.data;
  },

  // Update application status
  updateStatus: async (application_id, statusData) => {
    const response = await api.put(`/applications/${application_id}/status`, statusData);
    return response.data;
  },
};

// Risk Analysis APIs
export const riskAnalysisAPI = {
  // Perform risk analysis on a document
  analyze: async (document_id, include_llm_reasoning = true) => {
    const response = await api.post('/risk-analysis/', {
      document_id,
      include_llm_reasoning,
    });
    return response.data;
  },

  // Get risk analysis result for a document
  getByDocumentId: async (document_id) => {
    const response = await api.get(`/risk-analysis/${document_id}`);
    return response.data;
  },

  // Get risk summary for all documents of a user
  getUserRiskSummary: async (user_id) => {
    const response = await api.get(`/risk-analysis/user/${user_id}/summary`);
    return response.data;
  },

  // Get risk summary for all documents of an application
  getApplicationRiskSummary: async (application_id) => {
    const response = await api.get(`/risk-analysis/application/${application_id}/summary`);
    return response.data;
  },
};

// Admin Authentication APIs
export const adminAPI = {
  // Admin login
  login: async (email, password) => {
    const response = await api.post('/admin/login', {
      email,
      password,
    });
    // Store token in localStorage
    if (response.data.access_token) {
      localStorage.setItem('auth_token', response.data.access_token);
      localStorage.setItem('admin_data', JSON.stringify(response.data.admin));
    }
    return response.data;
  },

  // Get current admin info
  getMe: async () => {
    const response = await api.get('/admin/me');
    return response.data;
  },

  // Update admin profile
  updateProfile: async (profileData) => {
    const response = await api.put('/admin/me', profileData);
    // Update stored admin data
    if (response.data) {
      localStorage.setItem('admin_data', JSON.stringify(response.data));
    }
    return response.data;
  },

  // Create admin (requires authentication)
  create: async (adminData) => {
    const response = await api.post('/admin/create', adminData);
    return response.data;
  },

  // Create default admin (for initial setup)
  createDefault: async () => {
    const response = await api.post('/admin/create-default');
    return response.data;
  },

  // Logout (clear token)
  logout: () => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('admin_data');
  },
};

export default api;

