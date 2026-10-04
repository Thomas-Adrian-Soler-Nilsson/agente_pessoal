"use strict";

function isPasswordField(element) {
  if (!element) return false;
  const tagName = String(element.nodeName || element.tagName || "").toUpperCase();
  if (tagName !== "INPUT") return false;

  const getAttribute = name => typeof element.getAttribute === "function" ? element.getAttribute(name) : "";
  const type = String(element.type || getAttribute("type") || "").trim().toLowerCase();
  const autocomplete = String(element.autocomplete || getAttribute("autocomplete") || "").trim().toLowerCase();
  const tokens = autocomplete.split(/\s+/).filter(Boolean);
  return type === "password" || tokens.includes("current-password") || tokens.includes("new-password");
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { isPasswordField };
}
