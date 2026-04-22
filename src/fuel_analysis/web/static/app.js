/* Global app bootstrapping: service worker registration, nothing else. */

(function registerServiceWorker() {
  if (!("serviceWorker" in navigator)) return;
  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("/static/sw.js", { scope: "/" })
      .catch((err) => console.warn("SW registration failed:", err));
  });
})();
