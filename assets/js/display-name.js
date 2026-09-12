(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) {
    root.DIName = api;
    if (root.document) api.installMedicalDisplayFormatting(root.document);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const PARTICLES = new Set(["von", "vom", "van", "de", "del", "di", "da", "der", "den", "of", "the", "la", "le"]);
  const KNOWN_ACRONYMS = new Set(["AD", "BH", "CH", "FCI", "IDC", "IGP", "IPO", "ZTP"]);
  const COMPOUND_SEPARATOR = /([-‐‑‒–—'’])/u;

  function titleSegment(value) {
    const lower = String(value || "").toLocaleLowerCase();
    const letters = Array.from(lower);
    if (!letters.length) return "";
    return letters[0].toLocaleUpperCase() + letters.slice(1).join("");
  }

  function preservedToken(value) {
    const token = String(value || "");
    const upper = token.toLocaleUpperCase();
    if (KNOWN_ACRONYMS.has(upper)) return upper;
    if (/^[IVXLCDM]+$/u.test(upper) && upper.length <= 8) return upper;
    if (/\p{N}/u.test(token) || /[./&+_]/u.test(token)) return token;
    return "";
  }

  function titleToken(value) {
    const preserved = preservedToken(value);
    if (preserved) return preserved;
    return String(value || "")
      .split(COMPOUND_SEPARATOR)
      .map((part, index) => index % 2 ? part : titleSegment(part))
      .join("");
  }

  function editorialCase(source) {
    return source.split(" ").map((token, index) => {
      const lower = token.toLocaleLowerCase();
      if (index > 0 && PARTICLES.has(lower)) return lower;
      return titleToken(token);
    }).join(" ");
  }

  function displayRegisteredName(value) {
    const source = String(value ?? "").normalize("NFC").trim().replace(/\s+/gu, " ");
    if (!source) return "";
    // Preserve intentional mixed capitalization; retain legacy lowercase-input support.
    const mixedCase = source !== source.toLocaleUpperCase() && source !== source.toLocaleLowerCase();
    return mixedCase ? source : editorialCase(source);
  }

  function displayKennelName(value) {
    const source = String(value ?? "").normalize("NFC").trim().replace(/\s+/gu, " ");
    // Normalize shouting-case identity metadata; preserve intentional brand casing.
    const hasCasedLetters = source.toLocaleLowerCase() !== source.toLocaleUpperCase();
    return hasCasedLetters && source === source.toLocaleUpperCase()
      ? editorialCase(source)
      : source;
  }

  function displayMedicalSentence(value) {
    const source = String(value ?? "").normalize("NFC").trim().replace(/\s+/gu, " ");
    if (!source) return "";
    const lower = source.toLocaleLowerCase();
    const sentence = lower[0].toLocaleUpperCase() + lower.slice(1);
    // DCM remains the medical acronym; the surrounding phrase uses sentence case.
    return sentence.replace(/\bdcm\b/giu, "DCM");
  }

  function formatClinicalSubline(value) {
    const source = String(value ?? "").normalize("NFC").trim();
    if (!source) return "";
    return source.split(/\s+·\s+/u).map(part => {
      const trimmed = part.trim();
      // Keep formatted dates intact, e.g. "03 Mar 2026".
      if (/^\d{1,2}\s+[A-Za-z]{3}\s+\d{4}$/u.test(trimmed)) return trimmed;
      return displayMedicalSentence(trimmed);
    }).join(" · ");
  }

  function formatHealthRail(documentRef) {
    const rail = documentRef && documentRef.getElementById
      ? documentRef.getElementById("healthRail")
      : null;
    if (!rail || !rail.querySelectorAll) return false;

    let changed = false;
    rail.querySelectorAll(".surface-card").forEach(card => {
      const key = card.querySelector(".key")?.textContent?.trim() || "";
      const value = card.querySelector(".value");
      const sub = card.querySelector(".sub");

      if (key === "DCM clinical") {
        if (value) {
          const formatted = displayMedicalSentence(value.textContent);
          if (formatted && value.textContent !== formatted) {
            value.textContent = formatted;
            changed = true;
          }
        }
        if (sub) {
          const formatted = formatClinicalSubline(sub.textContent);
          if (formatted && sub.textContent !== formatted) {
            sub.textContent = formatted;
            changed = true;
          }
        }
      } else if (key === "Thyroid" || key === "Eyes") {
        if (value) {
          const formatted = displayMedicalSentence(value.textContent);
          if (formatted && value.textContent !== formatted) {
            value.textContent = formatted;
            changed = true;
          }
        }
      }
    });
    return changed;
  }

  function installMedicalDisplayFormatting(documentRef) {
    const rail = documentRef && documentRef.getElementById
      ? documentRef.getElementById("healthRail")
      : null;
    if (!rail) return false;

    formatHealthRail(documentRef);

    const Observer = (documentRef.defaultView && documentRef.defaultView.MutationObserver)
      || (typeof MutationObserver !== "undefined" ? MutationObserver : null);
    if (!Observer) return true;

    const observer = new Observer(() => formatHealthRail(documentRef));
    observer.observe(rail, { childList: true, subtree: true });
    return true;
  }

  return Object.freeze({
    displayRegisteredName,
    displayKennelName,
    displayMedicalSentence,
    formatClinicalSubline,
    formatHealthRail,
    installMedicalDisplayFormatting
  });
});
