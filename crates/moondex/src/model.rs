use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum TaskStatus {
    Pending,
    Blocked,
    InProgress,
    Completed,
    Failed,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct TaskClaim {
    pub owner: String,
    pub token: String,
    pub leased_until: String,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct Task {
    pub id: String,
    pub subject: String,
    pub description: String,
    pub status: TaskStatus,
    #[serde(default = "default_task_phase")]
    pub phase: String,
    pub owner: Option<String>,
    pub role: Option<String>,
    pub result: Option<String>,
    pub error: Option<String>,
    pub version: u64,
    pub claim: Option<TaskClaim>,
    pub created_at: String,
    pub completed_at: Option<String>,
}

fn default_task_phase() -> String {
    "implementation".into()
}

#[derive(Clone, Debug, Deserialize)]
pub struct CreateTaskInput {
    pub task_id: String,
    pub subject: String,
    pub description: String,
    pub role: Option<String>,
}

#[derive(Clone, Debug, Deserialize)]
pub struct ReadTaskInput {
    pub task_id: String,
}

#[derive(Clone, Debug, Deserialize)]
pub struct ClaimTaskInput {
    pub task_id: String,
    pub worker: String,
    pub expected_version: u64,
}

#[derive(Clone, Debug, Deserialize)]
pub struct TransitionTaskInput {
    pub task_id: String,
    pub from: TaskStatus,
    pub to: TaskStatus,
    pub claim_token: String,
    pub result: Option<String>,
    pub error: Option<String>,
}

#[derive(Clone, Debug, Deserialize)]
pub struct ReleaseTaskInput {
    pub task_id: String,
    pub worker: String,
    pub claim_token: String,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct RoleIdentity {
    pub role_id: String,
    pub surface_ref: Option<String>,
    pub updated_at: String,
}

#[derive(Clone, Debug, Deserialize)]
pub struct WriteRoleIdentityInput {
    pub role_id: String,
    pub surface_ref: Option<String>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum DispatchStatus {
    Pending,
    Notified,
    Delivered,
    Failed,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct DispatchRequest {
    pub request_id: String,
    pub kind: String,
    pub to_role: String,
    pub task_id: String,
    pub trigger_message: String,
    pub surface_ref: Option<String>,
    pub status: DispatchStatus,
    pub created_at: String,
    pub updated_at: String,
    pub last_reason: Option<String>,
    #[serde(default)]
    pub retry_count: u64,
    #[serde(default)]
    pub retry_history: Vec<DispatchRetryRecord>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct DispatchRetryRecord {
    pub attempted_at: String,
    pub surface_ref: Option<String>,
    pub outcome: String,
    pub reason: Option<String>,
}

#[derive(Clone, Debug, Deserialize)]
pub struct ReadDispatchInput {
    pub request_id: String,
}

#[derive(Clone, Debug, Deserialize)]
pub struct AckDispatchInput {
    pub request_id: String,
    pub role_id: String,
}

#[derive(Clone, Debug, Deserialize)]
pub struct RetryDispatchInput {
    pub request_id: String,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct RoleStatus {
    pub role_id: String,
    pub state: String,
    pub task_id: Option<String>,
    pub message: Option<String>,
    pub updated_at: String,
}

#[derive(Clone, Debug, Deserialize)]
pub struct WriteRoleStatusInput {
    pub role_id: String,
    pub state: String,
    pub task_id: Option<String>,
    pub message: Option<String>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct MailboxMessage {
    pub message_id: String,
    pub from_role: String,
    pub to_role: String,
    pub kind: String,
    pub task_id: Option<String>,
    pub body: String,
    pub created_at: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub read_at: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub consumed_at: Option<String>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct HookWarning {
    pub warning_id: String,
    pub hook: String,
    #[serde(rename = "type")]
    pub warning_type: String,
    pub severity: String,
    pub task_id: Option<String>,
    pub role_id: Option<String>,
    pub message_id: Option<String>,
    pub detail: String,
    pub created_at: String,
}

#[derive(Clone, Debug, Deserialize)]
pub struct WriteMailboxInput {
    pub from_role: String,
    pub to_role: Option<String>,
    pub kind: String,
    pub task_id: Option<String>,
    pub body: String,
}

#[derive(Clone, Debug, Deserialize)]
pub struct ReadMailboxInput {
    pub role_id: Option<String>,
    #[serde(default)]
    pub task_id: Option<String>,
    #[serde(default)]
    pub unread_only: Option<bool>,
    #[serde(default)]
    pub unconsumed_only: Option<bool>,
}

#[derive(Clone, Debug, Deserialize)]
pub struct ListStaleRolesInput {
    pub older_than_seconds: u64,
}

#[derive(Clone, Debug, Deserialize)]
pub struct RepairStateInput {
    #[serde(default)]
    pub apply: bool,
}

#[derive(Clone, Debug, Deserialize)]
pub struct ArchiveStateInput {
    #[serde(default)]
    pub apply: bool,
    #[serde(default)]
    pub older_than_seconds: u64,
    #[serde(default)]
    pub include_hook_warnings: bool,
}

#[derive(Clone, Debug, Default, Deserialize)]
pub struct ListEventsInput {
    #[serde(default)]
    pub task_id: Option<String>,
    #[serde(default)]
    pub kind: Option<String>,
    #[serde(default)]
    pub limit: Option<usize>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct PhaseEvent {
    pub event_id: String,
    pub kind: String,
    pub task_id: Option<String>,
    pub role_id: Option<String>,
    pub from_phase: Option<String>,
    pub to_phase: Option<String>,
    pub from_status: Option<TaskStatus>,
    pub to_status: Option<TaskStatus>,
    pub message_id: Option<String>,
    pub dispatch_request_id: Option<String>,
    pub created_at: String,
    pub detail: serde_json::Value,
}

#[derive(Clone, Debug, Deserialize)]
pub struct OrchestratorStepInput {
    #[serde(default)]
    pub apply: bool,
    #[serde(default = "default_allow_repair")]
    pub allow_repair: bool,
}

#[derive(Clone, Debug, Deserialize)]
pub struct OrchestratorLoopInput {
    #[serde(default)]
    pub apply: bool,
    pub max_steps: usize,
    #[serde(default = "default_allow_repair")]
    pub allow_repair: bool,
}

fn default_allow_repair() -> bool {
    true
}

#[derive(Clone, Debug, Deserialize)]
pub struct MarkMailboxReadInput {
    pub role_id: Option<String>,
    pub message_id: String,
}

#[derive(Clone, Debug, Deserialize)]
pub struct ConsumeMailboxInput {
    pub role_id: Option<String>,
    pub message_id: String,
}

#[derive(Clone, Debug, Deserialize)]
pub struct ConsumeMailboxForTaskInput {
    pub role_id: Option<String>,
    pub task_id: String,
    pub from_role: Option<String>,
    pub kind: Option<String>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct EvidenceRecord {
    pub evidence_id: String,
    pub kind: String,
    pub source_ref: String,
    pub path: String,
    pub lines: usize,
    pub captured_at: String,
}
