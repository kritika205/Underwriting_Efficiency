import { useNavigate } from "react-router-dom";

export default function ClientDashboard() {
  const navigate = useNavigate();

  return (
    <div style={s.page}>
      <div style={s.shell}>
        <div style={s.header}>
          <div>
            <h2 style={s.title}>Client Workspace</h2>
            <p style={s.subtitle}>Manage your loan applications securely</p>
          </div>
        </div>

        <div style={s.grid}>
          <div style={s.card} onClick={() => navigate("/client/apply")}>
            <div style={s.icon}>📄</div>
            <h4 style={s.cardTitle}>Upload Documents</h4>
            <p style={s.cardText}>
              Submit income proofs, identity and financial documents.
            </p>
          </div>

          <div style={s.card} onClick={() => navigate("/client/status")}>
            <div style={s.icon}>📊</div>
            <h4 style={s.cardTitle}>Application Status</h4>
            <p style={s.cardText}>
              Track approval progress and underwriter comments.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
const s = {
  page: {
    minHeight: "100vh",
    background: "#f4f4f4",
    display: "flex",
    justifyContent: "center",
    alignItems: "center"
  },

  shell: {
    background: "#ffffff",
    width: 780,
    padding: 40,
    borderRadius: 8,
    boxShadow: "0 12px 30px rgba(0,0,0,0.08)"
  },

  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    borderBottom: "1px solid #e5e7eb",
    paddingBottom: 18,
    marginBottom: 32
  },

  title: { margin: 0, fontSize: 22, color: "#111827" },

  subtitle: { margin: "4px 0 0", fontSize: 13, color: "#6b7280" },


  grid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: 24
  },

  card: {
    background: "#f9fafb",
    border: "1px solid #e5e7eb",
    padding: 26,
    borderRadius: 10,
    cursor: "pointer",
    transition: "all .25s",
    display: "flex",
    flexDirection: "column",
    gap: 10
  },

  icon: { fontSize: 30 },

  cardTitle: { margin: 0, fontSize: 16, color: "#111827" },

  cardText: { margin: 0, fontSize: 13, color: "#6b7280", lineHeight: 1.4 }
};
