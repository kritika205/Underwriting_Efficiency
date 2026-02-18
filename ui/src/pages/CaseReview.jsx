import { useState, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  ocrAPI,
  applicationAPI,
  crossValidationAPI,
  checkBackendHealth,
} from "../services/api";
import { formatDate, formatDateTime } from "../utils/dateUtils";
import { formatValue } from "../utils/valueFormatter";
import ValueDisplay from "../components/ValueDisplay";
import "../pages/CaseReview.css";

/* ===================== DOCUMENT MAP ===================== */
const DOC_TYPE_MAP = {
  AADHAAR: "Aadhaar",
  PAN: "PAN",
  DRIVING_LICENSE: "Driving License",
  PASSPORT: "Passport",
  PAYSLIP: "Payslip",
  CIBIL_SCORE_REPORT: "CIBIL",
  GST_RETURN: "GST Return",
  BANK_STATEMENT: "Bank Statement",
  OFFER_LETTER: "Offer Letter",
  RENT_AGREEMENT: "RENT_AGREEMENT",
  DEALER_INVOICE: "DEALER_INVOICE",
  LAND_RECORDS: "LAND_RECORDS",
  WATER_BILL: "WATER_BILL",
  ELECTRICITY_BILL: "ELECTRICITY_BILL",
  ITR_FORM: "ITR Form",
  BALANCE_SHEET: "Balance Sheet",
  BUSINESS_REGISTRATION: "Business Registration",
  MEDICAL_BILLS: "Medical Bills",
};

/* ===================== HELPERS ===================== */
const formatFieldName = (key) =>
  key
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");

/* ===================== COMPONENT ===================== */
export default function CaseReview() {
  const { caseId } = useParams();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [userName, setUserName] = useState("Loading...");
  const [documents, setDocuments] = useState({});
  const [activeDoc, setActiveDoc] = useState(null);

  /* ===================== LOAD DATA ===================== */
  useEffect(() => {
    loadCase();
  }, [caseId]);

  const loadCase = async () => {
    try {
      setLoading(true);
      setError(null);

      const health = await checkBackendHealth();
      if (!health.success) {
        setError("Backend not reachable");
        return;
      }

      /* Application - caseId is now application_id */
      try {
        const application = await applicationAPI.getById(caseId);
        setUserName(application.name || application.email || "Unknown Applicant");
      } catch {
        setUserName("Unknown Applicant");
      }

      /* OCR - caseId is now application_id */
      const extractionRes = await ocrAPI.getApplicationExtractions(caseId);
      if (!extractionRes?.all_extractions?.length) {
        setError("No documents found for this case.");
        return;
      }

      /* Validation */
      let validationMap = {};
      try {
        const validation = await crossValidationAPI.validateApplication(caseId);
        validation?.validations?.forEach((v) => {
          validationMap[v.document_id] = v;
        });
      } catch {}

      /* Group by doc */
      const grouped = {};
      extractionRes.all_extractions.forEach((doc) => {
        const name = DOC_TYPE_MAP[doc.document_type] || doc.document_type;
        // Debug logging for offer letters
        if (doc.document_type === "OFFER_LETTER") {
          console.log("Offer Letter Document:", {
            document_id: doc.document_id,
            document_type: doc.document_type,
            extracted_data: doc.extracted_data,
            has_data: !!doc.extracted_data,
            data_keys: doc.extracted_data ? Object.keys(doc.extracted_data) : [],
          });
        }
        grouped[name] = {
          extracted: doc.extracted_data || {},
          validation: validationMap[doc.document_id],
        };
      });

      setDocuments(grouped);
      setActiveDoc(Object.keys(grouped)[0]);
    } catch (err) {
      setError(err.message || "Failed to load case");
    } finally {
      setLoading(false);
    }
  };

  /* ===================== BUILD TABLE ===================== */
  const buildRows = () => {
    const doc = documents[activeDoc];
    if (!doc) return [];

    const rows = [];
    const data = doc.extracted || {};
    const validation = doc.validation || {};
    
    // Debug logging for offer letter
    if (activeDoc === "OFFER_LETTER") {
      console.log("Building rows for OFFER_LETTER:", {
        activeDoc,
        extracted: data,
        data_keys: Object.keys(data),
        data_length: Object.keys(data).length,
      });
    }
    
    const fieldStatus = {};

    validation.matches?.forEach((m) => {
      fieldStatus[m.field] = { status: "match", value: m.profile_value };
    });
    validation.mismatches?.forEach((m) => {
      fieldStatus[m.field] = { status: "mismatch", value: m.profile_value };
    });

    Object.entries(data).forEach(([key, val]) => {
      const status = fieldStatus[key];
      rows.push({
        field: formatFieldName(key),
        value: val, // Store raw value for ValueDisplay component
        match: status
          ? status.status === "match"
            ? `✓ ${formatValue(status.value)}`
            : `✗ ${formatValue(status.value)}`
          : "-",
        matchType: status?.status || "neutral",
      });
    });

    return rows;
  };

  const rows = buildRows();

  /* ===================== STATES ===================== */
  if (loading) {
    return <div className="case-loading">Loading case…</div>;
  }

  if (error) {
    return <div className="case-error">{error}</div>;
  }

  /* ===================== UI ===================== */
  return (
    <div className="case-page">
      {/* ===== HEADER ===== */}
      <div className="case-header">
        <div>
          <div className="case-title">{userName}</div>
          <div className="case-subtitle">Case ID: {caseId}</div>
        </div>

        <div className="case-actions">
          <button
            className="btn-kaara-outline"
            onClick={() => navigate(-1)}
          >
            ← Back
          </button>
          <button
            className="btn-kaara"
            onClick={() => navigate(`/admin/case/${caseId}/risk`)}
          >
            View Risk Analysis
          </button>
        </div>
      </div>

      {/* ===== DOCUMENT TABS ===== */}
      <div className="doc-tabs">
        {Object.keys(documents).map((doc) => (
          <div
            key={doc}
            className={`doc-tab ${
              activeDoc === doc ? "active" : ""
            }`}
            onClick={() => setActiveDoc(doc)}
          >
            {doc}
          </div>
        ))}
      </div>

      {/* ===== TABLE ===== */}
      <div className="case-card">
        <div className="case-table-header">
          <span>Field</span>
          <span>Extracted Value</span>
          <span>Match with Bank DB</span>
        </div>

        {rows.length === 0 ? (
          <div className="case-empty">
            No data available for this document.
            {activeDoc === "Offer Letter" && (
              <div style={{ marginTop: "10px", fontSize: "0.9em", color: "#666" }}>
                Please ensure the document has been processed through OCR extraction.
              </div>
            )}
          </div>
        ) : (
          rows.map((r, i) => (
            <div key={i} className="case-table-row">
              <span className="col-field">{r.field}</span>
              <span className="col-value">
                <ValueDisplay value={r.value} />
              </span>
              <span
                className={`col-match ${
                  r.matchType === "match"
                    ? "match-ok"
                    : r.matchType === "mismatch"
                    ? "match-bad"
                    : "match-neutral"
                }`}
              >
                {r.match}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
