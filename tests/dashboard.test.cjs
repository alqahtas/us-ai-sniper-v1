const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const html = fs.readFileSync(path.join(__dirname, "../src/us_sniper/dashboard.html"), "utf8");
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const {
  validateSnapshot, displayState, connectionState, emptySnapshot, simulationSnapshot
} = vm.runInNewContext(script + "\n({validateSnapshot, displayState, connectionState, emptySnapshot, simulationSnapshot})");

test("each simulation scenario is valid and has a distinct outcome", () => {
  for (const scenario of ["not_run", "no_valid_data", "no_opportunities", "accepted"]) {
    const snapshot = simulationSnapshot(scenario);
    assert.equal(validateSnapshot(snapshot, "simulation"), true);
    assert.equal(displayState(snapshot), scenario);
    assert.equal(validateSnapshot(snapshot, "ibkr_paper"), false);
  }
});

test("paper snapshots require a read-only paper feed", () => {
  const base = emptySnapshot();
  assert.equal(validateSnapshot(base, "ibkr_paper"), true);
  assert.equal(validateSnapshot({...base, mode: "live"}, "ibkr_paper"), false);
  assert.equal(validateSnapshot({...base, read_only: false}, "ibkr_paper"), false);
  assert.equal(validateSnapshot({...base, schema_version: 2}, "ibkr_paper"), false);
});

test("valid completed scans may have zero opportunities, but require usable symbols", () => {
  const snapshot = simulationSnapshot("no_opportunities");
  snapshot.source = "ibkr_paper";
  assert.equal(validateSnapshot(snapshot, "ibkr_paper"), true);
  assert.equal(displayState(snapshot), "no_opportunities");
  snapshot.scan.valid_symbols = [];
  assert.equal(validateSnapshot(snapshot, "ibkr_paper"), false);
});

test("accepted opportunities require valid price ordering, score, reasons and symbol", () => {
  const invalid = [
    {stop: 130}, {entry: "124.35"}, {target: Infinity}, {score: 101}, {reasons: [" "]}, {symbol: "DEMO-C"}
  ];
  for (const change of invalid) {
    const snapshot = simulationSnapshot("accepted");
    Object.assign(snapshot.scan.opportunities[0], change);
    assert.equal(validateSnapshot(snapshot, "simulation"), false);
  }
  const short = simulationSnapshot("accepted");
  short.scan.opportunities[1].target = 83;
  assert.equal(validateSnapshot(short, "simulation"), false);
});

test("a paper connection status expires and future timestamps cannot confirm a connection", () => {
  const snapshot = emptySnapshot();
  const time = "2026-01-05T15:30:00Z";
  const now = Date.parse(time);
  assert.equal(connectionState(snapshot, now), "unknown");
  snapshot.connection = {state: "connected", checked_at: time};
  assert.equal(validateSnapshot(snapshot, "ibkr_paper"), true);
  assert.equal(connectionState(snapshot, now + 60_000), "connected");
  assert.equal(connectionState(snapshot, now + 300_001), "stale");
  assert.equal(connectionState(snapshot, now - 1), "stale");
  snapshot.connection.checked_at = "2026-01-05T15:30:00";
  assert.equal(validateSnapshot(snapshot, "ibkr_paper"), false);
});
