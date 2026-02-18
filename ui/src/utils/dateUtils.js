/**
 * Date utility functions for consistent UTC timestamp handling
 */

/**
 * Parse a date input (string, Date, or object) and ensure it's treated as UTC
 * @param {string|Date|Object} dateInput - Date input in various formats
 * @returns {Date|null} - Parsed Date object or null if invalid
 */
export const parseUTCDate = (dateInput) => {
  if (!dateInput) return null;
  
  try {
    let date;
    
    // Handle different date formats
    if (dateInput instanceof Date) {
      date = dateInput;
    } else if (typeof dateInput === 'string') {
      // If the string doesn't end with 'Z' or timezone offset, assume it's UTC
      if (!dateInput.includes('Z') && !dateInput.match(/[+-]\d{2}:\d{2}$/)) {
        // No timezone info - assume UTC and append 'Z'
        date = new Date(dateInput.endsWith('Z') ? dateInput : dateInput + 'Z');
      } else {
        date = new Date(dateInput);
      }
    } else if (typeof dateInput === 'object' && dateInput !== null) {
      if (dateInput.$date) {
        // MongoDB date format
        date = new Date(dateInput.$date);
      } else if (dateInput.timestamp) {
        date = new Date(dateInput.timestamp);
      } else {
        // Try to convert to string and parse
        const dateStr = String(dateInput);
        date = new Date(dateStr.includes('Z') || dateStr.match(/[+-]\d{2}:\d{2}$/) ? dateStr : dateStr + 'Z');
      }
    } else {
      return null;
    }
    
    // Check if date is valid
    if (isNaN(date.getTime())) {
      return null;
    }
    
    return date;
  } catch (error) {
    console.warn("Error parsing UTC date:", error, "Input:", dateInput);
    return null;
  }
};

/**
 * Format a date to a readable string in local timezone
 * @param {string|Date|Object} dateInput - Date input in various formats
 * @param {Object} options - Formatting options
 * @returns {string} - Formatted date string or "Unknown"
 */
export const formatDateTime = (dateInput, options = {}) => {
  const date = parseUTCDate(dateInput);
  if (!date) return "Unknown";
  
  const defaultOptions = {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
    timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone
  };
  
  return date.toLocaleString('en-US', { ...defaultOptions, ...options });
};

/**
 * Format a date to date-only string in local timezone
 * @param {string|Date|Object} dateInput - Date input in various formats
 * @returns {string} - Formatted date string or "Unknown"
 */
export const formatDate = (dateInput) => {
  const date = parseUTCDate(dateInput);
  if (!date) return "Unknown";
  
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone
  });
};

/**
 * Calculate time ago from a date
 * @param {string|Date|Object} dateInput - Date input in various formats
 * @returns {string} - Time ago string (e.g., "2h ago", "3d ago")
 */
export const calculateTimeAgo = (dateInput) => {
  const date = parseUTCDate(dateInput);
  if (!date) return "Unknown";
  
  try {
    const now = new Date();
    const diffMs = now - date;
    
    // Handle negative differences (future dates)
    if (diffMs < 0) {
      return "Just now";
    }
    
    // Calculate time differences
    const diffSeconds = Math.floor(diffMs / 1000);
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);
    const diffWeeks = Math.floor(diffMs / 604800000);
    const diffMonths = Math.floor(diffMs / 2592000000);
    const diffYears = Math.floor(diffMs / 31536000000);

    // Return appropriate time string
    if (diffSeconds < 60) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    if (diffWeeks < 4) return `${diffWeeks}w ago`;
    if (diffMonths < 12) return `${diffMonths}mo ago`;
    return `${diffYears}y ago`;
  } catch (error) {
    console.warn("Error calculating time ago:", error, "Input:", dateInput);
    return "Unknown";
  }
};

