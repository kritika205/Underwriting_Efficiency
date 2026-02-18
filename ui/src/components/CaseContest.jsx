import { createContext, useContext, useState } from "react";

const CaseContext = createContext();

export function CaseProvider({ children }) {

  const [cases, setCases] = useState([
    {
      name: "Pinky Surajkumar Chourasiya",
      caseId: "UW-2024-1844",
      risk: "Critical",
      flags: 7,
      status: "Escalated",
      updated: "1h ago",
    },
    {
      name: "Emma Thompson",
      caseId: "UW-2024-1843",
      risk: "Medium",
      flags: 3,
      status: "In Review",
      updated: "4h ago",
    }
  ]);

  const updateDecision = (caseId, decision) => {
    setCases(prev =>
      prev.map(c =>
        c.caseId === caseId
          ? { ...c, status: decision, updated: "Just now" }
          : c
      )
    );
  };

  return (
    <CaseContext.Provider value={{ cases, updateDecision }}>
      {children}
    </CaseContext.Provider>
  );
}

export const useCases = () => useContext(CaseContext);
