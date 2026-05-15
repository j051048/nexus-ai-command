import { createRoot } from "react-dom/client";
import React from "react";
import App from "./App.tsx";
import "./index.css";
import "./styles/mobile.css";
import { reportWebVitals } from "./lib/webVitals";

// Service Worker is now auto-registered by vite-plugin-pwa (registerType: 'autoUpdate')

const app = import.meta.env.DEV ? (
  <React.StrictMode>
    <App />
  </React.StrictMode>
) : (
  <App />
);

createRoot(document.getElementById("root")!).render(app);

// Report Core Web Vitals (LCP, CLS, INP, FCP, TTFB) to Sentry in production
reportWebVitals();
