"use strict";
const releaseApi = "https://api.github.com/repos/BeastSlaya1/Stat-Tracker/releases/tags/v4.0.4";
const releasePrefix = "https://github.com/BeastSlaya1/Stat-Tracker/releases/download/v4.0.4/";
const platforms = {
  android: {name: "Stat-Tracker-Android-4.0.4.apk", size: 165938953, label: "Download for Android"},
  windows: {name: "Stat-Tracker-Windows-4.0.4-Setup.exe", size: 75090371, label: "Download for Windows"}
};
function releaseAsset(release, platform) {
  if (!release || release.draft || !Array.isArray(release.assets)) return null;
  return release.assets.find(asset => asset.name === platform.name &&
    asset.size === platform.size && asset.state === "uploaded" &&
    asset.browser_download_url === releasePrefix + platform.name) || null;
}
function appleLink(value) {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && !url.username && !url.password &&
      ((url.hostname === "testflight.apple.com" && url.pathname.startsWith("/join/")) ||
       (url.hostname === "apps.apple.com" && /\/id[0-9]+/.test(url.pathname))) ? url : null;
  } catch { return null; }
}
function showLink(id, url, label, status) {
  const link = document.createElement("a");
  link.href = url;
  link.textContent = label;
  document.getElementById(id + "-action").replaceChildren(link);
  document.getElementById(id + "-status").textContent = status;
}
async function loadDownloads() {
  const apple = appleLink(window.STAT_TRACKER_DOWNLOADS?.appleUrl);
  if (apple) {
    const beta = apple.hostname === "testflight.apple.com";
    showLink("apple", apple.href, beta ? "Join on TestFlight" : "View on the App Store",
      beta ? "Install Apple’s TestFlight app to join the beta." : "Available for iPhone and iPad.");
    document.getElementById("apple-details").textContent = beta ? "iPhone & iPad beta" : "iPhone & iPad";
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 8000);
  try {
    const response = await fetch(releaseApi, {signal: controller.signal, headers: {Accept: "application/vnd.github+json"}});
    if (response.status !== 404 && !response.ok) throw new Error("Release unavailable");
    const release = response.status === 404 ? null : await response.json();
    for (const [id, platform] of Object.entries(platforms)) {
      const asset = releaseAsset(release, platform);
      if (asset) showLink(id, asset.browser_download_url, platform.label,
        "Version 4.0.4 · Download hosted on GitHub");
      else {
        document.querySelector("#" + id + "-action button").textContent = "Not yet published";
        document.getElementById(id + "-status").textContent = "The updated download will appear here once released.";
      }
    }
  } catch {
    for (const id of Object.keys(platforms)) {
      showLink(id, "https://github.com/BeastSlaya1/Stat-Tracker/releases", "Check downloads on GitHub",
        "We couldn’t check availability. Open the releases page to see published files.");
    }
  } finally { clearTimeout(timer); }
}
if (typeof module !== "undefined") module.exports = {releaseAsset, appleLink, platforms};
if (typeof document !== "undefined") loadDownloads();
