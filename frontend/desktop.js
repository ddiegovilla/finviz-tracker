export const desktop = { enabled: false, csrf: "", running: false, revision: null };

export function timeoutSignal() {
  if (AbortSignal.timeout) return AbortSignal.timeout(15000);
  const controller = new AbortController();
  setTimeout(() => controller.abort(), 15000);
  return controller.signal;
}

export async function initializeDesktop(reload) {
  const controls = document.querySelector("#desktop-controls");
  const button = document.querySelector("#run-scan");
  const status = document.querySelector("#desktop-status");
  let polling = false;
  let stickyMessage = "";

  async function poll() {
    if (polling) return;
    polling = true;
    try {
      const response = await fetch("/api/desktop", { signal: timeoutSignal() });
      if (!response.ok) {
        if (desktop.enabled) throw new Error("Scan status unavailable. Try again shortly.");
        return;
      }
      const data = await response.json();
      const changed = desktop.revision !== null && data.revision !== desktop.revision;
      Object.assign(desktop, { enabled: true, csrf: data.csrf, running: data.running, revision: data.revision });
      controls.hidden = false;
      button.disabled = data.running;
      button.textContent = data.running ? "Scanning…" : "Run Scan";
      controls.setAttribute("aria-busy", String(data.running));
      document.querySelector("#desktop-heading").textContent = data.running ? "Collecting your filters" : "Daily collection";
      const message = data.running || data.message ? data.message : data.complete_today
        ? `Today’s complete scan is saved (${data.timezone}). Run again whenever you need.`
        : `No complete scan today (${data.timezone}). Choose Run Scan to collect all seven filters.`;
      const nextMessage = stickyMessage || message;
      if (status.textContent !== nextMessage) status.textContent = nextMessage;
      if (changed) await reload();
    } catch (error) {
      if (desktop.enabled) status.textContent = error.message;
    } finally {
      polling = false;
    }
  }

  window.runDesktopScan = async () => {
    if (!desktop.enabled || button.disabled) return;
    stickyMessage = "";
    button.disabled = true;
    status.textContent = "Starting seven-filter scan…";
    try {
      const response = await fetch("/api/scan", { method: "POST", headers: { "X-Finviz-Token": desktop.csrf }, signal: timeoutSignal() });
      if (!response.ok && response.status !== 409) throw new Error("The scan could not start. Try again.");
      await poll();
    } catch (error) {
      status.textContent = error.message;
      button.disabled = false;
    }
  };
  window.desktopMessage = async message => {
    stickyMessage = message;
    status.textContent = message;
    await reload();
    await poll();
  };
  button.addEventListener("click", window.runDesktopScan);
  await poll();
  if (desktop.enabled) {
    document.querySelector("footer > span:last-child").textContent = "Local history · Scans run only while the app is open";
    setInterval(poll, 1000);
  }
}
