import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import QuantAlphaFoundry from "../quant-alpha-foundry.jsx";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <QuantAlphaFoundry />
  </StrictMode>
);
