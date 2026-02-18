import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { TextInput } from "@carbon/react";
import { View } from "@carbon/icons-react";
import logo from "../components/Kaara.jpg";
import { userAPI, adminAPI, checkBackendHealth } from "../services/api";
import "./Login.css";

export default function Login({ onAdminLogin, onClientLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      await checkBackendHealth();

      // Check if it's an admin login
      if (email.endsWith("@admin.com")) {
        try {
          // Authenticate admin
          const response = await adminAPI.login(email, password);
          onAdminLogin(response.admin.email);
          navigate("/admin");
        } catch (err) {
          const errorMessage = err.response?.data?.detail || "Invalid email or password";
          setError(errorMessage);
        }
      } else {
        // Client login (existing logic)
        onClientLogin(email);
        navigate("/client");
      }
    } catch (err) {
      if (!error) {
        setError("Unable to connect to server");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-main-container">
      {/* LEFT PANEL */}
      <div className="login-left-panel">
        <div className="login-left-header">
          <div className="product-title">Underwriting Efficiency</div>
          <div className="product-by">
            by <img src={logo} alt="Kaara" className="kaara-logo" />
          </div>
        </div>

        {/* Animated Visual */}
        <div className="underwriting-visual">
          <div className="doc-card"></div>
          <div className="doc-card"></div>
          <div className="doc-card"></div>
          <div className="risk-pulse"></div>
        </div>

        <div className="login-left-text">
          <div className="welcome-heading">
            Welcome to AI-powered underwriting
          </div>
          <div className="welcome-desc">
            Automate document verification, detect risk signals, and enable
            transparent human-in-the-loop decisioning — all in one platform.
          </div>
        </div>
      </div>

      {/* RIGHT PANEL */}
      <div className="login-right-panel">
        <div className="login-form-area">
          <div className="login-form-heading">Log in</div>

          <form onSubmit={handleLogin}>
            <TextInput
              id="email"
              labelText="Email"
              placeholder="Enter your email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              style={{ marginBottom: 16 }}
            />

            <div className="password-wrapper">
              <TextInput
                id="password"
                labelText="Password"
                type={showPassword ? "text" : "password"}
                placeholder="Enter your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
              <span
                className="eye-icon"
                onClick={() => setShowPassword(!showPassword)}
              >
                <View size={20} />
              </span>
            </div>

            {error && <div className="login-error">{error}</div>}

            <button className="login-button" disabled={loading}>
              {loading ? "Signing in…" : "Log in"}
              <span className="login-button-icon">→</span>
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}