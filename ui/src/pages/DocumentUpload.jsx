import { useState, useEffect, useRef } from "react";
import {
  COMMON_DOCUMENTS,
  APPLICANT_DOCUMENTS,
  LOAN_DOCUMENTS,
  DOCUMENT_TYPE_MAP,
} from "../config/documentConfig";
import { documentAPI, ocrAPI, checkBackendHealth } from "../services/api";

// Reverse mapping: Backend document type -> UI document IDs (can be multiple)
const BACKEND_TO_UI_MAPPING = {};
Object.entries(DOCUMENT_TYPE_MAP).forEach(([uiId, backendType]) => {
  if (!BACKEND_TO_UI_MAPPING[backendType]) {
    BACKEND_TO_UI_MAPPING[backendType] = [];
  }
  BACKEND_TO_UI_MAPPING[backendType].push(uiId);
});

// Helper to find UI document ID from backend document type
const findUIDocumentId = (backendType, requiredDocs) => {
  if (!backendType) return null;
  const possibleIds = BACKEND_TO_UI_MAPPING[backendType] || [];
  
  // Find the first matching ID in required documents
  for (const doc of requiredDocs) {
    if (possibleIds.includes(doc.id)) {
      return doc.id;
    }
  }
  
  // If no exact match, return first possible ID (for documents not in required list)
  return possibleIds[0] || null;
};

export default function DocumentUpload({ applicantData }) {
  const [docs, setDocs] = useState({}); // Maps UI doc ID -> { file, documentId, uploaded: true }
  const [uploading, setUploading] = useState({}); // Maps document_id -> true/false
  const [uploadStatus, setUploadStatus] = useState({}); // Maps UI doc ID -> "processing" | "processed" | "error"
  const [documentErrors, setDocumentErrors] = useState({}); // Maps UI doc ID -> [errors]
  const [error, setError] = useState(null);
  const [backendConnected, setBackendConnected] = useState(true);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef(null);
  const { loanType, applicantType, userId, applicationId } = applicantData || {};

  /* ================= GET REQUIRED DOCUMENTS ================= */
  const getRequiredDocuments = () => {
    const required = [];
    
    // Identity documents (at least one)
    required.push(...COMMON_DOCUMENTS.identity.map(d => ({ ...d, category: "Identity Proof", required: false })));
    
    // Address documents (at least one)
    required.push(...COMMON_DOCUMENTS.address.map(d => ({ ...d, category: "Address Proof", required: false })));
    
    // Credit documents (at least one)
    required.push(...COMMON_DOCUMENTS.credit.map(d => ({ ...d, category: "Credit Documents", required: false })));
    
    // Applicant type documents
    if (applicantType && APPLICANT_DOCUMENTS[applicantType]) {
      required.push(...APPLICANT_DOCUMENTS[applicantType].map(d => ({ ...d, category: "Applicant Documents", required: false })));
    }
    
    // Loan type documents
    if (loanType && LOAN_DOCUMENTS[loanType]) {
      required.push(...LOAN_DOCUMENTS[loanType].map(d => ({ ...d, category: `${loanType} Documents`, required: false })));
    }
    
    return required;
  };

  const requiredDocuments = getRequiredDocuments();

  /* ================= INITIAL BACKEND CHECK ================= */
  useEffect(() => {
    const checkConnection = async () => {
      try {
        const healthCheck = await checkBackendHealth(false);
        setBackendConnected(healthCheck.success);
        if (!healthCheck.success && !healthCheck.error?.includes('timeout')) {
          setError(healthCheck.error || "Cannot connect to backend. Please ensure the server is running on http://localhost:8000");
        } else {
          setError(null);
        }
      } catch (err) {
        console.error("Initial backend check failed:", err);
        setBackendConnected(true);
      }
    };
    checkConnection();
  }, []);

  /* ================= HELPER FUNCTIONS ================= */
  const isAnyUploaded = (documents) => {
    if (!documents || documents.length === 0) return true;
    return documents.some((doc) => docs[doc.id]);
  };

  const allProcessed = () => {
    const uploadedDocs = requiredDocuments.filter(doc => docs[doc.id]);
    if (uploadedDocs.length === 0) return false;
    return uploadedDocs.every(doc => {
      const status = uploadStatus[doc.id];
      return status === "processed" || status === "error";
    });
  };

  const hasErrors = Object.keys(documentErrors).length > 0;

  // Group required documents by category
  const documentsByCategory = requiredDocuments.reduce((acc, doc) => {
    if (!acc[doc.category]) {
      acc[doc.category] = [];
    }
    acc[doc.category].push(doc);
    return acc;
  }, {});

  // Validation: Check if at least one document from each category is uploaded
  const identityValid = isAnyUploaded(COMMON_DOCUMENTS.identity);
  const addressValid = isAnyUploaded(COMMON_DOCUMENTS.address);
  const creditValid = isAnyUploaded(COMMON_DOCUMENTS.credit);
  const applicantDocsValid = isAnyUploaded(APPLICANT_DOCUMENTS?.[applicantType] || []);
  const loanDocsValid = isAnyUploaded(LOAN_DOCUMENTS?.[loanType] || []);

  const allUploaded = identityValid && addressValid && creditValid && applicantDocsValid && loanDocsValid;

  /* ================= FILE ACTIONS ================= */
  const handleFileUpload = async (file, uiDocumentId = null) => {
    if (!file) return;
  
    const tempId = uiDocumentId || `temp_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  
    // ✅ show file immediately
    setDocs((prev) => ({
      ...prev,
      [tempId]: {
        file,
        uploaded: true,
        temp: true
      }
    }));
  
    // ✅ show Uploading...
    setUploadStatus((prev) => ({
      ...prev,
      [tempId]: "uploading"
    }));
  
    try {
      setUploading((prev) => ({ ...prev, [tempId]: true }));
  

      // Upload without expected document type - let AI classify it
      const uploadResult = await documentAPI.upload(file, userId, applicationId, null);
      
      setBackendConnected(true);
      setError(null);
      
      if (uploadResult && uploadResult.document_id) {
        // Set temporary status
        setUploadStatus((prev) => ({
          ...prev,
          [tempId]: "processing"
        }));

        // Trigger OCR extraction (which includes classification)
        try {
          await ocrAPI.extract(uploadResult.document_id);
          
          // Fetch document to get classified type and validation errors
          const documentInfo = await documentAPI.getById(uploadResult.document_id);
          const classifiedType = documentInfo.document_type;
          const errors = documentInfo.validation_errors || [];
          
          // Find matching UI document ID from classified type
          const matchedDocId = uiDocumentId || findUIDocumentId(classifiedType, requiredDocuments);
          
          if (matchedDocId) {
            // Remove temp entry and add with matched ID
            setUploadStatus((prev) => {
              const copy = { ...prev };
              delete copy[tempId];
              copy[matchedDocId] = "processing";
              return copy;
            });
            
            setDocs((prev) => {
              const copy = { ...prev };
              delete copy[tempId];
              copy[matchedDocId] = {
                file,
                documentId: uploadResult.document_id,
                uploaded: true,
                classifiedType: classifiedType
              };
              return copy;
            });

            // Check for document type mismatch errors
            const typeMismatchErrors = errors.filter(e => 
              e && e.toLowerCase().includes("document type mismatch")
            );
            
            if (typeMismatchErrors.length > 0) {
              setDocumentErrors((prev) => ({
                ...prev,
                [matchedDocId]: typeMismatchErrors
              }));
              setUploadStatus((prev) => ({
                ...prev,
                [matchedDocId]: "error"
              }));
            } else {
              setUploadStatus((prev) => ({
                ...prev,
                [matchedDocId]: "processed"
              }));
            }
          } else {
            // Document type not in required list - show as uploaded but not matched
            setUploadStatus((prev) => {
              const copy = { ...prev };
              delete copy[tempId];
              copy[tempId] = "processed";
              return copy;
            });
            setDocs((prev) => {
              const copy = { ...prev };
              delete copy[tempId];
              copy[tempId] = {
                file,
                documentId: uploadResult.document_id,
                uploaded: true,
                classifiedType: classifiedType,
                unmatched: true
              };
              return copy;
            });
          }
        } catch (extractErr) {
          if (extractErr.code === 'ECONNABORTED' || extractErr.message?.includes('timeout')) {
            console.warn("OCR extraction timed out:", extractErr.message);
            setError("OCR extraction is taking longer than expected. Your document was uploaded successfully. The extraction may continue in the background.");
            setUploadStatus((prev) => {
              const copy = { ...prev };
              delete copy[tempId];
              copy[tempId] = "uploaded";
              return copy;
            });
          } else {
            console.warn("OCR extraction failed:", extractErr);
            setUploadStatus((prev) => {
              const copy = { ...prev };
              delete copy[tempId];
              copy[tempId] = "error";
              return copy;
            });
            setError("Failed to process document. Please try again.");
          }
        }
      } else {
        throw new Error("Upload failed: No document ID returned");
      }
    } catch (err) {
      console.error("Upload error:", err);
      
      if (err.code === 'ECONNREFUSED' || err.message?.includes('Network Error') || err.message?.includes('ERR_NETWORK') || (!err.response && err.request)) {
        setBackendConnected(false);
        setError("Cannot connect to backend. Please ensure the server is running on http://localhost:8000");
      } else if (err.code === 'ECONNABORTED' || err.message?.includes('timeout')) {
        setBackendConnected(false);
        setError("Upload request timed out. The server may be slow or processing a large file. Please try again.");
      } else {
        setError(err.response?.data?.detail || err.message || "Failed to upload document.");
      }
      
      setUploadStatus((prev) => {
        const copy = { ...prev };
        delete copy[tempId];
        copy[tempId] = "error";
        return copy;
      });
    } finally {
      setUploading((prev) => {
        const copy = { ...prev };
        delete copy[tempId];
        return copy;
      });
    }
  };

  const handleDelete = async (id) => {
    const doc = docs[id];
    if (doc && doc.documentId) {
      try {
        await documentAPI.delete(doc.documentId);
      } catch (err) {
        console.warn("Delete error:", err);
      }
    }
    
    setDocs((prev) => {
      const copy = { ...prev };
      delete copy[id];
      return copy;
    });
    setUploadStatus((prev) => {
      const copy = { ...prev };
      delete copy[id];
      return copy;
    });
    setDocumentErrors((prev) => {
      const copy = { ...prev };
      delete copy[id];
      return copy;
    });
  };

  const viewFile = (file) => {
    if (file && file.file) {
      window.open(URL.createObjectURL(file.file), "_blank");
    } else if (file instanceof File) {
      window.open(URL.createObjectURL(file), "_blank");
    }
  };

  /* ================= DRAG & DROP HANDLERS ================= */
  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileUpload(e.dataTransfer.files[0]);
    }
  };

  const handleFileInput = (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFileUpload(e.target.files[0]);
      e.target.value = ""; // Reset input
    }
  };

  /* ================= SUBMIT ================= */
  const handleSubmit = () => {
    if (!allUploaded) return;
    
    if (!allProcessed()) {
      alert("⏳ Please wait for all documents to finish processing before submitting.");
      return;
    }
    
    if (hasErrors) {
      const errorCount = Object.values(documentErrors).flat().length;
      alert(
        `❌ Error: ${errorCount} document type mismatch(es) detected.\n\n` +
        `Please fix the document type errors before submitting.`
      );
      return;
    }

    const confirm = window.confirm(
      "Please confirm that all uploaded documents are valid, clear, and correct.\n\nOnce submitted, changes cannot be made."
    );

    if (confirm) {
      alert("✅ Documents submitted successfully!");
      window.location.href = "/";
    }
  };

  /* ================= RENDER ================= */
  return (
    <div style={styles.wrapper}>
      {/* <div style={styles.header}>
        <h2 style={styles.title}>Document Upload</h2>
        <p style={styles.subtitle}>AI-Powered Document Processing - Simply upload your documents and our AI will automatically identify and validate them</p>
      </div> */}
      
      {error && !backendConnected && (
        <div style={styles.error}>
          {error}
        </div>
      )}
      
      {error && backendConnected && (
        <div style={styles.warningMsg}>
          {error}
        </div>
      )}

      <div style={styles.container}>
        {/* LEFT: Unified Upload Area */}
        <div style={styles.uploadSection}>
          <div style={styles.uploadHeader}>
            <h3 style={styles.uploadTitle}>Upload Documents</h3>
            <p style={styles.uploadSubtitle}>Drag & drop files here or click to browse</p>
          </div>
          
          <div
            style={{
              ...styles.dropZone,
              ...(dragActive ? styles.dropZoneActive : {}),
            }}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              hidden
              multiple
              accept=".pdf,.jpg,.jpeg,.png"
              onChange={handleFileInput}
            />
            
            <div style={styles.dropZoneContent}>
              <div style={styles.uploadIcon}>📄</div>
              <p style={styles.dropZoneText}>
                {dragActive ? "Drop files here" : "Click or drag files to upload"}
              </p>
              <p style={styles.dropZoneHint}>
                Supported formats: PDF, JPG, PNG
              </p>
            </div>
          </div>

          {/* Show uploaded files */}
          {Object.keys(docs).length > 0 && (
            <div style={styles.uploadedFiles}>
              <h4 style={styles.uploadedFilesTitle}>Uploaded Files</h4>
              {Object.entries(docs).map(([id, docData]) => {
                const status = uploadStatus[id] || "uploaded";
                const errors = documentErrors[id] || [];
                const isUploading = uploading[id];
                
                return (
                  <div key={id} style={styles.uploadedFileItem}>
                    <div style={styles.uploadedFileInfo}>
                      <span style={styles.fileIcon}>📎</span>
                      <span style={styles.fileName}>
                        {docData.file?.name || "Document"}
                      </span>
                      {docData.classifiedType && (
                        <span style={styles.classifiedType}>
                          (AI Detected: {docData.classifiedType})
                        </span>
                      )}
                    </div>
                    <div style={styles.uploadedFileActions}>
                      <span style={{
                        ...styles.statusBadge,
                        ...(status === "error" || errors.length > 0 
                          ? styles.statusError 
                          : status === "processing" 
                          ? styles.statusProcessing 
                          : styles.statusSuccess)
                      }}>
                        {status === "error" ? "Error" : status === "processing" || isUploading ? "Processing..." : "Processed"}
                      </span>
                      <button
                        style={styles.actionBtn}
                        onClick={(e) => {
                          e.stopPropagation();
                          viewFile(docData);
                        }}
                      >
                        👁 View
                      </button>
                      <button
                        style={styles.actionBtn}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(id);
                        }}
                      >
                        🗑 Delete
                      </button>
                    </div>
                    {errors.length > 0 && (
                      <div style={styles.errorBox}>
                        {errors.map((error, idx) => (
                          <div key={idx} style={styles.errorText}>
                            ❌ {error}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* RIGHT: Required Documents List */}
        <div style={styles.requiredSection}>
          <div style={styles.requiredHeader}>
            <h3 style={styles.requiredTitle}>Required Documents</h3>
            <p style={styles.requiredSubtitle}>Based on your {loanType} application</p>
          </div>

          <div style={styles.requiredList}>
            {Object.entries(documentsByCategory).map(([category, categoryDocs]) => {
              const categoryValid = isAnyUploaded(categoryDocs);
              const hasMultipleOptions = categoryDocs.length > 1;
              
              return (
                <div key={category} style={styles.categoryGroup}>
                  <div style={styles.categoryHeader}>
                    <div style={styles.categoryTitleWrapper}>
                      <span style={styles.categoryTitle}>{category}</span>
                      {hasMultipleOptions && (
                        <span style={styles.categoryNote}>
                          (Any one of them is enough)
                        </span>
                      )}
                    </div>
                    {categoryValid && (
                      <span style={styles.categoryStatusValid}>
                        ✓ Uploaded
                      </span>
                    )}
                  </div>
                  
                  <div style={styles.docList}>
                    {categoryDocs.map((doc) => {
                      const docData = docs[doc.id];
                      const uploaded = !!docData;
                      const status = uploadStatus[doc.id];
                      const errors = documentErrors[doc.id] || [];
                      
                      return (
                        <div key={doc.id} style={styles.requiredDocItem}>
                          <div style={styles.requiredDocInfo}>
                            <span style={styles.docBullet}>•</span>
                            <span style={{
                              ...styles.requiredDocLabel,
                              ...(uploaded && status === "processed" && errors.length === 0 
                                ? styles.requiredDocLabelUploaded 
                                : {})
                            }}>
                              {doc.label}
                            </span>
                            {uploaded && (
                              <span style={{
                                ...styles.docStatus,
                                ...(status === "error" || errors.length > 0 
                                  ? styles.docStatusError 
                                  : status === "processing" 
                                  ? styles.docStatusProcessing 
                                  : styles.docStatusSuccess)
                              }}>
                                {status === "error" || errors.length > 0 ? "✗" : status === "processing" ? "⏳" : "✓"}
                              </span>
                            )}
                          </div>
                          {errors.length > 0 && (
                            <div style={styles.smallErrorBox}>
                              {errors.map((error, idx) => (
                                <div key={idx} style={styles.smallErrorText}>
                                  ❌ {error}
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* SUBMIT BUTTON */}
      <div style={styles.submitBox}>
        <button
          onClick={handleSubmit}
          disabled={!allUploaded || !allProcessed() || hasErrors}
          style={{
            ...styles.submitBtn,
            background: (allUploaded && allProcessed() && !hasErrors) ? "#16A34A" : "#9CA3AF",
            cursor: (allUploaded && allProcessed() && !hasErrors) ? "pointer" : "not-allowed",
          }}
        >
          {!allProcessed() && allUploaded ? "Processing Documents..." : hasErrors ? "Fix Errors to Submit" : "Submit Application"}
        </button>

        {!allUploaded && (
          <p style={styles.warning}>
            Please complete all mandatory document requirements.
          </p>
        )}
        
        {hasErrors && (
          <p style={styles.errorMessage}>
            ❌ Please fix document type errors before submitting.
          </p>
        )}
        
        {!allProcessed() && allUploaded && (
          <p style={styles.infoMessage}>
            ⏳ Processing documents... Please wait.
          </p>
        )}
      </div>
    </div>
  );
}

/* ================= STYLES ================= */
const styles = {
  wrapper: {
    maxWidth: 1400,
    margin: "20px auto",
    background: "#fff",
    border: "1px solid #E5E7EB",
    borderRadius: 8,
  },
  
  header: {
    padding: "24px 32px",
    background: "linear-gradient(135deg,rgb(248, 248, 248))",
    color: "black",
  },
  title: {
    margin: 0,
    fontSize: 24,
    fontWeight: 600,
  },
  subtitle: {
    margin: "8px 0 0 0",
    fontSize: 14,
    opacity: 0.9,
  },
  container: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: 0,
  },
  uploadSection: {
    padding: "24px",
    borderRight: "1px solid #E5E7EB",
    background: "#F9FAFB",
    display: "flex",
    flexDirection: "column",
  },
  uploadHeader: {
    marginBottom: 20,
  },
  uploadTitle: {
    margin: "0 0 8px 0",
    fontSize: 18,
    fontWeight: 600,
    color: "#111827",
  },
  uploadSubtitle: {
    margin: 0,
    fontSize: 13,
    color: "#6B7280",
  },
  dropZone: {
    border: "2px dashed #D1D5DB",
    borderRadius: 8,
    padding: "10px 10px",
    textAlign: "center",
    cursor: "pointer",
    background: "#fff",
    transition: "all 0.2s",
    marginBottom: 24,
  },
  dropZoneActive: {
    borderColor: "#667eea",
    background: "#F3F4F6",
  },
  dropZoneContent: {
    pointerEvents: "none",
  },
  uploadIcon: {
    fontSize: 48,
    marginBottom: 16,
  },
  dropZoneText: {
    margin: "0 0 8px 0",
    fontSize: 16,
    fontWeight: 500,
    color: "#374151",
  },
  dropZoneHint: {
    margin: 0,
    fontSize: 12,
    color: "#9CA3AF",
  },
  uploadedFiles: {
    marginTop: 24,
    flex: 1,
    overflowY: "auto",
    paddingRight: 8,
    minHeight: 0,
  },
  uploadedFilesTitle: {
    margin: "0 0 12px 0",
    fontSize: 14,
    fontWeight: 600,
    color: "#374151",
  },
  uploadedFileItem: {
    padding: 12,
    background: "#fff",
    border: "1px solid #E5E7EB",
    borderRadius: 6,
    marginBottom: 8,
  },
  uploadedFileInfo: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    marginBottom: 8,
  },
  fileIcon: {
    fontSize: 16,
  },
  fileName: {
    flex: 1,
    fontSize: 13,
    color: "#374151",
    fontWeight: 500,
  },
  classifiedType: {
    fontSize: 11,
    color: "#6B7280",
    fontStyle: "italic",
  },
  uploadedFileActions: {
    display: "flex",
    alignItems: "center",
    gap: 8,
  },
  statusBadge: {
    padding: "4px 10px",
    borderRadius: 12,
    fontSize: 11,
    fontWeight: 500,
  },
  statusSuccess: {
    background: "#DCFCE7",
    color: "#166534",
  },
  statusProcessing: {
    background: "#FEF3C7",
    color: "#92400E",
  },
  statusError: {
    background: "#FEE2E2",
    color: "#991B1B",
  },
  actionBtn: {
    background: "none",
    border: "none",
    color: "#2563EB",
    cursor: "pointer",
    fontSize: 12,
    padding: "4px 8px",
  },
  requiredSection: {
    padding: "20px",
    background: "#fff",
  },
  requiredHeader: {
    marginBottom: 16,
    paddingBottom: 12,
    borderBottom: "1px solid #E5E7EB",
  },
  requiredTitle: {
    margin: "0 0 4px 0",
    fontSize: 16,
    fontWeight: 600,
    color: "#111827",
  },
  requiredSubtitle: {
    margin: 0,
    fontSize: 12,
    color: "#6B7280",
  },
  requiredList: {
    display: "flex",
    flexDirection: "column",
    gap: 12,
  },
  categoryGroup: {
    background: "#F9FAFB",
    borderRadius: 6,
    padding: 12,
    border: "1px solid #E5E7EB",
  },
  categoryHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 6,
  },
  categoryTitleWrapper: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    flex: 1,
  },
  categoryTitle: {
    fontSize: 13,
    fontWeight: 600,
    color: "#111827",
  },
  categoryNote: {
    fontSize: 11,
    color: "#6B7280",
    fontStyle: "italic",
    margin: 0,
  },
  categoryStatusValid: {
    fontSize: 10,
    fontWeight: 500,
    padding: "2px 8px",
    borderRadius: 10,
    background: "#DCFCE7",
    color: "#166534",
  },
  docList: {
    display: "flex",
    flexDirection: "column",
    gap: 4,
  },
  requiredDocItem: {
    padding: "4px 0",
  },
  requiredDocInfo: {
    display: "flex",
    alignItems: "center",
    gap: 6,
  },
  docBullet: {
    fontSize: 12,
    color: "#9CA3AF",
    lineHeight: 1,
  },
  requiredDocLabel: {
    flex: 1,
    fontSize: 12,
    color: "#374151",
  },
  requiredDocLabelUploaded: {
    color: "#166534",
    fontWeight: 500,
  },
  docStatus: {
    fontSize: 12,
    width: 16,
    height: 16,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    borderRadius: "50%",
    flexShrink: 0,
  },
  docStatusSuccess: {
    background: "#22C55E",
    color: "#fff",
  },
  docStatusProcessing: {
    background: "#F59E0B",
    color: "#fff",
  },
  docStatusError: {
    background: "#DC2626",
    color: "#fff",
  },
  errorBox: {
    padding: "8px 12px",
    background: "#FEE2E2",
    borderLeft: "3px solid #DC2626",
    marginTop: 8,
    borderRadius: 4,
  },
  errorText: {
    fontSize: 11,
    color: "#991B1B",
    marginBottom: 4,
    fontWeight: 500,
  },
  smallErrorBox: {
    padding: "4px 8px",
    background: "#FEE2E2",
    borderLeft: "2px solid #DC2626",
    marginTop: 4,
    marginLeft: 18,
    borderRadius: 3,
  },
  smallErrorText: {
    fontSize: 9,
    color: "#991B1B",
    marginBottom: 2,
  },
  submitBox: {
    padding: "24px 32px",
    textAlign: "center",
    borderTop: "1px solid #E5E7EB",
    background: "#F9FAFB",
  },
  submitBtn: {
    padding: "12px 32px",
    borderRadius: 6,
    border: "none",
    color: "#fff",
    fontSize: 15,
    fontWeight: 600,
    cursor: "pointer",
  },
  warning: {
    marginTop: 12,
    fontSize: 13,
    color: "#DC2626",
  },
  error: {
    padding: 12,
    background: "#FEE2E2",
    color: "#991B1B",
    borderRadius: 6,
    margin: "12px 24px",
    fontSize: 13,
  },
  warningMsg: {
    padding: 12,
    background: "#FEF3C7",
    color: "#92400E",
    borderRadius: 6,
    margin: "12px 24px",
    fontSize: 13,
  },
  errorMessage: {
    marginTop: 12,
    fontSize: 13,
    color: "#DC2626",
    fontWeight: 500,
  },
  infoMessage: {
    marginTop: 12,
    fontSize: 13,
    color: "#2563EB",
  },
};