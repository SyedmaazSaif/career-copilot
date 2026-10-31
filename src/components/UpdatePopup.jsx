import { useState } from "react";

const MAC_CMD =
  "curl -fsSL https://github.com/SyedmaazSaif/career-copilot/releases/latest/download/install-macos.sh | bash";
const WIN_CMD =
  "irm https://github.com/SyedmaazSaif/career-copilot/releases/latest/download/install-windows.ps1 | iex";

function detectOs() {
  const ua = navigator.userAgent || "";
  return /windows/i.test(ua) ? "windows" : "mac";
}

export default function UpdatePopup({
  update,
  updating,
  updateError,
  onUpdateNow,
  onRemindLater,
}) {
  const [copied, setCopied] = useState(false);
  const isWindows = detectOs() === "windows";
  const cmd = isWindows ? WIN_CMD : MAC_CMD;

  async function copy() {
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(cmd);
      } else {
        const ta = document.createElement("textarea");
        ta.value = cmd;
        ta.style.position = "fixed";
        ta.style.opacity = "0";
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
      }
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* copying is best-effort; the user can select the text by hand */
    }
  }

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="upd-title">
      <div className="modal update-modal">
        <div className="modal-head">
          <div className="modal-title-wrap">
            <div>
              <h2 id="upd-title">A new version of Career Copilot is ready</h2>
              <div className="modal-sub">
                You have {update.current} · the new version is {update.latest}
              </div>
            </div>
          </div>
        </div>

        <p className="update-kept">Your profile, saved jobs and applications are kept.</p>

        <p className="update-note">Close Career Copilot before pasting the command.</p>

        <div className="update-cmd-box">
          <code>{cmd}</code>
          <button className="btn-secondary update-copy" onClick={copy}>
            {copied ? "Copied" : "Copy command"}
          </button>
        </div>

        <ol className="update-steps">
          {isWindows ? (
            <>
              <li>Click <strong>Copy command</strong>.</li>
              <li>Click <strong>Start</strong>, type <strong>PowerShell</strong>, press Enter (use PowerShell, not Command Prompt).</li>
              <li>Right-click inside the window to paste, then press Enter.</li>
              <li>Wait until it says it is done; the app reopens by itself. If Windows shows "Windows protected your PC", click More info, then Run anyway.</li>
            </>
          ) : (
            <>
              <li>Click <strong>Copy command</strong>.</li>
              <li>Press <strong>Command + Space</strong>, type <strong>Terminal</strong>, press Enter.</li>
              <li>Press <strong>Command + V</strong> to paste, then press Enter.</li>
              <li>Wait until it says it is done; the app reopens by itself. If asked for a password, type your Mac password (letters will not appear) and press Enter.</li>
            </>
          )}
        </ol>

        {updateError && <div className="update-error">{updateError}</div>}

        <div className="modal-actions">
          {window.copilot?.updateApp && (
            <button className="btn-apply" onClick={onUpdateNow} disabled={updating}>
              {updating ? "Updating…" : "Update now"}
            </button>
          )}
          <button className="btn-secondary" onClick={onRemindLater}>
            Remind me later
          </button>
        </div>
      </div>
    </div>
  );
}
