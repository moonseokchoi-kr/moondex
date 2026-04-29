mod support;

use std::fs;
use std::os::unix::fs::PermissionsExt;

use support::{TestProject, run_err, run_ok, run_ok_vec};

#[test]
fn init_and_status_smoke() {
    let project = TestProject::new("init-and-status");

    let init = run_ok(&project, &["init"]);
    assert_eq!(init["operation"], "init");
    assert!(project.path().join(".moondex/state/config.json").exists());

    let status = run_ok(&project, &["status", "--json"]);
    assert_eq!(status["operation"], "status");
    assert_eq!(status["data"]["tasks"]["total"], 0);
}

#[test]
fn task_lifecycle_cli_smoke() {
    let project = TestProject::new("task-lifecycle");

    let create_input = serde_json::json!({
        "task_id": "T-01",
        "subject": "subject",
        "description": "description",
        "role": "implementer"
    })
    .to_string();
    let created = run_ok_vec(
        &project,
        vec![
            "api".into(),
            "create-task".into(),
            "--input".into(),
            create_input,
            "--json".into(),
        ],
    );
    assert_eq!(created["data"]["id"], "T-01");
    assert_eq!(created["data"]["status"], "pending");

    let claim_input = serde_json::json!({
        "task_id": "T-01",
        "worker": "implementer",
        "expected_version": 1
    })
    .to_string();
    let claimed = run_ok_vec(
        &project,
        vec![
            "api".into(),
            "claim-task".into(),
            "--input".into(),
            claim_input,
            "--json".into(),
        ],
    );
    let token = claimed["data"]["claim_token"]
        .as_str()
        .expect("claim token")
        .to_string();

    let transition_input = serde_json::json!({
        "task_id": "T-01",
        "from": "in_progress",
        "to": "completed",
        "claim_token": token,
        "result": "done",
        "error": null
    })
    .to_string();
    let transitioned = run_ok_vec(
        &project,
        vec![
            "api".into(),
            "transition-task".into(),
            "--input".into(),
            transition_input,
            "--json".into(),
        ],
    );
    assert_eq!(transitioned["data"]["status"], "completed");
}

#[test]
fn mailbox_phase_event_cli_smoke() {
    let project = TestProject::new("mailbox-phase-event");

    run_ok_vec(
        &project,
        vec![
            "api".into(),
            "create-task".into(),
            "--input".into(),
            serde_json::json!({
                "task_id": "T-01",
                "subject": "subject",
                "description": "description",
                "role": "implementer"
            })
            .to_string(),
            "--json".into(),
        ],
    );
    let claimed = run_ok_vec(
        &project,
        vec![
            "api".into(),
            "claim-task".into(),
            "--input".into(),
            serde_json::json!({
                "task_id": "T-01",
                "worker": "implementer",
                "expected_version": 1
            })
            .to_string(),
            "--json".into(),
        ],
    );
    let token = claimed["data"]["claim_token"].as_str().unwrap().to_string();
    run_ok_vec(
        &project,
        vec![
            "api".into(),
            "transition-task".into(),
            "--input".into(),
            serde_json::json!({
                "task_id": "T-01",
                "from": "in_progress",
                "to": "completed",
                "claim_token": token,
                "result": "done",
                "error": null
            })
            .to_string(),
            "--json".into(),
        ],
    );
    run_ok_vec(
        &project,
        vec![
            "api".into(),
            "write-mailbox".into(),
            "--input".into(),
            serde_json::json!({
                "from_role": "implementer",
                "kind": "result",
                "task_id": "T-01",
                "body": serde_json::json!({
                    "summary": "done",
                    "changed_files": ["src/lib.rs"],
                    "tests": ["cargo test -p moondex"]
                }).to_string()
            })
            .to_string(),
            "--json".into(),
        ],
    );
    run_ok_vec(
        &project,
        vec![
            "api".into(),
            "consume-mailbox-for-task".into(),
            "--input".into(),
            serde_json::json!({
                "task_id": "T-01",
                "from_role": "implementer",
                "kind": "result"
            })
            .to_string(),
            "--json".into(),
        ],
    );

    let events = run_ok_vec(
        &project,
        vec![
            "api".into(),
            "list-events".into(),
            "--input".into(),
            serde_json::json!({
                "task_id": "T-01",
                "kind": "phase_advanced"
            })
            .to_string(),
            "--json".into(),
        ],
    );
    assert_eq!(events["data"].as_array().unwrap().len(), 1);
    assert_eq!(events["data"][0]["from_phase"], "implementation");
    assert_eq!(events["data"][0]["to_phase"], "code_review");
}

#[test]
fn inspect_hooks_cli_smoke() {
    let project = TestProject::new("inspect-hooks");
    let hooks_dir = project.path().join(".codex/hooks");
    fs::create_dir_all(&hooks_dir).unwrap();

    for name in ["validate-role-transfer.sh", "validate-readiness.sh"] {
        let path = hooks_dir.join(name);
        fs::write(&path, "#!/usr/bin/env bash\nexit 0\n").unwrap();
        let mut permissions = fs::metadata(&path).unwrap().permissions();
        permissions.set_mode(0o755);
        fs::set_permissions(&path, permissions).unwrap();
    }

    let result = run_ok(&project, &["api", "inspect-hooks", "--json"]);
    let hooks = result["data"]["hooks"].as_array().unwrap();
    assert_eq!(hooks.len(), 2);
    assert!(hooks.iter().any(|hook| {
        hook["name"] == "validate-role-transfer.sh"
            && hook["target_operation"] == "validate-role-transfer"
            && hook["status"] == "ok"
    }));
    assert!(hooks.iter().any(|hook| {
        hook["name"] == "validate-readiness.sh"
            && hook["target_operation"] == "validate-readiness"
            && hook["status"] == "ok"
    }));
}

#[test]
fn invalid_command_returns_error_envelope() {
    let project = TestProject::new("invalid-command");
    let error = run_err(&project, &["api", "not-an-operation", "--json"]);
    assert_eq!(error["operation"], "cli");
    assert!(
        error["error"]["message"]
            .as_str()
            .unwrap()
            .contains("unknown api operation")
    );
}
