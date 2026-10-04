(function (root) {
  const MAX_NODES = 30000;
  const MAX_ACTIONABLES = 10000;
  const SAFE_ATTRIBUTES = new Set([
    "id", "class", "role", "aria-label", "title", "name", "type",
    "placeholder", "href", "tabindex", "onclick", "contenteditable",
    "disabled", "autocomplete", "aria-checked", "aria-pressed", "aria-expanded",
    "aria-selected", "aria-disabled"
  ]);
  const ACTIONABLE_TAGS = new Set([
    "a", "button", "input", "textarea", "select", "option", "label", "summary", "iframe", "frame"
  ]);
  const ACTIONABLE_ROLES = new Set([
    "button", "link", "tab", "menuitem", "option", "checkbox", "radio",
    "switch", "textbox", "combobox"
  ]);

  async function signatureFromSnapshot(snapshot, viewport = {}, cryptoProvider = root.crypto) {
    try {
      const strings = snapshot?.strings;
      const documents = snapshot?.documents;
      if (!Array.isArray(strings) || !Array.isArray(documents) || documents.length === 0 || documents.length > 128) return "";
      const stringAt = (index) => Number.isInteger(index) ? String(strings[index] || "") : "";
      const state = [
        "viewport",
        Math.round(Number(viewport.width) || 0),
        Math.round(Number(viewport.height) || 0),
        Math.round(Number(viewport.scrollX) || 0),
        Math.round(Number(viewport.scrollY) || 0),
        Math.round((Number(viewport.dpr) || 1) * 100)
      ];
      let totalNodes = 0;
      let totalActionables = 0;

      for (let documentIndex = 0; documentIndex < documents.length; documentIndex++) {
        const documentSnapshot = documents[documentIndex];
        const nodes = documentSnapshot?.nodes;
        const layout = documentSnapshot?.layout;
        const names = nodes?.nodeName;
        const parents = nodes?.parentIndex;
        if (!Array.isArray(names) || !Array.isArray(parents) || !Array.isArray(layout?.nodeIndex)
          || !Array.isArray(layout?.bounds) || !Array.isArray(layout?.styles)) return "";
        totalNodes += names.length;
        if (totalNodes > MAX_NODES) return "";

        const attributes = Array.from({ length: names.length }, () => ({}));
        for (let nodeIndex = 0; nodeIndex < names.length; nodeIndex++) {
          const flat = nodes.attributes?.[nodeIndex] || [];
          for (let attributeIndex = 0; attributeIndex + 1 < flat.length; attributeIndex += 2) {
            const name = stringAt(flat[attributeIndex]).toLowerCase();
            if (!SAFE_ATTRIBUTES.has(name)) continue;
            attributes[nodeIndex][name] = name === "onclick"
              ? "present"
              : stringAt(flat[attributeIndex + 1]).replace(/\s+/g, " ").trim().slice(0, 240);
          }
        }

        const clickable = new Set(nodes.isClickable?.index || []);
        const actionable = names.map((nameIndex, nodeIndex) => {
          const tag = stringAt(nameIndex).toLowerCase();
          const role = (attributes[nodeIndex].role || "").toLowerCase().trim();
          const tabindex = Number(attributes[nodeIndex].tabindex);
          return ACTIONABLE_TAGS.has(tag)
            || ACTIONABLE_ROLES.has(role)
            || Object.hasOwn(attributes[nodeIndex], "onclick")
            || (Number.isFinite(tabindex) && tabindex >= 0)
            || attributes[nodeIndex].contenteditable === "true"
            || clickable.has(nodeIndex);
        });

        const textByActionable = new Map();
        for (let nodeIndex = 0; nodeIndex < names.length; nodeIndex++) {
          if (stringAt(names[nodeIndex]).toLowerCase() !== "#text") continue;
          const textIndex = nodes.nodeValue?.[nodeIndex];
          let text = stringAt(textIndex).replace(/\s+/g, " ").trim();
          if (!text) continue;
          let ancestor = parents[nodeIndex];
          let depth = 0;
          while (Number.isInteger(ancestor) && ancestor >= 0 && depth++ < 64) {
            if (actionable[ancestor]) {
              const previous = textByActionable.get(ancestor) || "";
              textByActionable.set(ancestor, (previous + " " + text).trim().slice(0, 240));
            }
            ancestor = parents[ancestor];
          }
        }

        const layoutByNode = new Map();
        for (let layoutIndex = 0; layoutIndex < layout.nodeIndex.length; layoutIndex++) {
          layoutByNode.set(layout.nodeIndex[layoutIndex], layoutIndex);
        }
        state.push(
          "document", documentIndex, stringAt(documentSnapshot.frameId),
          stringAt(documentSnapshot.documentURL),
          Math.round(Number(documentSnapshot.scrollOffsetX) || 0),
          Math.round(Number(documentSnapshot.scrollOffsetY) || 0)
        );

        for (let nodeIndex = 0; nodeIndex < names.length; nodeIndex++) {
          if (!actionable[nodeIndex]) continue;
          const layoutIndex = layoutByNode.get(nodeIndex);
          const bounds = layoutIndex === undefined ? null : layout.bounds[layoutIndex];
          if (!Array.isArray(bounds) || bounds.length < 4 || !bounds.every(Number.isFinite)) continue;
          const [left, top, width, height] = bounds;
          if (width <= 1 || height <= 1) continue;
          const styleIndexes = layout.styles[layoutIndex] || [];
          if (!Array.isArray(styleIndexes) || styleIndexes.length < 6) return "";
          const styleValues = styleIndexes.map(stringAt);
          const display = styleValues[0] || "";
          const visibility = styleValues[1] || "";
          const opacity = Number(styleValues[2]);
          const pointerEvents = styleValues[3] || "";
          const cursor = styleValues[4] || "";
          const zIndex = styleValues[5] || "";
          if (display === "none" || visibility === "hidden" || visibility === "collapse" || opacity <= 0.01) continue;

          const tag = stringAt(names[nodeIndex]).toLowerCase();
          const safeAttributes = attributes[nodeIndex];
          totalActionables++;
          if (totalActionables > MAX_ACTIONABLES) return "";
          state.push(
            nodeIndex, tag, safeAttributes.role || "", safeAttributes.id || "",
            safeAttributes.class || "", safeAttributes["aria-label"] || "", safeAttributes.title || "",
            safeAttributes.name || "", safeAttributes.type || "", safeAttributes.placeholder || "",
            safeAttributes.href || "", safeAttributes.autocomplete || "", textByActionable.get(nodeIndex) || "",
            Math.round(left * 10), Math.round(top * 10), Math.round(width * 10), Math.round(height * 10),
            display, visibility, Number.isFinite(opacity) ? opacity : "", pointerEvents, cursor, zIndex,
            Object.hasOwn(safeAttributes, "disabled") ? "disabled" : "enabled",
            safeAttributes.contenteditable || "",
            (nodes.inputChecked?.index || []).includes(nodeIndex) ? "checked" : "unchecked",
            (nodes.optionSelected?.index || []).includes(nodeIndex) ? "selected" : "unselected"
          );
        }
      }

      if (!cryptoProvider?.subtle?.digest || typeof TextEncoder !== "function") return "";
      const bytes = new TextEncoder().encode(JSON.stringify(state));
      const digest = new Uint8Array(await cryptoProvider.subtle.digest("SHA-256", bytes));
      return Array.from(digest, (byte) => byte.toString(16).padStart(2, "0")).join("");
    } catch (_) {
      return "";
    }
  }

  function sameVisualState(captured, current) {
    return typeof captured === "string" && captured.length > 0
      && typeof current === "string" && current.length > 0
      && captured === current;
  }

  root.visualStateGuard = { signatureFromSnapshot, sameVisualState };
  if (typeof module !== "undefined" && module.exports) module.exports = root.visualStateGuard;
})(globalThis);
