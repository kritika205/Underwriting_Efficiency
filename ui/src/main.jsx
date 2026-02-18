import React from "react";
import ReactDOM from "react-dom/client";
import "./styles/global.css";
import App from "./App";
import { BrowserRouter } from "react-router-dom";
import { CaseProvider } from "./components/CaseContest";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <CaseProvider>
        <App />
      </CaseProvider>
    </BrowserRouter>
  </React.StrictMode>
);
