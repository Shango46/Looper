(function () {
  const POLL_MS = 15000;
  const STORAGE_KEY = "looper_last_seen_approval_count";

  function beep() {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.frequency.value = 880;
      gain.gain.setValueAtTime(0.15, ctx.currentTime);
      osc.start();
      osc.stop(ctx.currentTime + 0.18);
    } catch (e) {
      /* audio not available, ignore */
    }
  }

  function updateBadge(count) {
    const badge = document.getElementById("approvals-badge");
    if (!badge) return;
    if (count > 0) {
      badge.textContent = count;
      badge.style.display = "inline-block";
    } else {
      badge.style.display = "none";
    }
  }

  async function poll() {
    try {
      const resp = await fetch("/approvals/pending-count");
      const data = await resp.json();
      const count = data.count || 0;
      updateBadge(count);

      const lastSeen = parseInt(localStorage.getItem(STORAGE_KEY) || "0", 10);
      if (count > lastSeen) {
        if (window.Notification && Notification.permission === "granted") {
          new Notification("Looper: approval needed", {
            body: `${count} action${count === 1 ? "" : "s"} pending your approval.`,
          });
        }
        beep();
      }
      localStorage.setItem(STORAGE_KEY, String(count));
    } catch (e) {
      /* server not reachable, ignore this cycle */
    }
  }

  if (window.Notification && Notification.permission === "default") {
    Notification.requestPermission();
  }

  poll();
  setInterval(poll, POLL_MS);
})();
