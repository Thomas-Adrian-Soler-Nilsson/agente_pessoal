const assert = require("node:assert/strict");
const { test } = require("node:test");

let fieldPolicy = {};
try {
  fieldPolicy = require("./field_policy.js");
} catch (_) {
  // RED phase: a missing production policy is asserted as a behavior failure below.
}

test("classifies password type and password autocomplete tokens", () => {
  assert.equal(typeof fieldPolicy.isPasswordField, "function", "password classifier is available");
  assert.equal(fieldPolicy.isPasswordField({ nodeName: "INPUT", type: "password" }), true);
  assert.equal(fieldPolicy.isPasswordField({
    nodeName: "INPUT",
    type: "text",
    autocomplete: "section-login current-password",
  }), true);
  assert.equal(fieldPolicy.isPasswordField({
    nodeName: "INPUT",
    type: "text",
    autocomplete: "new-password",
  }), true);
});

test("allows ordinary text and textarea fields", () => {
  assert.equal(typeof fieldPolicy.isPasswordField, "function", "password classifier is available");
  assert.equal(fieldPolicy.isPasswordField({ nodeName: "INPUT", type: "text", autocomplete: "username" }), false);
  assert.equal(fieldPolicy.isPasswordField({ nodeName: "TEXTAREA", autocomplete: "new-password" }), false);
});
