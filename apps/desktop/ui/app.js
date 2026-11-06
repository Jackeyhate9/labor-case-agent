let runtimeInfo = {
  api_base: "http://127.0.0.1:17831",
  web_base: "http://127.0.0.1:3000",
  session_token: "",
};
const statusDot = document.querySelector("#status-dot");
const statusTitle = document.querySelector("#status-title");
const statusDetail = document.querySelector("#status-detail");

async function loadRuntimeInfo() {
  try {
    const invoke = window.__TAURI__?.core?.invoke;
    if (!invoke) return runtimeInfo;
    const info = await invoke("runtime_info");
    runtimeInfo = info;
    document.querySelector("#data-dir").textContent = info.data_dir;
    document.querySelector("#model-dir").textContent = info.model_dir;
    return info;
  } catch (error) {
    console.warn("Runtime path query failed", error);
    return runtimeInfo;
  }
}

async function checkHealth() {
  statusDot.className = "dot pending";
  statusTitle.textContent = "Checking the local API...";
  statusDetail.textContent = runtimeInfo.api_base;
  try {
    const response = await fetch(`${runtimeInfo.api_base}/api/system/health`, {
      cache: "no-store",
      credentials: "include",
      headers: runtimeInfo.session_token
        ? { "X-App-Session": runtimeInfo.session_token }
        : {},
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    const result = payload.data ?? payload;
    statusDot.className = "dot ok";
    statusTitle.textContent = "Local API is ready";
    statusDetail.textContent = `Status: ${result.status ?? "healthy"} · Version: ${result.version ?? "unknown"}`;
    await checkWorkspace();
  } catch (error) {
    statusDot.className = "dot fail";
    statusTitle.textContent = "Local API is not ready yet";
    statusDetail.textContent = `Retrying automatically. ${String(error)}`;
  }
}

async function checkWorkspace() {
  try {
    const response = await fetch(runtimeInfo.web_base, { cache: "no-store", mode: "no-cors" });
    if (response) {
      const fragment = new URLSearchParams({
        app_session: runtimeInfo.session_token,
        api_base: runtimeInfo.api_base,
      });
      window.location.replace(`${runtimeInfo.web_base}/#${fragment.toString()}`);
    }
  } catch {
    statusDetail.textContent = "API is ready; waiting for the full workspace...";
  }
}

document.querySelector("#retry").addEventListener("click", checkHealth);

async function bootstrap() {
  await loadRuntimeInfo();
  await checkHealth();
  setTimeout(checkHealth, 2500);
}

void bootstrap();
