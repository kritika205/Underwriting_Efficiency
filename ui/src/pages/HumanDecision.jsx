import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { applicationAPI, checkBackendHealth } from "../services/api";

export default function DecisionPage({ riskScore = 90 }) {
  const { caseId } = useParams();
  const navigate = useNavigate();

  const [decision, setDecision] = useState(null);
  const [aiDecision, setAiDecision] = useState(null);
  const [aiSuggestion, setAiSuggestion] = useState(null);
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const [conditions, setConditions] = useState({
    reduce: false,
    employer: false,
    bank: false,
  });

  const toggleCondition = (k) =>
    setConditions((p) => ({ ...p, [k]: !p[k] }));


  /* ===== AI AUTO SUGGESTION ===== */
  useEffect(() => {
    if (riskScore >= 80) {
      setDecision("reject");
      setAiDecision("reject");
      setAiSuggestion("Rejected due to high risk score (>80)");
    } else if (riskScore >= 60) {
      setDecision("conditional");
      setAiDecision("conditional");
      setAiSuggestion("Conditionally approved due to moderate risk (60–79)");
    } else {
      setDecision("approve");
      setAiDecision("approve");
      setAiSuggestion("Approved due to low risk score (<60)");
    }
  }, [riskScore]);

  const submitDecision = async () => {
    try {
      setSubmitting(true);
      setError(null);

      const health = await checkBackendHealth();
      if (!health.success) {
        setError("Backend not reachable");
        return;
      }

      let caseStatus = "In Review";
      if (decision === "approve") caseStatus = "Approved";
      if (decision === "conditional") caseStatus = "Conditionally Approved";
      if (decision === "reject") caseStatus = "Rejected";

      await applicationAPI.updateStatus(caseId, {
        status: caseStatus,
        decision,
        notes,
        conditions,
      });

      navigate("/admin");
    } catch (err) {
      setError(err.message || "Failed to submit decision");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={s.page}>
      <div style={s.card}>
        <div style={s.back} onClick={() => navigate(-1)}>
          ← Back to risk analysis
        </div>

        <h2>Decision</h2>
        <p style={s.subtitle}>Final underwriting action</p>

        <div style={s.layout}>
          {/* ===== LEFT ===== */}
          <div>
            {/* OPTIONS */}
            {[
              { k: "approve", t: "Approve", d: "Full approval without conditions" },
              {
                k: "conditional",
                t: "Approve with conditions",
                d: "Reduced amount or additional verification",
              },
              { k: "reject", t: "Reject", d: "Decline the application" },
            ].map((o) => (
              <div
                key={o.k}
                onClick={() => setDecision(o.k)}
                style={{
                  ...s.option,
                  ...(decision === o.k ? s.active : {}),
                  ...(decision === o.k && s[o.k]),
                }}
              >
                <div style={s.optionText}>
                  <div style={s.optionTitle}>{o.t}</div>
                  <div style={s.optionDesc}>{o.d}</div>
                </div>
              </div>
            ))}

            {/* ===== CONDITIONS (ONLY FOR CONDITIONAL) ===== */}
            {decision === "conditional" && (
              <div style={s.conditionsBox}>
                <div style={s.conditionsTitle}>Conditions</div>
                <div style={s.conditionPills}>
                  {[
                    ["reduce", "Reduce loan by 30%"],
                    ["employer", "Employer verification"],
                    ["bank", "Bank statements"],
                  ].map(([k, label]) => (
                    <div
                      key={k}
                      onClick={() => toggleCondition(k)}
                      style={{
                        ...s.conditionPill,
                        ...(conditions[k] ? s.pillActive : {}),
                      }}
                    >
                      {label}
                    </div>
                  ))}
                </div>
              </div>
            )}

            <label style={s.label}>Notes</label>
            <textarea
              style={s.textarea}
              placeholder="Add reviewer comments"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />

            {error && <div style={s.error}>{error}</div>}

            <button
              style={s.primaryBtn}
              disabled={submitting}
              onClick={submitDecision}
            >
              {submitting ? "Submitting…" : "Submit decision"}
            </button>
          </div>

          {/* ===== RIGHT : AI ===== */}
          <div>
            {aiSuggestion && (
              <div style={s.aiCard}>
                <div style={s.aiHeader}>🤖 AI Recommendation</div>
                <div style={s.aiBody}>
                  <strong>Suggested action:</strong>
                  <span style={s.aiDecision}>
                    {aiDecision === "reject"
                      ? "Reject"
                      : aiDecision === "conditional"
                      ? "Conditional"
                      : "Approve"}
                  </span>

                  <p style={s.aiReason}>{aiSuggestion}</p>

                  <ul style={s.aiPoints}>
                    <li>Risk score: {riskScore}</li>
                    <li>Critical anomaly count high</li>
                    <li>Identity / document inconsistency</li>
                  </ul>

                  <div style={s.aiFooter}>
                    Human reviewer can override this decision
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ================= STYLES ================= */

const s = {
  page: {
    minHeight: "100vh",
    background: "#f4f4f4",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
  },

  card: {
    width: 920,
    maxHeight: "90vh",
    background: "#fff",
    border: "1px solid #e0e0e0",
    borderRadius: 8,
    padding: 24,
    overflowY: "auto",
  },
  
  back: { fontSize: 13, color: "#525252", cursor: "pointer", marginBottom: 8 },
  subtitle: { fontSize: 13, color: "#6f6f6f", marginBottom: 16 },

  layout: { display: "grid", gridTemplateColumns: "1.3fr 0.7fr", gap: 20 },

  option: {
    borderWidth: 1,
    borderStyle: "solid",
    borderColor: "#d1d1d1",
    borderRadius: 6,
    padding: 14,
    marginBottom: 10,
    cursor: "pointer",
    transition: "all 0.18s ease",
  },

  active: {
    transform: "translateY(-2px)",
    boxShadow: "0 4px 10px rgba(0,0,0,0.08)",
  },

  approve: { borderColor: "#24a148", background: "rgba(36,161,72,0.08)" },
  conditional: { borderColor: "#f1c21b", background: "rgba(241,194,27,0.15)" },
  reject: { borderColor: "#da1e28", background: "rgba(218,30,40,0.08)" },

  optionText: { display: "flex", flexDirection: "column", gap: 4 },
  optionTitle: { fontSize: 15, fontWeight: 600 },
  optionDesc: { fontSize: 13, color: "#6f6f6f" },

  conditionsBox: {
    border: "1px solid #f1c21b",
    background: "rgba(241,194,27,0.08)",
    borderRadius: 6,
    padding: 12,
    marginBottom: 12,
  },

  conditionsTitle: { fontSize: 13, fontWeight: 600, marginBottom: 8 },

  conditionPills: { display: "flex", gap: 8, flexWrap: "wrap" },

  conditionPill: {
    padding: "6px 12px",
    borderRadius: 999,
    border: "1px solid #d1d1d1",
    cursor: "pointer",
    fontSize: 12,
    background: "#fff",
  },

  pillActive: {
    background: "#da1e28",
    borderColor: "#da1e28",
    color: "#fff",
  },

  label: { fontSize: 13, marginBottom: 6 },
  textarea: { width: "100%", minHeight: 80, resize: "none", padding: 10 },

  primaryBtn: {
    marginTop: 12,
    width: "100%",
    padding: "10px 16px",
    background: "#da1e28",
    color: "#fff",
    border: "none",
    borderRadius: 4,
    fontWeight: 600,
    cursor: "pointer",
  },

  error: { fontSize: 13, color: "#da1e28" },

  aiCard: { border: "1px solid #e0e0e0", borderRadius: 8, background: "#fafafa" },
  aiHeader: { padding: 10, fontWeight: 600, background: "#f4f4f4" },
  aiBody: { padding: 14 },
  aiDecision: {
    marginLeft: 8,
    padding: "2px 8px",
    borderRadius: 999,
    background: "#fee2e2",
    color: "#991b1b",
    fontWeight: 600,
  },
  aiReason: { marginTop: 8 },
  aiPoints: { marginTop: 8, paddingLeft: 18 },
  aiFooter: { marginTop: 12, fontSize: 11, fontStyle: "italic" },
};
