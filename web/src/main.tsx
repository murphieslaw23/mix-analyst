import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { bootstrapApiSession } from "./auth/session";
import "./index.css";

bootstrapApiSession();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
