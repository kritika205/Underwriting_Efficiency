/**
 * Format values for display, handling nested objects, arrays, and special types
 * @param {any} value - The value to format
 * @returns {string} - Formatted string representation
 */
export const formatValue = (value) => {
  if (value === null || value === undefined) return "N/A";
  
  // Handle arrays
  if (Array.isArray(value)) {
    if (value.length === 0) return "N/A";
    return value.map(item => formatValue(item)).join(", ");
  }
  
  // Handle booleans
  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }
  
  // Handle numbers (format large numbers with commas)
  if (typeof value === "number") {
    if (Math.abs(value) > 100) {
      return value.toLocaleString();
    }
    return String(value);
  }
  
  // Handle objects (nested structures)
  if (typeof value === "object") {
    const entries = Object.entries(value);
    if (entries.length === 0) return "N/A";
    
    // Format as key-value pairs
    return entries
      .map(([k, v]) => {
        const formattedKey = k
          .split("_")
          .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
          .join(" ");
        return `${formattedKey}: ${formatValue(v)}`;
      })
      .join("; ");
  }
  
  // Handle strings
  return String(value);
};

/**
 * Format value with truncation for display in limited space
 * @param {any} value - The value to format
 * @param {number} maxLength - Maximum length before truncation
 * @returns {string} - Formatted and potentially truncated string
 */
export const formatValueTruncated = (value, maxLength = 50) => {
  const formatted = formatValue(value);
  if (formatted.length > maxLength) {
    return formatted.substring(0, maxLength) + "...";
  }
  return formatted;
};

