import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { applicationAPI, userAPI } from "../services/api";

export default function ApplicationStatus({ userId, userEmail }) {
  const [applications, setApplications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [finalUserId, setFinalUserId] = useState(userId);
  const [userExists, setUserExists] = useState(false);
  const navigate = useNavigate();

  // Get userId from email if not provided and verify user exists
  useEffect(() => {
    const fetchUserId = async () => {
      if (!finalUserId && userEmail) {
        try {
          const users = await userAPI.list();
          const user = users.find(u => u.email === userEmail);
          if (user) {
            setFinalUserId(user.user_id);
          } else {
            setError("User account not found. Please contact support.");
            setLoading(false);
          }
        } catch (err) {
          console.error("Error fetching user:", err);
          setError("Unable to verify user account. Please try again.");
          setLoading(false);
        }
      }
    };
    fetchUserId();
  }, [finalUserId, userEmail]);

  // Verify user exists before loading applications
  useEffect(() => {
    const verifyUser = async () => {
      if (finalUserId) {
        try {
          // Check if user exists
          await userAPI.getById(finalUserId);
          setUserExists(true);
        } catch (err) {
          console.error("Error verifying user:", err);
          if (err.response?.status === 404) {
            setError("User account not found. Please contact support or create a new account.");
          } else {
            setError("Unable to verify user account. Please try again.");
          }
          setLoading(false);
          setUserExists(false);
        }
      }
    };
    verifyUser();
  }, [finalUserId]);

  const loadApplications = async () => {
    if (!finalUserId || !userExists) {
      setLoading(false);
      return;
    }

    try {
      setError(null);
      const apps = await applicationAPI.list({ user_id: finalUserId });
      setApplications(apps || []);
    } catch (err) {
      console.error("Error fetching applications:", err);
      setError("Unable to fetch application status. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (finalUserId && userExists) {
      loadApplications();
      // Real-time polling every 10 seconds
      const interval = setInterval(loadApplications, 10000);
      return () => clearInterval(interval);
    }
  }, [finalUserId, userExists]);

  const getStatusBadgeStyle = (status) => {
    const statusMap = {
      "Approved": { bg: "#22c55e", color: "#fff" },
      "Rejected": { bg: "#ef4444", color: "#fff" },
      //"Conditionally Approved": { bg: "#f59e0b", color: "#fff" },
      "Conditionally Approved": { bg: "#f59e0b", color: "#fff" }, // legacy
      "In Review": { bg: "#2563eb", color: "#fff" },
      "SUBMITTED": { bg: "#6b7280", color: "#fff" }
    };
    
    const style = statusMap[status] || { bg: "#9ca3af", color: "#fff" };
    return {
      background: style.bg,
      color: style.color,
      padding: "6px 14px",
      borderRadius: 20,
      fontSize: 13,
      fontWeight: 500,
      display: "inline-block"
    };
  };

  const formatDate = (dateString) => {
    if (!dateString) return "—";
    try {
      return new Date(dateString).toLocaleString();
    } catch {
      return dateString;
    }
  };

  const formatCurrency = (amount) => {
    if (!amount) return "—";
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0
    }).format(amount);
  };

  const getSummaryMessage = (status) => {
    if (!status) return null;
    const statusUpper = status.toUpperCase().trim();
    if (statusUpper === "APPROVED") {
      return "Congratulations! Your application is Approved.";
    } else if (statusUpper === "REJECTED") {
      return "Sorry, your application is rejected.";
    } else if (statusUpper === "CONDITIONALLY APPROVED" || statusUpper === "CONDITIONALLY APPROVED") {
      return "Your application has been conditionally approved. Please review the conditions and requirements below.";
    }
    return null;
  };

  const isConditionallyApproved = (status) => {
    if (!status) return false;
    const statusUpper = status.toUpperCase().trim();
    return statusUpper === "CONDITIONALLY APPROVED" || statusUpper === "CONDITIONALLY APPROVED";
  };

  const formatConditionKey = (key) => {
    // Convert camelCase/snake_case to readable format
    const readableKey = key
      .replace(/_/g, " ")
      .replace(/([A-Z])/g, " $1")
      .toLowerCase()
      .split(" ")
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");
    return readableKey;
  };

  const formatConditionValue = (key, value) => {
    // Handle boolean values
    if (typeof value === "boolean") {
      if (value === true) {
        // Map common condition keys to user-friendly messages
        const conditionMessages = {
          "reduce": "Reduce Loan Amount",
          "employer": "Employer Verification Required",
          "bank": "Bank Statement Verification Required",
          "income": "Income Verification Required",
          "documents": "Additional Documents Required",
          "guarantor": "Guarantor Required",
          "collateral": "Collateral Required"
        };
        return conditionMessages[key.toLowerCase()] || `${formatConditionKey(key)} Required`;
      }
      return null; // Don't show false conditions
    }
    
    // Handle string values
    if (typeof value === "string") {
      return value;
    }
    
    // Handle other types
    return String(value);
  };

  const getFormattedConditions = (conditions) => {
    if (!conditions || typeof conditions !== "object") return [];
    
    const formatted = [];
    Object.entries(conditions).forEach(([key, value]) => {
      const formattedValue = formatConditionValue(key, value);
      if (formattedValue !== null) {
        formatted.push({
          key: formatConditionKey(key),
          value: formattedValue
        });
      }
    });
    return formatted;
  };

  if (loading) {
    return (
      <div style={s.page}>
        <div style={s.container}>
          <div style={s.loading}>Loading application status...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={s.page}>
        <div style={s.container}>
          <div style={s.error}>{error}</div>
          <button style={s.retryButton} onClick={loadApplications}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={s.page}>
      <div style={s.container}>
        <div style={s.header}>
          <div>
            <h2 style={s.title}>Application Status</h2>
            <p style={s.subtitle}>Track your loan application progress</p>
          </div>
          <button style={s.backButton} onClick={() => navigate("/client")}>
            ← Back to Dashboard
          </button>
        </div>

        {applications.length === 0 ? (
          <div style={s.emptyState}>
            <div style={s.emptyIcon}>📋</div>
            <h3 style={s.emptyTitle}>No Applications Found</h3>
            <p style={s.emptyText}>
              You haven't submitted any applications yet.
            </p>
            <button
              style={s.applyButton}
              onClick={() => navigate("/client/apply")}
            >
              Submit New Application
            </button>
          </div>
        ) : (
          <div style={s.applicationsList}>
            {applications.map((app) => (
              <div key={app.application_id} style={s.applicationCard}>
                <div style={s.cardHeader}>
                  <div>
                    <h3 style={s.appId}>Application ID: {app.application_id}</h3>
                    <p style={s.appDate}>
                      Created: {formatDate(app.created_at)}
                    </p>
                  </div>
                  <span style={getStatusBadgeStyle(app.status)}>
                    {app.status || "In Review"}
                  </span>
                </div>

                <div style={s.cardBody}>
                  <div style={s.detailsGrid}>
                    <div style={s.detailItem}>
                      <span style={s.detailLabel}>Loan Type</span>
                      <span style={s.detailValue}>
                        {app.loan_type || "—"}
                      </span>
                    </div>
                    <div style={s.detailItem}>
                      <span style={s.detailLabel}>Applicant Type</span>
                      <span style={s.detailValue}>
                        {app.applicant_type || "—"}
                      </span>
                    </div>
                    <div style={s.detailItem}>
                      <span style={s.detailLabel}>Loan Amount</span>
                      <span style={s.detailValue}>
                        {formatCurrency(app.loan_amount)}
                      </span>
                    </div>
                    <div style={s.detailItem}>
                      <span style={s.detailLabel}>Last Updated</span>
                      <span style={s.detailValue}>
                        {formatDate(app.updated_at)}
                      </span>
                    </div>
                  </div>

                  {/* Summary Section - Shows status-based message */}
                  {getSummaryMessage(app.status) && (
                    <div style={s.section}>
                      <h4 style={s.sectionTitle}>Summary</h4>
                      <p style={(() => {
                        const statusUpper = app.status?.toUpperCase().trim() || "";
                        if (statusUpper === "APPROVED") return { ...s.sectionContent, ...s.summaryApproved };
                        if (statusUpper === "REJECTED") return { ...s.sectionContent, ...s.summaryRejected };
                        if (isConditionallyApproved(app.status)) return { ...s.sectionContent, ...s.summaryConditional };
                        return s.sectionContent;
                      })()}>
                        {getSummaryMessage(app.status)}
                      </p>
                    </div>
                  )}

                  {/* Conditions - Only show for conditionally approved applications */}
                  {isConditionallyApproved(app.status) && app.case_conditions && Object.keys(app.case_conditions).length > 0 && (
                    <div style={s.section}>
                      <h4 style={s.sectionTitle}>Conditions and Requirements</h4>
                      <div style={s.conditionsList}>
                        {getFormattedConditions(app.case_conditions).map((condition, index) => (
                          <div key={index} style={s.conditionItem}>
                            <span style={s.conditionIcon}>✓</span>
                            <span style={s.conditionText}>{condition.value}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {app.case_decision && (
                    <div style={s.section}>
                      <h4 style={s.sectionTitle}>Decision</h4>
                      <p style={s.sectionContent}>{app.case_decision}</p>
                    </div>
                  )}

                  {app.case_notes && (
                    <div style={s.section}>
                      <h4 style={s.sectionTitle}>Notes</h4>
                      <p style={s.sectionContent}>{app.case_notes}</p>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

const s = {
  page: {
    minHeight: "100vh",
    background: "#f8fafc",
    padding: "24px"
  },
  container: {
    maxWidth: 1000,
    margin: "0 auto"
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 32,
    flexWrap: "wrap",
    gap: 16
  },
  title: {
    margin: 0,
    fontSize: 28,
    color: "#111827",
    fontWeight: 600
  },
  subtitle: {
    margin: "8px 0 0",
    fontSize: 14,
    color: "#6b7280"
  },
  backButton: {
    padding: "8px 16px",
    background: "#fff",
    border: "1px solid #e5e7eb",
    borderRadius: 6,
    cursor: "pointer",
    fontSize: 14,
    color: "#374151",
    transition: "all 0.2s"
  },
  applicationsList: {
    display: "flex",
    flexDirection: "column",
    gap: 20
  },
  applicationCard: {
    background: "#fff",
    borderRadius: 12,
    padding: 24,
    boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
    border: "1px solid #e5e7eb",
    transition: "box-shadow 0.2s"
  },
  cardHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 20,
    flexWrap: "wrap",
    gap: 12
  },
  appId: {
    margin: 0,
    fontSize: 18,
    color: "#111827",
    fontWeight: 600
  },
  appDate: {
    margin: "4px 0 0",
    fontSize: 13,
    color: "#6b7280"
  },
  cardBody: {
    display: "flex",
    flexDirection: "column",
    gap: 20
  },
  detailsGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
    gap: 16
  },
  detailItem: {
    display: "flex",
    flexDirection: "column",
    gap: 4
  },
  detailLabel: {
    fontSize: 12,
    color: "#6b7280",
    fontWeight: 500,
    textTransform: "uppercase",
    letterSpacing: "0.5px"
  },
  detailValue: {
    fontSize: 15,
    color: "#111827",
    fontWeight: 500
  },
  section: {
    paddingTop: 16,
    borderTop: "1px solid #e5e7eb"
  },
  sectionTitle: {
    margin: "0 0 8px",
    fontSize: 14,
    color: "#374151",
    fontWeight: 600
  },
  sectionContent: {
    margin: 0,
    fontSize: 14,
    color: "#4b5563",
    lineHeight: 1.6
  },
  summaryApproved: {
    color: "#059669",
    fontWeight: 600,
    fontSize: 15
  },
  summaryRejected: {
    color: "#dc2626",
    fontWeight: 600,
    fontSize: 15
  },
  summaryConditional: {
    color: "#d97706",
    fontWeight: 600,
    fontSize: 15
  },
  conditionsList: {
    display: "flex",
    flexDirection: "column",
    gap: 10
  },
  conditionItem: {
    padding: 14,
    background: "#fffbeb",
    border: "1px solid #fde68a",
    borderRadius: 8,
    fontSize: 14,
    color: "#78350f",
    lineHeight: 1.6,
    display: "flex",
    alignItems: "flex-start",
    gap: 12
  },
  conditionIcon: {
    color: "#d97706",
    fontSize: 18,
    fontWeight: "bold",
    flexShrink: 0,
    marginTop: 2
  },
  conditionText: {
    flex: 1,
    fontWeight: 500
  },
  emptyState: {
    textAlign: "center",
    padding: "60px 20px",
    background: "#fff",
    borderRadius: 12,
    boxShadow: "0 1px 3px rgba(0,0,0,0.1)"
  },
  emptyIcon: {
    fontSize: 48,
    marginBottom: 16
  },
  emptyTitle: {
    margin: "0 0 8px",
    fontSize: 20,
    color: "#111827",
    fontWeight: 600
  },
  emptyText: {
    margin: "0 0 24px",
    fontSize: 14,
    color: "#6b7280"
  },
  applyButton: {
    padding: "12px 24px",
    background: "#2563eb",
    color: "#fff",
    border: "none",
    borderRadius: 6,
    fontSize: 14,
    fontWeight: 500,
    cursor: "pointer",
    transition: "background 0.2s"
  },
  loading: {
    textAlign: "center",
    padding: 60,
    fontSize: 16,
    color: "#6b7280"
  },
  error: {
    padding: 20,
    background: "#fef2f2",
    border: "1px solid #fecaca",
    borderRadius: 8,
    color: "#dc2626",
    fontSize: 14,
    marginBottom: 16
  },
  retryButton: {
    padding: "10px 20px",
    background: "#2563eb",
    color: "#fff",
    border: "none",
    borderRadius: 6,
    fontSize: 14,
    cursor: "pointer"
  }
};
