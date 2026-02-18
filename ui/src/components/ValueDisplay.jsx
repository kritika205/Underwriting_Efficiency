import { formatValue } from "../utils/valueFormatter";

/**
 * Component to display values, with special handling for arrays of objects (tables)
 */
export default function ValueDisplay({ value }) {
  // Check if value is an array of objects (should be displayed as table)
  if (Array.isArray(value) && value.length > 0 && typeof value[0] === "object" && !Array.isArray(value[0])) {
    return <TableDisplay data={value} />;
  }

  // Check if value is an object with nested arrays of objects (like accounts in CIBIL)
  if (typeof value === "object" && value !== null && !Array.isArray(value)) {
    // Check if any property is an array of objects
    const arrayOfObjectsKeys = Object.keys(value).filter(
      (key) => Array.isArray(value[key]) && 
      value[key].length > 0 && 
      typeof value[key][0] === "object"
    );

    if (arrayOfObjectsKeys.length > 0) {
      // Render object with tables for array properties
      return (
        <div className="value-display-container">
          {Object.entries(value).map(([key, val]) => {
            if (Array.isArray(val) && val.length > 0 && typeof val[0] === "object") {
              return (
                <div key={key} style={{ marginBottom: "16px" }}>
                  <div style={{ 
                    fontWeight: 600, 
                    marginBottom: "8px",
                    fontSize: "13px",
                    color: "#525252"
                  }}>
                    {key.split("_").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" ")}
                  </div>
                  <TableDisplay data={val} />
                </div>
              );
            } else {
              return (
                <div key={key} style={{ marginBottom: "8px" }}>
                  <span style={{ fontWeight: 600, marginRight: "8px" }}>
                    {key.split("_").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" ")}:
                  </span>
                  <span>{formatValue(val)}</span>
                </div>
              );
            }
          })}
        </div>
      );
    }
  }

  // Default: format as string
  return <span>{formatValue(value)}</span>;
}

/**
 * Component to display array of objects as a table
 */
function TableDisplay({ data }) {
  if (!data || data.length === 0) return <span>N/A</span>;

  // Get all unique keys from all objects
  const allKeys = new Set();
  data.forEach((item) => {
    if (typeof item === "object" && item !== null) {
      Object.keys(item).forEach((key) => allKeys.add(key));
    }
  });

  const columns = Array.from(allKeys);

  if (columns.length === 0) return <span>N/A</span>;

  return (
    <div className="nested-table-container">
      <table className="nested-table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col}>
                {col
                  .split("_")
                  .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
                  .join(" ")}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, idx) => (
            <tr key={idx}>
              {columns.map((col) => (
                <td key={col}>{formatValue(row[col])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}


