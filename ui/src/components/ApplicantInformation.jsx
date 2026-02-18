import { useState } from "react";

export default function ApplicantInformation({ onChange, initialData }) {
  const [formData, setFormData] = useState({
    name: initialData?.name || "",
    loanType: initialData?.loanType || "",
    applicantType: initialData?.applicantType || "",
    loanAmount: initialData?.loanAmount || "",
    email: initialData?.email || "",
    phone: initialData?.phone || "",
  });

  const [errors, setErrors] = useState({
    email: null,
    phone: null,
    loanAmount: null,
  });

  const handleChange = (e) => {
    const updated = { ...formData, [e.target.name]: e.target.value };
    setFormData(updated);

    const { name, value } = e.target;
    const newErrors = { ...errors };

    if (name === "email") {
      const emailValid = /^[^\s@]+@[^\s@]+\.com$/.test(value);
      newErrors.email = emailValid ? null : "Email must end with .com";
    }

    if (name === "phone") {
      const digits = value.replace(/\D/g, "");
      newErrors.phone =
        digits.length === 10 ? null : "Phone number must have 10 digits";
    }

    if (name === "loanAmount") {
      const amt = Number(String(value).replace(/[^0-9.]/g, "")) || 0;
      newErrors.loanAmount =
        amt >= 25000 ? null : "Loan amount must be at least ₹25,000";
    }

    setErrors(newErrors);
    onChange && onChange(updated);
  };

  return (
    <div className="card" style={styles.wrapper}>
      {/* Header */}
      <div style={styles.header}>Applicant Information</div>

      <div style={styles.form}>
        <div style={styles.grid}>
          {/* Name */}
          <div>
            <label style={styles.label}>
              Name <span style={styles.required}>*</span>
            </label>
            <input
              name="name"
              value={formData.name}
              onChange={handleChange}
              style={styles.input}
            />
          </div>

          {/* Loan Type */}
          <div>
            <label style={styles.label}>
              Loan Type <span style={styles.required}>*</span>
            </label>
            <select
              name="loanType"
              value={formData.loanType}
              onChange={handleChange}
              style={styles.input}
            >
              <option value="">Select type</option>
              <option>Agriculture Loan</option>
              <option>Business Loan</option>
              <option>Personal Loan</option>
              <option>Vehicle Loan</option>
              <option>Medical Loan</option>
            </select>
          </div>

          {/* Applicant Type */}
          <div>
            <label style={styles.label}>
              Applicant Type <span style={styles.required}>*</span>
            </label>
            <select
              name="applicantType"
              value={formData.applicantType}
              onChange={handleChange}
              style={styles.input}
            >
              <option value="">Select type</option>
              <option>Salaried</option>
              <option>Self-Employed / Business Owner</option>
            </select>
          </div>

          {/* Loan Amount */}
          <div>
            <label style={styles.label}>
              Loan Amount <span style={styles.required}>*</span>
            </label>
            <input
              name="loanAmount"
              value={formData.loanAmount}
              onChange={handleChange}
              placeholder=""
              style={{width:'100%'}}
            />
            {errors.loanAmount && (
              <div style={styles.errorText}>{errors.loanAmount}</div>
            )}
          </div>

          {/* Email */}
          <div>
            <label style={styles.label}>
              Email <span style={styles.required}>*</span>
            </label>
            <input
              type="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              placeholder="example@email.com"
              style={styles.input}
            />
            {errors.email && (
              <div style={styles.errorText}>{errors.email}</div>
            )}
          </div>

          {/* Phone */}
          <div>
            <label style={styles.label}>
              Phone Number <span style={styles.required}>*</span>
            </label>
            <input
              name="phone"
              value={formData.phone}
              onChange={handleChange}
              placeholder="+91"
              style={styles.input}
            />
            {errors.phone && (
              <div style={styles.errorText}>{errors.phone}</div>
            )}
          </div>
        </div>

        {/* Info box */}
        <div style={styles.infoBox}>
          Based on this information, the system will determine the required
          supporting documents.
        </div>
      </div>
    </div>
  );
}

/* ===================== STYLES (CARBON + KAARA) ===================== */

const styles = {
  wrapper: {
    maxWidth: 1000,
    background: "#ffffff",
    border: "1px solid #e0e0e0",
    borderRadius: 8,
  },

  header: {
    padding: "14px 20px",
    fontSize: 14,
    fontWeight: 600,
    color: "#161616",
    borderBottom: "1px solid #e0e0e0",
    background: "#f4f4f4",
  },

  form: {
    padding: 20,
  },

  grid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: 20,
  },

  label: {
    display: "block",
    marginBottom: 6,
    fontSize: 13,
    fontWeight: 500,
    color: "#161616",
  },

  required: {
    color: "#da1e28", // Kaara red
  },

  input: {
    width: "100%",
    height: 40,
    padding: "8px 12px",
    borderRadius: 4,
    borderWidth: 1,
    borderStyle: "solid",
    borderColor: "#8d8d8d",
    fontSize: 14,
    color: "#161616",
    background: "#ffffff",
  },

  errorText: {
    marginTop: 6,
    fontSize: 12,
    color: "#da1e28",
  },

  infoBox: {
    marginTop: 20,
    padding: 12,
    background: "rgba(218, 30, 40, 0.06)", // Kaara red tint
    color: "#a1121f",
    borderRadius: 6,
    fontSize: 13,
    border: "1px solid rgba(218, 30, 40, 0.2)",
  },
};
