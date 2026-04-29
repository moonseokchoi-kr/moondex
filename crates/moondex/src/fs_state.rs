use std::collections::HashSet;
use std::fs;
use std::fs::OpenOptions;
use std::io::{BufRead, BufReader, Write};
use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

use serde::Serialize;
use serde::de::DeserializeOwned;

use crate::model::{
    AckDispatchInput, ArchiveStateInput, ClaimTaskInput, ConsumeMailboxForTaskInput,
    ConsumeMailboxInput, CreateTaskInput, DispatchRequest, DispatchRetryRecord, DispatchStatus,
    EvidenceRecord, HookWarning, ListEventsInput, ListStaleRolesInput, MailboxMessage,
    MarkMailboxReadInput, PhaseEvent, ReadMailboxInput, ReleaseTaskInput, RepairStateInput,
    RetryDispatchInput, RoleIdentity, RoleStatus, Task, TaskClaim, TaskStatus, TransitionTaskInput,
    WriteMailboxInput, WriteRoleIdentityInput, WriteRoleStatusInput,
};

const MAX_DISPATCH_RETRIES: u64 = 3;

#[derive(Clone, Debug)]
pub struct StateStore {
    root: PathBuf,
}

impl StateStore {
    pub fn new(cwd: impl AsRef<Path>) -> Self {
        Self {
            root: cwd.as_ref().join(".moondex").join("state"),
        }
    }

    #[cfg(test)]
    pub fn from_root(root: impl AsRef<Path>) -> Self {
        Self {
            root: root.as_ref().to_path_buf(),
        }
    }

    pub fn root(&self) -> &Path {
        &self.root
    }

    pub fn init(&self) -> Result<(), String> {
        for dir in [
            self.root.clone(),
            self.root.join("tasks"),
            self.root.join("roles"),
            self.root.join("mailbox"),
            self.root.join("dispatch"),
            self.root.join("evidence"),
            self.root.join("hooks"),
        ] {
            fs::create_dir_all(&dir).map_err(|err| format!("create {}: {err}", dir.display()))?;
        }
        let config = self.root.join("config.json");
        if !config.exists() {
            write_json_atomic(
                &config,
                &serde_json::json!({
                    "schema_version": "1.0",
                    "runtime": "moondex",
                    "created_at": now_string(),
                }),
            )?;
        }
        let dispatch = self.root.join("dispatch").join("requests.json");
        if !dispatch.exists() {
            write_json_atomic(&dispatch, &Vec::<DispatchRequest>::new())?;
        }
        let evidence = self.root.join("evidence").join("index.json");
        if !evidence.exists() {
            write_json_atomic(&evidence, &Vec::<EvidenceRecord>::new())?;
        }
        let hook_warnings = self.hook_warnings_path();
        if !hook_warnings.exists() {
            write_json_atomic(&hook_warnings, &Vec::<HookWarning>::new())?;
        }
        let events = self.root.join("events.jsonl");
        if !events.exists() {
            fs::write(&events, "").map_err(|err| format!("write {}: {err}", events.display()))?;
        }
        Ok(())
    }

    pub fn status(&self) -> Result<serde_json::Value, String> {
        let tasks = self.list_tasks()?;
        let dispatch = self.list_dispatch()?;
        let role_statuses = self.list_role_statuses()?;
        let orchestrator_mailbox = self.read_mailbox_messages("orchestrator")?;
        Ok(serde_json::json!({
            "state_root": self.root,
            "tasks": {
                "total": tasks.len(),
                "pending": tasks.iter().filter(|task| task.status == TaskStatus::Pending).count(),
                "blocked": tasks.iter().filter(|task| task.status == TaskStatus::Blocked).count(),
                "in_progress": tasks.iter().filter(|task| task.status == TaskStatus::InProgress).count(),
                "completed": tasks.iter().filter(|task| task.status == TaskStatus::Completed).count(),
                "failed": tasks.iter().filter(|task| task.status == TaskStatus::Failed).count(),
            },
            "dispatch": {
                "total": dispatch.len(),
                "pending": dispatch.iter().filter(|request| matches!(request.status, DispatchStatus::Pending)).count(),
                "notified": dispatch.iter().filter(|request| matches!(request.status, DispatchStatus::Notified)).count(),
                "delivered": dispatch.iter().filter(|request| matches!(request.status, DispatchStatus::Delivered)).count(),
                "failed": dispatch.iter().filter(|request| matches!(request.status, DispatchStatus::Failed)).count(),
            },
            "roles": {
                "total_with_status": role_statuses.len(),
                "statuses": role_statuses,
            },
            "mailbox": {
                "orchestrator_messages": orchestrator_mailbox.len(),
                "orchestrator_unread": orchestrator_mailbox.iter().filter(|message| message.read_at.is_none()).count(),
                "orchestrator_unconsumed": orchestrator_mailbox.iter().filter(|message| message.consumed_at.is_none()).count(),
            },
        }))
    }

    pub fn audit_state(&self) -> Result<serde_json::Value, String> {
        let mailbox = self.audit_mailbox()?;
        let dispatch = self.audit_dispatch()?;
        let events = self.audit_events()?;
        let hook_warnings = self.read_hook_warnings()?;
        Ok(serde_json::json!({
            "mailbox": mailbox,
            "dispatch": dispatch,
            "events": events,
            "hook_warnings": hook_warnings,
            "summary": {
                "mailbox_issues": mailbox.len(),
                "dispatch_issues": dispatch.len(),
                "event_issues": events.len(),
                "hook_warnings": hook_warnings.len(),
            }
        }))
    }

    pub fn repair_state(&self, input: RepairStateInput) -> Result<serde_json::Value, String> {
        let before = self.audit_state()?;
        if !input.apply {
            return Ok(serde_json::json!({
                "applied": false,
                "before": before,
                "after": before,
            }));
        }

        let repaired_mailbox = self.repair_mailbox()?;
        let repaired_dispatch = self.repair_dispatch()?;
        let after = self.audit_state()?;
        Ok(serde_json::json!({
            "applied": true,
            "repaired": {
                "mailbox_messages": repaired_mailbox,
                "dispatch_requests": repaired_dispatch,
            },
            "before": before,
            "after": after,
        }))
    }

    pub fn archive_state(&self, input: ArchiveStateInput) -> Result<serde_json::Value, String> {
        self.init()?;
        let candidates = self.archive_candidates(&input)?;
        let archive_id = format!("archive-{}", unix_seconds());
        if !input.apply {
            return Ok(serde_json::json!({
                "applied": false,
                "archive_id": archive_id,
                "candidates": candidates,
            }));
        }

        let archive_dir = self.root.join("archive").join(&archive_id);
        fs::create_dir_all(&archive_dir)
            .map_err(|err| format!("create {}: {err}", archive_dir.display()))?;
        write_json_atomic(
            &archive_dir.join("manifest.json"),
            &serde_json::json!({
                "archive_id": archive_id,
                "created_at": now_string(),
                "older_than_seconds": input.older_than_seconds,
                "include_hook_warnings": input.include_hook_warnings,
                "candidates": candidates,
            }),
        )?;

        let archived_tasks = self.apply_archive_tasks(&archive_dir, &candidates)?;
        let archived_mailbox = self.apply_archive_mailbox(&archive_dir, &candidates)?;
        let archived_dispatch = self.apply_archive_dispatch(&archive_dir, &candidates)?;
        let archived_hooks = self.apply_archive_hook_warnings(&archive_dir, &candidates)?;
        self.append_event(PhaseEvent {
            event_id: make_token("event", "archive_created"),
            kind: "archive_created".into(),
            task_id: None,
            role_id: None,
            from_phase: None,
            to_phase: None,
            from_status: None,
            to_status: None,
            message_id: None,
            dispatch_request_id: None,
            created_at: now_string(),
            detail: serde_json::json!({
                "archive_id": archive_id,
                "archive_path": archive_dir,
                "archived": {
                    "tasks": archived_tasks,
                    "mailbox_messages": archived_mailbox,
                    "dispatch_requests": archived_dispatch,
                    "hook_warnings": archived_hooks,
                    "evidence": 0,
                }
            }),
        })?;

        Ok(serde_json::json!({
            "applied": true,
            "archive_id": archive_id,
            "archive_path": archive_dir,
            "archived": {
                "tasks": archived_tasks,
                "mailbox_messages": archived_mailbox,
                "dispatch_requests": archived_dispatch,
                "hook_warnings": archived_hooks,
                "evidence": 0,
            },
            "after": self.audit_state()?,
        }))
    }

    pub fn list_events(&self, input: ListEventsInput) -> Result<Vec<PhaseEvent>, String> {
        if let Some(task_id) = input.task_id.as_deref() {
            validate_id("task_id", task_id)?;
        }
        if let Some(kind) = input.kind.as_deref() {
            validate_event_kind(kind)?;
        }
        let mut events = self.read_events()?;
        if let Some(task_id) = input.task_id {
            events.retain(|event| event.task_id.as_deref() == Some(task_id.as_str()));
        }
        if let Some(kind) = input.kind {
            events.retain(|event| event.kind == kind);
        }
        if let Some(limit) = input.limit {
            let keep_from = events.len().saturating_sub(limit);
            events = events.into_iter().skip(keep_from).collect();
        }
        Ok(events)
    }

    pub fn inspect_hooks(&self) -> Result<serde_json::Value, String> {
        let hooks_dir = self.project_root().join(".codex").join("hooks");
        let mut hooks = Vec::new();
        if hooks_dir.exists() {
            for entry in fs::read_dir(&hooks_dir)
                .map_err(|err| format!("read {}: {err}", hooks_dir.display()))?
            {
                let entry = entry.map_err(|err| format!("read hook entry: {err}"))?;
                let path = entry.path();
                if !path.is_file() {
                    continue;
                }
                let name = path
                    .file_name()
                    .and_then(|value| value.to_str())
                    .unwrap_or("unknown")
                    .to_string();
                if !name.ends_with(".sh") {
                    continue;
                }
                let metadata = fs::metadata(&path)
                    .map_err(|err| format!("metadata {}: {err}", path.display()))?;
                let executable = metadata.permissions().mode() & 0o111 != 0;
                let target_operation = match name.as_str() {
                    "validate-role-transfer.sh" => "validate-role-transfer",
                    "validate-readiness.sh" => "validate-readiness",
                    _ => "unknown",
                };
                let smoke_command = match target_operation {
                    "validate-role-transfer" => format!(
                        "{} '{{\"from_role\":\"implementer\",\"kind\":\"result\",\"task_id\":\"T-01\",\"body\":\"{{\\\"summary\\\":\\\"done\\\",\\\"changed_files\\\":[],\\\"tests\\\":[\\\"cargo test -p moondex\\\"]}}\"}}'",
                        path.display()
                    ),
                    "validate-readiness" => format!(
                        "{} '{{\"task\":{{\"task_id\":\"T-01\",\"subject\":\"Add gate\",\"description\":\"Implement gate.\"}},\"plan\":{{\"plan_id\":\"P-01\",\"task_id\":\"T-01\",\"objective\":\"Implement gate.\",\"scope_paths\":[\"crates/moondex/src/fs_state.rs\"],\"acceptance_criteria\":[\"gate passes\"],\"verification_commands\":[\"cargo test -p moondex\"],\"ownership\":[\"crates/moondex/src/fs_state.rs\"]}}}}'",
                        path.display()
                    ),
                    _ => format!("{} '<json-payload>'", path.display()),
                };
                hooks.push(serde_json::json!({
                    "name": name,
                    "path": path,
                    "executable": executable,
                    "target_operation": target_operation,
                    "smoke_command": smoke_command,
                    "status": if executable && target_operation != "unknown" { "ok" } else if executable { "unknown_operation" } else { "not_executable" },
                }));
            }
        }
        hooks.sort_by(|left, right| {
            left["name"]
                .as_str()
                .unwrap_or("")
                .cmp(right["name"].as_str().unwrap_or(""))
        });
        Ok(serde_json::json!({
            "hooks_dir": hooks_dir,
            "hooks": hooks,
            "contract": "repo-local .codex/hooks discovery only; native Codex lifecycle auto-discovery is not assumed",
        }))
    }

    pub fn create_task(&self, input: CreateTaskInput) -> Result<Task, String> {
        self.init()?;
        validate_id("task_id", &input.task_id)?;
        let path = self.task_path(&input.task_id);
        if path.exists() {
            return Err("task_already_exists".into());
        }
        let task = Task {
            id: input.task_id,
            subject: input.subject,
            description: input.description,
            status: TaskStatus::Pending,
            phase: role_to_phase(input.role.as_deref()),
            owner: None,
            role: input.role,
            result: None,
            error: None,
            version: 1,
            claim: None,
            created_at: now_string(),
            completed_at: None,
        };
        self.write_task(&task)?;
        self.append_event(PhaseEvent {
            event_id: make_token("event", "task_created"),
            kind: "task_created".into(),
            task_id: Some(task.id.clone()),
            role_id: task.role.clone(),
            from_phase: None,
            to_phase: Some(task.phase.clone()),
            from_status: None,
            to_status: Some(TaskStatus::Pending),
            message_id: None,
            dispatch_request_id: None,
            created_at: now_string(),
            detail: serde_json::json!({
                "subject": task.subject.clone(),
            }),
        })?;
        Ok(task)
    }

    pub fn read_task(&self, task_id: &str) -> Result<Task, String> {
        validate_id("task_id", task_id)?;
        read_json(&self.task_path(task_id))
    }

    pub fn list_tasks(&self) -> Result<Vec<Task>, String> {
        let tasks_dir = self.root.join("tasks");
        if !tasks_dir.exists() {
            return Ok(Vec::new());
        }
        let mut tasks = Vec::new();
        for entry in fs::read_dir(&tasks_dir)
            .map_err(|err| format!("read {}: {err}", tasks_dir.display()))?
        {
            let entry = entry.map_err(|err| format!("read task entry: {err}"))?;
            if entry.path().extension().and_then(|value| value.to_str()) == Some("json") {
                tasks.push(read_json(&entry.path())?);
            }
        }
        tasks.sort_by(|left: &Task, right| left.id.cmp(&right.id));
        Ok(tasks)
    }

    pub fn claim_task(&self, input: ClaimTaskInput) -> Result<serde_json::Value, String> {
        let mut task = self.read_task(&input.task_id)?;
        let from_status = task.status.clone();
        let from_phase = task.phase.clone();
        if task.version != input.expected_version {
            return Err("claim_conflict: expected_version does not match".into());
        }
        if matches!(task.status, TaskStatus::Completed | TaskStatus::Failed) {
            return Err("already_terminal".into());
        }
        if task.status == TaskStatus::InProgress && task.claim.is_some() {
            return Err("claim_conflict: task already claimed".into());
        }
        let token = make_token(&task.id, &input.worker);
        task.status = TaskStatus::InProgress;
        task.owner = Some(input.worker.clone());
        task.claim = Some(TaskClaim {
            owner: input.worker,
            token: token.clone(),
            leased_until: lease_until_string(15 * 60),
        });
        task.version += 1;
        self.write_task(&task)?;
        self.append_event(PhaseEvent {
            event_id: make_token("event", "task_claimed"),
            kind: "task_claimed".into(),
            task_id: Some(task.id.clone()),
            role_id: task.owner.clone(),
            from_phase: Some(from_phase),
            to_phase: Some(task.phase.clone()),
            from_status: Some(from_status),
            to_status: Some(TaskStatus::InProgress),
            message_id: None,
            dispatch_request_id: None,
            created_at: now_string(),
            detail: serde_json::json!({
                "expected_version": input.expected_version,
                "claim_token": token.clone(),
            }),
        })?;
        Ok(serde_json::json!({ "task": task, "claim_token": token }))
    }

    pub fn transition_task(&self, input: TransitionTaskInput) -> Result<Task, String> {
        let mut task = self.read_task(&input.task_id)?;
        let from_status = task.status.clone();
        let from_phase = task.phase.clone();
        if task.status != input.from {
            return Err("invalid_transition: current status does not match from".into());
        }
        if task.status != TaskStatus::InProgress {
            return Err("invalid_transition: only in_progress can transition terminal".into());
        }
        if !matches!(&input.to, TaskStatus::Completed | TaskStatus::Failed) {
            return Err("invalid_transition: target must be completed or failed".into());
        }
        let claim = task.claim.as_ref().ok_or("claim_conflict: missing claim")?;
        if claim.token != input.claim_token {
            return Err("claim_conflict: token mismatch".into());
        }
        let role_id = claim.owner.clone();
        let to_status = input.to.clone();
        task.status = to_status.clone();
        task.result = input.result;
        task.error = input.error;
        task.completed_at = Some(now_string());
        task.claim = None;
        task.version += 1;
        self.write_task(&task)?;
        self.append_event(PhaseEvent {
            event_id: make_token("event", "task_transitioned"),
            kind: "task_transitioned".into(),
            task_id: Some(task.id.clone()),
            role_id: Some(role_id),
            from_phase: Some(from_phase),
            to_phase: Some(task.phase.clone()),
            from_status: Some(from_status),
            to_status: Some(to_status),
            message_id: None,
            dispatch_request_id: None,
            created_at: now_string(),
            detail: serde_json::json!({
                "has_result": task.result.is_some(),
                "has_error": task.error.is_some(),
            }),
        })?;
        Ok(task)
    }

    pub fn release_task_claim(&self, input: ReleaseTaskInput) -> Result<Task, String> {
        let mut task = self.read_task(&input.task_id)?;
        let from_status = task.status.clone();
        let from_phase = task.phase.clone();
        let claim = task.claim.as_ref().ok_or("claim_conflict: missing claim")?;
        if claim.owner != input.worker || claim.token != input.claim_token {
            return Err("claim_conflict: token mismatch".into());
        }
        task.status = TaskStatus::Pending;
        task.owner = None;
        task.claim = None;
        task.version += 1;
        self.write_task(&task)?;
        self.append_event(PhaseEvent {
            event_id: make_token("event", "task_released"),
            kind: "task_released".into(),
            task_id: Some(task.id.clone()),
            role_id: Some(input.worker),
            from_phase: Some(from_phase),
            to_phase: Some(task.phase.clone()),
            from_status: Some(from_status),
            to_status: Some(TaskStatus::Pending),
            message_id: None,
            dispatch_request_id: None,
            created_at: now_string(),
            detail: serde_json::json!({}),
        })?;
        Ok(task)
    }

    pub fn write_role_identity(
        &self,
        input: WriteRoleIdentityInput,
    ) -> Result<RoleIdentity, String> {
        self.init()?;
        validate_id("role_id", &input.role_id)?;
        let identity = RoleIdentity {
            role_id: input.role_id.clone(),
            surface_ref: input.surface_ref,
            updated_at: now_string(),
        };
        let dir = self.root.join("roles").join(&input.role_id);
        fs::create_dir_all(&dir).map_err(|err| format!("create {}: {err}", dir.display()))?;
        write_json_atomic(&dir.join("identity.json"), &identity)?;
        Ok(identity)
    }

    pub fn write_role_status(&self, input: WriteRoleStatusInput) -> Result<RoleStatus, String> {
        self.init()?;
        validate_id("role_id", &input.role_id)?;
        if let Some(task_id) = input.task_id.as_deref() {
            validate_id("task_id", task_id)?;
        }
        let status = RoleStatus {
            role_id: input.role_id.clone(),
            state: input.state,
            task_id: input.task_id,
            message: input.message,
            updated_at: now_string(),
        };
        let dir = self.root.join("roles").join(&input.role_id);
        fs::create_dir_all(&dir).map_err(|err| format!("create {}: {err}", dir.display()))?;
        write_json_atomic(&dir.join("status.json"), &status)?;
        Ok(status)
    }

    pub fn list_role_statuses(&self) -> Result<Vec<RoleStatus>, String> {
        let roles_dir = self.root.join("roles");
        if !roles_dir.exists() {
            return Ok(Vec::new());
        }
        let mut statuses = Vec::new();
        for entry in fs::read_dir(&roles_dir)
            .map_err(|err| format!("read {}: {err}", roles_dir.display()))?
        {
            let entry = entry.map_err(|err| format!("read role entry: {err}"))?;
            let status_path = entry.path().join("status.json");
            if status_path.exists() {
                statuses.push(read_json(&status_path)?);
            }
        }
        statuses.sort_by(|left: &RoleStatus, right| left.role_id.cmp(&right.role_id));
        Ok(statuses)
    }

    pub fn list_stale_roles(&self, input: ListStaleRolesInput) -> Result<Vec<RoleStatus>, String> {
        let now = unix_seconds();
        self.list_role_statuses().map(|statuses| {
            statuses
                .into_iter()
                .filter(|status| {
                    status
                        .updated_at
                        .parse::<u64>()
                        .map(|updated_at| now.saturating_sub(updated_at) > input.older_than_seconds)
                        .unwrap_or(true)
                })
                .collect()
        })
    }

    pub fn dispatch(&self, role: &str, task_id: &str) -> Result<DispatchRequest, String> {
        self.init()?;
        validate_id("role", role)?;
        let task = self.read_task(task_id)?;
        if matches!(task.status, TaskStatus::Completed | TaskStatus::Failed) {
            return Err("invalid_dispatch: terminal task cannot be dispatched".into());
        }
        if let Some(task_role) = task.role.as_deref() {
            if task_role != role {
                return Err("invalid_dispatch: task role does not match dispatch role".into());
            }
        }
        if let Some(claim) = task.claim.as_ref() {
            if claim.owner != role {
                return Err("invalid_dispatch: task already claimed by another owner".into());
            }
        }
        let role_dir = self.root.join("roles").join(role);
        fs::create_dir_all(&role_dir)
            .map_err(|err| format!("create {}: {err}", role_dir.display()))?;
        let inbox = self.render_role_inbox(role, &task)?;
        fs::write(role_dir.join("inbox.md"), inbox)
            .map_err(|err| format!("write role inbox: {err}"))?;

        let identity_path = role_dir.join("identity.json");
        let surface_ref = if identity_path.exists() {
            let identity: RoleIdentity = read_json(&identity_path)?;
            identity.surface_ref
        } else {
            None
        };
        let now = now_string();
        let request = DispatchRequest {
            request_id: make_token("dispatch", role),
            kind: "inbox".into(),
            to_role: role.into(),
            task_id: task.id,
            trigger_message: format!("# moondex: read your inbox for task {task_id}\n"),
            surface_ref: surface_ref.clone(),
            status: DispatchStatus::Pending,
            created_at: now.clone(),
            updated_at: now,
            last_reason: if surface_ref.is_some() {
                Some("created".into())
            } else {
                Some("surface_ref_missing".into())
            },
            retry_count: 0,
            retry_history: Vec::new(),
        };
        let mut requests = self.list_dispatch()?;
        requests.push(request.clone());
        write_json_atomic(&self.dispatch_path(), &requests)?;
        self.append_event(PhaseEvent {
            event_id: make_token("event", "dispatch_created"),
            kind: "dispatch_created".into(),
            task_id: Some(request.task_id.clone()),
            role_id: Some(request.to_role.clone()),
            from_phase: Some(task.phase.clone()),
            to_phase: Some(task.phase.clone()),
            from_status: Some(task.status.clone()),
            to_status: Some(task.status.clone()),
            message_id: None,
            dispatch_request_id: Some(request.request_id.clone()),
            created_at: now_string(),
            detail: serde_json::json!({
                "surface_ref": request.surface_ref.clone(),
                "last_reason": request.last_reason.clone(),
            }),
        })?;
        if surface_ref.is_none() {
            self.append_hook_warning(
                "dispatch",
                "surface_ref_missing",
                Some(&request.task_id),
                Some(role),
                None,
                "dispatch target has no registered role identity surface",
            )?;
        }
        Ok(request)
    }

    pub fn list_dispatch(&self) -> Result<Vec<DispatchRequest>, String> {
        let path = self.dispatch_path();
        if !path.exists() {
            return Ok(Vec::new());
        }
        read_json(&path)
    }

    pub fn read_dispatch(&self, request_id: &str) -> Result<DispatchRequest, String> {
        self.list_dispatch()?
            .into_iter()
            .find(|request| request.request_id == request_id)
            .ok_or_else(|| "dispatch_not_found".into())
    }

    pub fn mark_dispatch(
        &self,
        request_id: &str,
        status: DispatchStatus,
        reason: impl Into<String>,
    ) -> Result<DispatchRequest, String> {
        let mut requests = self.list_dispatch()?;
        let reason = reason.into();
        let mut updated = None;
        let mut from_status = None;
        for request in &mut requests {
            if request.request_id == request_id {
                from_status = Some(request.status.clone());
                request.status = status.clone();
                request.updated_at = now_string();
                request.last_reason = Some(reason.clone());
                if let Some(retry) = request.retry_history.last_mut() {
                    if retry.outcome == "pending" {
                        retry.outcome = dispatch_status_name(&status).into();
                        retry.reason = Some(reason.clone());
                        retry.surface_ref = request.surface_ref.clone();
                    }
                }
                updated = Some(request.clone());
                break;
            }
        }
        let updated = updated.ok_or_else(|| "dispatch_not_found".to_string())?;
        write_json_atomic(&self.dispatch_path(), &requests)?;
        self.append_event(PhaseEvent {
            event_id: make_token("event", "dispatch_marked"),
            kind: "dispatch_marked".into(),
            task_id: Some(updated.task_id.clone()),
            role_id: Some(updated.to_role.clone()),
            from_phase: None,
            to_phase: None,
            from_status: None,
            to_status: None,
            message_id: None,
            dispatch_request_id: Some(updated.request_id.clone()),
            created_at: now_string(),
            detail: serde_json::json!({
                "from_dispatch_status": from_status.map(|status| dispatch_status_name(&status)),
                "to_dispatch_status": dispatch_status_name(&updated.status),
                "reason": reason,
            }),
        })?;
        Ok(updated)
    }

    pub fn ack_dispatch(&self, input: AckDispatchInput) -> Result<DispatchRequest, String> {
        validate_id("role_id", &input.role_id)?;
        let request = self.read_dispatch(&input.request_id)?;
        if request.to_role != input.role_id {
            return Err("dispatch_role_mismatch".into());
        }
        if matches!(request.status, DispatchStatus::Failed) {
            return Err("invalid_dispatch_ack: failed request cannot be delivered".into());
        }
        self.mark_dispatch(&input.request_id, DispatchStatus::Delivered, "ack_by_role")
    }

    pub fn retry_dispatch(&self, input: RetryDispatchInput) -> Result<DispatchRequest, String> {
        validate_id("request_id", &input.request_id)?;
        let mut request = self.read_dispatch(&input.request_id)?;
        if matches!(request.status, DispatchStatus::Delivered) {
            return Err("invalid_dispatch_retry: delivered request cannot be retried".into());
        }
        if request.retry_count >= MAX_DISPATCH_RETRIES {
            let from_status = request.status.clone();
            request.status = DispatchStatus::Failed;
            request.updated_at = now_string();
            request.last_reason = Some("retry_exhausted".into());
            self.replace_dispatch(request.clone())?;
            self.append_event(PhaseEvent {
                event_id: make_token("event", "dispatch_marked"),
                kind: "dispatch_marked".into(),
                task_id: Some(request.task_id.clone()),
                role_id: Some(request.to_role.clone()),
                from_phase: None,
                to_phase: None,
                from_status: None,
                to_status: None,
                message_id: None,
                dispatch_request_id: Some(request.request_id.clone()),
                created_at: now_string(),
                detail: serde_json::json!({
                    "from_dispatch_status": dispatch_status_name(&from_status),
                    "to_dispatch_status": dispatch_status_name(&request.status),
                    "reason": "retry_exhausted",
                    "retry_count": request.retry_count,
                }),
            })?;
            return Err("retry_exhausted: max retry attempts reached".into());
        }
        let identity_path = self
            .root
            .join("roles")
            .join(&request.to_role)
            .join("identity.json");
        if identity_path.exists() {
            let identity: RoleIdentity = read_json(&identity_path)?;
            request.surface_ref = identity.surface_ref;
        }
        request.status = DispatchStatus::Pending;
        request.updated_at = now_string();
        request.last_reason = Some("retry_requested".into());
        request.retry_count += 1;
        request.retry_history.push(DispatchRetryRecord {
            attempted_at: request.updated_at.clone(),
            surface_ref: request.surface_ref.clone(),
            outcome: "pending".into(),
            reason: Some("retry_requested".into()),
        });
        let request = self.replace_dispatch(request)?;
        self.append_event(PhaseEvent {
            event_id: make_token("event", "dispatch_marked"),
            kind: "dispatch_marked".into(),
            task_id: Some(request.task_id.clone()),
            role_id: Some(request.to_role.clone()),
            from_phase: None,
            to_phase: None,
            from_status: None,
            to_status: None,
            message_id: None,
            dispatch_request_id: Some(request.request_id.clone()),
            created_at: now_string(),
            detail: serde_json::json!({
                "to_dispatch_status": dispatch_status_name(&request.status),
                "reason": "retry_requested",
                "retry_count": request.retry_count,
            }),
        })?;
        Ok(request)
    }

    pub fn write_mailbox(&self, input: WriteMailboxInput) -> Result<MailboxMessage, String> {
        self.init()?;
        validate_id("from_role", &input.from_role)?;
        validate_mailbox_kind(&input.kind)?;
        validate_mailbox_body_schema(&input.kind, &input.body)?;
        let to_role = input
            .to_role
            .clone()
            .unwrap_or_else(|| "orchestrator".into());
        validate_id("to_role", &to_role)?;
        if let Some(task_id) = input.task_id.as_deref() {
            validate_id("task_id", task_id)?;
        }
        let validation = validate_role_transfer_payload(&serde_json::json!({
            "from_role": input.from_role.clone(),
            "kind": input.kind.clone(),
            "task_id": input.task_id.clone(),
            "body": input.body.clone(),
        }));
        if !validation["valid"].as_bool().unwrap_or(false) {
            return Err(format!(
                "invalid_role_transfer_contract: {}",
                validation["errors"]
            ));
        }
        let warnings = validation["warnings"]
            .as_array()
            .cloned()
            .unwrap_or_default();
        let message = MailboxMessage {
            message_id: make_token("message", &input.from_role),
            from_role: input.from_role,
            to_role: to_role.clone(),
            kind: input.kind,
            task_id: input.task_id,
            body: input.body,
            created_at: now_string(),
            read_at: None,
            consumed_at: None,
        };
        let mut messages = self.read_mailbox_messages(&to_role)?;
        messages.push(message.clone());
        write_json_atomic(&self.mailbox_path(&to_role), &messages)?;
        for warning in warnings {
            let warning_type = warning["code"].as_str().unwrap_or("role_transfer_warning");
            let detail = warning["detail"]
                .as_str()
                .unwrap_or("role transfer warning");
            self.append_hook_warning(
                "write-mailbox",
                warning_type,
                message.task_id.as_deref(),
                Some(&message.from_role),
                Some(&message.message_id),
                detail,
            )?;
        }
        Ok(message)
    }

    pub fn read_mailbox(&self, input: ReadMailboxInput) -> Result<Vec<MailboxMessage>, String> {
        let role_id = input.role_id.unwrap_or_else(|| "orchestrator".into());
        validate_id("role_id", &role_id)?;
        if let Some(task_id) = input.task_id.as_deref() {
            validate_id("task_id", task_id)?;
        }
        let mut messages = self.read_mailbox_messages(&role_id)?;
        if let Some(task_id) = input.task_id {
            messages.retain(|message| message.task_id.as_deref() == Some(task_id.as_str()));
        }
        if input.unread_only.unwrap_or(false) {
            messages.retain(|message| message.read_at.is_none());
        }
        if input.unconsumed_only.unwrap_or(false) {
            messages.retain(|message| message.consumed_at.is_none());
        }
        Ok(messages)
    }

    pub fn mark_mailbox_read(&self, input: MarkMailboxReadInput) -> Result<MailboxMessage, String> {
        let role_id = input.role_id.unwrap_or_else(|| "orchestrator".into());
        self.update_mailbox_message(&role_id, &input.message_id, |message| {
            if message.read_at.is_none() {
                message.read_at = Some(now_string());
            }
        })
    }

    pub fn consume_mailbox(&self, input: ConsumeMailboxInput) -> Result<MailboxMessage, String> {
        let role_id = input.role_id.unwrap_or_else(|| "orchestrator".into());
        let message = self.update_mailbox_message(&role_id, &input.message_id, |message| {
            let now = now_string();
            if message.read_at.is_none() {
                message.read_at = Some(now.clone());
            }
            if message.consumed_at.is_none() {
                message.consumed_at = Some(now);
            }
        })?;
        self.append_event(PhaseEvent {
            event_id: make_token("event", "mailbox_consumed"),
            kind: "mailbox_consumed".into(),
            task_id: message.task_id.clone(),
            role_id: Some(role_id.clone()),
            from_phase: None,
            to_phase: None,
            from_status: None,
            to_status: None,
            message_id: Some(message.message_id.clone()),
            dispatch_request_id: None,
            created_at: now_string(),
            detail: serde_json::json!({
                "from_role": message.from_role.clone(),
                "to_role": message.to_role.clone(),
                "kind": message.kind.clone(),
            }),
        })?;
        self.advance_task_after_orchestrator_consume(&role_id, &message)?;
        Ok(message)
    }

    pub fn consume_mailbox_for_task(
        &self,
        input: ConsumeMailboxForTaskInput,
    ) -> Result<MailboxMessage, String> {
        let role_id = input.role_id.unwrap_or_else(|| "orchestrator".into());
        validate_id("role_id", &role_id)?;
        validate_id("task_id", &input.task_id)?;
        if let Some(from_role) = input.from_role.as_deref() {
            validate_id("from_role", from_role)?;
        }
        if let Some(kind) = input.kind.as_deref() {
            validate_mailbox_kind(kind)?;
        }
        let messages = self.read_mailbox_messages(&role_id)?;
        let message_id = messages
            .iter()
            .filter(|message| message.consumed_at.is_none())
            .filter(|message| message.task_id.as_deref() == Some(input.task_id.as_str()))
            .filter(|message| {
                input
                    .from_role
                    .as_deref()
                    .map(|from_role| message.from_role == from_role)
                    .unwrap_or(true)
            })
            .filter(|message| {
                input
                    .kind
                    .as_deref()
                    .map(|kind| message.kind == kind)
                    .unwrap_or(true)
            })
            .map(|message| message.message_id.clone())
            .next()
            .ok_or_else(|| "mailbox_message_not_found".to_string())?;
        self.consume_mailbox(ConsumeMailboxInput {
            role_id: Some(role_id),
            message_id,
        })
    }

    pub fn validate_role_transfer(
        &self,
        input: serde_json::Value,
    ) -> Result<serde_json::Value, String> {
        Ok(validate_role_transfer_payload(&input))
    }

    pub fn validate_readiness(
        &self,
        input: serde_json::Value,
    ) -> Result<serde_json::Value, String> {
        Ok(validate_readiness_payload(&input))
    }

    pub fn next_action(&self) -> Result<serde_json::Value, String> {
        let audit = self.audit_state()?;
        if audit["summary"]["mailbox_issues"].as_u64().unwrap_or(0) > 0
            || audit["summary"]["dispatch_issues"].as_u64().unwrap_or(0) > 0
        {
            return Ok(serde_json::json!({
                "action": "repair_state",
                "reason": "audit-state reports mailbox or dispatch issues",
                "command": "moondex api repair-state --input '{\"apply\":true}' --json",
                "confidence": "high",
            }));
        }
        if audit["summary"]["hook_warnings"].as_u64().unwrap_or(0) > 0 {
            return Ok(serde_json::json!({
                "action": "review_hook_warnings",
                "reason": "durable hook warnings are present",
                "command": "moondex api audit-state --json",
                "confidence": "high",
            }));
        }

        let orchestrator_messages = self.read_mailbox_messages("orchestrator")?;
        if let Some(message) = orchestrator_messages
            .iter()
            .find(|message| message.consumed_at.is_none())
        {
            return Ok(serde_json::json!({
                "action": "consume_mailbox",
                "reason": format!("orchestrator has unconsumed {} message for task {}", message.kind, message.task_id.as_deref().unwrap_or("unknown")),
                "task_id": message.task_id,
                "role_id": "orchestrator",
                "message_id": message.message_id,
                "from_role": message.from_role,
                "kind": message.kind,
                "command": format!("moondex api consume-mailbox-for-task --input '{{\"role_id\":\"orchestrator\",\"task_id\":\"{}\",\"from_role\":\"{}\",\"kind\":\"{}\"}}' --json", message.task_id.as_deref().unwrap_or(""), message.from_role, message.kind),
                "confidence": "high",
            }));
        }

        if let Some(request) = self.list_dispatch()?.into_iter().find(|request| {
            matches!(
                request.status,
                DispatchStatus::Pending | DispatchStatus::Notified
            )
        }) {
            return Ok(serde_json::json!({
                "action": "ack_dispatch_wait",
                "reason": format!("dispatch request {} is not delivered", request.request_id),
                "task_id": request.task_id,
                "role_id": request.to_role,
                "command": format!("moondex api ack-dispatch --input '{{\"request_id\":\"{}\",\"role_id\":\"{}\"}}' --json", request.request_id, request.to_role),
                "confidence": "medium",
            }));
        }

        if let Some(message) = orchestrator_messages.iter().find(|message| {
            message.from_role == "code-reviewer"
                && message.kind == "review_approved"
                && message.task_id.is_some()
                && mailbox_body_bool(&message.body, "compliance_review_required")
        }) {
            let task_id = message.task_id.as_deref().unwrap_or("");
            let already_dispatched = self.list_dispatch()?.into_iter().any(|request| {
                request.task_id == task_id && request.to_role == "compliance-reviewer"
            });
            if !already_dispatched {
                return Ok(serde_json::json!({
                    "action": "dispatch_compliance_reviewer",
                    "reason": format!("code-reviewer marked compliance required for task {task_id}"),
                    "task_id": task_id,
                    "role_id": "compliance-reviewer",
                    "command": format!("moondex dispatch compliance-reviewer {task_id} --json"),
                    "confidence": "high",
                }));
            }
        }

        if let Some(message) = orchestrator_messages.iter().find(|message| {
            message.from_role == "code-reviewer"
                && message.kind == "review_approved"
                && message.task_id.is_some()
                && mailbox_body_bool(&message.body, "tester_required")
        }) {
            let task_id = message.task_id.as_deref().unwrap_or("");
            let already_dispatched = self
                .list_dispatch()?
                .into_iter()
                .any(|request| request.task_id == task_id && request.to_role == "tester");
            if !already_dispatched {
                return Ok(serde_json::json!({
                    "action": "dispatch_tester",
                    "reason": format!("code-reviewer requested independent tester evidence for task {task_id}"),
                    "task_id": task_id,
                    "role_id": "tester",
                    "command": format!("moondex dispatch tester {task_id} --json"),
                    "confidence": "high",
                }));
            }
        }

        if let Some(task) = self
            .list_tasks()?
            .into_iter()
            .find(|task| task.status == TaskStatus::Pending && task.owner.is_none())
        {
            let role = task.role.clone().unwrap_or_else(|| "implementer".into());
            let action = match role.as_str() {
                "code-reviewer" => "dispatch_code_reviewer",
                "compliance-reviewer" => "dispatch_compliance_reviewer",
                "tester" => "dispatch_tester",
                "implementer" => "dispatch_implementer",
                _ => "dispatch_implementer",
            };
            return Ok(serde_json::json!({
                "action": action,
                "reason": format!("pending task {} has no owner", task.id),
                "task_id": task.id,
                "role_id": role,
                "command": format!("moondex dispatch {} {} --json", role, task.id),
                "confidence": "medium",
            }));
        }

        Ok(serde_json::json!({
            "action": "wait",
            "reason": "no actionable mailbox, dispatch, audit, or pending task state found",
            "confidence": "medium",
        }))
    }

    pub fn write_evidence(
        &self,
        source_ref: &str,
        lines: usize,
        content: &str,
    ) -> Result<EvidenceRecord, String> {
        self.init()?;
        let evidence_id = make_token("evidence", &sanitize_ref(source_ref));
        let filename = format!("{evidence_id}.txt");
        let path = self.root.join("evidence").join(&filename);
        fs::write(&path, content).map_err(|err| format!("write {}: {err}", path.display()))?;
        let record = EvidenceRecord {
            evidence_id,
            kind: "cmux_capture".into(),
            source_ref: source_ref.into(),
            path: path.display().to_string(),
            lines,
            captured_at: now_string(),
        };
        let mut records = self.list_evidence()?;
        records.push(record.clone());
        write_json_atomic(&self.evidence_index_path(), &records)?;
        Ok(record)
    }

    pub fn list_evidence(&self) -> Result<Vec<EvidenceRecord>, String> {
        let path = self.evidence_index_path();
        if !path.exists() {
            return Ok(Vec::new());
        }
        read_json(&path)
    }

    fn render_role_inbox(&self, role: &str, task: &Task) -> Result<String, String> {
        let previous_messages = self.relevant_task_messages(role, &task.id)?;
        let payload = serde_json::json!({
            "task": {
                "id": task.id,
                "subject": task.subject,
                "description": task.description,
                "status": task.status,
                "phase": task.phase,
                "role": role,
                "version": task.version,
            },
            "previous_messages": previous_messages,
            "expected_output": expected_output_contract(role),
        });
        let pretty_payload = serde_json::to_string_pretty(&payload)
            .map_err(|err| format!("serialize inbox payload: {err}"))?;
        let mut previous = String::new();
        if let Some(messages) = payload["previous_messages"].as_array() {
            for message in messages {
                let summary = message["body"]["summary"]
                    .as_str()
                    .or_else(|| message["body"]["reason"].as_str())
                    .unwrap_or("no summary");
                previous.push_str(&format!(
                    "- from `{}` kind `{}`: {}\n",
                    message["from_role"].as_str().unwrap_or("unknown"),
                    message["kind"].as_str().unwrap_or("unknown"),
                    summary
                ));
            }
        }
        if previous.is_empty() {
            previous.push_str("- none\n");
        }
        Ok(format!(
            "# Moondex Assignment\n\nrole: `{role}`\ntask_id: `{}`\nphase: `{}`\nsubject: {}\n\n## Previous Context\n{}\n## Expected Output\n{}\n\n## Machine Payload\n```json\n{}\n```\n\nRead `.moondex/state/tasks/{}.json`, claim if needed, and report through moondex state.\n",
            task.id,
            task.phase,
            task.subject,
            previous,
            expected_output_summary(role),
            pretty_payload,
            task.id,
        ))
    }

    fn relevant_task_messages(
        &self,
        role: &str,
        task_id: &str,
    ) -> Result<Vec<serde_json::Value>, String> {
        let mut messages: Vec<_> = self
            .read_mailbox_messages("orchestrator")?
            .into_iter()
            .filter(|message| message.task_id.as_deref() == Some(task_id))
            .filter(|message| match role {
                "code-reviewer" => message.from_role == "implementer",
                "compliance-reviewer" => {
                    matches!(message.from_role.as_str(), "implementer" | "code-reviewer")
                }
                "tester" => matches!(
                    message.from_role.as_str(),
                    "implementer" | "code-reviewer" | "compliance-reviewer"
                ),
                _ => false,
            })
            .collect();
        messages.sort_by(|left, right| left.created_at.cmp(&right.created_at));
        let keep = messages.len().saturating_sub(4);
        Ok(messages
            .into_iter()
            .skip(keep)
            .map(|message| {
                let body = serde_json::from_str::<serde_json::Value>(&message.body)
                    .unwrap_or_else(|_| serde_json::json!({ "raw": message.body }));
                serde_json::json!({
                    "message_id": message.message_id,
                    "from_role": message.from_role,
                    "kind": message.kind,
                    "created_at": message.created_at,
                    "consumed_at": message.consumed_at,
                    "body": body,
                })
            })
            .collect())
    }

    fn task_path(&self, task_id: &str) -> PathBuf {
        self.root.join("tasks").join(format!("{task_id}.json"))
    }

    fn dispatch_path(&self) -> PathBuf {
        self.root.join("dispatch").join("requests.json")
    }

    fn mailbox_path(&self, role_id: &str) -> PathBuf {
        self.root.join("mailbox").join(format!("{role_id}.json"))
    }

    fn evidence_index_path(&self) -> PathBuf {
        self.root.join("evidence").join("index.json")
    }

    fn hook_warnings_path(&self) -> PathBuf {
        self.root.join("hooks").join("warnings.json")
    }

    fn events_path(&self) -> PathBuf {
        self.root.join("events.jsonl")
    }

    fn project_root(&self) -> PathBuf {
        self.root
            .parent()
            .and_then(Path::parent)
            .map(Path::to_path_buf)
            .unwrap_or_else(|| self.root.clone())
    }

    fn append_event(&self, event: PhaseEvent) -> Result<(), String> {
        self.init()?;
        validate_event_kind(&event.kind)?;
        let line = serde_json::to_string(&event).map_err(|err| format!("serialize json: {err}"))?;
        let path = self.events_path();
        let mut file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&path)
            .map_err(|err| format!("open {}: {err}", path.display()))?;
        writeln!(file, "{line}").map_err(|err| format!("write {}: {err}", path.display()))
    }

    fn read_events(&self) -> Result<Vec<PhaseEvent>, String> {
        let path = self.events_path();
        if !path.exists() {
            return Ok(Vec::new());
        }
        let file =
            fs::File::open(&path).map_err(|err| format!("open {}: {err}", path.display()))?;
        let reader = BufReader::new(file);
        let mut events = Vec::new();
        for (index, line) in reader.lines().enumerate() {
            let line = line.map_err(|err| format!("read {}: {err}", path.display()))?;
            if line.trim().is_empty() {
                continue;
            }
            let event: PhaseEvent = serde_json::from_str(&line)
                .map_err(|err| format!("malformed_event_log_line:{}:{}", index + 1, err))?;
            events.push(event);
        }
        Ok(events)
    }

    fn archive_candidates(&self, input: &ArchiveStateInput) -> Result<serde_json::Value, String> {
        let now = unix_seconds();
        let tasks: Vec<_> = self
            .list_tasks()?
            .into_iter()
            .filter(|task| task.status == TaskStatus::Completed)
            .filter(|task| {
                is_old_enough(task.completed_at.as_deref(), now, input.older_than_seconds)
            })
            .map(|task| {
                serde_json::json!({
                    "task_id": task.id,
                    "phase": task.phase,
                    "completed_at": task.completed_at,
                })
            })
            .collect();

        let mut mailbox_messages = Vec::new();
        let mailbox_dir = self.root.join("mailbox");
        if mailbox_dir.exists() {
            for entry in fs::read_dir(&mailbox_dir)
                .map_err(|err| format!("read {}: {err}", mailbox_dir.display()))?
            {
                let entry = entry.map_err(|err| format!("read mailbox entry: {err}"))?;
                if entry.path().extension().and_then(|value| value.to_str()) != Some("json") {
                    continue;
                }
                let role_id = entry
                    .path()
                    .file_stem()
                    .and_then(|value| value.to_str())
                    .unwrap_or("unknown")
                    .to_string();
                let messages: Vec<MailboxMessage> = read_json(&entry.path())?;
                for message in messages {
                    if message.consumed_at.is_some()
                        && is_old_enough(
                            message.consumed_at.as_deref(),
                            now,
                            input.older_than_seconds,
                        )
                    {
                        mailbox_messages.push(serde_json::json!({
                            "role_id": role_id,
                            "message_id": message.message_id,
                            "task_id": message.task_id,
                            "from_role": message.from_role,
                            "kind": message.kind,
                            "consumed_at": message.consumed_at,
                        }));
                    }
                }
            }
        }

        let dispatch_requests: Vec<_> = self
            .list_dispatch()?
            .into_iter()
            .filter(|request| matches!(request.status, DispatchStatus::Delivered))
            .filter(|request| {
                is_old_enough(Some(&request.updated_at), now, input.older_than_seconds)
            })
            .map(|request| {
                serde_json::json!({
                    "request_id": request.request_id,
                    "task_id": request.task_id,
                    "to_role": request.to_role,
                    "updated_at": request.updated_at,
                })
            })
            .collect();

        let hook_warnings: Vec<_> = if input.include_hook_warnings {
            self.read_hook_warnings()?
                .into_iter()
                .filter(|warning| {
                    is_old_enough(Some(&warning.created_at), now, input.older_than_seconds)
                })
                .map(|warning| {
                    serde_json::json!({
                        "warning_id": warning.warning_id,
                        "type": warning.warning_type,
                        "created_at": warning.created_at,
                    })
                })
                .collect()
        } else {
            Vec::new()
        };

        Ok(serde_json::json!({
            "tasks": tasks,
            "mailbox_messages": mailbox_messages,
            "dispatch_requests": dispatch_requests,
            "hook_warnings": hook_warnings,
            "evidence": [],
        }))
    }

    fn apply_archive_tasks(
        &self,
        archive_dir: &Path,
        candidates: &serde_json::Value,
    ) -> Result<usize, String> {
        let task_ids: Vec<String> = candidates["tasks"]
            .as_array()
            .into_iter()
            .flatten()
            .filter_map(|item| item["task_id"].as_str().map(str::to_string))
            .collect();
        let mut archived = Vec::new();
        for task_id in &task_ids {
            let path = self.task_path(task_id);
            if path.exists() {
                let task: Task = read_json(&path)?;
                archived.push(task);
                fs::remove_file(&path)
                    .map_err(|err| format!("remove {}: {err}", path.display()))?;
            }
        }
        write_json_atomic(&archive_dir.join("tasks.json"), &archived)?;
        Ok(archived.len())
    }

    fn apply_archive_mailbox(
        &self,
        archive_dir: &Path,
        candidates: &serde_json::Value,
    ) -> Result<usize, String> {
        let mut ids_by_role: std::collections::HashMap<String, HashSet<String>> =
            std::collections::HashMap::new();
        for item in candidates["mailbox_messages"]
            .as_array()
            .into_iter()
            .flatten()
        {
            let Some(role_id) = item["role_id"].as_str() else {
                continue;
            };
            let Some(message_id) = item["message_id"].as_str() else {
                continue;
            };
            ids_by_role
                .entry(role_id.to_string())
                .or_default()
                .insert(message_id.to_string());
        }

        let mut archived = Vec::new();
        for (role_id, ids) in ids_by_role {
            let path = self.mailbox_path(&role_id);
            if !path.exists() {
                continue;
            }
            let mut messages: Vec<MailboxMessage> = read_json(&path)?;
            let mut kept = Vec::new();
            for message in messages.drain(..) {
                if ids.contains(&message.message_id) {
                    archived.push(message);
                } else {
                    kept.push(message);
                }
            }
            write_json_atomic(&path, &kept)?;
        }
        write_json_atomic(&archive_dir.join("mailbox_messages.json"), &archived)?;
        Ok(archived.len())
    }

    fn apply_archive_dispatch(
        &self,
        archive_dir: &Path,
        candidates: &serde_json::Value,
    ) -> Result<usize, String> {
        let ids: HashSet<String> = candidates["dispatch_requests"]
            .as_array()
            .into_iter()
            .flatten()
            .filter_map(|item| item["request_id"].as_str().map(str::to_string))
            .collect();
        let mut archived = Vec::new();
        let mut kept = Vec::new();
        for request in self.list_dispatch()? {
            if ids.contains(&request.request_id) {
                archived.push(request);
            } else {
                kept.push(request);
            }
        }
        write_json_atomic(&self.dispatch_path(), &kept)?;
        write_json_atomic(&archive_dir.join("dispatch_requests.json"), &archived)?;
        Ok(archived.len())
    }

    fn apply_archive_hook_warnings(
        &self,
        archive_dir: &Path,
        candidates: &serde_json::Value,
    ) -> Result<usize, String> {
        let ids: HashSet<String> = candidates["hook_warnings"]
            .as_array()
            .into_iter()
            .flatten()
            .filter_map(|item| item["warning_id"].as_str().map(str::to_string))
            .collect();
        let mut archived = Vec::new();
        let mut kept = Vec::new();
        for warning in self.read_hook_warnings()? {
            if ids.contains(&warning.warning_id) {
                archived.push(warning);
            } else {
                kept.push(warning);
            }
        }
        write_json_atomic(&self.hook_warnings_path(), &kept)?;
        write_json_atomic(&archive_dir.join("hook_warnings.json"), &archived)?;
        Ok(archived.len())
    }

    fn read_mailbox_messages(&self, role_id: &str) -> Result<Vec<MailboxMessage>, String> {
        let path = self.mailbox_path(role_id);
        if !path.exists() {
            return Ok(Vec::new());
        }
        read_json(&path)
    }

    fn update_mailbox_message(
        &self,
        role_id: &str,
        message_id: &str,
        update: impl FnOnce(&mut MailboxMessage),
    ) -> Result<MailboxMessage, String> {
        validate_id("role_id", role_id)?;
        validate_id("message_id", message_id)?;
        let mut messages = self.read_mailbox_messages(role_id)?;
        let mut updated = None;
        for message in &mut messages {
            if message.message_id == message_id {
                update(message);
                updated = Some(message.clone());
                break;
            }
        }
        let updated = updated.ok_or_else(|| "mailbox_message_not_found".to_string())?;
        write_json_atomic(&self.mailbox_path(role_id), &messages)?;
        Ok(updated)
    }

    fn write_task(&self, task: &Task) -> Result<(), String> {
        write_json_atomic(&self.task_path(&task.id), task)
    }

    fn advance_task_after_orchestrator_consume(
        &self,
        role_id: &str,
        message: &MailboxMessage,
    ) -> Result<(), String> {
        if role_id != "orchestrator" {
            return Ok(());
        }
        let Some(task_id) = message.task_id.as_deref() else {
            return Ok(());
        };
        let path = self.task_path(task_id);
        if !path.exists() {
            return Ok(());
        }
        let mut task = self.read_task(task_id)?;
        let from_phase = task.phase.clone();
        let from_status = task.status.clone();
        let from_role = task.role.clone();
        let mut changed = false;
        match (message.from_role.as_str(), message.kind.as_str()) {
            ("implementer", "result") => {
                if task.phase == "implementation" && task.status == TaskStatus::Completed {
                    task.status = TaskStatus::Pending;
                    task.phase = "code_review".into();
                    task.role = Some("code-reviewer".into());
                    task.owner = None;
                    task.claim = None;
                    task.completed_at = None;
                    changed = true;
                }
            }
            ("code-reviewer", "review_approved") => {
                if task.phase == "code_review" {
                    if mailbox_body_bool(&message.body, "compliance_review_required") {
                        task.status = TaskStatus::Pending;
                        task.phase = "compliance_review".into();
                        task.role = Some("compliance-reviewer".into());
                        task.owner = None;
                        task.claim = None;
                        task.completed_at = None;
                    } else if mailbox_body_bool(&message.body, "tester_required") {
                        task.status = TaskStatus::Pending;
                        task.phase = "testing".into();
                        task.role = Some("tester".into());
                        task.owner = None;
                        task.claim = None;
                        task.completed_at = None;
                    } else {
                        task.status = TaskStatus::Completed;
                        task.phase = "done".into();
                        task.role = None;
                        task.owner = None;
                        task.claim = None;
                        if task.completed_at.is_none() {
                            task.completed_at = Some(now_string());
                        }
                    }
                    changed = true;
                }
            }
            ("compliance-reviewer", "review_approved") => {
                if task.phase == "compliance_review" {
                    if mailbox_body_bool(&message.body, "tester_required") {
                        task.status = TaskStatus::Pending;
                        task.phase = "testing".into();
                        task.role = Some("tester".into());
                        task.owner = None;
                        task.claim = None;
                        task.completed_at = None;
                    } else {
                        task.status = TaskStatus::Completed;
                        task.phase = "done".into();
                        task.role = None;
                        task.owner = None;
                        task.claim = None;
                        if task.completed_at.is_none() {
                            task.completed_at = Some(now_string());
                        }
                    }
                    changed = true;
                }
            }
            ("tester", "result") => {
                if task.phase == "testing" {
                    task.status = TaskStatus::Completed;
                    task.phase = "done".into();
                    task.role = None;
                    task.owner = None;
                    task.claim = None;
                    if task.completed_at.is_none() {
                        task.completed_at = Some(now_string());
                    }
                    changed = true;
                }
            }
            (_, "blocked") => {
                task.status = TaskStatus::Blocked;
                task.error = Some(format!(
                    "{} reported blocked during {}",
                    message.from_role, task.phase
                ));
                task.owner = None;
                task.claim = None;
                changed = true;
            }
            _ => {}
        }
        if changed {
            task.version += 1;
            self.write_task(&task)?;
            self.append_event(PhaseEvent {
                event_id: make_token("event", "phase_advanced"),
                kind: "phase_advanced".into(),
                task_id: Some(task.id.clone()),
                role_id: task.role.clone().or(from_role),
                from_phase: Some(from_phase),
                to_phase: Some(task.phase.clone()),
                from_status: Some(from_status),
                to_status: Some(task.status.clone()),
                message_id: Some(message.message_id.clone()),
                dispatch_request_id: None,
                created_at: now_string(),
                detail: serde_json::json!({
                    "from_role": message.from_role.clone(),
                    "message_kind": message.kind.clone(),
                }),
            })?;
        }
        Ok(())
    }

    fn replace_dispatch(&self, updated: DispatchRequest) -> Result<DispatchRequest, String> {
        let mut requests = self.list_dispatch()?;
        let mut found = false;
        for request in &mut requests {
            if request.request_id == updated.request_id {
                *request = updated.clone();
                found = true;
                break;
            }
        }
        if !found {
            return Err("dispatch_not_found".into());
        }
        write_json_atomic(&self.dispatch_path(), &requests)?;
        Ok(updated)
    }

    fn read_hook_warnings(&self) -> Result<Vec<HookWarning>, String> {
        let path = self.hook_warnings_path();
        if !path.exists() {
            return Ok(Vec::new());
        }
        read_json(&path)
    }

    fn append_hook_warning(
        &self,
        hook: &str,
        warning_type: &str,
        task_id: Option<&str>,
        role_id: Option<&str>,
        message_id: Option<&str>,
        detail: &str,
    ) -> Result<(), String> {
        let mut warnings = self.read_hook_warnings()?;
        warnings.push(HookWarning {
            warning_id: make_token("hook-warning", warning_type),
            hook: hook.into(),
            warning_type: warning_type.into(),
            severity: "warning".into(),
            task_id: task_id.map(str::to_string),
            role_id: role_id.map(str::to_string),
            message_id: message_id.map(str::to_string),
            detail: detail.into(),
            created_at: now_string(),
        });
        write_json_atomic(&self.hook_warnings_path(), &warnings)
    }

    fn audit_mailbox(&self) -> Result<Vec<serde_json::Value>, String> {
        let mailbox_dir = self.root.join("mailbox");
        if !mailbox_dir.exists() {
            return Ok(Vec::new());
        }
        let mut issues = Vec::new();
        for entry in fs::read_dir(&mailbox_dir)
            .map_err(|err| format!("read {}: {err}", mailbox_dir.display()))?
        {
            let entry = entry.map_err(|err| format!("read mailbox entry: {err}"))?;
            if entry.path().extension().and_then(|value| value.to_str()) != Some("json") {
                continue;
            }
            let role_id = entry
                .path()
                .file_stem()
                .and_then(|value| value.to_str())
                .unwrap_or("unknown")
                .to_string();
            let messages: Vec<MailboxMessage> = read_json(&entry.path())?;
            for message in messages {
                let valid_kind = validate_mailbox_kind(&message.kind).is_ok();
                if !valid_kind {
                    issues.push(serde_json::json!({
                        "type": "invalid_mailbox_kind",
                        "role_id": role_id,
                        "message_id": message.message_id,
                        "kind": message.kind,
                    }));
                }
                let schema_kind = if valid_kind {
                    message.kind.as_str()
                } else {
                    "blocked"
                };
                if validate_mailbox_body_schema(schema_kind, &message.body).is_err() {
                    issues.push(serde_json::json!({
                        "type": "invalid_mailbox_body_schema",
                        "role_id": role_id,
                        "message_id": message.message_id,
                        "kind": schema_kind,
                    }));
                }
            }
        }
        Ok(issues)
    }

    fn audit_dispatch(&self) -> Result<Vec<serde_json::Value>, String> {
        let mut issues = Vec::new();
        for request in self.list_dispatch()? {
            if !request.trigger_message.starts_with("# moondex:")
                || !request.trigger_message.ends_with('\n')
            {
                issues.push(serde_json::json!({
                    "type": "unsafe_dispatch_trigger",
                    "request_id": request.request_id,
                    "task_id": request.task_id,
                    "to_role": request.to_role,
                }));
            }
            if matches!(request.status, DispatchStatus::Notified)
                && request.surface_ref.as_deref() == Some("surface:999999")
            {
                issues.push(serde_json::json!({
                    "type": "invalid_surface_notified",
                    "request_id": request.request_id,
                    "task_id": request.task_id,
                    "to_role": request.to_role,
                    "surface_ref": request.surface_ref,
                }));
            }
        }
        Ok(issues)
    }

    fn audit_events(&self) -> Result<Vec<serde_json::Value>, String> {
        let path = self.events_path();
        if !path.exists() {
            return Ok(Vec::new());
        }
        let file =
            fs::File::open(&path).map_err(|err| format!("open {}: {err}", path.display()))?;
        let reader = BufReader::new(file);
        let mut issues = Vec::new();
        for (index, line) in reader.lines().enumerate() {
            let line = line.map_err(|err| format!("read {}: {err}", path.display()))?;
            if line.trim().is_empty() {
                continue;
            }
            match serde_json::from_str::<PhaseEvent>(&line) {
                Ok(event) => {
                    if let Err(error) = validate_event_kind(&event.kind) {
                        issues.push(serde_json::json!({
                            "type": "invalid_event_kind",
                            "line": index + 1,
                            "event_id": event.event_id,
                            "kind": event.kind,
                            "error": error,
                        }));
                    }
                }
                Err(error) => issues.push(serde_json::json!({
                    "type": "malformed_event_log_line",
                    "line": index + 1,
                    "error": error.to_string(),
                })),
            }
        }
        Ok(issues)
    }

    fn repair_mailbox(&self) -> Result<usize, String> {
        let mailbox_dir = self.root.join("mailbox");
        if !mailbox_dir.exists() {
            return Ok(0);
        }
        let mut repaired = 0;
        for entry in fs::read_dir(&mailbox_dir)
            .map_err(|err| format!("read {}: {err}", mailbox_dir.display()))?
        {
            let entry = entry.map_err(|err| format!("read mailbox entry: {err}"))?;
            if entry.path().extension().and_then(|value| value.to_str()) != Some("json") {
                continue;
            }
            let mut messages: Vec<MailboxMessage> = read_json(&entry.path())?;
            for message in &mut messages {
                if validate_mailbox_kind(&message.kind).is_err() {
                    message.kind = "blocked".into();
                    repaired += 1;
                }
                if validate_mailbox_body_schema(&message.kind, &message.body).is_err() {
                    message.body = repair_mailbox_body_schema(&message.kind, &message.body)?;
                    repaired += 1;
                }
            }
            write_json_atomic(&entry.path(), &messages)?;
        }
        Ok(repaired)
    }

    fn repair_dispatch(&self) -> Result<usize, String> {
        let mut repaired = 0;
        let mut requests = self.list_dispatch()?;
        for request in &mut requests {
            if !request.trigger_message.starts_with("# moondex:")
                || !request.trigger_message.ends_with('\n')
            {
                request.trigger_message =
                    format!("# moondex: read your inbox for task {}\n", request.task_id);
                request.updated_at = now_string();
                request.last_reason = Some("repaired_unsafe_trigger".into());
                repaired += 1;
            }
            if matches!(request.status, DispatchStatus::Notified)
                && request.surface_ref.as_deref() == Some("surface:999999")
            {
                request.status = DispatchStatus::Failed;
                request.updated_at = now_string();
                request.last_reason = Some("repaired_invalid_surface_notified".into());
                repaired += 1;
            }
        }
        write_json_atomic(&self.dispatch_path(), &requests)?;
        Ok(repaired)
    }
}

fn read_json<T: DeserializeOwned>(path: &Path) -> Result<T, String> {
    let text = fs::read_to_string(path).map_err(|err| format!("read {}: {err}", path.display()))?;
    serde_json::from_str(&text).map_err(|err| format!("parse {}: {err}", path.display()))
}

fn write_json_atomic<T: Serialize>(path: &Path, value: &T) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|err| format!("create {}: {err}", parent.display()))?;
    }
    let filename = path
        .file_name()
        .and_then(|value| value.to_str())
        .ok_or_else(|| format!("invalid path: {}", path.display()))?;
    let tmp = path.with_file_name(format!(
        ".{filename}.{}.{}.tmp",
        std::process::id(),
        unix_millis()
    ));
    let body =
        serde_json::to_string_pretty(value).map_err(|err| format!("serialize json: {err}"))?;
    fs::write(&tmp, format!("{body}\n"))
        .map_err(|err| format!("write {}: {err}", tmp.display()))?;
    fs::rename(&tmp, path)
        .map_err(|err| format!("rename {} -> {}: {err}", tmp.display(), path.display()))
}

fn validate_id(name: &str, value: &str) -> Result<(), String> {
    let valid = !value.is_empty()
        && value.len() <= 80
        && value
            .chars()
            .all(|ch| ch.is_ascii_alphanumeric() || matches!(ch, '-' | '_' | '.'));
    if valid {
        Ok(())
    } else {
        Err(format!("invalid_{name}: {value}"))
    }
}

fn role_to_phase(role: Option<&str>) -> String {
    match role {
        Some("code-reviewer") => "code_review",
        Some("compliance-reviewer") => "compliance_review",
        Some("tester") => "testing",
        _ => "implementation",
    }
    .into()
}

fn expected_output_contract(role: &str) -> serde_json::Value {
    match role {
        "code-reviewer" | "compliance-reviewer" => serde_json::json!({
            "allowed_kinds": ["review_approved", "review_changes_requested", "blocked", "question", "status"],
            "review_approved_body": {
                "summary": "non-empty string",
                "checks": ["non-empty check summary"],
                "optional_decisions": {
                    "compliance_review_required": "boolean",
                    "tester_required": "boolean",
                    "changed_files": ["path or note"]
                }
            },
            "review_changes_requested_body": {
                "summary": "non-empty string",
                "changes": ["requested change"],
                "severity": "low | medium | high | blocking"
            }
        }),
        "tester" => serde_json::json!({
            "allowed_kinds": ["result", "blocked", "question", "status"],
            "result_body": {
                "summary": "non-empty string",
                "changed_files": ["path or note"],
                "tests": ["test command/result"],
                "not_run_reason": "required only when tests is empty or omitted"
            }
        }),
        _ => serde_json::json!({
            "allowed_kinds": ["result", "blocked", "question", "status"],
            "result_body": {
                "summary": "non-empty string",
                "changed_files": ["path or note"],
                "tests": ["test command/result"],
                "not_run_reason": "required only when tests is empty or omitted"
            }
        }),
    }
}

fn expected_output_summary(role: &str) -> &'static str {
    match role {
        "code-reviewer" | "compliance-reviewer" => {
            "Write `review_approved` or `review_changes_requested` to the orchestrator mailbox. Body must be a JSON object encoded as a string."
        }
        "tester" => {
            "Write `result` with concrete test evidence, or `blocked`/`question` if testing cannot proceed. Body must be a JSON object encoded as a string."
        }
        _ => {
            "Write `result` with changed files and test evidence, or `blocked`/`question` if implementation cannot proceed. Body must be a JSON object encoded as a string."
        }
    }
}

fn is_old_enough(timestamp: Option<&str>, now: u64, older_than_seconds: u64) -> bool {
    timestamp
        .and_then(|value| value.parse::<u64>().ok())
        .map(|timestamp| now.saturating_sub(timestamp) >= older_than_seconds)
        .unwrap_or(false)
}

fn validate_mailbox_kind(value: &str) -> Result<(), String> {
    if matches!(
        value,
        "result"
            | "blocked"
            | "question"
            | "review_approved"
            | "review_changes_requested"
            | "status"
    ) {
        Ok(())
    } else {
        Err(format!("invalid_mailbox_kind: {value}"))
    }
}

fn validate_event_kind(value: &str) -> Result<(), String> {
    if matches!(
        value,
        "task_created"
            | "task_claimed"
            | "task_released"
            | "task_transitioned"
            | "phase_advanced"
            | "mailbox_consumed"
            | "dispatch_created"
            | "dispatch_marked"
            | "archive_created"
    ) {
        Ok(())
    } else {
        Err(format!("invalid_event_kind: {value}"))
    }
}

fn validate_mailbox_body_schema(kind: &str, body: &str) -> Result<(), String> {
    if body.trim().is_empty() {
        return Err("invalid_mailbox_body: body must not be empty".into());
    }
    let value: serde_json::Value = serde_json::from_str(body)
        .map_err(|err| format!("invalid_mailbox_body_schema: body must be a JSON object: {err}"))?;
    let object = value
        .as_object()
        .ok_or_else(|| "invalid_mailbox_body_schema: body must be a JSON object".to_string())?;

    match kind {
        "result" => {
            require_non_empty_string(object, "summary")?;
            require_string_array(object, "changed_files", false)?;
            let tests_valid = object
                .get("tests")
                .map(|_| require_string_array(object, "tests", false))
                .transpose()?
                .unwrap_or(false);
            if !tests_valid {
                require_non_empty_string(object, "not_run_reason")?;
            }
        }
        "blocked" => {
            require_non_empty_string(object, "reason")?;
            require_non_empty_string(object, "needs")?;
        }
        "question" => {
            require_non_empty_string(object, "question")?;
            require_non_empty_string(object, "decision_needed")?;
        }
        "review_approved" => {
            require_non_empty_string(object, "summary")?;
            require_string_array(object, "checks", true)?;
        }
        "review_changes_requested" => {
            require_non_empty_string(object, "summary")?;
            require_string_array(object, "changes", true)?;
            let severity = require_non_empty_string(object, "severity")?;
            if !matches!(severity, "low" | "medium" | "high" | "blocking") {
                return Err(
                    "invalid_mailbox_body_schema: severity must be low, medium, high, or blocking"
                        .into(),
                );
            }
        }
        "status" => {
            require_non_empty_string(object, "state")?;
            require_non_empty_string(object, "summary")?;
        }
        _ => return Err(format!("invalid_mailbox_kind: {kind}")),
    }

    Ok(())
}

fn require_non_empty_string<'a>(
    object: &'a serde_json::Map<String, serde_json::Value>,
    field: &str,
) -> Result<&'a str, String> {
    object
        .get(field)
        .and_then(|value| value.as_str())
        .filter(|value| !value.trim().is_empty())
        .ok_or_else(|| format!("invalid_mailbox_body_schema: {field} must be a non-empty string"))
}

fn require_string_array(
    object: &serde_json::Map<String, serde_json::Value>,
    field: &str,
    require_non_empty: bool,
) -> Result<bool, String> {
    let array = object
        .get(field)
        .and_then(|value| value.as_array())
        .ok_or_else(|| format!("invalid_mailbox_body_schema: {field} must be an array"))?;
    if require_non_empty && array.is_empty() {
        return Err(format!(
            "invalid_mailbox_body_schema: {field} must not be empty"
        ));
    }
    if array
        .iter()
        .any(|value| !value.as_str().is_some_and(|text| !text.trim().is_empty()))
    {
        return Err(format!(
            "invalid_mailbox_body_schema: {field} must contain only non-empty strings"
        ));
    }
    Ok(!array.is_empty())
}

fn repair_mailbox_body_schema(kind: &str, body: &str) -> Result<String, String> {
    let text = if body.trim().is_empty() {
        "[repaired] empty mailbox body"
    } else {
        body.trim()
    };
    let repaired = match kind {
        "result" => serde_json::json!({
            "summary": text,
            "changed_files": [],
            "not_run_reason": "legacy plaintext message",
        }),
        "blocked" => serde_json::json!({
            "reason": text,
            "needs": "legacy follow-up required",
        }),
        "question" => serde_json::json!({
            "question": text,
            "decision_needed": "legacy triage required",
        }),
        "review_approved" => serde_json::json!({
            "summary": text,
            "checks": ["legacy plaintext approval"],
        }),
        "review_changes_requested" => serde_json::json!({
            "summary": text,
            "changes": ["legacy plaintext change request"],
            "severity": "medium",
        }),
        "status" => serde_json::json!({
            "state": "legacy",
            "summary": text,
        }),
        _ => return Err(format!("invalid_mailbox_kind: {kind}")),
    };
    serde_json::to_string(&repaired).map_err(|err| format!("serialize json: {err}"))
}

fn validate_role_transfer_payload(input: &serde_json::Value) -> serde_json::Value {
    let mut errors = Vec::new();
    let mut warnings = Vec::new();
    let contract = if input.get("contract_type").is_some() {
        validate_planning_contract(input, &mut errors, &mut warnings)
    } else if input.get("kind").is_some()
        || input.get("from_role").is_some()
        || input.get("body").is_some()
    {
        validate_role_transfer_mailbox(input, &mut errors, &mut warnings);
        "mailbox_output".into()
    } else {
        validate_role_transfer_handoff(input, &mut errors, &mut warnings);
        "handoff_payload".into()
    };

    serde_json::json!({
        "contract": contract,
        "valid": errors.is_empty(),
        "errors": errors,
        "warnings": warnings,
    })
}

fn validate_planning_contract(
    input: &serde_json::Value,
    errors: &mut Vec<serde_json::Value>,
    warnings: &mut Vec<serde_json::Value>,
) -> String {
    let Some(object) = input.as_object() else {
        push_issue(errors, "invalid_payload", "payload must be a JSON object");
        return "unknown".into();
    };
    let Some(contract_type) = required_string(object, "contract_type", errors) else {
        return "unknown".into();
    };

    match contract_type {
        "task_planner_input" => validate_task_planner_input(object, errors, warnings),
        "task_planner_output" => validate_task_planner_output(object, errors, warnings),
        "wave_dispatcher_input" => validate_wave_dispatcher_input(object, errors, warnings),
        "wave_dispatcher_output" => validate_wave_dispatcher_output(object, errors, warnings),
        "tester_input" => validate_tester_input(object, errors, warnings),
        other => push_issue(
            errors,
            "unknown_contract_type",
            &format!("unknown planning contract_type {other}"),
        ),
    }
    contract_type.into()
}

fn validate_task_planner_input(
    object: &serde_json::Map<String, serde_json::Value>,
    errors: &mut Vec<serde_json::Value>,
    _warnings: &mut Vec<serde_json::Value>,
) {
    for field in ["task_id", "source_role", "target_role", "output_contract"] {
        required_string(object, field, errors);
    }
    require_exact_string(object, "source_role", "orchestrator", errors);
    require_exact_string(object, "target_role", "task-planner", errors);
    required_object(object, "task", errors);
    for field in [
        "source_document_paths",
        "scope_paths",
        "planning_requirements",
    ] {
        required_non_empty_string_array(object, field, errors);
    }
}

fn validate_task_planner_output(
    object: &serde_json::Map<String, serde_json::Value>,
    errors: &mut Vec<serde_json::Value>,
    warnings: &mut Vec<serde_json::Value>,
) {
    for field in ["task_id", "plan_id", "source_role", "target_role", "status"] {
        required_string(object, field, errors);
    }
    require_exact_string(object, "source_role", "task-planner", errors);
    require_exact_string(object, "target_role", "orchestrator", errors);
    for field in ["ownership", "acceptance_criteria", "verification_commands"] {
        required_non_empty_string_array(object, field, errors);
    }
    match object.get("status").and_then(|value| value.as_str()) {
        Some("DONE") => {
            let has_plan_path = object
                .get("plan_path")
                .and_then(|value| value.as_str())
                .is_some_and(|value| !value.trim().is_empty());
            let has_plan = object.get("plan").is_some_and(|value| !value.is_null());
            if !has_plan_path && !has_plan {
                push_issue(
                    errors,
                    "missing_required_field",
                    "DONE task_planner_output requires plan_path or plan",
                );
            }
        }
        Some("BLOCKED") => {
            required_string(object, "blocked_reason", errors);
        }
        Some("NEEDS_CONTEXT") => {
            required_string(object, "needs", errors);
        }
        Some(_) => push_issue(
            errors,
            "invalid_status",
            "status must be DONE, NEEDS_CONTEXT, or BLOCKED",
        ),
        None => {}
    }
    add_verification_warnings(object, warnings);
}

fn validate_wave_dispatcher_input(
    object: &serde_json::Map<String, serde_json::Value>,
    errors: &mut Vec<serde_json::Value>,
    warnings: &mut Vec<serde_json::Value>,
) {
    for field in ["source_role", "target_role", "output_contract"] {
        required_string(object, field, errors);
    }
    require_exact_string(object, "source_role", "orchestrator", errors);
    require_exact_string(object, "target_role", "wave-dispatcher", errors);
    required_non_empty_string_array(object, "candidate_tasks", errors);
    required_non_empty_array(object, "plans", errors);
    for field in [
        "dependency_notes",
        "ownership_conflicts",
        "shared_contract_candidates",
    ] {
        required_array(object, field, errors);
    }
    if object
        .get("candidate_tasks")
        .and_then(|value| value.as_array())
        .is_some_and(|tasks| tasks.len() > 1)
        && object
            .get("parallel_safety_note")
            .and_then(|value| value.as_str())
            .is_none_or(|value| value.trim().is_empty())
    {
        push_issue(
            warnings,
            "missing_parallel_safety_note",
            "multiple candidate tasks should include parallel_safety_note",
        );
    }
}

fn validate_wave_dispatcher_output(
    object: &serde_json::Map<String, serde_json::Value>,
    errors: &mut Vec<serde_json::Value>,
    warnings: &mut Vec<serde_json::Value>,
) {
    for field in ["wave_id", "source_role", "target_role", "status"] {
        required_string(object, field, errors);
    }
    require_exact_string(object, "source_role", "wave-dispatcher", errors);
    require_exact_string(object, "target_role", "orchestrator", errors);
    for field in ["wave_groups", "dependency_graph", "verification_plan"] {
        required_non_empty_array(object, field, errors);
    }
    match object.get("status").and_then(|value| value.as_str()) {
        Some("APPROVED") => {
            required_non_empty_string_array(object, "validated_ready_tasks", errors);
        }
        Some("REVISION_REQUIRED") => {
            required_non_empty_array(object, "revision_requests", errors);
        }
        Some("BLOCKED") => {
            required_string(object, "blocked_reason", errors);
        }
        Some(_) => push_issue(
            errors,
            "invalid_status",
            "status must be APPROVED, REVISION_REQUIRED, or BLOCKED",
        ),
        None => {}
    }
    add_verification_plan_warnings(object, "verification_plan", warnings);
}

fn validate_tester_input(
    object: &serde_json::Map<String, serde_json::Value>,
    errors: &mut Vec<serde_json::Value>,
    warnings: &mut Vec<serde_json::Value>,
) {
    for field in [
        "task_id",
        "plan_id",
        "source_role",
        "target_role",
        "test_scope",
    ] {
        required_string(object, field, errors);
    }
    require_exact_string(object, "target_role", "tester", errors);
    for field in [
        "changed_files",
        "verification_commands",
        "acceptance_criteria",
        "environment_notes",
    ] {
        required_non_empty_string_array(object, field, errors);
    }
    add_verification_warnings(object, warnings);
}

fn validate_readiness_payload(input: &serde_json::Value) -> serde_json::Value {
    let mut blocked = Vec::new();
    let mut revision = Vec::new();
    let mut warnings = Vec::new();
    let mut missing_fields = Vec::new();

    let Some(object) = input.as_object() else {
        push_issue(
            &mut blocked,
            "invalid_payload",
            "payload must be a JSON object",
        );
        return readiness_result(blocked, revision, warnings, missing_fields);
    };

    let task = object.get("task").and_then(|value| value.as_object());
    let plan = object.get("plan").and_then(|value| value.as_object());
    let wave = object.get("wave").and_then(|value| value.as_object());

    if let Some(task) = task {
        require_readiness_string(
            task,
            "task.subject",
            "subject",
            &mut revision,
            &mut missing_fields,
        );
        require_readiness_string(
            task,
            "task.description",
            "description",
            &mut revision,
            &mut missing_fields,
        );
        if has_non_empty_string(task, "blocked_reason") {
            push_issue(
                &mut blocked,
                "blocked_reason",
                "task contains blocked_reason",
            );
        }
        if has_unresolved_dependency(task) {
            push_issue(
                &mut blocked,
                "unresolved_dependency",
                "task has an explicit unresolved dependency",
            );
        }
        if requires_decision(task) {
            push_issue(
                &mut blocked,
                "missing_upstream_decision",
                "task requires an upstream decision",
            );
        }
    } else {
        missing_fields.push("task".to_string());
        push_issue(&mut revision, "missing_required_field", "task is required");
    }

    if let Some(plan) = plan {
        require_readiness_string(
            plan,
            "plan.objective",
            "objective",
            &mut revision,
            &mut missing_fields,
        );
        for (label, field) in [
            ("plan.ownership", "ownership"),
            ("plan.scope_paths", "scope_paths"),
            ("plan.acceptance_criteria", "acceptance_criteria"),
            ("plan.verification_commands", "verification_commands"),
        ] {
            require_readiness_array(plan, label, field, &mut revision, &mut missing_fields);
        }
        if has_non_empty_string(plan, "blocked_reason") {
            push_issue(
                &mut blocked,
                "blocked_reason",
                "plan contains blocked_reason",
            );
        }
        if has_unresolved_dependency(plan) {
            push_issue(
                &mut blocked,
                "unresolved_dependency",
                "plan has an explicit unresolved dependency",
            );
        }
        if requires_decision(plan) {
            push_issue(
                &mut blocked,
                "missing_upstream_decision",
                "plan requires an upstream decision",
            );
        }
        add_readiness_plan_warnings(plan, &mut warnings);
    } else {
        missing_fields.push("plan".to_string());
        push_issue(&mut revision, "missing_required_field", "plan is required");
    }

    if let Some(wave) = wave {
        require_readiness_array(
            wave,
            "wave.dependency_graph",
            "dependency_graph",
            &mut revision,
            &mut missing_fields,
        );
        require_readiness_array(
            wave,
            "wave.verification_plan",
            "verification_plan",
            &mut revision,
            &mut missing_fields,
        );
        add_verification_plan_warnings_for_value(wave.get("verification_plan"), &mut warnings);
        if wave
            .get("validated_ready_tasks")
            .and_then(|value| value.as_array())
            .is_some_and(|tasks| tasks.len() > 1)
            && wave
                .get("parallel_safety_note")
                .and_then(|value| value.as_str())
                .is_none_or(|value| value.trim().is_empty())
        {
            push_issue(
                &mut warnings,
                "missing_parallel_safety_note",
                "wave has multiple tasks but no parallel-safety note",
            );
        }
        validate_wave_dependencies(task, plan, wave, &mut blocked);
    }

    readiness_result(blocked, revision, warnings, missing_fields)
}

fn readiness_result(
    blocked: Vec<serde_json::Value>,
    revision: Vec<serde_json::Value>,
    warnings: Vec<serde_json::Value>,
    missing_fields: Vec<String>,
) -> serde_json::Value {
    let decision = if !blocked.is_empty() {
        "BLOCKED"
    } else if !revision.is_empty() {
        "REVISION_REQUIRED"
    } else {
        "READY"
    };
    let mut errors = blocked;
    errors.extend(revision);
    serde_json::json!({
        "decision": decision,
        "errors": errors,
        "warnings": warnings,
        "missing_fields": missing_fields,
    })
}

fn validate_role_transfer_mailbox(
    input: &serde_json::Value,
    errors: &mut Vec<serde_json::Value>,
    warnings: &mut Vec<serde_json::Value>,
) {
    let Some(object) = input.as_object() else {
        push_issue(errors, "invalid_payload", "payload must be a JSON object");
        return;
    };

    let from_role = required_string(object, "from_role", errors);
    let kind = required_string(object, "kind", errors);
    let body = required_string(object, "body", errors);
    let task_id = object.get("task_id").and_then(|value| value.as_str());

    if let Some(role) = from_role {
        if is_canonical_role(role) && task_id.filter(|value| !value.trim().is_empty()).is_none() {
            push_issue(
                errors,
                "invalid_role_output_contract",
                "canonical role output requires task_id",
            );
        }
    }

    if let (Some(role), Some(kind)) = (from_role, kind) {
        if !role_allows_mailbox_kind(role, kind) {
            push_issue(
                errors,
                "invalid_role_output_contract",
                &format!("{role} cannot emit mailbox kind {kind}"),
            );
        }
        if let Some(body) = body {
            if let Err(error) = validate_mailbox_kind(kind) {
                push_issue(errors, "invalid_mailbox_kind", &error);
            } else if let Err(error) = validate_mailbox_body_schema(kind, body) {
                push_issue(errors, "invalid_mailbox_body_schema", &error);
            } else {
                add_mailbox_contract_warnings(role, kind, body, warnings);
            }
        }
    }
}

fn validate_role_transfer_handoff(
    input: &serde_json::Value,
    errors: &mut Vec<serde_json::Value>,
    warnings: &mut Vec<serde_json::Value>,
) {
    let Some(object) = input.as_object() else {
        push_issue(errors, "invalid_payload", "payload must be a JSON object");
        return;
    };

    for field in [
        "task_id",
        "plan_id",
        "source_role",
        "target_role",
        "current_status",
        "target_status",
        "handoff_summary",
    ] {
        required_string(object, field, errors);
    }
    for field in [
        "scope_paths",
        "verification_commands",
        "acceptance_criteria",
    ] {
        required_non_empty_string_array(object, field, errors);
    }

    if let Some(commands) = object
        .get("verification_commands")
        .and_then(|value| value.as_array())
    {
        if commands.len() == 1
            && commands
                .first()
                .and_then(|value| value.as_str())
                .is_some_and(|command| command.trim().len() < 8)
        {
            push_issue(
                warnings,
                "weak_verification_commands",
                "verification_commands look too weak for an execution handoff",
            );
        }
    }
}

fn add_mailbox_contract_warnings(
    role: &str,
    kind: &str,
    body: &str,
    warnings: &mut Vec<serde_json::Value>,
) {
    let Ok(value) = serde_json::from_str::<serde_json::Value>(body) else {
        return;
    };
    let Some(object) = value.as_object() else {
        return;
    };
    if kind == "result" {
        let changed_files_empty = object
            .get("changed_files")
            .and_then(|value| value.as_array())
            .map(|array| array.is_empty())
            .unwrap_or(true);
        let tests_empty = object
            .get("tests")
            .and_then(|value| value.as_array())
            .map(|array| array.is_empty())
            .unwrap_or(true);
        let not_run_reason = object
            .get("not_run_reason")
            .and_then(|value| value.as_str())
            .unwrap_or("");
        if changed_files_empty
            && tests_empty
            && !not_run_reason.to_ascii_lowercase().contains("docs")
        {
            push_issue(
                warnings,
                "weak_result_evidence",
                "result has no changed_files or tests and not_run_reason is not clearly docs-only",
            );
        }
    }
    if kind == "review_changes_requested" {
        let severity = object
            .get("severity")
            .and_then(|value| value.as_str())
            .unwrap_or("");
        let short_change = object
            .get("changes")
            .and_then(|value| value.as_array())
            .is_some_and(|changes| {
                changes.len() == 1
                    && changes
                        .first()
                        .and_then(|value| value.as_str())
                        .is_some_and(|change| change.trim().len() < 24)
            });
        if severity == "blocking" && short_change {
            push_issue(
                warnings,
                "underspecified_blocking_change",
                "blocking review change request should include enough detail to act on",
            );
        }
    }
    if role == "code-reviewer" && kind == "review_approved" {
        if object.get("compliance_review_required").is_none() {
            push_issue(
                warnings,
                "missing_compliance_review_decision",
                "code-reviewer approval should include compliance_review_required",
            );
        }
        let skipped = object
            .get("compliance_review_required")
            .and_then(|value| value.as_bool())
            == Some(false);
        let risky_path = object
            .get("changed_files")
            .and_then(|value| value.as_array())
            .is_some_and(|files| files.iter().any(is_compliance_sensitive_path_value));
        if skipped && risky_path {
            push_issue(
                warnings,
                "possibly_required_compliance_review",
                "compliance was skipped while changed_files include contract, CLI, schema, state, docs, or migration-sensitive paths",
            );
        }
    }
}

fn mailbox_body_bool(body: &str, field: &str) -> bool {
    serde_json::from_str::<serde_json::Value>(body)
        .ok()
        .and_then(|value| {
            value
                .get(field)
                .and_then(|value| value.as_bool())
                .map(bool::from)
        })
        .unwrap_or(false)
}

fn is_compliance_sensitive_path_value(value: &serde_json::Value) -> bool {
    let Some(path) = value.as_str() else {
        return false;
    };
    path.contains("docs/contracts")
        || path.contains("docs/execution")
        || path.contains("src/model")
        || path.contains("src/cli")
        || path.contains("fs_state")
        || path.contains("schema")
        || path.contains("migration")
        || path.contains("state")
}

fn require_exact_string(
    object: &serde_json::Map<String, serde_json::Value>,
    field: &str,
    expected: &str,
    errors: &mut Vec<serde_json::Value>,
) {
    if object
        .get(field)
        .and_then(|value| value.as_str())
        .is_some_and(|value| value == expected)
    {
        return;
    }
    push_issue(
        errors,
        "invalid_required_field",
        &format!("{field} must be {expected}"),
    );
}

fn required_object(
    object: &serde_json::Map<String, serde_json::Value>,
    field: &str,
    errors: &mut Vec<serde_json::Value>,
) {
    if object
        .get(field)
        .and_then(|value| value.as_object())
        .is_none()
    {
        push_issue(
            errors,
            "missing_required_field",
            &format!("{field} must be a JSON object"),
        );
    }
}

fn required_array(
    object: &serde_json::Map<String, serde_json::Value>,
    field: &str,
    errors: &mut Vec<serde_json::Value>,
) {
    if object
        .get(field)
        .and_then(|value| value.as_array())
        .is_none()
    {
        push_issue(
            errors,
            "missing_required_field",
            &format!("{field} must be an array"),
        );
    }
}

fn required_non_empty_array(
    object: &serde_json::Map<String, serde_json::Value>,
    field: &str,
    errors: &mut Vec<serde_json::Value>,
) {
    if object
        .get(field)
        .and_then(|value| value.as_array())
        .is_some_and(|array| !array.is_empty())
    {
        return;
    }
    push_issue(
        errors,
        "missing_required_field",
        &format!("{field} must be a non-empty array"),
    );
}

fn add_verification_warnings(
    object: &serde_json::Map<String, serde_json::Value>,
    warnings: &mut Vec<serde_json::Value>,
) {
    add_verification_plan_warnings(object, "verification_commands", warnings);
}

fn add_verification_plan_warnings(
    object: &serde_json::Map<String, serde_json::Value>,
    field: &str,
    warnings: &mut Vec<serde_json::Value>,
) {
    add_verification_plan_warnings_for_value(object.get(field), warnings);
}

fn add_verification_plan_warnings_for_value(
    value: Option<&serde_json::Value>,
    warnings: &mut Vec<serde_json::Value>,
) {
    if let Some(commands) = value.and_then(|value| value.as_array()) {
        if commands.len() == 1
            && commands
                .first()
                .and_then(|value| value.as_str())
                .is_some_and(|command| command.trim().len() < 8)
        {
            push_issue(
                warnings,
                "weak_verification_commands",
                "verification commands look too weak for execution readiness",
            );
        }
    }
}

fn require_readiness_string(
    object: &serde_json::Map<String, serde_json::Value>,
    label: &str,
    field: &str,
    errors: &mut Vec<serde_json::Value>,
    missing_fields: &mut Vec<String>,
) {
    if object
        .get(field)
        .and_then(|value| value.as_str())
        .is_some_and(|value| !value.trim().is_empty())
    {
        return;
    }
    missing_fields.push(label.into());
    push_issue(
        errors,
        "missing_required_field",
        &format!("{label} must be present"),
    );
}

fn require_readiness_array(
    object: &serde_json::Map<String, serde_json::Value>,
    label: &str,
    field: &str,
    errors: &mut Vec<serde_json::Value>,
    missing_fields: &mut Vec<String>,
) {
    if object
        .get(field)
        .and_then(|value| value.as_array())
        .is_some_and(|array| !array.is_empty())
    {
        return;
    }
    missing_fields.push(label.into());
    push_issue(
        errors,
        "missing_required_field",
        &format!("{label} must be present"),
    );
}

fn has_non_empty_string(object: &serde_json::Map<String, serde_json::Value>, field: &str) -> bool {
    object
        .get(field)
        .and_then(|value| value.as_str())
        .is_some_and(|value| !value.trim().is_empty())
}

fn has_unresolved_dependency(object: &serde_json::Map<String, serde_json::Value>) -> bool {
    object
        .get("unresolved_dependencies")
        .and_then(|value| value.as_array())
        .is_some_and(|items| !items.is_empty())
        || object
            .get("unresolved_dependency")
            .and_then(|value| value.as_str())
            .is_some_and(|value| !value.trim().is_empty())
}

fn requires_decision(object: &serde_json::Map<String, serde_json::Value>) -> bool {
    object
        .get("requires_decision")
        .and_then(|value| value.as_bool())
        .unwrap_or(false)
        || object
            .get("required_decisions")
            .and_then(|value| value.as_array())
            .is_some_and(|items| !items.is_empty())
}

fn add_readiness_plan_warnings(
    plan: &serde_json::Map<String, serde_json::Value>,
    warnings: &mut Vec<serde_json::Value>,
) {
    add_verification_plan_warnings(plan, "verification_commands", warnings);
    if plan
        .get("scope_paths")
        .and_then(|value| value.as_array())
        .is_some_and(|paths| {
            paths.iter().any(|value| {
                value
                    .as_str()
                    .is_some_and(|path| matches!(path.trim(), "." | "./" | ""))
            })
        })
    {
        push_issue(
            warnings,
            "broad_scope",
            "scope_paths include repository root or an empty path",
        );
    }
    if plan
        .get("acceptance_criteria")
        .and_then(|value| value.as_array())
        .is_some_and(|criteria| {
            criteria.iter().any(|value| {
                value
                    .as_str()
                    .is_some_and(|text| text.trim().len() < 8 || text.eq_ignore_ascii_case("done"))
            })
        })
    {
        push_issue(
            warnings,
            "vague_acceptance_criteria",
            "acceptance criteria look too vague",
        );
    }
}

fn validate_wave_dependencies(
    task: Option<&serde_json::Map<String, serde_json::Value>>,
    plan: Option<&serde_json::Map<String, serde_json::Value>>,
    wave: &serde_json::Map<String, serde_json::Value>,
    blocked: &mut Vec<serde_json::Value>,
) {
    let mut known_tasks = Vec::new();
    for object in [task, plan].into_iter().flatten() {
        if let Some(task_id) = object
            .get("task_id")
            .and_then(|value| value.as_str())
            .filter(|value| !value.trim().is_empty())
        {
            known_tasks.push(task_id.to_string());
        }
    }
    if let Some(tasks) = wave
        .get("validated_ready_tasks")
        .and_then(|value| value.as_array())
    {
        known_tasks.extend(
            tasks
                .iter()
                .filter_map(|value| value.as_str())
                .map(str::to_string),
        );
    }
    let Some(graph) = wave
        .get("dependency_graph")
        .and_then(|value| value.as_array())
    else {
        return;
    };
    for edge in graph {
        let Some(edge_object) = edge.as_object() else {
            continue;
        };
        if let Some(depends_on) = edge_object
            .get("depends_on")
            .and_then(|value| value.as_array())
        {
            for dependency in depends_on {
                let Some(dependency) = dependency.as_str() else {
                    continue;
                };
                if !known_tasks.iter().any(|task_id| task_id == dependency) {
                    push_issue(
                        blocked,
                        "unknown_wave_dependency",
                        &format!("wave dependency references unknown task {dependency}"),
                    );
                }
            }
        }
    }
}

fn required_string<'a>(
    object: &'a serde_json::Map<String, serde_json::Value>,
    field: &str,
    errors: &mut Vec<serde_json::Value>,
) -> Option<&'a str> {
    let value = object
        .get(field)
        .and_then(|value| value.as_str())
        .filter(|value| !value.trim().is_empty());
    if value.is_none() {
        push_issue(
            errors,
            "missing_required_field",
            &format!("{field} must be a non-empty string"),
        );
    }
    value
}

fn required_non_empty_string_array(
    object: &serde_json::Map<String, serde_json::Value>,
    field: &str,
    errors: &mut Vec<serde_json::Value>,
) {
    let valid = object
        .get(field)
        .and_then(|value| value.as_array())
        .filter(|array| !array.is_empty())
        .is_some_and(|array| {
            array
                .iter()
                .all(|value| value.as_str().is_some_and(|text| !text.trim().is_empty()))
        });
    if !valid {
        push_issue(
            errors,
            "missing_required_field",
            &format!("{field} must be a non-empty string array"),
        );
    }
}

fn is_canonical_role(role: &str) -> bool {
    matches!(
        role,
        "implementer" | "code-reviewer" | "compliance-reviewer" | "tester"
    )
}

fn role_allows_mailbox_kind(role: &str, kind: &str) -> bool {
    match role {
        "implementer" => matches!(kind, "result" | "blocked" | "question" | "status"),
        "tester" => matches!(kind, "result" | "blocked" | "question" | "status"),
        "code-reviewer" | "compliance-reviewer" => matches!(
            kind,
            "review_approved" | "review_changes_requested" | "blocked" | "question" | "status"
        ),
        _ => true,
    }
}

fn push_issue(issues: &mut Vec<serde_json::Value>, code: &str, detail: &str) {
    issues.push(serde_json::json!({
        "code": code,
        "detail": detail,
    }));
}

fn dispatch_status_name(status: &DispatchStatus) -> &'static str {
    match status {
        DispatchStatus::Pending => "pending",
        DispatchStatus::Notified => "notified",
        DispatchStatus::Delivered => "delivered",
        DispatchStatus::Failed => "failed",
    }
}

fn now_string() -> String {
    unix_seconds().to_string()
}

fn lease_until_string(seconds_from_now: u64) -> String {
    (unix_seconds() + seconds_from_now).to_string()
}

fn make_token(prefix: &str, owner: &str) -> String {
    format!("{prefix}-{owner}-{}", unix_millis())
}

fn sanitize_ref(value: &str) -> String {
    value
        .chars()
        .map(|ch| {
            if ch.is_ascii_alphanumeric() || matches!(ch, '-' | '_' | '.') {
                ch
            } else {
                '-'
            }
        })
        .collect()
}

fn unix_seconds() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("system clock before unix epoch")
        .as_secs()
}

fn unix_millis() -> u128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("system clock before unix epoch")
        .as_millis()
}

#[cfg(test)]
#[path = "fs_state_tests.rs"]
mod tests;
