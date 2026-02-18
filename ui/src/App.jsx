import { useState } from "react";
import { Routes, Route, Navigate } from "react-router-dom";

import Login from "./pages/Login";
import ApplicationForm from "./pages/ApplicationForm";
import DocumentUpload from "./pages/DocumentUpload";
import AdminDashboard from "./pages/AdminDasboard";
import CaseReview from "./pages/CaseReview";
import RiskAnalysis from "./pages/RiskAnalysis";
import HumanDecision from "./pages/HumanDecision";
import ClientDashboard from "./pages/ClientDashboard";
import ApplicationStatus from "./pages/ApplicationStatus";

export default function App() {
  const [role, setRole] = useState(null); // null | admin | client
  const [userEmail, setUserEmail] = useState(null);
  const [userId, setUserId] = useState(null);
  const [step, setStep] = useState(1);
  const [applicationData, setApplicationData] = useState(null);

  const handleLogout = () => {
    setRole(null);
    setUserEmail(null);
    setUserId(null);
    setStep(1);
    setApplicationData(null);
  };

  return (
    <Routes>

      {/* LOGIN */}
      <Route
        path="/"
        element={
          <Login
            onAdminLogin={(email) => {
              setRole("admin");
              setUserEmail(email);
            }}
            onClientLogin={(email, id) => {
              setRole("client");
              setUserEmail(email);
              if (id) setUserId(id); // ✅ SINGLE SOURCE OF userId
            }}
          />
        }
      />

      {/* ADMIN */}
      <Route
        path="/admin"
        element={role === "admin" ? <AdminDashboard /> : <Navigate to="/" />}
      />

      <Route
        path="/admin/case/:caseId"
        element={role === "admin" ? <CaseReview /> : <Navigate to="/" />}
      />

      <Route
        path="/admin/case/:caseId/risk"
        element={role === "admin" ? <RiskAnalysis /> : <Navigate to="/" />}
      />

      <Route
        path="/admin/case/:caseId/decision"
        element={role === "admin" ? <HumanDecision /> : <Navigate to="/" />}
      />

      {/* CLIENT DASHBOARD */}
      <Route
        path="/client"
        element={role === "client" ? <ClientDashboard /> : <Navigate to="/" />}
      />

      {/* CLIENT APPLY (RESTORED FLOW) */}
      <Route
        path="/client/apply"
        element={
          role === "client" ? (
            step === 1 ? (
              <ApplicationForm
                userEmail={userEmail}
                onContinue={(data) => {
                  setApplicationData(data);
                  if(data.userId) setUserId(data.userId);
                  setStep(2);
                }}
              />
            ) : (
              <DocumentUpload applicantData={applicationData} />
            )
          ) : (
            <Navigate to="/" />
          )
        }
      />

      {/* CLIENT STATUS */}
      <Route
        path="/client/status"
        element={role === "client" ? <ApplicationStatus userId={userId} userEmail={userEmail} /> : <Navigate to="/" />}
      />

    </Routes>
  );
}
