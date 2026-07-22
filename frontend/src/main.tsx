import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { AuthProvider } from "./context/AuthContext";
import { DemoProvider } from "./context/DemoContext";
import { SudoViewProvider } from "./context/SudoViewContext";
import { ToastProvider } from "./context/ToastContext";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AuthProvider>
      <ToastProvider>
        <SudoViewProvider>
          <DemoProvider>
            <App />
          </DemoProvider>
        </SudoViewProvider>
      </ToastProvider>
    </AuthProvider>
  </StrictMode>,
);
