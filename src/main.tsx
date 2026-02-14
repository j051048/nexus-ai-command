import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import "./index.css";
import "./styles/mobile.css";

// Service Worker is now auto-registered by vite-plugin-pwa (registerType: 'autoUpdate')

createRoot(document.getElementById("root")!).render(<App />);
