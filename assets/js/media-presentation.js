(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.DIMedia = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const ORIGINAL_FRAME_SPEC = Object.freeze({
    aspectRatio: "",
    orientation: "original",
    fit: "contain",
  });
  const PUBLIC_FRAME_SPECS = Object.freeze({
    hero: Object.freeze({ aspectRatio: "4 / 5", orientation: "portrait", fit: "cover" }),
    head: Object.freeze({ aspectRatio: "4 / 5", orientation: "portrait", fit: "cover" }),
    profile: Object.freeze({ aspectRatio: "16 / 10", orientation: "landscape", fit: "contain" }),
    stack: Object.freeze({ aspectRatio: "4 / 5", orientation: "portrait", fit: "contain" }),
    movement: Object.freeze({ aspectRatio: "3 / 2", orientation: "landscape", fit: "cover" }),
    movement_video: Object.freeze({ aspectRatio: "3 / 2", orientation: "landscape", fit: "cover" }),
    gallery: Object.freeze({ aspectRatio: "4 / 5", orientation: "portrait", fit: "cover" }),
  });

  const clamp = value => Math.min(100, Math.max(0, Number(value)));

  function normalizeFocalPoint(value) {
    const x = Number(value && value.x);
    const y = Number(value && value.y);
    return {
      x: Number.isFinite(x) ? clamp(x) : 50,
      y: Number.isFinite(y) ? clamp(y) : 50,
    };
  }

  function focalPointFor(media, role) {
    return normalizeFocalPoint(media && media.focal_points && media.focal_points[role]);
  }

  function objectPosition(value) {
    const point = normalizeFocalPoint(value);
    return `${point.x}% ${point.y}%`;
  }

  function normalizeFitMode(value) {
    return String(value || "").toLowerCase() === "contain" ? "contain" : "cover";
  }

  function normalizeGalleryItem(value) {
    const source = value && typeof value === "object" ? value : {};
    const path = String(typeof value === "string" ? value : source.path || "").trim();
    if (!path) return null;
    const item = {
      path,
      focal_point: normalizeFocalPoint(source.focal_point),
      fit_mode: normalizeFitMode(source.fit_mode),
    };
    const caption = String(source.caption || "").trim();
    if (caption) item.caption = caption;
    return item;
  }

  function frameSpecFor(role) {
    return PUBLIC_FRAME_SPECS[String(role || "").toLowerCase()] || ORIGINAL_FRAME_SPEC;
  }

  function applyFocalPoint(element, value) {
    if (element && element.style) element.style.objectPosition = objectPosition(value);
    return element;
  }

  function applyPublicFrame(element, media, role) {
    if (!element || !element.style) return element;
    const spec = frameSpecFor(role);
    element.style.objectFit = spec.fit;
    element.style.objectPosition = objectPosition(focalPointFor(media, role));
    if (spec.aspectRatio) element.style.aspectRatio = spec.aspectRatio;
    else if (typeof element.style.removeProperty === "function") element.style.removeProperty("aspect-ratio");
    else element.style.aspectRatio = "";
    return element;
  }

  return Object.freeze({
    normalizeFocalPoint,
    normalizeFitMode,
    normalizeGalleryItem,
    focalPointFor,
    objectPosition,
    frameSpecFor,
    applyFocalPoint,
    applyPublicFrame,
  });
});
