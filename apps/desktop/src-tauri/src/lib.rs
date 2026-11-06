use std::process::{Child, Command};
use std::sync::Mutex;

use serde::Serialize;
use tauri::{AppHandle, Manager, RunEvent, State};
use tauri_plugin_shell::{process::CommandChild, ShellExt};
use uuid::Uuid;

struct ProcessState {
    api: Mutex<Option<CommandChild>>,
    web: Mutex<Option<Child>>,
    session_token: String,
    api_port: u16,
    web_port: u16,
}

fn stop_api(child: CommandChild) {
    #[cfg(target_os = "windows")]
    {
        // A PyInstaller one-file executable has a bootloader parent and an
        // extracted child. Killing only the bootloader leaves the API bound
        // to its port, so terminate the complete process tree on Windows.
        let pid = child.pid();
        use std::os::windows::process::CommandExt;
        let _ = Command::new("taskkill")
            .args(["/PID", &pid.to_string(), "/T", "/F"])
            .creation_flags(0x08000000)
            .status();
    }
    #[cfg(not(target_os = "windows"))]
    {
        let _ = child.kill();
    }
}

#[derive(Serialize)]
struct RuntimeInfo {
    api_base: String,
    web_base: String,
    data_dir: String,
    model_dir: String,
    session_token: String,
}

fn local_root() -> std::path::PathBuf {
    if let Some(configured) = std::env::var_os("LABOR_CASE_AGENT_HOME") {
        return std::path::PathBuf::from(configured);
    }
    std::env::var_os("LOCALAPPDATA")
        .map(std::path::PathBuf::from)
        .unwrap_or_else(std::env::temp_dir)
        .join("LaborCaseAgent")
}

fn reserve_loopback_port() -> std::io::Result<u16> {
    let listener = std::net::TcpListener::bind(("127.0.0.1", 0))?;
    Ok(listener.local_addr()?.port())
}

#[tauri::command]
fn runtime_info(state: State<'_, ProcessState>) -> RuntimeInfo {
    let root = local_root();
    RuntimeInfo {
        api_base: format!("http://127.0.0.1:{}", state.api_port),
        web_base: format!("http://127.0.0.1:{}", state.web_port),
        data_dir: root.join("data").display().to_string(),
        model_dir: root.join("models").display().to_string(),
        session_token: state.session_token.clone(),
    }
}

pub fn run() {
    let session_token = Uuid::new_v4().simple().to_string();
    let api_port = reserve_loopback_port().expect("failed to reserve an API port");
    let mut web_port = reserve_loopback_port().expect("failed to reserve a web port");
    while web_port == api_port {
        web_port = reserve_loopback_port().expect("failed to reserve a distinct web port");
    }
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(ProcessState {
            api: Mutex::new(None),
            web: Mutex::new(None),
            session_token,
            api_port,
            web_port,
        })
        .setup(|app| {
            let state = app.state::<ProcessState>();
            let session_token = state.session_token.clone();
            let api_port = state.api_port;
            let web_port = state.web_port;
            let cors_origins = format!(
                "http://tauri.localhost,tauri://localhost,http://127.0.0.1:{web_port}"
            );
            let (_events, api_child) = app
                .shell()
                .sidecar("labor-case-api")?
                .env("APP_SESSION_TOKEN", session_token)
                .env("API_PORT", api_port.to_string())
                .env("CORS_ORIGINS", cors_origins)
                .spawn()?;
            app.state::<ProcessState>()
                .api
                .lock()
                .expect("sidecar mutex poisoned")
                .replace(api_child);

            let resource_dir = app.path().resource_dir()?;
            // On Windows the bundle places configured resources under a
            // `resources` directory next to the installed executable.
            let bundled_resources = resource_dir.join("resources");
            let node = bundled_resources.join("node").join("node.exe");
            let web_dir = bundled_resources.join("web");
            let server = web_dir.join("server.js");
            if !server.is_file() {
                return Err(format!("bundled web entrypoint is missing: {}", server.display()).into());
            }
            let mut command = Command::new(node);
            command
                // Keep the argument relative to `current_dir`: absolute
                // installed paths contain spaces and some Windows Node
                // launch paths split them before Node sees the module name.
                .arg("server.js")
                .current_dir(web_dir)
                .env("HOSTNAME", "127.0.0.1")
                .env("PORT", web_port.to_string())
                .env("NODE_ENV", "production");
            #[cfg(target_os = "windows")]
            {
                use std::os::windows::process::CommandExt;
                command.creation_flags(0x08000000);
            }
            let web_child = command.spawn()?;
            app.state::<ProcessState>()
                .web
                .lock()
                .expect("web mutex poisoned")
                .replace(web_child);
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![runtime_info])
        .build(tauri::generate_context!())
        .expect("failed to build desktop application");

    app.run(|app_handle: &AppHandle, event| {
        if matches!(event, RunEvent::Exit | RunEvent::ExitRequested { .. }) {
            let state = app_handle.state::<ProcessState>();
            let api_child = {
                state
                    .api
                    .lock()
                    .expect("sidecar mutex poisoned")
                    .take()
            };
            if let Some(child) = api_child {
                stop_api(child);
            }
            let web_child = {
                state
                    .web
                    .lock()
                    .expect("web mutex poisoned")
                    .take()
            };
            if let Some(mut child) = web_child {
                let _ = child.kill();
                let _ = child.wait();
            }
        }
    });
}
