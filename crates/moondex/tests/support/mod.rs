use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::{SystemTime, UNIX_EPOCH};

pub struct TestProject {
    root: PathBuf,
}

impl TestProject {
    pub fn new(name: &str) -> Self {
        let root = std::env::temp_dir().join(format!(
            "moondex-cli-{name}-{}-{}",
            std::process::id(),
            unix_millis()
        ));
        fs::create_dir_all(&root).expect("create temp project");
        Self { root }
    }

    pub fn path(&self) -> &Path {
        &self.root
    }
}

impl Drop for TestProject {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.root);
    }
}

pub fn run_ok(project: &TestProject, args: &[&str]) -> serde_json::Value {
    run_ok_vec(project, args.iter().map(|arg| arg.to_string()).collect())
}

pub fn run_ok_vec(project: &TestProject, args: Vec<String>) -> serde_json::Value {
    let output = command_output(project, args);
    assert!(
        output.status.success(),
        "expected success\nstdout:\n{}\nstderr:\n{}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    let envelope = parse_stdout(&output.stdout);
    assert_eq!(envelope["ok"], true, "expected ok envelope: {envelope}");
    envelope
}

pub fn run_err(project: &TestProject, args: &[&str]) -> serde_json::Value {
    let output = command_output(project, args.iter().map(|arg| arg.to_string()).collect());
    assert!(
        !output.status.success(),
        "expected failure\nstdout:\n{}\nstderr:\n{}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    let envelope = parse_stdout(&output.stdout);
    assert_eq!(envelope["ok"], false, "expected error envelope: {envelope}");
    envelope
}

fn command_output(project: &TestProject, args: Vec<String>) -> std::process::Output {
    Command::new(env!("CARGO_BIN_EXE_moondex"))
        .current_dir(project.path())
        .args(args)
        .output()
        .expect("run moondex")
}

fn parse_stdout(stdout: &[u8]) -> serde_json::Value {
    let stdout = String::from_utf8_lossy(stdout);
    serde_json::from_str(&stdout).unwrap_or_else(|err| panic!("parse stdout json: {err}\n{stdout}"))
}

fn unix_millis() -> u128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("system clock before unix epoch")
        .as_millis()
}
