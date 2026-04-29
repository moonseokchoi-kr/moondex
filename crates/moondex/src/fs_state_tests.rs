use super::*;
use crate::model::{
    AckDispatchInput, ArchiveStateInput, ClaimTaskInput, ConsumeMailboxForTaskInput,
    ConsumeMailboxInput, CreateTaskInput, ListEventsInput, MarkMailboxReadInput, ReadMailboxInput,
    ReleaseTaskInput, RepairStateInput, RetryDispatchInput, TransitionTaskInput, WriteMailboxInput,
    WriteRoleIdentityInput, WriteRoleStatusInput,
};

#[test]
fn claim_conflict_checks_version() {
    let store = temp_store("claim_conflict_checks_version");
    store
        .create_task(CreateTaskInput {
            task_id: "T-01".into(),
            subject: "subject".into(),
            description: "description".into(),
            role: None,
        })
        .unwrap();
    let err = store
        .claim_task(ClaimTaskInput {
            task_id: "T-01".into(),
            worker: "implementer".into(),
            expected_version: 9,
        })
        .unwrap_err();
    assert!(err.contains("claim_conflict"));
}

#[test]
fn transition_requires_claim_token() {
    let store = temp_store("transition_requires_claim_token");
    store
        .create_task(CreateTaskInput {
            task_id: "T-01".into(),
            subject: "subject".into(),
            description: "description".into(),
            role: None,
        })
        .unwrap();
    let claimed = store
        .claim_task(ClaimTaskInput {
            task_id: "T-01".into(),
            worker: "implementer".into(),
            expected_version: 1,
        })
        .unwrap();
    assert!(claimed["claim_token"].as_str().is_some());
    let err = store
        .transition_task(TransitionTaskInput {
            task_id: "T-01".into(),
            from: TaskStatus::InProgress,
            to: TaskStatus::Completed,
            claim_token: "wrong".into(),
            result: Some("done".into()),
            error: None,
        })
        .unwrap_err();
    assert!(err.contains("claim_conflict"));
}

#[test]
fn release_requeues_task() {
    let store = temp_store("release_requeues_task");
    store
        .create_task(CreateTaskInput {
            task_id: "T-01".into(),
            subject: "subject".into(),
            description: "description".into(),
            role: None,
        })
        .unwrap();
    let claimed = store
        .claim_task(ClaimTaskInput {
            task_id: "T-01".into(),
            worker: "implementer".into(),
            expected_version: 1,
        })
        .unwrap();
    let token = claimed["claim_token"].as_str().unwrap().to_string();
    let released = store
        .release_task_claim(ReleaseTaskInput {
            task_id: "T-01".into(),
            worker: "implementer".into(),
            claim_token: token,
        })
        .unwrap();
    assert_eq!(released.status, TaskStatus::Pending);
    assert!(released.claim.is_none());
}

#[test]
fn dispatch_without_surface_stays_pending() {
    let store = temp_store("dispatch_without_surface_stays_pending");
    store
        .create_task(CreateTaskInput {
            task_id: "T-01".into(),
            subject: "subject".into(),
            description: "description".into(),
            role: None,
        })
        .unwrap();
    let request = store.dispatch("implementer", "T-01").unwrap();
    assert!(matches!(request.status, DispatchStatus::Pending));
    assert_eq!(request.last_reason.as_deref(), Some("surface_ref_missing"));
    assert_eq!(
        request.trigger_message,
        "# moondex: read your inbox for task T-01\n"
    );
}

#[test]
fn ack_dispatch_marks_delivered() {
    let store = temp_store("ack_dispatch_marks_delivered");
    store
        .create_task(CreateTaskInput {
            task_id: "T-01".into(),
            subject: "subject".into(),
            description: "description".into(),
            role: Some("implementer".into()),
        })
        .unwrap();
    let request = store.dispatch("implementer", "T-01").unwrap();
    let delivered = store
        .ack_dispatch(AckDispatchInput {
            request_id: request.request_id,
            role_id: "implementer".into(),
        })
        .unwrap();
    assert!(matches!(delivered.status, DispatchStatus::Delivered));
    assert_eq!(delivered.last_reason.as_deref(), Some("ack_by_role"));
}

#[test]
fn role_status_is_listed_in_status() {
    let store = temp_store("role_status_is_listed_in_status");
    let status = store
        .write_role_status(WriteRoleStatusInput {
            role_id: "implementer".into(),
            state: "working".into(),
            task_id: Some("T-01".into()),
            message: Some("editing files".into()),
        })
        .unwrap();
    assert_eq!(status.state, "working");

    let runtime_status = store.status().unwrap();
    assert_eq!(runtime_status["roles"]["total_with_status"], 1);
    assert_eq!(
        runtime_status["roles"]["statuses"][0]["role_id"],
        "implementer"
    );
}

#[test]
fn mailbox_defaults_to_orchestrator() {
    let store = temp_store("mailbox_defaults_to_orchestrator");
    let message = store
        .write_mailbox(WriteMailboxInput {
            from_role: "implementer".into(),
            to_role: None,
            kind: "result".into(),
            task_id: Some("T-01".into()),
            body: result_body("tests passed"),
        })
        .unwrap();
    assert_eq!(message.to_role, "orchestrator");

    let messages = store
        .read_mailbox(ReadMailboxInput {
            role_id: None,
            task_id: None,
            unread_only: None,
            unconsumed_only: None,
        })
        .unwrap();
    assert_eq!(messages.len(), 1);
    assert_eq!(messages[0].body, result_body("tests passed"));
}

#[test]
fn mailbox_read_and_consume_are_tracked() {
    let store = temp_store("mailbox_read_and_consume_are_tracked");
    let first = store
        .write_mailbox(WriteMailboxInput {
            from_role: "implementer".into(),
            to_role: None,
            kind: "result".into(),
            task_id: Some("T-01".into()),
            body: result_body("first"),
        })
        .unwrap();
    let second = store
        .write_mailbox(WriteMailboxInput {
            from_role: "reviewer".into(),
            to_role: None,
            kind: "review_approved".into(),
            task_id: Some("T-01".into()),
            body: review_approved_body("second"),
        })
        .unwrap();

    let read = store
        .mark_mailbox_read(MarkMailboxReadInput {
            role_id: None,
            message_id: first.message_id,
        })
        .unwrap();
    assert!(read.read_at.is_some());
    assert!(read.consumed_at.is_none());

    let consumed = store
        .consume_mailbox(ConsumeMailboxInput {
            role_id: None,
            message_id: second.message_id,
        })
        .unwrap();
    assert!(consumed.read_at.is_some());
    assert!(consumed.consumed_at.is_some());

    let unread = store
        .read_mailbox(ReadMailboxInput {
            role_id: None,
            task_id: None,
            unread_only: Some(true),
            unconsumed_only: None,
        })
        .unwrap();
    assert!(unread.is_empty());

    let unconsumed = store
        .read_mailbox(ReadMailboxInput {
            role_id: None,
            task_id: None,
            unread_only: None,
            unconsumed_only: Some(true),
        })
        .unwrap();
    assert_eq!(unconsumed.len(), 1);
    assert_eq!(unconsumed[0].body, result_body("first"));
}

#[test]
fn mailbox_rejects_invalid_contract_output() {
    let store = temp_store("mailbox_rejects_invalid_contract_output");
    let bad_kind = store
        .write_mailbox(WriteMailboxInput {
            from_role: "implementer".into(),
            to_role: None,
            kind: "anything".into(),
            task_id: Some("T-01".into()),
            body: result_body("body"),
        })
        .unwrap_err();
    assert!(bad_kind.contains("invalid_mailbox_kind"));

    let empty_body = store
        .write_mailbox(WriteMailboxInput {
            from_role: "implementer".into(),
            to_role: None,
            kind: "result".into(),
            task_id: Some("T-01".into()),
            body: " ".into(),
        })
        .unwrap_err();
    assert!(empty_body.contains("invalid_mailbox_body"));
}

#[test]
fn mailbox_accepts_valid_body_schema_for_all_kinds() {
    let store = temp_store("mailbox_accepts_valid_body_schema_for_all_kinds");
    for (from_role, kind, body) in [
        ("implementer", "result", result_body("done")),
        (
            "implementer",
            "blocked",
            r#"{"reason":"blocked","needs":"decision"}"#.into(),
        ),
        (
            "implementer",
            "question",
            r#"{"question":"Which path?","decision_needed":"Pick A or B"}"#.into(),
        ),
        (
            "code-reviewer",
            "review_approved",
            review_approved_body("approved"),
        ),
        (
            "code-reviewer",
            "review_changes_requested",
            r#"{"summary":"needs changes","changes":["fix test"],"severity":"high"}"#.into(),
        ),
        (
            "implementer",
            "status",
            r#"{"state":"working","summary":"editing files"}"#.into(),
        ),
    ] {
        store
            .write_mailbox(WriteMailboxInput {
                from_role: from_role.into(),
                to_role: None,
                kind: kind.into(),
                task_id: Some("T-01".into()),
                body,
            })
            .unwrap();
    }
}

#[test]
fn mailbox_rejects_invalid_body_schema() {
    let store = temp_store("mailbox_rejects_invalid_body_schema");
    let plaintext = store
        .write_mailbox(WriteMailboxInput {
            from_role: "implementer".into(),
            to_role: None,
            kind: "result".into(),
            task_id: Some("T-01".into()),
            body: "plain text".into(),
        })
        .unwrap_err();
    assert!(plaintext.contains("invalid_mailbox_body_schema"));

    let malformed = store
        .write_mailbox(WriteMailboxInput {
            from_role: "implementer".into(),
            to_role: None,
            kind: "result".into(),
            task_id: Some("T-01".into()),
            body: "{\"summary\":".into(),
        })
        .unwrap_err();
    assert!(malformed.contains("invalid_mailbox_body_schema"));

    let missing_required = store
        .write_mailbox(WriteMailboxInput {
            from_role: "implementer".into(),
            to_role: None,
            kind: "blocked".into(),
            task_id: Some("T-01".into()),
            body: r#"{"reason":"blocked"}"#.into(),
        })
        .unwrap_err();
    assert!(missing_required.contains("needs must be a non-empty string"));

    let missing_result_outcome = store
        .write_mailbox(WriteMailboxInput {
            from_role: "implementer".into(),
            to_role: None,
            kind: "result".into(),
            task_id: Some("T-01".into()),
            body: r#"{"summary":"done","changed_files":[]}"#.into(),
        })
        .unwrap_err();
    assert!(missing_result_outcome.contains("not_run_reason"));

    let invalid_severity = store
        .write_mailbox(WriteMailboxInput {
            from_role: "implementer".into(),
            to_role: None,
            kind: "review_changes_requested".into(),
            task_id: Some("T-01".into()),
            body: r#"{"summary":"needs changes","changes":["fix"],"severity":"urgent"}"#.into(),
        })
        .unwrap_err();
    assert!(invalid_severity.contains("severity"));
}

#[test]
fn validate_role_transfer_accepts_valid_mailbox_output() {
    let store = temp_store("validate_role_transfer_accepts_valid_mailbox_output");
    let result = store
        .validate_role_transfer(serde_json::json!({
            "from_role": "implementer",
            "kind": "result",
            "task_id": "T-01",
            "body": result_body("done"),
        }))
        .unwrap();

    assert_eq!(result["contract"], "mailbox_output");
    assert_eq!(result["valid"], true);
    assert_eq!(result["errors"].as_array().unwrap().len(), 0);
}

#[test]
fn validate_role_transfer_rejects_invalid_role_kind() {
    let store = temp_store("validate_role_transfer_rejects_invalid_role_kind");
    let result = store
        .validate_role_transfer(serde_json::json!({
            "from_role": "implementer",
            "kind": "review_approved",
            "task_id": "T-01",
            "body": review_approved_body("approved"),
        }))
        .unwrap();

    assert_eq!(result["valid"], false);
    assert_eq!(result["errors"][0]["code"], "invalid_role_output_contract");
}

#[test]
fn validate_role_transfer_rejects_missing_task_id_for_canonical_role() {
    let store = temp_store("validate_role_transfer_rejects_missing_task_id_for_canonical_role");
    let result = store
        .validate_role_transfer(serde_json::json!({
            "from_role": "code-reviewer",
            "kind": "review_approved",
            "body": review_approved_body("approved"),
        }))
        .unwrap();

    assert_eq!(result["valid"], false);
    assert!(
        result["errors"]
            .as_array()
            .unwrap()
            .iter()
            .any(|error| { error["detail"].as_str().unwrap().contains("task_id") })
    );
}

#[test]
fn validate_role_transfer_allows_non_canonical_role_with_valid_body() {
    let store = temp_store("validate_role_transfer_allows_non_canonical_role_with_valid_body");
    let result = store
        .validate_role_transfer(serde_json::json!({
            "from_role": "tester",
            "kind": "result",
            "task_id": "T-01",
            "body": result_body("done"),
        }))
        .unwrap();

    assert_eq!(result["valid"], true);
}

#[test]
fn validate_role_transfer_accepts_valid_handoff_payload() {
    let store = temp_store("validate_role_transfer_accepts_valid_handoff_payload");
    let result = store
        .validate_role_transfer(serde_json::json!({
            "task_id": "T-01",
            "plan_id": "P-01",
            "source_role": "orchestrator",
            "target_role": "implementer",
            "current_status": "validated-ready",
            "target_status": "implementing",
            "scope_paths": ["crates/moondex/src/fs_state.rs"],
            "verification_commands": ["cargo test -p moondex"],
            "acceptance_criteria": ["tests pass"],
            "handoff_summary": "Implement the approved task.",
        }))
        .unwrap();

    assert_eq!(result["contract"], "handoff_payload");
    assert_eq!(result["valid"], true);
}

#[test]
fn validate_role_transfer_rejects_invalid_handoff_payload() {
    let store = temp_store("validate_role_transfer_rejects_invalid_handoff_payload");
    let result = store
        .validate_role_transfer(serde_json::json!({
            "task_id": "T-01",
            "source_role": "orchestrator",
            "target_role": "implementer",
        }))
        .unwrap();

    assert_eq!(result["valid"], false);
    assert!(
        result["errors"]
            .as_array()
            .unwrap()
            .iter()
            .any(|error| { error["detail"].as_str().unwrap().contains("plan_id") })
    );
}

#[test]
fn validate_role_transfer_returns_warnings_without_invalidating() {
    let store = temp_store("validate_role_transfer_returns_warnings_without_invalidating");
    let result = store
        .validate_role_transfer(serde_json::json!({
            "from_role": "implementer",
            "kind": "result",
            "task_id": "T-01",
            "body": serde_json::json!({
                "summary": "done",
                "changed_files": [],
                "not_run_reason": "not run",
            }).to_string(),
        }))
        .unwrap();

    assert_eq!(result["valid"], true);
    assert_eq!(result["warnings"][0]["code"], "weak_result_evidence");
}

#[test]
fn validate_role_transfer_accepts_planning_contracts() {
    let store = temp_store("validate_role_transfer_accepts_planning_contracts");
    for payload in [
        serde_json::json!({
            "contract_type": "task_planner_input",
            "task_id": "T-01",
            "source_role": "orchestrator",
            "target_role": "task-planner",
            "task": {"subject": "Add gate", "description": "Add validator"},
            "source_document_paths": ["docs/execution/WORK_TRACKER.md"],
            "scope_paths": ["crates/moondex/src/fs_state.rs"],
            "planning_requirements": ["produce executor-ready plan"],
            "output_contract": "docs/contracts/plan-schema.md"
        }),
        serde_json::json!({
            "contract_type": "task_planner_output",
            "task_id": "T-01",
            "plan_id": "P-01",
            "source_role": "task-planner",
            "target_role": "orchestrator",
            "status": "DONE",
            "plan_path": "docs/plans/P-01.md",
            "ownership": ["crates/moondex/src/fs_state.rs"],
            "acceptance_criteria": ["validator rejects missing fields"],
            "verification_commands": ["cargo test -p moondex"]
        }),
        serde_json::json!({
            "contract_type": "wave_dispatcher_input",
            "source_role": "orchestrator",
            "target_role": "wave-dispatcher",
            "candidate_tasks": ["T-01"],
            "plans": [{"task_id": "T-01", "plan_id": "P-01"}],
            "dependency_notes": [],
            "ownership_conflicts": [],
            "shared_contract_candidates": [],
            "output_contract": "docs/contracts/wave-schema.md"
        }),
        serde_json::json!({
            "contract_type": "wave_dispatcher_output",
            "wave_id": "W-01",
            "source_role": "wave-dispatcher",
            "target_role": "orchestrator",
            "status": "APPROVED",
            "wave_groups": [{"id": "G-01", "tasks": ["T-01"]}],
            "dependency_graph": [{"task_id": "T-01", "depends_on": []}],
            "verification_plan": ["cargo test -p moondex"],
            "validated_ready_tasks": ["T-01"]
        }),
        serde_json::json!({
            "contract_type": "tester_input",
            "task_id": "T-01",
            "plan_id": "P-01",
            "source_role": "orchestrator",
            "target_role": "tester",
            "test_scope": "E2E reset flow",
            "changed_files": ["integration_test/reset_test.dart"],
            "verification_commands": ["flutter test integration_test"],
            "acceptance_criteria": ["reset flow passes"],
            "environment_notes": ["simulator available"]
        }),
    ] {
        let result = store.validate_role_transfer(payload).unwrap();
        assert_eq!(result["valid"], true);
    }
}

#[test]
fn validate_role_transfer_rejects_invalid_planning_contracts() {
    let store = temp_store("validate_role_transfer_rejects_invalid_planning_contracts");
    let result = store
        .validate_role_transfer(serde_json::json!({
            "contract_type": "task_planner_output",
            "task_id": "T-01",
            "plan_id": "P-01",
            "source_role": "task-planner",
            "target_role": "orchestrator",
            "status": "DONE",
            "ownership": ["crates/moondex/src/fs_state.rs"],
            "acceptance_criteria": ["tests pass"],
            "verification_commands": ["cargo test -p moondex"]
        }))
        .unwrap();
    assert_eq!(result["valid"], false);
    assert!(result["errors"].as_array().unwrap().iter().any(|error| {
        error["detail"]
            .as_str()
            .unwrap()
            .contains("plan_path or plan")
    }));

    let unknown = store
        .validate_role_transfer(serde_json::json!({"contract_type": "unknown"}))
        .unwrap();
    assert_eq!(unknown["valid"], false);
    assert_eq!(unknown["errors"][0]["code"], "unknown_contract_type");
}

#[test]
fn validate_readiness_returns_expected_decisions() {
    let store = temp_store("validate_readiness_returns_expected_decisions");
    let ready = store.validate_readiness(valid_readiness_payload()).unwrap();
    assert_eq!(ready["decision"], "READY");

    let mut missing_verification = valid_readiness_payload();
    missing_verification["plan"]["verification_commands"] = serde_json::json!([]);
    let revision = store.validate_readiness(missing_verification).unwrap();
    assert_eq!(revision["decision"], "REVISION_REQUIRED");
    assert!(
        revision["missing_fields"]
            .as_array()
            .unwrap()
            .iter()
            .any(|field| field == "plan.verification_commands")
    );

    let mut blocked = valid_readiness_payload();
    blocked["plan"]["blocked_reason"] = serde_json::json!("waiting on API decision");
    let blocked = store.validate_readiness(blocked).unwrap();
    assert_eq!(blocked["decision"], "BLOCKED");
}

#[test]
fn validate_readiness_supports_wave_and_warning_only_ready() {
    let store = temp_store("validate_readiness_supports_wave_and_warning_only_ready");
    let payload = serde_json::json!({
        "task": {"task_id": "T-01", "subject": "x", "description": "y"},
        "plan": {
            "plan_id": "P-01",
            "task_id": "T-01",
            "objective": "Ship one change",
            "scope_paths": ["."],
            "acceptance_criteria": ["done"],
            "verification_commands": ["test"],
            "ownership": ["."]
        },
        "wave": {
            "wave_id": "W-01",
            "validated_ready_tasks": ["T-01"],
            "dependency_graph": [{"task_id": "T-01", "depends_on": []}],
            "verification_plan": ["test"]
        }
    });
    let result = store.validate_readiness(payload).unwrap();
    assert_eq!(result["decision"], "READY");
    assert!(!result["warnings"].as_array().unwrap().is_empty());
}

#[test]
fn validate_readiness_blocks_unknown_wave_dependency() {
    let store = temp_store("validate_readiness_blocks_unknown_wave_dependency");
    let mut payload = valid_readiness_payload();
    payload["wave"] = serde_json::json!({
        "wave_id": "W-01",
        "validated_ready_tasks": ["T-01"],
        "dependency_graph": [{"task_id": "T-01", "depends_on": ["T-02"]}],
        "verification_plan": ["cargo test -p moondex"]
    });
    let result = store.validate_readiness(payload).unwrap();
    assert_eq!(result["decision"], "BLOCKED");
}

#[test]
fn write_mailbox_enforces_role_contract_and_records_warnings() {
    let store = temp_store("write_mailbox_enforces_role_contract_and_records_warnings");
    let invalid_kind = store
        .write_mailbox(WriteMailboxInput {
            from_role: "implementer".into(),
            to_role: None,
            kind: "review_approved".into(),
            task_id: Some("T-01".into()),
            body: review_approved_body("approved"),
        })
        .unwrap_err();
    assert!(invalid_kind.contains("invalid_role_transfer_contract"));

    let missing_task = store
        .write_mailbox(WriteMailboxInput {
            from_role: "tester".into(),
            to_role: None,
            kind: "result".into(),
            task_id: None,
            body: result_body("done"),
        })
        .unwrap_err();
    assert!(missing_task.contains("invalid_role_transfer_contract"));

    store
        .write_mailbox(WriteMailboxInput {
            from_role: "implementer".into(),
            to_role: None,
            kind: "result".into(),
            task_id: Some("T-01".into()),
            body: result_body("warning"),
        })
        .unwrap();
    let audit = store.audit_state().unwrap();
    assert_eq!(audit["summary"]["mailbox_issues"], 0);
    assert_eq!(audit["summary"]["hook_warnings"], 1);
    assert_eq!(audit["hook_warnings"][0]["type"], "weak_result_evidence");
}

#[test]
fn dispatch_guards_terminal_role_mismatch_and_records_surface_warning() {
    let store = temp_store("dispatch_guards_terminal_role_mismatch_and_records_surface_warning");
    store
        .create_task(CreateTaskInput {
            task_id: "T-01".into(),
            subject: "subject".into(),
            description: "description".into(),
            role: Some("implementer".into()),
        })
        .unwrap();
    let mismatch = store.dispatch("tester", "T-01").unwrap_err();
    assert!(mismatch.contains("task role does not match"));

    let request = store.dispatch("implementer", "T-01").unwrap();
    assert_eq!(request.last_reason.as_deref(), Some("surface_ref_missing"));
    let audit = store.audit_state().unwrap();
    assert_eq!(audit["summary"]["hook_warnings"], 1);

    store
        .claim_task(ClaimTaskInput {
            task_id: "T-01".into(),
            worker: "implementer".into(),
            expected_version: 1,
        })
        .unwrap();
    let claimed = store.read_task("T-01").unwrap();
    let token = claimed.claim.unwrap().token;
    store
        .transition_task(TransitionTaskInput {
            task_id: "T-01".into(),
            from: TaskStatus::InProgress,
            to: TaskStatus::Completed,
            claim_token: token,
            result: Some("done".into()),
            error: None,
        })
        .unwrap();
    let terminal = store.dispatch("implementer", "T-01").unwrap_err();
    assert!(terminal.contains("terminal task"));
}

#[test]
fn next_action_prioritizes_runtime_state() {
    let store = temp_store("next_action_prioritizes_runtime_state");
    store.init().unwrap();
    let mailbox = vec![MailboxMessage {
        message_id: "message-bad".into(),
        from_role: "implementer".into(),
        to_role: "orchestrator".into(),
        kind: "result".into(),
        task_id: Some("T-01".into()),
        body: "plain".into(),
        created_at: now_string(),
        read_at: None,
        consumed_at: None,
    }];
    write_json_atomic(&store.mailbox_path("orchestrator"), &mailbox).unwrap();
    assert_eq!(store.next_action().unwrap()["action"], "repair_state");
}

#[test]
fn next_action_recommends_consume_dispatch_and_implementation() {
    let mailbox_store = temp_store("next_action_recommends_consume");
    mailbox_store
        .write_mailbox(WriteMailboxInput {
            from_role: "implementer".into(),
            to_role: None,
            kind: "result".into(),
            task_id: Some("T-01".into()),
            body: serde_json::json!({
                "summary": "done",
                "changed_files": ["crates/moondex/src/fs_state.rs"],
                "tests": ["cargo test -p moondex"]
            })
            .to_string(),
        })
        .unwrap();
    let consume_action = mailbox_store.next_action().unwrap();
    assert_eq!(consume_action["action"], "consume_mailbox");
    assert_eq!(consume_action["role_id"], "orchestrator");
    assert_eq!(consume_action["from_role"], "implementer");
    assert_eq!(consume_action["kind"], "result");
    assert!(consume_action["message_id"].as_str().is_some());

    let dispatch_store = temp_store("next_action_recommends_dispatch_wait");
    dispatch_store
        .create_task(CreateTaskInput {
            task_id: "T-01".into(),
            subject: "subject".into(),
            description: "description".into(),
            role: Some("implementer".into()),
        })
        .unwrap();
    dispatch_store
        .write_role_identity(WriteRoleIdentityInput {
            role_id: "implementer".into(),
            surface_ref: Some("surface:2".into()),
        })
        .unwrap();
    dispatch_store.dispatch("implementer", "T-01").unwrap();
    assert_eq!(
        dispatch_store.next_action().unwrap()["action"],
        "ack_dispatch_wait"
    );

    let task_store = temp_store("next_action_recommends_implementation");
    task_store
        .create_task(CreateTaskInput {
            task_id: "T-02".into(),
            subject: "subject".into(),
            description: "description".into(),
            role: Some("implementer".into()),
        })
        .unwrap();
    assert_eq!(
        task_store.next_action().unwrap()["action"],
        "dispatch_implementer"
    );
}

#[test]
fn next_action_recommends_compliance_after_review_decision() {
    let store = temp_store("next_action_recommends_compliance_after_review_decision");
    let message = store
        .write_mailbox(WriteMailboxInput {
            from_role: "code-reviewer".into(),
            to_role: None,
            kind: "review_approved".into(),
            task_id: Some("T-01".into()),
            body: serde_json::json!({
                "summary": "No code issues found; compliance required.",
                "checks": ["reviewed implementation"],
                "compliance_review_required": true,
                "changed_files": ["docs/execution/moondex-cli-plan.md"]
            })
            .to_string(),
        })
        .unwrap();
    store
        .consume_mailbox(ConsumeMailboxInput {
            role_id: None,
            message_id: message.message_id,
        })
        .unwrap();

    let action = store.next_action().unwrap();
    assert_eq!(action["action"], "dispatch_compliance_reviewer");
    assert_eq!(action["task_id"], "T-01");
}

#[test]
fn same_task_advances_from_implementation_to_review_to_done() {
    let store = temp_store("same_task_advances_from_implementation_to_review_to_done");
    store
        .create_task(CreateTaskInput {
            task_id: "T-01".into(),
            subject: "subject".into(),
            description: "description".into(),
            role: Some("implementer".into()),
        })
        .unwrap();
    let claimed = store
        .claim_task(ClaimTaskInput {
            task_id: "T-01".into(),
            worker: "implementer".into(),
            expected_version: 1,
        })
        .unwrap();
    let token = claimed["claim_token"].as_str().unwrap().to_string();
    store
        .transition_task(TransitionTaskInput {
            task_id: "T-01".into(),
            from: TaskStatus::InProgress,
            to: TaskStatus::Completed,
            claim_token: token,
            result: Some("implementation done".into()),
            error: None,
        })
        .unwrap();
    store
        .write_mailbox(WriteMailboxInput {
            from_role: "implementer".into(),
            to_role: None,
            kind: "result".into(),
            task_id: Some("T-01".into()),
            body: serde_json::json!({
                "summary": "implementation done",
                "changed_files": ["src/lib.rs"],
                "tests": ["cargo test -p moondex"]
            })
            .to_string(),
        })
        .unwrap();
    store
        .consume_mailbox_for_task(ConsumeMailboxForTaskInput {
            role_id: None,
            task_id: "T-01".into(),
            from_role: Some("implementer".into()),
            kind: Some("result".into()),
        })
        .unwrap();

    let task = store.read_task("T-01").unwrap();
    assert_eq!(task.status, TaskStatus::Pending);
    assert_eq!(task.phase, "code_review");
    assert_eq!(task.role.as_deref(), Some("code-reviewer"));
    assert_eq!(
        store.next_action().unwrap()["action"],
        "dispatch_code_reviewer"
    );

    let dispatch = store.dispatch("code-reviewer", "T-01").unwrap();
    assert_eq!(dispatch.to_role, "code-reviewer");
    let claimed = store
        .claim_task(ClaimTaskInput {
            task_id: "T-01".into(),
            worker: "code-reviewer".into(),
            expected_version: 4,
        })
        .unwrap();
    let token = claimed["claim_token"].as_str().unwrap().to_string();
    store
        .transition_task(TransitionTaskInput {
            task_id: "T-01".into(),
            from: TaskStatus::InProgress,
            to: TaskStatus::Completed,
            claim_token: token,
            result: Some("review approved".into()),
            error: None,
        })
        .unwrap();
    store
        .write_mailbox(WriteMailboxInput {
            from_role: "code-reviewer".into(),
            to_role: None,
            kind: "review_approved".into(),
            task_id: Some("T-01".into()),
            body: serde_json::json!({
                "summary": "approved",
                "checks": ["reviewed"],
                "compliance_review_required": false
            })
            .to_string(),
        })
        .unwrap();
    store
        .consume_mailbox_for_task(ConsumeMailboxForTaskInput {
            role_id: None,
            task_id: "T-01".into(),
            from_role: Some("code-reviewer".into()),
            kind: Some("review_approved".into()),
        })
        .unwrap();

    let task = store.read_task("T-01").unwrap();
    assert_eq!(task.status, TaskStatus::Completed);
    assert_eq!(task.phase, "done");
    assert!(task.role.is_none());
}

#[test]
fn same_task_review_can_advance_to_compliance() {
    let store = temp_store("same_task_review_can_advance_to_compliance");
    store
        .create_task(CreateTaskInput {
            task_id: "T-01".into(),
            subject: "subject".into(),
            description: "description".into(),
            role: Some("code-reviewer".into()),
        })
        .unwrap();
    let claimed = store
        .claim_task(ClaimTaskInput {
            task_id: "T-01".into(),
            worker: "code-reviewer".into(),
            expected_version: 1,
        })
        .unwrap();
    let token = claimed["claim_token"].as_str().unwrap().to_string();
    store
        .transition_task(TransitionTaskInput {
            task_id: "T-01".into(),
            from: TaskStatus::InProgress,
            to: TaskStatus::Completed,
            claim_token: token,
            result: Some("review approved with compliance".into()),
            error: None,
        })
        .unwrap();
    store
        .write_mailbox(WriteMailboxInput {
            from_role: "code-reviewer".into(),
            to_role: None,
            kind: "review_approved".into(),
            task_id: Some("T-01".into()),
            body: serde_json::json!({
                "summary": "approved",
                "checks": ["reviewed"],
                "compliance_review_required": true
            })
            .to_string(),
        })
        .unwrap();
    store
        .consume_mailbox_for_task(ConsumeMailboxForTaskInput {
            role_id: None,
            task_id: "T-01".into(),
            from_role: Some("code-reviewer".into()),
            kind: Some("review_approved".into()),
        })
        .unwrap();

    let task = store.read_task("T-01").unwrap();
    assert_eq!(task.status, TaskStatus::Pending);
    assert_eq!(task.phase, "compliance_review");
    assert_eq!(task.role.as_deref(), Some("compliance-reviewer"));
}

#[test]
fn mailbox_filters_by_task_id() {
    let store = temp_store("mailbox_filters_by_task_id");
    store
        .write_mailbox(WriteMailboxInput {
            from_role: "implementer".into(),
            to_role: None,
            kind: "result".into(),
            task_id: Some("T-01".into()),
            body: result_body("one"),
        })
        .unwrap();
    store
        .write_mailbox(WriteMailboxInput {
            from_role: "implementer".into(),
            to_role: None,
            kind: "result".into(),
            task_id: Some("T-02".into()),
            body: result_body("two"),
        })
        .unwrap();

    let messages = store
        .read_mailbox(ReadMailboxInput {
            role_id: None,
            task_id: Some("T-02".into()),
            unread_only: None,
            unconsumed_only: None,
        })
        .unwrap();
    assert_eq!(messages.len(), 1);
    assert_eq!(messages[0].body, result_body("two"));
}

#[test]
fn consume_mailbox_for_task_consumes_matching_message() {
    let store = temp_store("consume_mailbox_for_task_consumes_matching_message");
    store
        .write_mailbox(WriteMailboxInput {
            from_role: "implementer".into(),
            to_role: None,
            kind: "result".into(),
            task_id: Some("T-01".into()),
            body: result_body("implementation done"),
        })
        .unwrap();
    store
        .write_mailbox(WriteMailboxInput {
            from_role: "reviewer".into(),
            to_role: None,
            kind: "review_approved".into(),
            task_id: Some("T-01".into()),
            body: review_approved_body("review approved"),
        })
        .unwrap();
    store
        .write_mailbox(WriteMailboxInput {
            from_role: "implementer".into(),
            to_role: None,
            kind: "result".into(),
            task_id: Some("T-02".into()),
            body: result_body("other task"),
        })
        .unwrap();

    let consumed = store
        .consume_mailbox_for_task(ConsumeMailboxForTaskInput {
            role_id: None,
            task_id: "T-01".into(),
            from_role: Some("implementer".into()),
            kind: Some("result".into()),
        })
        .unwrap();
    assert_eq!(consumed.body, result_body("implementation done"));
    assert!(consumed.read_at.is_some());
    assert!(consumed.consumed_at.is_some());

    let unconsumed = store
        .read_mailbox(ReadMailboxInput {
            role_id: None,
            task_id: Some("T-01".into()),
            unread_only: None,
            unconsumed_only: Some(true),
        })
        .unwrap();
    assert_eq!(unconsumed.len(), 1);
    assert_eq!(unconsumed[0].from_role, "reviewer");
    assert_eq!(unconsumed[0].kind, "review_approved");
}

#[test]
fn evidence_capture_writes_file_and_index() {
    let store = temp_store("evidence_capture_writes_file_and_index");
    let record = store
        .write_evidence("surface:2", 80, "terminal output")
        .unwrap();
    assert_eq!(record.source_ref, "surface:2");
    assert!(Path::new(&record.path).exists());

    let records = store.list_evidence().unwrap();
    assert_eq!(records.len(), 1);
    assert_eq!(records[0].evidence_id, record.evidence_id);
}

#[test]
fn retry_dispatch_requeues_existing_request() {
    let store = temp_store("retry_dispatch_requeues_existing_request");
    store
        .create_task(CreateTaskInput {
            task_id: "T-01".into(),
            subject: "subject".into(),
            description: "description".into(),
            role: Some("implementer".into()),
        })
        .unwrap();
    let request = store.dispatch("implementer", "T-01").unwrap();
    store
        .mark_dispatch(
            &request.request_id,
            DispatchStatus::Failed,
            "transport failed",
        )
        .unwrap();

    let retried = store
        .retry_dispatch(RetryDispatchInput {
            request_id: request.request_id.clone(),
        })
        .unwrap();
    assert!(matches!(retried.status, DispatchStatus::Pending));
    assert_eq!(retried.last_reason.as_deref(), Some("retry_requested"));
    assert_eq!(retried.retry_count, 1);
    assert_eq!(retried.retry_history.len(), 1);
    assert_eq!(retried.retry_history[0].outcome, "pending");

    let notified = store
        .mark_dispatch(
            &request.request_id,
            DispatchStatus::Notified,
            "cmux_retry_send_ok",
        )
        .unwrap();
    assert_eq!(notified.retry_count, 1);
    assert_eq!(notified.retry_history[0].outcome, "notified");
    assert_eq!(
        notified.retry_history[0].reason.as_deref(),
        Some("cmux_retry_send_ok")
    );
}

#[test]
fn retry_dispatch_exhausts_after_max_attempts() {
    let store = temp_store("retry_dispatch_exhausts_after_max_attempts");
    store
        .create_task(CreateTaskInput {
            task_id: "T-01".into(),
            subject: "subject".into(),
            description: "description".into(),
            role: Some("implementer".into()),
        })
        .unwrap();
    let request = store.dispatch("implementer", "T-01").unwrap();

    for expected_count in 1..=MAX_DISPATCH_RETRIES {
        let retried = store
            .retry_dispatch(RetryDispatchInput {
                request_id: request.request_id.clone(),
            })
            .unwrap();
        assert!(matches!(retried.status, DispatchStatus::Pending));
        assert_eq!(retried.last_reason.as_deref(), Some("retry_requested"));
        assert_eq!(retried.retry_count, expected_count);
        assert_eq!(retried.retry_history.len() as u64, expected_count);
    }

    let exhausted = store
        .retry_dispatch(RetryDispatchInput {
            request_id: request.request_id.clone(),
        })
        .unwrap_err();
    assert!(exhausted.contains("retry_exhausted"));

    let request = store.read_dispatch(&request.request_id).unwrap();
    assert!(matches!(request.status, DispatchStatus::Failed));
    assert_eq!(request.last_reason.as_deref(), Some("retry_exhausted"));
    assert_eq!(request.retry_count, MAX_DISPATCH_RETRIES);
    assert_eq!(request.retry_history.len() as u64, MAX_DISPATCH_RETRIES);
}

#[test]
fn retry_dispatch_rejects_delivered_request_before_limit_check() {
    let store = temp_store("retry_dispatch_rejects_delivered_request_before_limit_check");
    store
        .create_task(CreateTaskInput {
            task_id: "T-01".into(),
            subject: "subject".into(),
            description: "description".into(),
            role: Some("implementer".into()),
        })
        .unwrap();
    let request = store.dispatch("implementer", "T-01").unwrap();
    store
        .ack_dispatch(AckDispatchInput {
            request_id: request.request_id.clone(),
            role_id: "implementer".into(),
        })
        .unwrap();

    let error = store
        .retry_dispatch(RetryDispatchInput {
            request_id: request.request_id,
        })
        .unwrap_err();
    assert!(error.contains("delivered request cannot be retried"));
}

#[test]
fn audit_and_repair_legacy_plaintext_mailbox_body() {
    let store = temp_store("audit_and_repair_legacy_plaintext_mailbox_body");
    store.init().unwrap();
    let mailbox = vec![MailboxMessage {
        message_id: "message-legacy".into(),
        from_role: "implementer".into(),
        to_role: "orchestrator".into(),
        kind: "result".into(),
        task_id: Some("T-01".into()),
        body: "legacy result text".into(),
        created_at: now_string(),
        read_at: None,
        consumed_at: None,
    }];
    write_json_atomic(&store.mailbox_path("orchestrator"), &mailbox).unwrap();

    let audit = store.audit_state().unwrap();
    assert_eq!(audit["summary"]["mailbox_issues"], 1);
    assert_eq!(audit["mailbox"][0]["type"], "invalid_mailbox_body_schema");

    let repair = store
        .repair_state(RepairStateInput { apply: true })
        .unwrap();
    assert_eq!(repair["after"]["summary"]["mailbox_issues"], 0);

    let messages = store
        .read_mailbox(ReadMailboxInput {
            role_id: None,
            task_id: Some("T-01".into()),
            unread_only: None,
            unconsumed_only: None,
        })
        .unwrap();
    let body: serde_json::Value = serde_json::from_str(&messages[0].body).unwrap();
    assert_eq!(body["summary"], "legacy result text");
    assert_eq!(body["not_run_reason"], "legacy plaintext message");
}

#[test]
fn repair_state_fixes_legacy_invalid_entries() {
    let store = temp_store("repair_state_fixes_legacy_invalid_entries");
    store.init().unwrap();
    let mailbox = vec![MailboxMessage {
        message_id: "message-bad".into(),
        from_role: "implementer".into(),
        to_role: "orchestrator".into(),
        kind: "anything".into(),
        task_id: Some("T-01".into()),
        body: " ".into(),
        created_at: now_string(),
        read_at: None,
        consumed_at: None,
    }];
    write_json_atomic(&store.mailbox_path("orchestrator"), &mailbox).unwrap();
    let dispatch = vec![DispatchRequest {
        request_id: "dispatch-bad".into(),
        kind: "inbox".into(),
        to_role: "implementer".into(),
        task_id: "T-01".into(),
        trigger_message: "moondex: read your inbox".into(),
        surface_ref: Some("surface:999999".into()),
        status: DispatchStatus::Notified,
        created_at: now_string(),
        updated_at: now_string(),
        last_reason: Some("legacy".into()),
        retry_count: 0,
        retry_history: Vec::new(),
    }];
    write_json_atomic(&store.dispatch_path(), &dispatch).unwrap();

    let audit = store.audit_state().unwrap();
    assert_eq!(audit["summary"]["mailbox_issues"], 2);
    assert_eq!(audit["summary"]["dispatch_issues"], 2);
    assert_eq!(audit["mailbox"][1]["type"], "invalid_mailbox_body_schema");

    let repair = store
        .repair_state(RepairStateInput { apply: true })
        .unwrap();
    assert_eq!(repair["after"]["summary"]["mailbox_issues"], 0);
    assert_eq!(repair["after"]["summary"]["dispatch_issues"], 0);

    let messages = store
        .read_mailbox(ReadMailboxInput {
            role_id: None,
            task_id: Some("T-01".into()),
            unread_only: None,
            unconsumed_only: None,
        })
        .unwrap();
    assert_eq!(messages[0].kind, "blocked");
    let body: serde_json::Value = serde_json::from_str(&messages[0].body).unwrap();
    assert_eq!(body["reason"], "[repaired] empty mailbox body");
    assert_eq!(body["needs"], "legacy follow-up required");

    let requests = store.list_dispatch().unwrap();
    assert!(matches!(requests[0].status, DispatchStatus::Failed));
    assert!(requests[0].trigger_message.starts_with("# moondex:"));
}

#[test]
fn dispatch_inbox_includes_previous_phase_context_and_output_contract() {
    let store = temp_store("dispatch_inbox_includes_previous_phase_context_and_output_contract");
    store
        .create_task(CreateTaskInput {
            task_id: "T-01".into(),
            subject: "subject".into(),
            description: "description".into(),
            role: Some("code-reviewer".into()),
        })
        .unwrap();
    store
        .write_mailbox(WriteMailboxInput {
            from_role: "implementer".into(),
            to_role: None,
            kind: "result".into(),
            task_id: Some("T-01".into()),
            body: serde_json::json!({
                "summary": "implementation finished",
                "changed_files": ["crates/moondex/src/fs_state.rs"],
                "tests": ["cargo test -p moondex"]
            })
            .to_string(),
        })
        .unwrap();

    store.dispatch("code-reviewer", "T-01").unwrap();
    let inbox = fs::read_to_string(
        store
            .root
            .join("roles")
            .join("code-reviewer")
            .join("inbox.md"),
    )
    .unwrap();
    assert!(inbox.contains("implementation finished"));
    assert!(inbox.contains("\"previous_messages\""));
    assert!(inbox.contains("\"expected_output\""));
    assert!(inbox.contains("review_approved"));
}

#[test]
fn archive_state_dry_run_and_apply_prune_only_eligible_records() {
    let store = temp_store("archive_state_dry_run_and_apply_prune_only_eligible_records");
    store
        .create_task(CreateTaskInput {
            task_id: "T-DONE".into(),
            subject: "done".into(),
            description: "done".into(),
            role: Some("implementer".into()),
        })
        .unwrap();
    let claimed = store
        .claim_task(ClaimTaskInput {
            task_id: "T-DONE".into(),
            worker: "implementer".into(),
            expected_version: 1,
        })
        .unwrap();
    let token = claimed["claim_token"].as_str().unwrap().to_string();
    store
        .transition_task(TransitionTaskInput {
            task_id: "T-DONE".into(),
            from: TaskStatus::InProgress,
            to: TaskStatus::Completed,
            claim_token: token,
            result: Some("done".into()),
            error: None,
        })
        .unwrap();
    store
        .create_task(CreateTaskInput {
            task_id: "T-PENDING".into(),
            subject: "pending".into(),
            description: "pending".into(),
            role: Some("implementer".into()),
        })
        .unwrap();
    store
        .write_role_identity(WriteRoleIdentityInput {
            role_id: "implementer".into(),
            surface_ref: Some("surface:2".into()),
        })
        .unwrap();
    let delivered = store.dispatch("implementer", "T-PENDING").unwrap();
    store
        .ack_dispatch(AckDispatchInput {
            request_id: delivered.request_id.clone(),
            role_id: "implementer".into(),
        })
        .unwrap();
    let failed = store.dispatch("implementer", "T-PENDING").unwrap();
    store
        .mark_dispatch(&failed.request_id, DispatchStatus::Failed, "test_failed")
        .unwrap();
    write_json_atomic(
        &store.mailbox_path("orchestrator"),
        &vec![
            MailboxMessage {
                message_id: "message-consumed".into(),
                from_role: "tester".into(),
                to_role: "orchestrator".into(),
                kind: "result".into(),
                task_id: Some("T-DONE".into()),
                body: result_body("consumed"),
                created_at: now_string(),
                read_at: Some(now_string()),
                consumed_at: Some(now_string()),
            },
            MailboxMessage {
                message_id: "message-open".into(),
                from_role: "tester".into(),
                to_role: "orchestrator".into(),
                kind: "result".into(),
                task_id: Some("T-PENDING".into()),
                body: result_body("open"),
                created_at: now_string(),
                read_at: None,
                consumed_at: None,
            },
        ],
    )
    .unwrap();

    let dry_run = store
        .archive_state(ArchiveStateInput {
            apply: false,
            older_than_seconds: 0,
            include_hook_warnings: false,
        })
        .unwrap();
    assert_eq!(dry_run["applied"], false);
    assert_eq!(dry_run["candidates"]["tasks"].as_array().unwrap().len(), 1);
    assert_eq!(
        dry_run["candidates"]["mailbox_messages"]
            .as_array()
            .unwrap()
            .len(),
        1
    );
    assert_eq!(
        dry_run["candidates"]["dispatch_requests"]
            .as_array()
            .unwrap()
            .len(),
        1
    );

    let applied = store
        .archive_state(ArchiveStateInput {
            apply: true,
            older_than_seconds: 0,
            include_hook_warnings: false,
        })
        .unwrap();
    assert_eq!(applied["archived"]["tasks"], 1);
    assert_eq!(applied["archived"]["mailbox_messages"], 1);
    assert_eq!(applied["archived"]["dispatch_requests"], 1);
    assert!(store.read_task("T-DONE").is_err());
    assert!(store.read_task("T-PENDING").is_ok());
    let remaining_messages = store
        .read_mailbox(ReadMailboxInput {
            role_id: None,
            task_id: None,
            unread_only: None,
            unconsumed_only: None,
        })
        .unwrap();
    assert_eq!(remaining_messages.len(), 1);
    assert_eq!(remaining_messages[0].message_id, "message-open");
    let remaining_dispatch = store.list_dispatch().unwrap();
    assert_eq!(remaining_dispatch.len(), 1);
    assert!(matches!(
        remaining_dispatch[0].status,
        DispatchStatus::Failed
    ));
    let events = store
        .list_events(ListEventsInput {
            task_id: Some("T-DONE".into()),
            kind: None,
            limit: None,
        })
        .unwrap();
    assert!(!events.is_empty());
    assert!(store.events_path().exists());
}

#[test]
fn phase_advance_appends_event() {
    let store = temp_store("phase_advance_appends_event");
    store
        .create_task(CreateTaskInput {
            task_id: "T-01".into(),
            subject: "subject".into(),
            description: "description".into(),
            role: Some("implementer".into()),
        })
        .unwrap();
    let claimed = store
        .claim_task(ClaimTaskInput {
            task_id: "T-01".into(),
            worker: "implementer".into(),
            expected_version: 1,
        })
        .unwrap();
    let token = claimed["claim_token"].as_str().unwrap().to_string();
    store
        .transition_task(TransitionTaskInput {
            task_id: "T-01".into(),
            from: TaskStatus::InProgress,
            to: TaskStatus::Completed,
            claim_token: token,
            result: Some("done".into()),
            error: None,
        })
        .unwrap();
    store
        .write_mailbox(WriteMailboxInput {
            from_role: "implementer".into(),
            to_role: None,
            kind: "result".into(),
            task_id: Some("T-01".into()),
            body: serde_json::json!({
                "summary": "done",
                "changed_files": ["src/lib.rs"],
                "tests": ["cargo test -p moondex"]
            })
            .to_string(),
        })
        .unwrap();
    store
        .consume_mailbox_for_task(ConsumeMailboxForTaskInput {
            role_id: None,
            task_id: "T-01".into(),
            from_role: Some("implementer".into()),
            kind: Some("result".into()),
        })
        .unwrap();

    let events = store
        .list_events(ListEventsInput {
            task_id: Some("T-01".into()),
            kind: Some("phase_advanced".into()),
            limit: None,
        })
        .unwrap();
    assert_eq!(events.len(), 1);
    assert_eq!(events[0].from_phase.as_deref(), Some("implementation"));
    assert_eq!(events[0].to_phase.as_deref(), Some("code_review"));
    assert_eq!(
        events[0]
            .message_id
            .as_deref()
            .unwrap()
            .starts_with("message-"),
        true
    );
}

#[test]
fn list_events_filters_task_kind_and_limit() {
    let store = temp_store("list_events_filters_task_kind_and_limit");
    store
        .create_task(CreateTaskInput {
            task_id: "T-01".into(),
            subject: "one".into(),
            description: "one".into(),
            role: Some("implementer".into()),
        })
        .unwrap();
    store
        .create_task(CreateTaskInput {
            task_id: "T-02".into(),
            subject: "two".into(),
            description: "two".into(),
            role: Some("tester".into()),
        })
        .unwrap();
    let claimed = store
        .claim_task(ClaimTaskInput {
            task_id: "T-01".into(),
            worker: "implementer".into(),
            expected_version: 1,
        })
        .unwrap();
    let token = claimed["claim_token"].as_str().unwrap().to_string();
    store
        .release_task_claim(ReleaseTaskInput {
            task_id: "T-01".into(),
            worker: "implementer".into(),
            claim_token: token,
        })
        .unwrap();

    let t01_events = store
        .list_events(ListEventsInput {
            task_id: Some("T-01".into()),
            kind: None,
            limit: None,
        })
        .unwrap();
    assert_eq!(t01_events.len(), 3);
    assert!(
        t01_events
            .iter()
            .all(|event| event.task_id.as_deref() == Some("T-01"))
    );

    let created = store
        .list_events(ListEventsInput {
            task_id: None,
            kind: Some("task_created".into()),
            limit: Some(1),
        })
        .unwrap();
    assert_eq!(created.len(), 1);
    assert_eq!(created[0].task_id.as_deref(), Some("T-02"));
}

#[test]
fn audit_reports_malformed_event_log_line() {
    let store = temp_store("audit_reports_malformed_event_log_line");
    store.init().unwrap();
    fs::write(store.events_path(), "{\"event_id\":\"ok\"}\nnot-json\n").unwrap();

    let audit = store.audit_state().unwrap();
    assert_eq!(audit["summary"]["event_issues"], 2);
    assert_eq!(audit["events"][0]["type"], "malformed_event_log_line");
}

#[test]
fn inspect_hooks_reports_repo_local_validators() {
    let project_root = std::env::temp_dir().join(format!("moondex-hooks-{}", unix_millis()));
    let hooks_dir = project_root.join(".codex").join("hooks");
    fs::create_dir_all(&hooks_dir).unwrap();
    for name in ["validate-role-transfer.sh", "validate-readiness.sh"] {
        let path = hooks_dir.join(name);
        fs::write(&path, "#!/usr/bin/env bash\nexit 0\n").unwrap();
        let mut permissions = fs::metadata(&path).unwrap().permissions();
        permissions.set_mode(0o755);
        fs::set_permissions(&path, permissions).unwrap();
    }
    let store = StateStore::from_root(project_root.join(".moondex").join("state"));
    let result = store.inspect_hooks().unwrap();
    let hooks = result["hooks"].as_array().unwrap();
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

fn temp_store(name: &str) -> StateStore {
    let root = std::env::temp_dir().join(format!("moondex-{name}-{}", unix_millis()));
    StateStore::from_root(root)
}

fn valid_readiness_payload() -> serde_json::Value {
    serde_json::json!({
        "task": {
            "task_id": "T-01",
            "subject": "Add readiness validator",
            "description": "Validate executor readiness before dispatch."
        },
        "plan": {
            "plan_id": "P-01",
            "task_id": "T-01",
            "objective": "Implement readiness validator.",
            "scope_paths": ["crates/moondex/src/fs_state.rs"],
            "acceptance_criteria": ["validator returns READY for complete payload"],
            "verification_commands": ["cargo test -p moondex"],
            "ownership": ["crates/moondex/src/fs_state.rs"]
        }
    })
}

fn result_body(summary: &str) -> String {
    serde_json::json!({
        "summary": summary,
        "changed_files": [],
        "not_run_reason": "not run",
    })
    .to_string()
}

fn review_approved_body(summary: &str) -> String {
    serde_json::json!({
        "summary": summary,
        "checks": ["checked"],
    })
    .to_string()
}
