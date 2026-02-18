import { useState } from "react";
import ApplicantInformation from "../components/ApplicantInformation";
import { userAPI, applicationAPI, checkBackendHealth } from "../services/api";

function ApplicationForm({ onContinue, userEmail, userId }) { 
    const [formData, setFormData] = useState({ 
        name: "", 
        loanType: "", 
        applicantType: "", 
        loanAmount: "", 
        email: userEmail || "", 
        phone: "", 
    }); 
    
    const [showError, setShowError] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    
    const isFormValid = (() => {
        const { name, loanType, applicantType, loanAmount, email, phone } = formData;
        if ([name, loanType, applicantType, loanAmount, email, phone].some(v => String(v).trim() === "")) return false;
        const emailValid = /^[^\s@]+@[^\s@]+\.com$/.test(email);
        const phoneDigits = String(phone).replace(/\D/g, '');
        const phoneValid = phoneDigits.length === 10;
        const loanValid = Number(String(loanAmount).replace(/[^0-9.]/g, '')) >= 25000;
        return emailValid && phoneValid && loanValid;
    })();
    
    const handleContinue = async () => { 
        if (!isFormValid) { 
            setShowError(true); 
            return; 
        }
        
        try {
            setLoading(true);
            setError(null);
            
            // Check backend connection
            const healthCheck = await checkBackendHealth();
            if (!healthCheck.success) {
                setError("Cannot connect to backend. Please ensure the server is running.");
                setLoading(false);
                return;
            }
            
            // Create or get user
            let finalUserId = userId;
            if (!finalUserId) {
                try {
                    // Try to find existing user by email
                    const users = await userAPI.list();
                    const existingUser = users.find(u => u.email === formData.email);
                    
                    if (existingUser) {
                        finalUserId = existingUser.user_id;
                    } else {
                        // Create new user - only send organization if it has a value
                        const userPayload = {
                            email: formData.email.trim(),
                            name: formData.name.trim(),
                        };
                        
                        // Only include organization if it's not empty
                        if (formData.organization && formData.organization.trim()) {
                            userPayload.organization = formData.organization.trim();
                        }
                        
                        const newUser = await userAPI.create(userPayload);
                        finalUserId = newUser.user_id;
                    }
                } catch (err) {
                    console.error("Error creating/getting user:", err);
                    // Extract detailed error message from response
                    let errorMessage = "Failed to create user account. Please try again.";
                    if (err.response?.data?.detail) {
                        if (Array.isArray(err.response.data.detail)) {
                            // Pydantic validation errors come as array
                            errorMessage = err.response.data.detail.map(e => e.msg || e.message || JSON.stringify(e)).join(", ");
                        } else {
                            errorMessage = err.response.data.detail;
                        }
                    } else if (err.response?.data?.message) {
                        errorMessage = err.response.data.message;
                    }
                    setError(errorMessage);
                    setLoading(false);
                    return;
                }
            }
            
            // Create a new application for this submission
            let applicationId;
            try {
                const applicationPayload = {
                    user_id: finalUserId,
                    email: formData.email.trim(),
                    name: formData.name.trim(),
                    loan_type: formData.loanType,
                    applicant_type: formData.applicantType,
                    loan_amount: Number(String(formData.loanAmount).replace(/[^0-9.]/g, ''))
                };
                
                const newApplication = await applicationAPI.create(applicationPayload);
                applicationId = newApplication.application_id;
            } catch (err) {
                console.error("Error creating application:", err);
                let errorMessage = "Failed to create application. Please try again.";
                if (err.response?.data?.detail) {
                    if (Array.isArray(err.response.data.detail)) {
                        errorMessage = err.response.data.detail.map(e => e.msg || e.message || JSON.stringify(e)).join(", ");
                    } else {
                        errorMessage = err.response.data.detail;
                    }
                } else if (err.response?.data?.message) {
                    errorMessage = err.response.data.message;
                }
                setError(errorMessage);
                setLoading(false);
                return;
            }
            
            // Pass data with userId and applicationId
            onContinue({ ...formData, userId: finalUserId, applicationId: applicationId });
        } catch (err) {
            console.error("Error:", err);
            setError(err.response?.data?.detail || err.message || "An error occurred.");
        } finally {
            setLoading(false);
        }
    }; 
    
    return ( 
    <div style={styles.page}> 
    <ApplicantInformation onChange={setFormData} initialData={formData} /> 
    {showError && <p style={styles.error}>Fill missing details</p>}
    {error && <p style={styles.error}>{error}</p>}
        <button 
            onClick={handleContinue} 
            disabled={loading || !isFormValid}
            style={{
                ...styles.continueBtn, 
                opacity: (isFormValid && !loading) ? 1 : 0.5,
                cursor: (isFormValid && !loading) ? "pointer" : "not-allowed"
            }} 
        > 
        {loading ? "Processing..." : "Continue"}
        </button> 
        </div> 
    ); 
} 

const styles = { 
    page: { 
        minHeight: "100vh", 
        background: "#F9FAFB", 
        display: "flex", 
        flexDirection: "column", 
        alignItems: "center", 
        justifyContent: "center", 
        gap: 16, 
    }, 
        
    continueBtn: { 
        padding: "10px 24px",
        borderRadius: 6,
        border: "none",
        background: "#DA1E28",     // Kaara red
        color: "#FFFFFF",
        fontSize: 14,
        fontWeight: 600,
        transition: "all 0.15s ease",
      },
      
    
    error: {
        color: "#DC2626",
        fontSize: 13,
    },
};

export default ApplicationForm;