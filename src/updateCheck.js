// Update check for when the app is NOT running inside Electron (`npm run web`,
// or the app opened in a browser). Electron's main process does its own check
// and pushes the result over IPC; this is the same check from the renderer.
//
// The install path is a git clone, so "an update" means main's package.json has
// a higher version than the one baked in at build time. raw.githubusercontent
// sends CORS headers, so the fetch works from a page.

const REPO = typeof __APP_REPO__ === "string" && __APP_REPO__
  ? __APP_REPO__
  : "SyedmaazSaif/career-copilot";

export const CURRENT_VERSION =
  typeof __APP_VERSION__ === "string" ? __APP_VERSION__ : "0.0.0";

const REMOTE_PKG_URL = `https://raw.githubusercontent.com/${REPO}/main/package.json`;
export const RELEASES_URL = `https://github.com/${REPO}/releases`;

// Compare dotted numeric versions. Returns 1 if a > b, -1 if a < b, else 0.
export function compareVersions(a, b) {
  const pa = String(a).split(".").map((n) => parseInt(n, 10) || 0);
  const pb = String(b).split(".").map((n) => parseInt(n, 10) || 0);
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    const d = (pa[i] || 0) - (pb[i] || 0);
    if (d !== 0) return d > 0 ? 1 : -1;
  }
  return 0;
}

/** Resolve to {current, latest, url} when an update exists, else null.
 *  Never throws: an update check must not be able to break the app. */
export async function checkForUpdate() {
  try {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 5000);
    const res = await fetch(REMOTE_PKG_URL, {
      signal: ctrl.signal,
      cache: "no-store",
    });
    clearTimeout(timer);
    if (!res.ok) return null;
    const latest = (await res.json()).version;
    if (latest && compareVersions(latest, CURRENT_VERSION) > 0) {
      return { current: CURRENT_VERSION, latest, url: RELEASES_URL };
    }
  } catch {
    /* offline, blocked, or malformed — best-effort only */
  }
  return null;
}
