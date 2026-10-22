#!/usr/bin/env node
/**
 * Start career-copilot with nothing on screen but the app window.
 *
 * The old launch path was `npm run dev`, which runs `concurrently` to start
 * Vite and Electron. That works, but every layer of it is a console program:
 * npm, concurrently and the two children each want a terminal, so starting the
 * app meant a Terminal window on macOS and a cmd/PowerShell window on Windows
 * sitting there for as long as the app ran. Closing it killed the app, so it
 * could not even be tidied away.
 *
 * This script replaces that whole chain with one Node process that spawns Vite
 * and Electron directly -- no npm, no shell, no `cmd /c`, and `windowsHide` on
 * every child. Output goes to a log file instead of a screen nobody reads:
 *
 *     ~/.career-copilot/logs/app.log        (macOS / Linux)
 *     %USERPROFILE%\.career-copilot\logs\app.log   (Windows)
 *
 * Run it directly -- `node scripts/start.js` -- or via `npm start`. Developers
 * who do want the live output in a terminal still have `npm run dev`.
 */
"use strict";

const { spawn } = require("child_process");
const fs = require("fs");
const net = require("net");
const os = require("os");
const path = require("path");

const ROOT = path.join(__dirname, "..");
const VITE_PORT = 5173;
const LOG_DIR = path.join(os.homedir(), ".career-copilot", "logs");
const LOG_FILE = path.join(LOG_DIR, "app.log");
const MAX_LOG_BYTES = 5 * 1024 * 1024;

// ---------------------------------------------------------------------------
// Logging. Nothing this script writes should ever reach a console, because
// there is deliberately no console to write to.
// ---------------------------------------------------------------------------
fs.mkdirSync(LOG_DIR, { recursive: true });
try {
  // Keep one previous run's log, so a crash is still diagnosable, and stop the
  // file growing without bound.
  if (fs.statSync(LOG_FILE).size > MAX_LOG_BYTES) {
    fs.renameSync(LOG_FILE, `${LOG_FILE}.1`);
  }
} catch {
  /* no log yet -- nothing to rotate */
}
// Written synchronously on purpose. A buffered stream loses whatever has not
// been flushed when the process exits, and the lines most worth keeping are the
// ones written immediately before a fatal exit -- with no console, the log is
// the only place they could ever appear.
function log(message) {
  try {
    fs.appendFileSync(LOG_FILE, `[${new Date().toISOString()}] ${message}\n`);
  } catch {
    /* an unwritable log must never be the reason the app fails to start */
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
// Vite's "localhost" can resolve to either loopback address depending on the
// machine's DNS order, and checking only one used to mean an already-running
// server on the other family went undetected -- so a second launch tried to
// bind the port again, crashed, and orphaned the first, working server with
// nothing left to manage it. Checking both closes that gap.
function probeHost(port, host) {
  return new Promise((resolve) => {
    const socket = net.connect({ host, port });
    const done = (answer) => {
      socket.destroy();
      resolve(answer);
    };
    socket.setTimeout(700);
    socket.once("connect", () => done(true));
    socket.once("timeout", () => done(false));
    socket.once("error", () => done(false));
  });
}

async function portInUse(port) {
  const [v4, v6] = await Promise.all([
    probeHost(port, "127.0.0.1"),
    probeHost(port, "::1"),
  ]);
  return v4 || v6;
}

async function waitForPort(port, timeoutMs = 60000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await portInUse(port)) return true;
    await new Promise((r) => setTimeout(r, 300));
  }
  return false;
}

// Children write straight into the log file's descriptor: no pipes to drain,
// and no output can leak to a terminal.
function childStdio() {
  const fd = fs.openSync(LOG_FILE, "a");
  return ["ignore", fd, fd];
}

function fail(message) {
  log(`FATAL: ${message}`);
  log(`Run setup again in this folder to repair the install: ${ROOT}`);
  process.exit(1);
}

// ---------------------------------------------------------------------------
// Start-up
// ---------------------------------------------------------------------------
let vite = null;
let electron = null;
let shuttingDown = false;

function shutdown(code) {
  if (shuttingDown) return;
  shuttingDown = true;
  for (const child of [electron, vite]) {
    if (child && child.exitCode === null && !child.killed) {
      try {
        child.kill();
      } catch {
        /* already gone */
      }
    }
  }
  log(`career-copilot stopped (code ${code})`);
  // A beat for the children to actually die before this process disappears,
  // so nothing is left holding port 5173 or 8000.
  setTimeout(() => process.exit(code), 150);
}

async function main() {
  log("---------------------------------------------");
  log(`career-copilot starting from ${ROOT}`);

  const viteBin = path.join(ROOT, "node_modules", "vite", "bin", "vite.js");
  if (!fs.existsSync(viteBin)) {
    fail("node_modules is missing or incomplete (Vite not found).");
  }

  // Already running? Vite holding the port means an earlier launch is still
  // alive. Start Electron anyway: its single-instance lock will focus the
  // window that already exists and this process will exit straight after.
  if (await portInUse(VITE_PORT)) {
    log(`Vite is already serving on ${VITE_PORT}; reusing it.`);
  } else {
    log("Starting Vite...");
    vite = spawn(process.execPath, [viteBin], {
      cwd: ROOT,
      stdio: childStdio(),
      windowsHide: true,
      env: { ...process.env, FORCE_COLOR: "0" },
    });
    vite.on("error", (err) => fail(`Vite failed to start: ${err.message}`));
    vite.on("exit", (code) => {
      log(`Vite exited (code ${code})`);
      if (!shuttingDown) shutdown(code === null ? 1 : code);
    });

    if (!(await waitForPort(VITE_PORT))) {
      fail(`Vite did not start listening on ${VITE_PORT} within 60s.`);
    }
    log(`Vite is up on ${VITE_PORT}.`);
  }

  // `require("electron")` from plain Node returns the path to the Electron
  // binary (inside Electron it would return the API instead).
  let electronBin;
  try {
    electronBin = require("electron");
  } catch (err) {
    fail(`Electron is not installed: ${err.message}`);
  }
  if (typeof electronBin !== "string" || !fs.existsSync(electronBin)) {
    fail("The Electron binary is missing. Run setup again to repair it.");
  }

  log("Starting the app window...");
  electron = spawn(electronBin, ["."], {
    cwd: ROOT,
    stdio: childStdio(),
    windowsHide: true,
    env: { ...process.env, NODE_ENV: "development" },
  });
  electron.on("error", (err) => fail(`Electron failed to start: ${err.message}`));
  electron.on("exit", (code) => {
    log(`App window closed (code ${code})`);
    shutdown(code === null ? 0 : code);
  });
}

// Closing the app window, logging out, or a `kill` all take everything down
// together -- no orphaned Vite or Python process left listening.
for (const signal of ["SIGINT", "SIGTERM", "SIGHUP"]) {
  process.on(signal, () => shutdown(0));
}
process.on("uncaughtException", (err) => {
  log(`Unexpected error: ${err && err.stack ? err.stack : err}`);
  shutdown(1);
});

main().catch((err) => fail(err && err.stack ? err.stack : String(err)));
