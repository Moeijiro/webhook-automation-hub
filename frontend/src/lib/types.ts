/** Mirrors the Pydantic schemas served by the FastAPI backend. */

export interface User {
  id: number;
  email: string;
  created_at: string;
}

export type ActionType = "discord_webhook" | "telegram_message" | "http_request";

export interface Workflow {
  id: number;
  name: string;
  trigger_type: string;
  action_type: ActionType;
  config: Record<string, unknown>;
  enabled: boolean;
  created_at: string;
  updated_at: string;
  webhook_url: string;
  signature_required: boolean;
  executions: number;
  last_execution_at: string | null;
}

export interface WorkflowDetail extends Workflow {
  signing_secret: string | null;
  curl_example: string;
}

export type ExecutionStatus = "success" | "failed" | "processing";

export interface Execution {
  id: number;
  workflow_id: number;
  status: ExecutionStatus;
  attempts: number;
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
  trigger_payload: Record<string, unknown> | null;
  action_result: Record<string, unknown> | null;
  error: string | null;
}

export interface ExecutionPage {
  items: Execution[];
  total: number;
  limit: number;
  offset: number;
}

export interface ApiKey {
  id: number;
  name: string;
  prefix: string;
  active: boolean;
  created_at: string;
  last_used_at: string | null;
}

export interface CreatedApiKey extends ApiKey {
  key: string;
  warning: string;
}

export interface Stats {
  workflows: number;
  active_workflows: number;
  executions: number;
  succeeded: number;
  failed: number;
  processing: number;
  executions_last_24h: number;
  success_rate: number | null;
}

export interface ActionCatalogEntry {
  type: ActionType;
  label: string;
  description: string;
  secret_fields: string[];
  schema: Record<string, unknown>;
}
