"use strict";

const assert = require("node:assert/strict");
const {
  normalizeFocalPoint,
  normalizeFitMode,
  normalizeGalleryItem,
  focalPointFor,
  objectPosition,
  frameSpecFor,
  applyFocalPoint,
  applyPublicFrame,
} = require("../assets/js/media-presentation.js");

assert.deepEqual(normalizeFocalPoint(), {x:50, y:50});
assert.deepEqual(normalizeFocalPoint({x:-10, y:140}), {x:0, y:100});
assert.deepEqual(focalPointFor({hero:"media/dog.jpg"}, "hero"), {x:50, y:50});
assert.deepEqual(focalPointFor({focal_points:{hero:{x:35, y:22}}}, "hero"), {x:35, y:22});
assert.equal(objectPosition({x:35, y:22}), "35% 22%");
assert.equal(normalizeFitMode("contain"), "contain");
assert.equal(normalizeFitMode("unsupported"), "cover");
assert.deepEqual(normalizeGalleryItem("media/dog.jpg"), {path:"media/dog.jpg", focal_point:{x:50,y:50}, fit_mode:"cover"});
assert.deepEqual(normalizeGalleryItem({path:"media/dog-02.jpg", focal_point:{x:38,y:21}, fit_mode:"contain", caption:"Front"}), {path:"media/dog-02.jpg", focal_point:{x:38,y:21}, fit_mode:"contain", caption:"Front"});
const element = {style:{}};
applyFocalPoint(element, {x:61, y:39});
assert.equal(element.style.objectPosition, "61% 39%");

assert.deepEqual(frameSpecFor("hero"), {aspectRatio:"4 / 5", orientation:"portrait", fit:"cover"});
assert.deepEqual(frameSpecFor("head"), {aspectRatio:"4 / 5", orientation:"portrait", fit:"cover"});
assert.deepEqual(frameSpecFor("stack"), {aspectRatio:"4 / 5", orientation:"portrait", fit:"contain"});
assert.deepEqual(frameSpecFor("movement"), {aspectRatio:"3 / 2", orientation:"landscape", fit:"cover"});
assert.deepEqual(frameSpecFor("movement_video"), {aspectRatio:"3 / 2", orientation:"landscape", fit:"cover"});
assert.deepEqual(frameSpecFor("gallery"), {aspectRatio:"4 / 5", orientation:"portrait", fit:"cover"});
assert.deepEqual(frameSpecFor("profile"), {aspectRatio:"16 / 10", orientation:"landscape", fit:"contain"});

const publicImage = {style:{}};
applyPublicFrame(publicImage, {focal_points:{hero:{x:42,y:27}}}, "hero");
assert.equal(publicImage.style.aspectRatio, "4 / 5");
assert.equal(publicImage.style.objectFit, "cover");
assert.equal(publicImage.style.objectPosition, "42% 27%");

const legacyImage = {style:{}};
applyPublicFrame(legacyImage, {}, "hero");
assert.equal(legacyImage.style.objectPosition, "50% 50%");

console.log("Portrait-first frame mapping and focal-point compatibility PASS");
