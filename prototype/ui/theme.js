// dakit theme boot (runs before first paint): a stored choice wins,
// otherwise the OS preference decides. Storage can throw in private modes.
(function () {
  var stored = null;
  try { stored = localStorage.getItem("dakit-theme"); } catch (e) { stored = null; }
  document.documentElement.dataset.theme =
    stored === "dark" || stored === "light"
      ? stored
      : (window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
})();
