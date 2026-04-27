use serde::de::DeserializeOwned;

use crate::cmux;
use crate::envelope::print_ok;
use crate::fs_state::StateStore;
use crate::model::{
    AckDispatchInput, ArchiveStateInput, ClaimTaskInput, ConsumeMailboxForTaskInput,
    ConsumeMailboxInput, CreateTaskInput, DispatchStatus, ListEventsInput, ListStaleRolesInput,
    MarkMailboxReadInput, OrchestratorLoopInput, OrchestratorStepInput, ReadDispatchInput,
    ReadMailboxInput, ReadTaskInput, ReleaseTaskInput, RepairStateInput, RetryDispatchInput,
    TransitionTaskInput, WriteMailboxInput, WriteRoleIdentityInput, WriteRoleStatusInput,
};

pub fn run(args: Vec<String>) -> Result<(), String> {
    let store = StateStore::new(std::env::current_dir().map_err(|err| err.to_string())?);
    match args.first().map(String::as_str) {
        None | Some("help") | Some("--help") | Some("-h") => {
            print_ok("help", usage());
            Ok(())
        }
        Some("init") => {
            store.init()?;
            print_ok("init", serde_json::json!({ "state_root": store.root() }));
            Ok(())
        }
        Some("status") => {
            store.init()?;
            print_ok("status", store.status()?);
            Ok(())
        }
        Some("dispatch") => dispatch(&store, &args[1..]),
        Some("role") => role_cmd(&store, &args[1..]),
        Some("api") => api(&store, &args[1..]),
        Some("cmux") => cmux_cmd(&store, &args[1..]),
        Some(command) => Err(format!("unknown command: {command}")),
    }
}

fn dispatch(store: &StateStore, args: &[String]) -> Result<(), String> {
    let role = args.first().ok_or("dispatch requires <role> <task-id>")?;
    let task_id = args.get(1).ok_or("dispatch requires <role> <task-id>")?;
    let output = dispatch_and_notify(store, role, task_id)?;
    print_ok("dispatch", output);
    Ok(())
}

fn dispatch_and_notify(
    store: &StateStore,
    role: &str,
    task_id: &str,
) -> Result<serde_json::Value, String> {
    let request = store.dispatch(role, task_id)?;
    let output = if let Some(surface_ref) = request.surface_ref.as_deref() {
        match cmux::send_text(surface_ref, &request.trigger_message) {
            Ok(cmux_output) => {
                let request = store.mark_dispatch(
                    &request.request_id,
                    DispatchStatus::Notified,
                    "cmux_send_ok",
                )?;
                serde_json::json!({ "dispatch": request, "cmux": cmux_output })
            }
            Err(error) => {
                let request =
                    store.mark_dispatch(&request.request_id, DispatchStatus::Failed, &error)?;
                serde_json::json!({ "dispatch": request, "cmux_error": error })
            }
        }
    } else {
        serde_json::json!({ "dispatch": request })
    };
    Ok(output)
}

fn api(store: &StateStore, args: &[String]) -> Result<(), String> {
    let operation = args.first().ok_or("api requires <operation>")?.as_str();
    let result = match operation {
        "create-task" => {
            let input: CreateTaskInput = parse_input(args)?;
            to_json(store.create_task(input)?)?
        }
        "read-task" => {
            let input: ReadTaskInput = parse_input(args)?;
            to_json(store.read_task(&input.task_id)?)?
        }
        "list-tasks" => to_json(store.list_tasks()?)?,
        "claim-task" => {
            let input: ClaimTaskInput = parse_input(args)?;
            store.claim_task(input)?
        }
        "transition-task" => {
            let input: TransitionTaskInput = parse_input(args)?;
            to_json(store.transition_task(input)?)?
        }
        "release-task" => {
            let input: ReleaseTaskInput = parse_input(args)?;
            to_json(store.release_task_claim(input)?)?
        }
        "write-role-identity" => {
            let input: WriteRoleIdentityInput = parse_input(args)?;
            to_json(store.write_role_identity(input)?)?
        }
        "write-role-status" => {
            let input: WriteRoleStatusInput = parse_input(args)?;
            to_json(store.write_role_status(input)?)?
        }
        "ack-dispatch" => {
            let input: AckDispatchInput = parse_input(args)?;
            to_json(store.ack_dispatch(input)?)?
        }
        "retry-dispatch" => {
            let input: RetryDispatchInput = parse_input(args)?;
            retry_dispatch(store, input)?
        }
        "read-dispatch" => {
            let input: ReadDispatchInput = parse_input(args)?;
            to_json(store.read_dispatch(&input.request_id)?)?
        }
        "list-dispatch" => to_json(store.list_dispatch()?)?,
        "list-events" => {
            let input: ListEventsInput = parse_input_optional(args)?;
            to_json(store.list_events(input)?)?
        }
        "inspect-hooks" => store.inspect_hooks()?,
        "write-mailbox" => {
            let input: WriteMailboxInput = parse_input(args)?;
            to_json(store.write_mailbox(input)?)?
        }
        "read-mailbox" => {
            let input: ReadMailboxInput = parse_input(args)?;
            to_json(store.read_mailbox(input)?)?
        }
        "mark-mailbox-read" => {
            let input: MarkMailboxReadInput = parse_input(args)?;
            to_json(store.mark_mailbox_read(input)?)?
        }
        "consume-mailbox" => {
            let input: ConsumeMailboxInput = parse_input(args)?;
            to_json(store.consume_mailbox(input)?)?
        }
        "consume-mailbox-for-task" => {
            let input: ConsumeMailboxForTaskInput = parse_input(args)?;
            to_json(store.consume_mailbox_for_task(input)?)?
        }
        "validate-role-transfer" => {
            let input: serde_json::Value = parse_input(args)?;
            store.validate_role_transfer(input)?
        }
        "validate-readiness" => {
            let input: serde_json::Value = parse_input(args)?;
            store.validate_readiness(input)?
        }
        "next-action" => store.next_action()?,
        "orchestrator-step" => {
            let input: OrchestratorStepInput = parse_input(args)?;
            orchestrator_step(store, input)?
        }
        "orchestrator-loop" => {
            let input: OrchestratorLoopInput = parse_input(args)?;
            orchestrator_loop(store, input)?
        }
        "list-evidence" => to_json(store.list_evidence()?)?,
        "list-stale-roles" => {
            let input: ListStaleRolesInput = parse_input(args)?;
            to_json(store.list_stale_roles(input)?)?
        }
        "audit-state" => store.audit_state()?,
        "repair-state" => {
            let input: RepairStateInput = parse_input(args)?;
            store.repair_state(input)?
        }
        "archive-state" => {
            let input: ArchiveStateInput = parse_input(args)?;
            store.archive_state(input)?
        }
        unknown => return Err(format!("unknown api operation: {unknown}")),
    };
    print_ok(operation, result);
    Ok(())
}

fn orchestrator_step(
    store: &StateStore,
    input: OrchestratorStepInput,
) -> Result<serde_json::Value, String> {
    let action = store.next_action()?;
    if !input.apply {
        return Ok(serde_json::json!({
            "applied": false,
            "stopped": true,
            "reason": "dry_run",
            "action": action,
        }));
    }

    let action_name = action["action"].as_str().unwrap_or("wait");
    match action_name {
        "consume_mailbox" => {
            let task_id = action["task_id"]
                .as_str()
                .ok_or("orchestrator_step_missing_task_id")?;
            let from_role = action["from_role"]
                .as_str()
                .ok_or("orchestrator_step_missing_from_role")?;
            let kind = action["kind"]
                .as_str()
                .ok_or("orchestrator_step_missing_kind")?;
            let consumed = store.consume_mailbox_for_task(ConsumeMailboxForTaskInput {
                role_id: Some("orchestrator".into()),
                task_id: task_id.into(),
                from_role: Some(from_role.into()),
                kind: Some(kind.into()),
            })?;
            Ok(serde_json::json!({
                "applied": true,
                "operation": "consume_mailbox_for_task",
                "action": action,
                "result": consumed,
            }))
        }
        "dispatch_implementer"
        | "dispatch_code_reviewer"
        | "dispatch_compliance_reviewer"
        | "dispatch_tester" => {
            let role = action["role_id"]
                .as_str()
                .ok_or("orchestrator_step_missing_role_id")?;
            let task_id = action["task_id"]
                .as_str()
                .ok_or("orchestrator_step_missing_task_id")?;
            let result = dispatch_and_notify(store, role, task_id)?;
            Ok(serde_json::json!({
                "applied": true,
                "operation": "dispatch",
                "action": action,
                "result": result,
            }))
        }
        "repair_state" if input.allow_repair => {
            let result = store.repair_state(RepairStateInput { apply: true })?;
            Ok(serde_json::json!({
                "applied": true,
                "operation": "repair_state",
                "action": action,
                "result": result,
            }))
        }
        "repair_state" => Ok(serde_json::json!({
            "applied": false,
            "stopped": true,
            "reason": "repair_state_disabled",
            "action": action,
        })),
        _ => Ok(serde_json::json!({
            "applied": false,
            "stopped": true,
            "reason": format!("non_mutating_action:{action_name}"),
            "action": action,
        })),
    }
}

fn orchestrator_loop(
    store: &StateStore,
    input: OrchestratorLoopInput,
) -> Result<serde_json::Value, String> {
    if input.max_steps == 0 {
        return Err("orchestrator_loop_requires_max_steps".into());
    }
    if input.max_steps > 100 {
        return Err("orchestrator_loop_max_steps_must_be_100_or_less".into());
    }
    if !input.apply {
        return orchestrator_step(
            store,
            OrchestratorStepInput {
                apply: false,
                allow_repair: input.allow_repair,
            },
        );
    }

    let mut steps = Vec::new();
    let mut seen = std::collections::HashSet::new();
    let mut stopped_reason = "max_steps_reached".to_string();
    for _ in 0..input.max_steps {
        let step = orchestrator_step(
            store,
            OrchestratorStepInput {
                apply: true,
                allow_repair: input.allow_repair,
            },
        )?;
        let action = step["action"].clone();
        let fingerprint = action_fingerprint(&action);
        let applied = step["applied"].as_bool().unwrap_or(false);
        let reason = step["reason"].as_str().map(str::to_string);
        steps.push(step);

        if !applied {
            stopped_reason = reason.unwrap_or_else(|| "non_mutating_action".into());
            break;
        }
        if !seen.insert(fingerprint) {
            stopped_reason = "repeated_action_guard".into();
            break;
        }
    }

    Ok(serde_json::json!({
        "applied": steps.iter().any(|step| step["applied"].as_bool().unwrap_or(false)),
        "stopped_reason": stopped_reason,
        "steps": steps,
        "next_action": store.next_action()?,
    }))
}

fn action_fingerprint(action: &serde_json::Value) -> String {
    format!(
        "{}:{}:{}:{}",
        action["action"].as_str().unwrap_or("unknown"),
        action["task_id"].as_str().unwrap_or(""),
        action["role_id"].as_str().unwrap_or(""),
        action["message_id"].as_str().unwrap_or("")
    )
}

fn retry_dispatch(
    store: &StateStore,
    input: RetryDispatchInput,
) -> Result<serde_json::Value, String> {
    let request = store.retry_dispatch(input)?;
    let output = if let Some(surface_ref) = request.surface_ref.as_deref() {
        match cmux::send_text(surface_ref, &request.trigger_message) {
            Ok(cmux_output) => {
                let request = store.mark_dispatch(
                    &request.request_id,
                    DispatchStatus::Notified,
                    "cmux_retry_send_ok",
                )?;
                serde_json::json!({ "dispatch": request, "cmux": cmux_output })
            }
            Err(error) => {
                let request =
                    store.mark_dispatch(&request.request_id, DispatchStatus::Failed, &error)?;
                serde_json::json!({ "dispatch": request, "cmux_error": error })
            }
        }
    } else {
        serde_json::json!({ "dispatch": request })
    };
    Ok(output)
}

fn role_cmd(store: &StateStore, args: &[String]) -> Result<(), String> {
    match args.first().map(String::as_str) {
        Some("register-current") => {
            let role_id = args
                .get(1)
                .ok_or("role register-current requires <role-id>")?;
            let (surface_ref, cmux_identity) = cmux::current_surface_ref()?;
            let identity = store.write_role_identity(WriteRoleIdentityInput {
                role_id: role_id.clone(),
                surface_ref: Some(surface_ref),
            })?;
            print_ok(
                "role.register-current",
                serde_json::json!({
                    "identity": identity,
                    "cmux": cmux_identity,
                }),
            );
            Ok(())
        }
        Some(command) => Err(format!("unknown role command: {command}")),
        None => Err("role requires <command>".into()),
    }
}

fn cmux_cmd(store: &StateStore, args: &[String]) -> Result<(), String> {
    match args.first().map(String::as_str) {
        Some("identify") => {
            print_ok("cmux.identify", cmux::identify()?);
            Ok(())
        }
        Some("capture") => {
            let surface_ref =
                flag_value(args, "--surface").ok_or("cmux capture requires --surface")?;
            let lines = flag_value(args, "--lines")
                .map(|value| value.parse::<usize>())
                .transpose()
                .map_err(|err| format!("invalid --lines: {err}"))?
                .unwrap_or(120);
            let text = cmux::capture_pane(surface_ref, lines)?;
            let evidence = store.write_evidence(surface_ref, lines, &text)?;
            print_ok(
                "cmux.capture",
                serde_json::json!({
                    "evidence": evidence,
                    "content": text,
                }),
            );
            Ok(())
        }
        Some(command) => Err(format!("unknown cmux command: {command}")),
        None => Err("cmux requires <command>".into()),
    }
}

fn parse_input<T: DeserializeOwned>(args: &[String]) -> Result<T, String> {
    let input = args
        .windows(2)
        .find(|pair| pair[0] == "--input")
        .map(|pair| pair[1].as_str())
        .ok_or("missing --input '<json>'")?;
    serde_json::from_str(input).map_err(|err| format!("invalid --input json: {err}"))
}

fn parse_input_optional<T: DeserializeOwned + Default>(args: &[String]) -> Result<T, String> {
    let Some(input) = args
        .windows(2)
        .find(|pair| pair[0] == "--input")
        .map(|pair| pair[1].as_str())
    else {
        return Ok(T::default());
    };
    serde_json::from_str(input).map_err(|err| format!("invalid --input json: {err}"))
}

fn flag_value<'a>(args: &'a [String], flag: &str) -> Option<&'a str> {
    args.windows(2)
        .find(|pair| pair[0] == flag)
        .map(|pair| pair[1].as_str())
}

fn usage() -> serde_json::Value {
    serde_json::json!({
        "commands": [
            "moondex init",
            "moondex status --json",
            "moondex dispatch <role> <task-id> --json",
            "moondex role register-current <role-id> --json",
            "moondex cmux identify --json",
            "moondex api create-task --input '<json>' --json",
            "moondex api read-task --input '<json>' --json",
            "moondex api list-tasks --json",
            "moondex api claim-task --input '<json>' --json",
            "moondex api transition-task --input '<json>' --json",
            "moondex api release-task --input '<json>' --json",
            "moondex api write-role-identity --input '<json>' --json",
            "moondex api write-role-status --input '<json>' --json",
            "moondex api ack-dispatch --input '<json>' --json",
            "moondex api retry-dispatch --input '<json>' --json",
            "moondex api list-dispatch --json",
            "moondex api list-events --input '<json>' --json",
            "moondex api inspect-hooks --json",
            "moondex api read-dispatch --input '<json>' --json",
            "moondex api write-mailbox --input '<json>' --json",
            "moondex api read-mailbox --input '<json>' --json",
            "moondex api mark-mailbox-read --input '<json>' --json",
            "moondex api consume-mailbox --input '<json>' --json",
            "moondex api consume-mailbox-for-task --input '<json>' --json",
            "moondex api validate-role-transfer --input '<json>' --json",
            "moondex api validate-readiness --input '<json>' --json",
            "moondex api next-action --json",
            "moondex api orchestrator-step --input '<json>' --json",
            "moondex api orchestrator-loop --input '<json>' --json",
            "moondex api list-evidence --json",
            "moondex api list-stale-roles --input '<json>' --json",
            "moondex api audit-state --json",
            "moondex api repair-state --input '<json>' --json",
            "moondex api archive-state --input '<json>' --json",
            "moondex cmux capture --surface <surface> --lines 120 --json"
        ]
    })
}

fn to_json(value: impl serde::Serialize) -> Result<serde_json::Value, String> {
    serde_json::to_value(value).map_err(|err| format!("serialize json: {err}"))
}
