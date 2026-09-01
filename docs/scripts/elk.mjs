import elkLayouts from "https://unpkg.com/@mermaid-js/layout-elk@0.2/dist/mermaid-layout-elk.esm.min.mjs";
import mermaid from "https://unpkg.com/mermaid@11/dist/mermaid.esm.min.mjs";

mermaid.registerLayoutLoaders(elkLayouts);

mermaid.initialize({
  layout: "elk",
  startOnLoad: false,
  securityLevel: "loose",
});

window.mermaid = mermaid;
