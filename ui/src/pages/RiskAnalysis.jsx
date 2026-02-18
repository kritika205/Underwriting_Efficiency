import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import RiskSpeedometer from "../components/RiskSpeedometer";
import HumanDecision from "./HumanDecision";
import { riskAnalysisAPI, checkBackendHealth } from "../services/api";
import { formatValueTruncated } from "../utils/valueFormatter";
import "../pages/CaseReview.css";
// Map document types to display names
const DOC_TYPE_MAP = {
  AADHAAR: "Aadhaar",
  PAN: "PAN",
  DRIVING_LICENSE: "Driving License",
  PASSPORT: "Passport",
  PAYSLIP: "Payslip",
  CIBIL_SCORE_REPORT: "CIBIL",
  GST_RETURN: "GST Return",
  MEDICAL_BILL: "Medical Bills",
  BANK_STATEMENT: "Bank Statement",
  ADDRESS_PROOF: "Address Proof",
};
 
// Helper to categorize anomalies by type
const categorizeAnomaly = (anomaly) => {
  const type = (anomaly.type || "").toLowerCase();
  const field = (anomaly.field || "").toLowerCase();

  // Identity-related flags
  if (type.includes("name") || type.includes("identity") || type.includes("pan") ||
      type.includes("aadhaar") || type.includes("address") || type.includes("phone") ||
      type.includes("dob") || type.includes("date_of_birth") || field.includes("name") ||
      field.includes("address") || field.includes("phone")) {
    return "Identity Flags";
  }

  // Financial behavior flags - includes bank statement anomalies
  if (type.includes("income") || type.includes("salary") || type.includes("credit") ||
      type.includes("utilization") || type.includes("inquiry") || type.includes("cibil") ||
      type.includes("dti") || type.includes("debt") || type.includes("emi") ||
      type.includes("obligation") || type.includes("liquidity") || type.includes("balance") ||
      type.includes("round_tripping") || type.includes("transaction") ||
      type.includes("fraud") || type.includes("hidden") ||
      field.includes("income") || field.includes("salary") || field.includes("credit") ||
      field.includes("dti") || field.includes("transactions") || field.includes("obligations") ||
      field.includes("balance")) {
    return "Financial Behaviour Flags";
  }

  // Document quality flags
  if (type.includes("document") || type.includes("tamper") || type.includes("quality") ||
      type.includes("metadata") || type.includes("employer") || type.includes("inconsistent") ||
      type.includes("missing") || type.includes("gap") || type.includes("sequence_error")) {
    return "Document Flags";
  }

  // Default category
  return "Other Flags";
};
 
// Transform backend anomalies to frontend format
const transformAnomalies = (analyses) => {
  const flagsByCategory = {};
  const allAnomaliesBySeverity = {
    critical: [],
    high: [],
    medium: [],
    low: []
  };
 
  // First, collect all flag items
  analyses.forEach((analysis) => {
    const anomalies = analysis.anomalies || {};
    const documentType = DOC_TYPE_MAP[analysis.document_type] || analysis.document_type || "Unknown Document";
    const documentId = analysis.document_id || "unknown";
   
    // Process each severity level
    ["critical_anomalies", "high_anomalies", "medium_anomalies", "low_anomalies"].forEach((severityKey) => {
      const anomaliesList = anomalies[severityKey] || [];
      const severity = severityKey.replace("_anomalies", "");
     
      anomaliesList.forEach((anomaly, index) => {
        const category = categorizeAnomaly(anomaly);
       
        // Create flag item
        const title = anomaly.type
          ? anomaly.type.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase())
          : "Anomaly Detected";
       
        const desc = anomaly.reason || `Anomaly in ${anomaly.field || "document"}`;
        const reason = anomaly.reason || `Detected in ${documentType}: ${anomaly.value || "N/A"}`;
       
        const flagItem = {
          title,
          desc,
          severity,
          reason,
          documentType,
          documentId,
          field: anomaly.field || "N/A",
          value: anomaly.value || "N/A",
          type: anomaly.type || "unknown",
          // Add unique ID to prevent deduplication issues
          uniqueId: `${documentId}-${severity}-${index}-${anomaly.type || 'unknown'}`
        };
       
        if (!flagsByCategory[category]) {
          flagsByCategory[category] = [];
        }
       
        flagsByCategory[category].push(flagItem);
        allAnomaliesBySeverity[severity].push(flagItem);
      });
    });
  });
 
  // Deduplicate flags - remove duplicates based on type, field, value, and documentId
  const deduplicateFlags = (items) => {
    const seen = new Set();
    const deduplicated = [];
    
    items.forEach((item) => {
      // Create a unique key based on type, field, value, and documentId
      const key = `${item.type}-${item.field}-${item.value}-${item.documentId}`.toLowerCase();
      
      if (!seen.has(key)) {
        seen.add(key);
        deduplicated.push(item);
      }
    });
    
    return deduplicated;
  };

  // Convert to array format - deduplicate all flags
  const categorizedFlags = Object.entries(flagsByCategory).map(([category, items]) => {
    // Deduplicate all categories to prevent showing the same anomaly multiple times
    const processedItems = deduplicateFlags(items);
    
    return {
      category,
      items: processedItems,
      count: processedItems.length
    };
  });

  // Rebuild bySeverity from deduplicated categorized flags to ensure consistency
  const deduplicatedBySeverity = {
    critical: [],
    high: [],
    medium: [],
    low: []
  };
  
  // Collect all deduplicated items from categorized flags
  categorizedFlags.forEach(({ items }) => {
    items.forEach((item) => {
      deduplicatedBySeverity[item.severity].push(item);
    });
  });

  return {
    categorized: categorizedFlags,
    bySeverity: deduplicatedBySeverity,
    total: Object.values(deduplicatedBySeverity).reduce((sum, arr) => sum + arr.length, 0)
  };
};
 
 
export default function RiskAssessment(){
  const { caseId } = useParams();
  const navigate = useNavigate();
  const [open, setOpen] = useState(null);
  const [showDecision, setShowDecision] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [flags, setFlags] = useState({ categorized: [], bySeverity: {}, total: 0 });
  const [score, setScore] = useState(0);
  const [riskSummary, setRiskSummary] = useState(null);
  const [backendConnected, setBackendConnected] = useState(true);
  const [viewMode, setViewMode] = useState("categorized"); // "categorized" or "bySeverity"
 
  useEffect(() => {
    loadRiskAnalysis();
  }, [caseId]);
 
  const loadRiskAnalysis = async () => {
    try {
      setLoading(true);
      setError(null);
 
      // Check backend connection
      const healthCheck = await checkBackendHealth();
      if (!healthCheck.success) {
        setBackendConnected(false);
        setError("Cannot connect to backend. Please ensure the server is running.");
        setLoading(false);
        return;
      }
      setBackendConnected(true);
 
      // Get risk summary for application (caseId is now application_id)
      const summary = await riskAnalysisAPI.getApplicationRiskSummary(caseId);
     
      if (!summary || summary.total_documents === 0) {
        setError("No risk analysis data found. Please run risk analysis on documents first.");
        setFlags({ categorized: [], bySeverity: {}, total: 0 });
        setScore(0);
        setLoading(false);
        return;
      }
 
      setRiskSummary(summary);
 
      // Use final_risk_score (improved logic that accounts for anomaly count)
      // Fallback to average_risk_score for backwards compatibility
      const finalScore = summary.final_risk_score || summary.average_risk_score || 0;
      setScore(finalScore);
 
      // Fetch individual risk analyses for all documents to get detailed anomalies
      const analysesPromises = (summary.analyses || []).map(async (analysis) => {
        try {
          return await riskAnalysisAPI.getByDocumentId(analysis.document_id);
        } catch (err) {
          console.warn(`Could not fetch risk analysis for ${analysis.document_id}:`, err);
          return null;
        }
      });
 
      const analyses = (await Promise.all(analysesPromises)).filter(a => a !== null);
 
      if (analyses.length === 0) {
        setError("Could not load risk analysis details. Please try again.");
        setFlags({ categorized: [], bySeverity: {}, total: 0 });
        setScore(0);
        setLoading(false);
        return;
      }
 
      // Transform anomalies to flags format
      const transformedFlags = transformAnomalies(analyses);
      setFlags(transformedFlags);
 
    } catch (err) {
      console.error("Error loading risk analysis:", err);
      setError(err.response?.data?.detail || err.message || "Failed to load risk analysis.");
    } finally {
      setLoading(false);
    }
  };
 
  if (showDecision) {
    return (
      <HumanDecision
        caseId={caseId}
        riskScore={score}   // 👈 ADD THIS
        onBack={() => setShowDecision(false)}
      />
    );
  }
  
 
  if (loading) {
    return (
      <div className="page container">
        <div style={s.loading}>Loading risk analysis...</div>
      </div>
    );
  }
 
  if (error && !backendConnected) {
    return (
      <div className="page container">
        <div style={s.error}>
          {error}
          <button className="btn btn-ghost" onClick={loadRiskAnalysis}>
            Retry
          </button>
        </div>
      </div>
    );
  }
 
  if (error || flags.total === 0) {
    return (
      <div className="page container">
       <div className="case-actions">
          <button
            className="btn-kaara-outline"
            onClick={() => navigate(-1)}
          >
            ← Back
          </button>
          </div>
        <div style={s.error}>
          {error || "No risk flags found for this case."}
        </div>
      </div>
    );
  }
 
  return(
    <div className="page container">
      <span style={s.back} onClick={()=>navigate(-1)}>← Back</span>
 
      <div className="card risk-header" style={{padding:20}}>
        <div>
          <h2>Risk Assessment Score</h2>
          <p>Case ID: {caseId} · Underwriter: Sarah Mitchell</p>
          {riskSummary && (
            <p style={{ fontSize: 13, color: "#6b7280", marginTop: 4 }}>
              Risk Score: {riskSummary.final_risk_score || riskSummary.average_risk_score}
              {riskSummary.final_risk_score && riskSummary.final_risk_score !== riskSummary.average_risk_score && (
                <span style={{ fontSize: 11, color: "#9ca3af" }}> (avg: {riskSummary.average_risk_score}, max: {riskSummary.max_risk_score})</span>
              )} ·
              Total Anomalies: {flags.total} ({flags.bySeverity.critical?.length || 0} Critical, {flags.bySeverity.high?.length || 0} High, {flags.bySeverity.medium?.length || 0} Medium, {flags.bySeverity.low?.length || 0} Low) ·
              Documents Analyzed: {riskSummary.total_documents}
            </p>
          )}
         
          <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
            <button
              style={{
                ...s.viewModeBtn,
                background: viewMode === "categorized" ? "#dc2626" : "#e5e7eb",
                color: viewMode === "categorized" ? "#fff" : "#374151"
              }}
              onClick={() => setViewMode("categorized")}
            >
              By Category
            </button>
            <button
              style={{
                ...s.viewModeBtn,
                background: viewMode === "bySeverity" ? "#dc2626" : "#e5e7eb",
                color: viewMode === "bySeverity" ? "#fff" : "#374151"
              }}
              onClick={() => setViewMode("bySeverity")}
            >
              By Severity
            </button>
          </div>
 
          {/* <table style={s.table}>
            <tbody>
              <tr><td>Critical Flag</td><td>25 pts</td></tr>
              <tr><td>High Flag</td><td>15 pts</td></tr>
              <tr><td>Medium Flag</td><td>8 pts</td></tr>
              <tr><td>Low Flag</td><td>3 pts</td></tr>
            </tbody>
          </table> */}
        </div>
 
        <div style={{textAlign:"right"}}>
          <button
            style={s.decisionBtn}
            onClick={() => setShowDecision(true)}
          >
            Proceed to Decision
          </button>
 
          <RiskSpeedometer score={score}/>
        </div>
      </div>
 
      {viewMode === "categorized" ? (
        // Categorized view
        flags.categorized.map((block, i) => (
          <div key={i} style={{ marginTop: 24 }}>
            <h3 style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span>{block.category}</span>
              <span style={{ fontSize: 14, color: "#6b7280", fontWeight: "normal" }}>
                {block.count} {block.count === 1 ? "anomaly" : "anomalies"} 
              </span>
            </h3>
            <div style={s.grid}>
              {block.items.map((f, j) => {
                const uniqueKey = `${i}-${j}-${f.uniqueId}`;
                return (
                  <div key={uniqueKey} style={{...s.card,...s[f.severity]}}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start", marginBottom: 8 }}>
                      <b style={{ flex: 1 }}>{f.title}</b>
                      <span style={{
                        ...s.severityBadge,
                        ...s[`${f.severity}Badge`]
                      }}>
                        {f.severity.toUpperCase()}
                      </span>
                    </div>
                    <p style={{ marginBottom: 8 }}>{f.desc}</p>
                    {f.documentType && (
                      <p style={{ fontSize: 11, color: "#6b7280", marginBottom: 4 }}>
                        📄 Document: {f.documentType}
                      </p>
                    )}
                    {f.field && f.field !== "N/A" && (
                      <p style={{ fontSize: 11, color: "#6b7280", marginBottom: 4 }}>
                        Field: {f.field}
                      </p>
                    )}
                    {f.value && f.value !== "N/A" && (
                      <p style={{ fontSize: 11, color: "#6b7280", marginBottom: 8 }}>
                        Value: {formatValueTruncated(f.value, 50)}
                      </p>
                    )}
 
                    <span onClick={()=>setOpen(open===uniqueKey?null:uniqueKey)} style={s.explain}>
                      {open===uniqueKey ? "Hide Details ▴" : "Show Details ▾"}
                    </span>
 
                    {open===uniqueKey && (
                      <div style={s.reason}>
                        <div><strong>Reason:</strong> {f.reason}</div>
                        {f.type && <div style={{ marginTop: 4 }}><strong>Type:</strong> {f.type}</div>}
                        {f.documentId && <div style={{ marginTop: 4 }}><strong>Document ID:</strong> {f.documentId}</div>}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ))
      ) : (
        // By Severity view
        ["critical", "high", "medium", "low"].map((severity) => {
          const severityAnomalies = flags.bySeverity[severity] || [];
          if (severityAnomalies.length === 0) return null;
         
          return (
            <div key={severity} style={{ marginTop: 24 }}>
              <h3 style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ textTransform: "capitalize" }}>{severity} Severity Anomalies</span>
                <span style={{ fontSize: 14, color: "#6b7280", fontWeight: "normal" }}>
                  {severityAnomalies.length} {severityAnomalies.length=== 1 ? "anomaly" : "anomalies"}
                </span>
              </h3>
              <div style={s.grid}>
                {severityAnomalies.map((f, j) => {
                  const uniqueKey = `severity-${severity}-${j}-${f.uniqueId}`;
                  return (
                    <div key={uniqueKey} style={{...s.card,...s[f.severity]}}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start", marginBottom: 8 }}>
                        <b style={{ flex: 1 }}>{f.title}</b>
                        <span style={{
                          ...s.severityBadge,
                          ...s[`${f.severity}Badge`]
                        }}>
                          {f.severity.toUpperCase()}
                        </span>
                      </div>
                      <p style={{ marginBottom: 8 }}>{f.desc}</p>
                      {f.documentType && (
                        <p style={{ fontSize: 11, color: "#6b7280", marginBottom: 4 }}>
                          📄 Document: {f.documentType}
                        </p>
                      )}
                      {f.field && f.field !== "N/A" && (
                        <p style={{ fontSize: 11, color: "#6b7280", marginBottom: 4 }}>
                          Field: {f.field}
                        </p>
                      )}
                      {f.value && f.value !== "N/A" && (
                        <p style={{ fontSize: 11, color: "#6b7280", marginBottom: 8 }}>
                          Value: {String(f.value).length > 50 ? String(f.value).substring(0, 50) + "..." : f.value}
                        </p>
                      )}
 
                      <span onClick={()=>setOpen(open===uniqueKey?null:uniqueKey)} style={s.explain}>
                        {open===uniqueKey ? "Hide Details ▴" : "Show Details ▾"}
                      </span>
 
                      {open===uniqueKey && (
                        <div style={s.reason}>
                          <div><strong>Reason:</strong> {f.reason}</div>
                          {f.type && <div style={{ marginTop: 4 }}><strong>Type:</strong> {f.type}</div>}
                          {f.documentId && <div style={{ marginTop: 4 }}><strong>Document ID:</strong> {f.documentId}</div>}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })
      )}
    </div>
  )
}
 
const s={
  page:{padding:30,background:"#f8fafc"},
  back:{marginBottom: 12,
    color: "#dc2626",
    padding: "6px 14px",
    cursor: "pointer",
    fontSize: 13,
    fontWeight: 500,},
  header:{background:"#fff",padding:20,borderRadius:12,display:"flex",justifyContent:"space-between"},
  table:{marginTop:10,fontSize:13},
  grid:{display:"grid",gridTemplateColumns:"repeat(3,1fr)",gap:20},
  card:{padding:16,borderRadius:10},
  critical:{border:"1px solid #fecaca",background:"#fff1f2"},
  high:{border:"1px solid #fecaca",background:"#fff1f2"},
  medium:{border:"1px solid #fde68a",background:"#fffbeb"},
  low:{border:"1px solid #bbf7d0",background:"#ecfdf5"},
  explain:{color:"#2563eb",cursor:"pointer"},
  reason:{marginTop:8,fontSize:13,color:"#374151"},
 
  decisionBtn:{
    marginBottom:12,
    background:"#dc2626",
    color:"#fff",
    border:"none",
    padding:"8px 18px",
    borderRadius:6,
    cursor:"pointer",
    fontWeight:500
  },
  loading: {
    textAlign: "center",
    padding: 40,
    fontSize: 16,
    color: "#6b7280",
  },
  error: {
    padding: 16,
    background: "#fee2e2",
    color: "#991b1b",
    borderRadius: 8,
    margin: 20,
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  retryBtn: {
    padding: "6px 12px",
    background: "#dc2626",
    color: "#fff",
    border: "none",
    borderRadius: 6,
    cursor: "pointer",
    fontSize: 12,
  },
  viewModeBtn: {
    padding: "6px 12px",
    border: "none",
    borderRadius: 6,
    cursor: "pointer",
    fontSize: 13,
    fontWeight: 500,
  },
  severityBadge: {
    padding: "2px 8px",
    borderRadius: 4,
    fontSize: 10,
    fontWeight: 600,
    textTransform: "uppercase",
  },
  criticalBadge: {
    background: "#fee2e2",
    color: "#991b1b",
  },
  highBadge: {
    background: "#fee2e2",
    color: "#991b1b",
  },
  mediumBadge: {
    background: "#fef3c7",
    color: "#92400e",
  },
  lowBadge: {
    background: "#dcfce7",
    color: "#166534",
  },
  backBtn: {
    
  }

 
};