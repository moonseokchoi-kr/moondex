use std::process::Command;

pub fn identify() -> Result<serde_json::Value, String> {
    let output = Command::new("cmux")
        .arg("identify")
        .arg("--json")
        .output()
        .map_err(|err| format!("cmux identify failed to start: {err}"))?;
    command_json("cmux identify", output)
}

pub fn current_surface_ref() -> Result<(String, serde_json::Value), String> {
    let identity = identify()?;
    let surface_ref = identity
        .get("caller")
        .and_then(|caller| caller.get("surface_ref"))
        .or_else(|| {
            identity
                .get("focused")
                .and_then(|focused| focused.get("surface_ref"))
        })
        .and_then(|value| value.as_str())
        .ok_or("cmux identify did not include caller or focused surface_ref")?
        .to_string();
    Ok((surface_ref, identity))
}

pub fn send_text(surface_ref: &str, text: &str) -> Result<serde_json::Value, String> {
    ensure_surface_exists(surface_ref)?;
    let output = Command::new("cmux")
        .arg("send")
        .arg("--surface")
        .arg(surface_ref)
        .arg(text)
        .output()
        .map_err(|err| format!("cmux send failed to start: {err}"))?;
    let result = command_json("cmux send", output)?;
    if let Some(stdout) = result.get("stdout").and_then(|value| value.as_str()) {
        let expected = format!("OK {surface_ref}");
        if !stdout.starts_with(&expected) {
            return Err(format!(
                "cmux send target mismatch: expected {surface_ref}, got {stdout}"
            ));
        }
    }
    Ok(result)
}

pub fn capture_pane(surface_ref: &str, lines: usize) -> Result<String, String> {
    ensure_surface_exists(surface_ref)?;
    let output = Command::new("cmux")
        .arg("capture-pane")
        .arg("--surface")
        .arg(surface_ref)
        .arg("--scrollback")
        .arg("--lines")
        .arg(lines.to_string())
        .output()
        .map_err(|err| format!("cmux capture-pane failed to start: {err}"))?;
    command_text("cmux capture-pane", output)
}

fn ensure_surface_exists(surface_ref: &str) -> Result<(), String> {
    let output = Command::new("cmux")
        .arg("tree")
        .arg("--json")
        .output()
        .map_err(|err| format!("cmux tree failed to start: {err}"))?;
    let tree = command_json("cmux tree", output)?;
    if contains_surface_ref(&tree, surface_ref) {
        Ok(())
    } else {
        Err(format!("cmux surface not found: {surface_ref}"))
    }
}

fn contains_surface_ref(value: &serde_json::Value, surface_ref: &str) -> bool {
    match value {
        serde_json::Value::Object(map) => map.iter().any(|(key, value)| {
            (key == "surface_ref" || key == "ref") && value.as_str() == Some(surface_ref)
                || contains_surface_ref(value, surface_ref)
        }),
        serde_json::Value::Array(values) => values
            .iter()
            .any(|value| contains_surface_ref(value, surface_ref)),
        _ => false,
    }
}

fn command_json(command: &str, output: std::process::Output) -> Result<serde_json::Value, String> {
    let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
    if !output.status.success() {
        return Err(format!(
            "{command} exited with {}: {}",
            output.status,
            if stderr.is_empty() { stdout } else { stderr }
        ));
    }
    if stdout.is_empty() {
        return Ok(serde_json::json!({ "stdout": "" }));
    }
    serde_json::from_str(&stdout).or_else(|_| Ok(serde_json::json!({ "stdout": stdout })))
}

fn command_text(command: &str, output: std::process::Output) -> Result<String, String> {
    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
    if output.status.success() {
        Ok(stdout)
    } else {
        Err(format!(
            "{command} exited with {}: {}",
            output.status,
            if stderr.is_empty() {
                stdout.trim().to_string()
            } else {
                stderr
            }
        ))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn detects_surface_ref_inside_cmux_tree() {
        let tree = serde_json::json!({
            "windows": [{
                "workspaces": [{
                    "panes": [{
                        "surfaces": [{ "ref": "surface:14" }]
                    }]
                }]
            }]
        });
        assert!(contains_surface_ref(&tree, "surface:14"));
        assert!(!contains_surface_ref(&tree, "surface:999999"));
    }
}
