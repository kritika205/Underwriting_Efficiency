import axios from 'axios';

const BACKEND_BASE_URL = import.meta.env.VITE_API_BASE_URL?.replace('/api/v1', '') || 'http://localhost:8000';

// Only log backend URL in development mode
if (import.meta.env.DEV) {
  console.log('[Health Check] Backend URL:', BACKEND_BASE_URL);
}

// Health check cache
let healthCheckCache = {
  status: null, // 'checking' | 'connected' | 'disconnected'
  lastCheck: null,
  promise: null,
  error: null,
  data: null,
};

// Cache duration: 30 seconds (don't check more than once every 30 seconds)
const CACHE_DURATION = 30000; // 30 seconds - reduce frequency to avoid overloading backend
const HEALTH_CHECK_TIMEOUT = 15000; // 15 seconds - increased timeout for busy backend

/**
 * Check backend health with caching and debouncing
 * @param {boolean} force - Force a new check even if cache is valid
 * @returns {Promise<{success: boolean, error?: string, data?: any}>}
 */
export const checkBackendHealth = async (force = false) => {
  const now = Date.now();
  
  // If we have a recent successful check and not forcing, return cached result
  if (!force && healthCheckCache.status === 'connected' && healthCheckCache.lastCheck) {
    const timeSinceLastCheck = now - healthCheckCache.lastCheck;
    if (timeSinceLastCheck < CACHE_DURATION) {
      return { success: true, data: healthCheckCache.data };
    }
  }
  
  // If we have a recent failed check and not forcing, return cached result (avoid hammering backend)
  if (!force && healthCheckCache.status === 'disconnected' && healthCheckCache.lastCheck) {
    const timeSinceLastCheck = now - healthCheckCache.lastCheck;
    if (timeSinceLastCheck < CACHE_DURATION / 2) { // Cache failures for half the duration
      return { success: false, error: healthCheckCache.error };
    }
  }
  
  // If there's already a check in progress, return that promise
  if (healthCheckCache.promise) {
    return healthCheckCache.promise;
  }
  
  // Set status to checking
  healthCheckCache.status = 'checking';
  
  // Create health check promise
  healthCheckCache.promise = (async () => {
    // Use the dedicated health check endpoint (separated from root)
    const endpoint = '/api/health/';
    
    try {
      const response = await axios.get(`${BACKEND_BASE_URL}${endpoint}`, {
        timeout: HEALTH_CHECK_TIMEOUT,
        validateStatus: (status) => status < 500, // Accept 2xx, 3xx, 4xx but not 5xx
      });
      
      // Success - update cache
      healthCheckCache.status = 'connected';
      healthCheckCache.lastCheck = now;
      healthCheckCache.data = response.data;
      healthCheckCache.error = null;
      healthCheckCache.promise = null;
      
      // Only log success if it's a fresh check (not from cache)
      if (force || !healthCheckCache.lastCheck || (now - healthCheckCache.lastCheck) > CACHE_DURATION) {
        console.log(`[Health Check] Successfully connected via ${endpoint}`);
      }
      return { success: true, data: response.data };
    } catch (error) {
      // Only log warnings for actual failures, not timeouts during busy periods
      // Suppress warnings if it's a timeout and we're not forcing a check
      const isTimeout = error.code === 'ECONNABORTED' || error.message?.includes('timeout');
      if (!isTimeout || force) {
        console.warn(`[Health Check] Failed to connect via ${endpoint}:`, error.message);
      }
      
      // Return detailed error
      let errorMessage = 'Unknown error';
      
      if (error.code === 'ECONNREFUSED') {
        errorMessage = `Cannot connect to backend at ${BACKEND_BASE_URL}. Please ensure the backend server is running on port 8000.`;
      } else if (error.code === 'ECONNABORTED' || error.message.includes('timeout')) {
        errorMessage = `Backend connection timeout after ${HEALTH_CHECK_TIMEOUT}ms. The server may be slow or unresponsive.`;
      } else if (error.message.includes('Network Error') || error.message.includes('ERR_NETWORK')) {
        errorMessage = `Network error connecting to ${BACKEND_BASE_URL}. Check CORS settings and ensure the backend is accessible.`;
      } else if (error.response) {
        // Server responded but with an error status
        if (error.response.status === 404) {
          errorMessage = `Backend endpoint not found. The server may be running but the health endpoint is missing.`;
        } else {
          errorMessage = `Backend returned error ${error.response.status}: ${error.response.data?.detail || error.response.data?.message || 'Unknown error'}`;
        }
      } else if (error.request) {
        // Request was made but no response received
        errorMessage = `No response from backend at ${BACKEND_BASE_URL}. The server may be running but not responding.`;
      } else {
        errorMessage = `Error: ${error.message || 'Unknown error'}`;
      }
      
      // Log detailed error for debugging (only if not a timeout or forcing check)
      if (!isTimeout || force) {
        console.error('[Health Check] Health check failed:', {
          code: error.code,
          message: error.message,
          response: error.response?.status,
          request: error.request ? 'Request made' : 'No request',
          url: `${BACKEND_BASE_URL}${endpoint}`,
        });
      }
      
      healthCheckCache.status = 'disconnected';
      healthCheckCache.lastCheck = now;
      healthCheckCache.error = errorMessage;
      healthCheckCache.promise = null;
      
      return {
        success: false,
        error: errorMessage,
      };
    }
  })();
  
  return healthCheckCache.promise;
};

/**
 * Get current health status from cache (synchronous)
 * @returns {{status: string, lastCheck: number, error: string|null}}
 */
export const getHealthStatus = () => {
  return {
    status: healthCheckCache.status,
    lastCheck: healthCheckCache.lastCheck,
    error: healthCheckCache.error,
  };
};

/**
 * Clear health check cache (useful for forcing a fresh check)
 */
export const clearHealthCheckCache = () => {
  healthCheckCache = {
    status: null,
    lastCheck: null,
    promise: null,
    error: null,
    data: null,
  };
};

/**
 * Check if backend is likely connected based on cache
 * @returns {boolean|null}
 */
export const isBackendLikelyConnected = () => {
  if (!healthCheckCache.lastCheck) return null; // Unknown
  
  const timeSinceLastCheck = Date.now() - healthCheckCache.lastCheck;
  
  // If last check was recent and successful, likely connected
  if (healthCheckCache.status === 'connected' && timeSinceLastCheck < CACHE_DURATION * 2) {
    return true;
  }
  
  // If last check was recent and failed, likely disconnected
  if (healthCheckCache.status === 'disconnected' && timeSinceLastCheck < CACHE_DURATION * 2) {
    return false;
  }
  
  return null; // Unknown - cache expired
};
