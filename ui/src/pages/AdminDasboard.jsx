import { useEffect, useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { applicationAPI, riskAnalysisAPI, adminAPI } from "../services/api";
import { formatDateTime } from "../utils/dateUtils";
import logo from "../components/Kaara.jpg";
import "../pages/admin-dashboard.css";

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

  return "Other";
};

// Deduplicate identity flags - remove duplicates based on type, field, and value
const deduplicateIdentityFlags = (anomalies) => {
  const seen = new Set();
  const deduplicated = [];
  
  anomalies.forEach((anomaly) => {
    // Create a unique key based on type, field, and value for identity flags
    const key = `${anomaly.type || ''}-${anomaly.field || ''}-${anomaly.value || ''}`.toLowerCase();
    
    if (!seen.has(key)) {
      seen.add(key);
      deduplicated.push(anomaly);
    }
  });
  
  return deduplicated;
};

// Calculate deduplicated flag count from detailed analyses
const calculateDeduplicatedFlagCount = async (applicationId, summary) => {
  if (!summary || !summary.analyses || summary.analyses.length === 0) {
    return summary?.total_anomalies || 0;
  }

  try {
    // Fetch detailed risk analyses for all documents (similar to RiskAnalysis.jsx)
    const analysesPromises = summary.analyses.map(async (analysis) => {
      try {
        return await riskAnalysisAPI.getByDocumentId(analysis.document_id);
      } catch (err) {
        console.warn(`Could not fetch risk analysis for ${analysis.document_id}:`, err);
        return null;
      }
    });

    const detailedAnalyses = (await Promise.all(analysesPromises)).filter(a => a !== null);

    if (detailedAnalyses.length === 0) {
      return summary.total_anomalies || 0;
    }

    const allAnomalies = [];
    
    // Collect all anomalies from all detailed analyses
    detailedAnalyses.forEach((analysis) => {
      const anomalies = analysis.anomalies || {};
      ["critical_anomalies", "high_anomalies", "medium_anomalies", "low_anomalies"].forEach((severityKey) => {
        const anomaliesList = anomalies[severityKey] || [];
        anomaliesList.forEach((anomaly) => {
          allAnomalies.push(anomaly);
        });
      });
    });

    // Separate identity flags from others
    const identityFlags = allAnomalies.filter(anomaly => categorizeAnomaly(anomaly) === "Identity Flags");
    const otherFlags = allAnomalies.filter(anomaly => categorizeAnomaly(anomaly) !== "Identity Flags");

    // Deduplicate identity flags
    const deduplicatedIdentity = deduplicateIdentityFlags(identityFlags);

    // Return total count (deduplicated identity + all others)
    return deduplicatedIdentity.length + otherFlags.length;
  } catch (err) {
    console.warn(`Error calculating deduplicated flags for ${applicationId}:`, err);
    return summary?.total_anomalies || 0;
  }
};

export default function AdminDashboard() {
  const navigate = useNavigate();

  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [adminInfo, setAdminInfo] = useState(null);
  const [loadingAdmin, setLoadingAdmin] = useState(true);
  const [showProfileModal, setShowProfileModal] = useState(false);
  const [profileForm, setProfileForm] = useState({ name: "", email: "", currentPassword: "", newPassword: "", confirmPassword: "" });
  const [profileError, setProfileError] = useState("");

  /* ===== PROFILE DROPDOWN ===== */
  const [menuOpen, setMenuOpen] = useState(false);

  /* ===== TABLE CONTROLS ===== */
  const [searchOpen, setSearchOpen] = useState(false);
  const [filterOpen, setFilterOpen] = useState(false);

  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [sortAsc, setSortAsc] = useState(false); // Default to descending (newest first)

  const actionsRef = useRef(null);

  /* ===== CLOSE ALL POPOVERS ===== */
  const closeAllPopovers = () => {
    setSearchOpen(false);
    setFilterOpen(false);
  };

  /* ===== LOAD CASES (APPLICATIONS) ===== */
  const loadCases = async () => {
    setLoading(true);

    const applications = await applicationAPI.list();

    const data = await Promise.all(
      applications.map(async (app) => {
        let risk = "Low";
        let flags = 0;

        try {
          const s = await riskAnalysisAPI.getApplicationRiskSummary(app.application_id);
          // Calculate deduplicated flag count (removes duplicate identity flags)
          flags = await calculateDeduplicatedFlagCount(app.application_id, s);
          const score = s?.final_risk_score || 0;

          if (score >= 80) risk = "Critical";
          else if (score >= 60) risk = "High";
          else if (score >= 30) risk = "Medium";
        } catch {}

        return {
          name: app.name || app.email || "Unknown Applicant",
          caseId: app.application_id,
          userId: app.user_id,
          loanType: app.loan_type || "N/A",
          risk,
          flags,
          status: app.status || "In Review",
          updated: formatDateTime(app.updated_at || app.created_at),
          updatedAt: app.updated_at || app.created_at, // Raw timestamp for sorting
        };
      })
    );

    setRows(data);
    setLoading(false);
  };

  /* ===== LOAD ADMIN INFO ===== */
  const loadAdminInfo = async () => {
    try {
      setLoadingAdmin(true);
      // Try to get from localStorage first
      const storedAdmin = localStorage.getItem('admin_data');
      if (storedAdmin) {
        setAdminInfo(JSON.parse(storedAdmin));
      }
      
      // Fetch fresh admin info from API
      const admin = await adminAPI.getMe();
      setAdminInfo(admin);
      localStorage.setItem('admin_data', JSON.stringify(admin));
    } catch (err) {
      console.error("Failed to load admin info:", err);
      // If API fails, use stored data
      const storedAdmin = localStorage.getItem('admin_data');
      if (storedAdmin) {
        setAdminInfo(JSON.parse(storedAdmin));
      }
    } finally {
      setLoadingAdmin(false);
    }
  };

  /* ===== UPDATE ADMIN PROFILE ===== */
  const handleUpdateProfile = async (e) => {
    e.preventDefault();
    setProfileError("");

    // Validate password change if new password is provided
    if (profileForm.newPassword) {
      if (!profileForm.currentPassword) {
        setProfileError("Current password is required to change password");
        return;
      }
      if (profileForm.newPassword !== profileForm.confirmPassword) {
        setProfileError("New passwords do not match");
        return;
      }
      if (profileForm.newPassword.length < 6) {
        setProfileError("Password must be at least 6 characters");
        return;
      }
    }

    try {
      const updateData = {};
      
      // Only include fields that have changed
      if (profileForm.name && profileForm.name.trim() && profileForm.name !== adminInfo.name) {
        updateData.name = profileForm.name.trim();
      }
      
      if (profileForm.newPassword) {
        updateData.current_password = profileForm.currentPassword;
        updateData.new_password = profileForm.newPassword;
      }

      if (Object.keys(updateData).length === 0) {
        setProfileError("No changes to save");
        return;
      }

      const updatedAdmin = await adminAPI.updateProfile(updateData);
      setAdminInfo(updatedAdmin);
      setShowProfileModal(false);
      setProfileForm({ name: "", email: "", currentPassword: "", newPassword: "", confirmPassword: "" });
      setProfileError("");
    } catch (err) {
      setProfileError(err.response?.data?.detail || "Failed to update profile");
    }
  };

  useEffect(() => {
    loadCases();
    loadAdminInfo();
  }, []);

  useEffect(() => {
    const handleClickAnywhere = (e) => {
      if (actionsRef.current && !actionsRef.current.contains(e.target)) {
        setSearchOpen(false);
        setFilterOpen(false);
      }
    };
  
    document.addEventListener("mousedown", handleClickAnywhere);
  
    return () => {
      document.removeEventListener("mousedown", handleClickAnywhere);
    };
  }, []);
  

  /* ===== APPLY SEARCH + FILTER + SORT ===== */
  const visibleRows = rows
    .filter((r) =>
      r.name.toLowerCase().includes(searchTerm.toLowerCase())
    )
    .filter((r) =>
      statusFilter === "ALL" ? true : r.status === statusFilter
    )
    .sort((a, b) => {
      // Sort by timestamp (newest first by default)
      const timeA = a.updatedAt ? new Date(a.updatedAt).getTime() : 0;
      const timeB = b.updatedAt ? new Date(b.updatedAt).getTime() : 0;
      
      if (sortAsc) {
        // Ascending: oldest first
        return timeA - timeB;
      } else {
        // Descending: newest first (default)
        return timeB - timeA;
      }
    });

  return (
    <div className="rm-shell">

      {/* ===== HEADER ===== */}
      <header className="rm-header">
        <div className="rm-brand">
          <div className="rm-title">Underwriting Effciency</div>
          <div className="rm-sub">
            by <img src={logo} alt="Kaara" />
          </div>
        </div>

        <div className="rm-user">
          <div
            className="rm-profile-click"
            onClick={() => setMenuOpen(v => !v)}
          >
            <div className="rm-avatar">
              {adminInfo?.name ? adminInfo.name.charAt(0).toUpperCase() : "A"}
            </div>
            <div className="rm-user-info">
              <div className="rm-name">
                {loadingAdmin ? "Loading..." : (adminInfo?.name || "Admin")}
              </div>
              <div className="rm-role">
                {adminInfo?.email || "admin@admin.com"}
              </div>
            </div>
          </div>

          {menuOpen && (
            <div className="rm-dropdown">
              <button
                className="rm-dropdown-item"
                onClick={() => {
                  setShowProfileModal(true);
                  setProfileForm({
                    name: adminInfo?.name || "",
                    email: adminInfo?.email || "",
                    currentPassword: "",
                    newPassword: "",
                    confirmPassword: ""
                  });
                  setMenuOpen(false);
                }}
              >
                Update Profile
              </button>
              <button
                className="rm-dropdown-item"
                onClick={() => {
                  adminAPI.logout();
                  navigate("/");
                }}
              >
                Logout
              </button>
            </div>
          )}
        </div>
      </header>

      {/* ===== PAGE TITLE ===== */}
      <section className="rm-page-title">
        <h1>Dashboard</h1>
        <p>Monitor and manage underwriting cases</p>
      </section>

      {/* ===== KPI ===== */}
      <section className="rm-kpis">
        <div className="rm-kpi">
          <span>Total Cases</span>
          <strong>{rows.length}</strong>
        </div>
        <div className="rm-kpi">
          <span>Approved</span>
          <strong>{rows.filter(r => r.status === "Approved").length}</strong>
        </div>
        <div className="rm-kpi">
          <span>In Review</span>
          <strong>{rows.filter(r => r.status === "In Review").length}</strong>
        </div>
        <div className="rm-kpi">
          <span>Rejected</span>
          <strong>{rows.filter(r => r.status === "Rejected").length}</strong>
        </div>
      </section>

      {/* ===== TABLE ===== */}
      <section className="rm-table">

        <div className="rm-table-title-row">
          <div className="rm-table-title">Customer Records</div>

          <div className="rm-table-actions" ref={actionsRef}>

    {/* SEARCH */}
    <div className="rm-icon-wrap">
      <button
        className="rm-icon-btn"
        onClick={() => {
          setSearchOpen(v => !v);
        }}
      >
        <svg viewBox="0 0 32 32" stroke="currentColor" strokeWidth="2" fill="none">
          <circle cx="14" cy="14" r="6" />
          <line x1="19" y1="19" x2="26" y2="26" />
        </svg>
      </button>

      {searchOpen && (
        <div className="rm-popover">
          <input
            className="rm-search-pop"
            placeholder="Search name…"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            autoFocus
          />
        </div>
      )}
    </div>

    {/* FILTER */}
    <div className="rm-icon-wrap">
      <button
        className="rm-icon-btn"
        onClick={() => {
          setFilterOpen(v => !v);
        }}
      >
      <svg
        viewBox="0 0 32 32"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M4 6h24" />
        <path d="M8 14h16" />
        <path d="M12 22h8" />
      </svg>

      </button>

      {filterOpen && (
        <div className="rm-popover">
          <select
            className="rm-filter-pop"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="ALL">All</option>
            <option value="Approved">Approved</option>
            <option value="Rejected">Rejected</option>
            <option value="In Review">In Review</option>
          </select>
        </div>
      )}
    </div>

    {/* SORT */}
    <button
      className="rm-icon-btn"
      onClick={() => {
        closeAllPopovers();
        setSortAsc(v => !v);
      }}
    >
      <svg viewBox="0 0 32 32" stroke="currentColor" strokeWidth="2" fill="none">
        <line x1="16" y1="6" x2="16" y2="26" />
        <polyline points="10,12 16,6 22,12" />
        <polyline points="10,20 16,26 22,20" />
      </svg>
    </button>

    {/* REFRESH */}
    <button
      className="rm-icon-btn"
      onClick={loadCases}
    >
      <svg viewBox="0 0 32 32" stroke="currentColor" strokeWidth="2" fill="none">
        <path d="M26 16a10 10 0 1 1-3-7.2" />
        <polyline points="26,6 26,12 20,12" />
      </svg>
    </button>

  </div>

          </div>


        <div className="rm-table-head">
          <span>Applicant</span>
          <span>User ID</span>
          <span>Loan Type</span>
          <span>Risk</span>
          <span>Flags</span>
          <span>Status</span>
          <span>Updated</span>
          <span>Action</span>
        </div>

        {loading ? (
          <div className="rm-empty">Loading…</div>
        ) : (
          visibleRows.map((r, i) => (
            <div key={i} className="rm-row">
              <span style={{ fontWeight: 500 }}>{r.name}</span>
              <span style={{ fontSize: '12px', color: '#6f6f6f', fontFamily: 'monospace' }}>
                {r.userId?.length > 15 ? `${r.userId.substring(0, 12)}...` : r.userId}
              </span>
              <span>{r.loanType}</span>
              <span className={`risk-${r.risk.toLowerCase()}`}>{r.risk}</span>
              <span style={{ textAlign: 'center' }}>{r.flags}</span>
              <span
                className={`rm-status-badge rm-status-${r.status
                  .toLowerCase()
                  .replace(/\s/g, "-")}`}
              >
                {r.status || 'In Review'}
              </span>
              <span style={{ fontSize: '12px', color: '#6f6f6f' }}>{r.updated}</span>
              <span
                className="rm-action"
                onClick={() => navigate(`/admin/case/${r.caseId}`)}
              >
                Review →
              </span>
            </div>
          ))
        )}
      </section>

      {/* ===== PROFILE UPDATE MODAL ===== */}
      {showProfileModal && (
        <div className="rm-modal-overlay" onClick={() => setShowProfileModal(false)}>
          <div className="rm-modal" onClick={(e) => e.stopPropagation()}>
            <div className="rm-modal-header">
              <h2>Update Profile</h2>
              <button
                className="rm-modal-close"
                onClick={() => {
                  setShowProfileModal(false);
                  setProfileError("");
                  setProfileForm({ name: "", email: "", currentPassword: "", newPassword: "", confirmPassword: "" });
                }}
              >
                ×
              </button>
            </div>
            <form onSubmit={handleUpdateProfile} className="rm-modal-body">
              <div className="rm-form-group">
                <label>Name</label>
                <input
                  type="text"
                  value={profileForm.name}
                  onChange={(e) => setProfileForm({ ...profileForm, name: e.target.value })}
                  placeholder="Admin Name"
                  required
                />
              </div>
              <div className="rm-form-group">
                <label>Email</label>
                <input
                  type="email"
                  value={profileForm.email}
                  disabled
                  style={{ opacity: 0.6, cursor: "not-allowed" }}
                />
                <small style={{ color: "#6f6f6f", fontSize: "12px" }}>
                  Email cannot be changed
                </small>
              </div>
              <div className="rm-form-group">
                <label>Current Password (to change password)</label>
                <input
                  type="password"
                  value={profileForm.currentPassword}
                  onChange={(e) => setProfileForm({ ...profileForm, currentPassword: e.target.value })}
                  placeholder="Leave empty to keep current password"
                />
              </div>
              {profileForm.currentPassword && (
                <>
                  <div className="rm-form-group">
                    <label>New Password</label>
                    <input
                      type="password"
                      value={profileForm.newPassword}
                      onChange={(e) => setProfileForm({ ...profileForm, newPassword: e.target.value })}
                      placeholder="Enter new password"
                      minLength={6}
                    />
                  </div>
                  <div className="rm-form-group">
                    <label>Confirm New Password</label>
                    <input
                      type="password"
                      value={profileForm.confirmPassword}
                      onChange={(e) => setProfileForm({ ...profileForm, confirmPassword: e.target.value })}
                      placeholder="Confirm new password"
                      minLength={6}
                    />
                  </div>
                </>
              )}
              {profileError && (
                <div style={{ color: "#da1e28", fontSize: "14px", marginBottom: "16px" }}>
                  {profileError}
                </div>
              )}
              <div className="rm-modal-footer">
                <button
                  type="button"
                  className="rm-btn-secondary"
                  onClick={() => {
                    setShowProfileModal(false);
                    setProfileError("");
                    setProfileForm({ name: "", email: "", currentPassword: "", newPassword: "", confirmPassword: "" });
                  }}
                >
                  Cancel
                </button>
                <button type="submit" className="rm-btn-primary">
                  Save Changes
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}


/*import { useState, useRef, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { userAPI, riskAnalysisAPI, checkBackendHealth } from "../services/api";
import { formatDateTime } from "../utils/dateUtils";
import logo from "../components/Kaara.jpg";

export default function AdminDashboard() {
  const adminName = "Sarah Adams";
  const navigate = useNavigate();
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const menuRef = useRef(null);

  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  /* ===== CLOSE PROFILE DROPDOWN ===== 
  useEffect(() => {
    const handler = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  /* ===== LOAD CASES ===== 
  const loadCases = async () => {
    try {
      setLoading(true);
      setError(null);

      const health = await checkBackendHealth();
      if (!health.success) {
        setError("Backend not reachable");
        return;
      }

      const users = await userAPI.list();

      const casesData = await Promise.all(
        users.map(async (user) => {
          let risk = "Low";
          let flags = 0;

          try {
            const summary = await riskAnalysisAPI.getUserRiskSummary(user.user_id);
            flags = summary?.total_anomalies || 0;

            const score =
              summary?.final_risk_score ||
              summary?.average_risk_score ||
              0;

            if (score >= 80) risk = "Critical";
            else if (score >= 60) risk = "High";
            else if (score >= 30) risk = "Medium";
          } catch {}

          const updated =
            user.case_updated_at ||
            user.created_at ||
            null;

          return {
            name: user.name || user.email,
            caseId: user.user_id,
            risk,
            flags,
            // backend status untouched
            rawStatus: user.case_status || "In Review",
            updated: updated
              ? formatDateTime(updated, {
                  month: "short",
                  day: "numeric",
                  year: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                })
              : "—",
          };
        })
      );

      setRows(casesData);
    } catch (err) {
      setError(err.message || "Failed to load cases");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (location.pathname === "/admin") loadCases();
  }, [location.pathname]);

  const handleLogout = () => navigate("/");

  /* ===== KPI COUNTS (CORRECTED) ===== 
  const total = rows.length;
  const approved = rows.filter(r => r.rawStatus === "Approved").length;
  const inReview = rows.filter(r => r.rawStatus === "In Review").length;
  const rejected = rows.filter(r => r.rawStatus === "Rejected").length;

  /* ===== STATUS LABEL MAPPER ===== 
  const getDisplayStatus = (status) => {
    if (status === "Reviewed") return "Approved";
    if (status === "Escalated") return "Rejected";
    return status;
  };

  useEffect(() => {
  if (rows.length > 0) {
    console.log("CASE STATUSES →", rows.map(r => r.status));
  }
}, [rows]);


  return (
    <div className="page container">

      {/* ===== TOP BAR =====} 
      <div className="app-header">
        <div >
          <div className="app-title">Underwriting Efficiency Platform</div>
          <div className="app-subtitle">
            by <img src={logo} alt="Kaara" className="kaara-logo" />
          </div>
        </div>

        <div className="profile-chip" ref={menuRef}>
          <div onClick={() => setOpen(!open)} style={{display:"flex",gap:10,cursor:"pointer"}}>
            <div className="avatar">{adminName[0]}</div>
            <div>
              <div className="profile-name">{adminName}</div>
              <div className="profile-role">Lead Risk Analyst</div>
            </div>
          </div>

          {open && (
            <div className="profile-menu">
              <button className="logout-btn" onClick={handleLogout}>
                Logout
              </button>
            </div>
          )}
        </div>
      </div>

      {/* ===== KPI CARDS ===== 
      <div className="kpi-row">
        <div className="kpi-card">
          <div className="kpi-label">Total Cases</div>
          <div className="kpi-value">{total}</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-label">Approved</div>
          <div className="kpi-value">{approved}</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-label">In Review</div>
          <div className="kpi-value">{inReview}</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-label">Rejected</div>
          <div className="kpi-value">{rejected}</div>
        </div>
      </div>

      {/* ===== TABLE ===== 
      <div className="table-shell">
        <div className="table-title">
          My Underwriting Cases
          <span className="table-sub">
            Review, approve or reject applications
          </span>
          <button
            className="refresh-btn"
            onClick={loadCases}
            disabled={loading}
          >
            ⟳ Refresh
          </button>
        </div>

        {loading ? (
          <div className="text-muted">Loading cases…</div>
        ) : error ? (
          <div className="pill pill-error">{error}</div>
        ) : (
          <>
            <div className="table-header">
              <span>Applicant</span>
              <span>Case ID</span>
              <span>Risk</span>
              <span>Flags</span>
              <span>Status</span>
              <span>Updated</span>
              <span>Action</span>
            </div>

            {rows.map((r, i) => (
              <div key={i} className="table-row">
                <span>{r.name}</span>
                <span>{r.caseId}</span>

                    <span
                      className={`risk-bubble ${
                        r.risk === "Low"
                          ? "risk-low"
                          : r.risk === "Medium"
                          ? "risk-medium"
                          : "risk-high"
                      }`}
                    >
                      {r.risk}
                    </span>


                <span style={{ color: "#DA1E28" }}>{r.flags}</span>

                <span className="text-muted">
                  {getDisplayStatus(r.rawStatus)}
                </span>

                <span className="text-muted">{r.updated}</span>

                <span
                  className="review-link"
                  onClick={() => navigate(`/admin/case/${r.caseId}`)}
                >
                  Review →
                </span>
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  );
}
*/