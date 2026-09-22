import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/Feedback";
import { Field, Input, Select, Textarea, Toggle } from "@/components/ui/Field";
import type { ActionType, WorkflowDetail } from "@/lib/types";

const PLACEHOLDER_HINT = "Use {{field}} to insert values from the incoming JSON, e.g. {{order_id}}.";

const DEFAULTS: Record<ActionType, Record<string, unknown>> = {
  discord_webhook: {
    webhook_url: "",
    message_template: "New order #{{order_id}}\nCustomer: {{customer}}\nAmount: ${{amount}}",
  },
  telegram_message: {
    bot_token: "",
    chat_id: "",
    message_template: "New order #{{order_id}} from {{customer}}",
  },
  http_request: {
    method: "POST",
    url: "",
    headers_text: "{}",
    body_template: '{"order": "{{order_id}}"}',
    json_body: true,
  },
};

/** The create form. Editing an existing workflow reuses the same fields. */
export function WorkflowForm({
  onCreated,
  onCancel,
}: {
  onCreated: (workflow: WorkflowDetail) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState("");
  const [actionType, setActionType] = useState<ActionType>("discord_webhook");
  const [config, setConfig] = useState<Record<string, unknown>>(DEFAULTS.discord_webhook);
  const [enabled, setEnabled] = useState(true);
  const [requireSignature, setRequireSignature] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const set = (key: string, value: unknown) =>
    setConfig((current) => ({ ...current, [key]: value }));

  const changeAction = (next: ActionType) => {
    setActionType(next);
    setConfig(DEFAULTS[next]);
    setError(null);
  };

  const submit = async () => {
    setSaving(true);
    setError(null);
    try {
      const payload = { ...config };
      if (actionType === "http_request") {
        // Headers are edited as JSON; parse before sending so a typo is caught
        // here rather than as a validation error from the API.
        try {
          payload.headers = JSON.parse(String(payload.headers_text || "{}"));
        } catch {
          throw new ApiError(422, "Headers must be a JSON object, e.g. {\"Authorization\": \"Bearer …\"}");
        }
        delete payload.headers_text;
        if (!payload.body_template) delete payload.body_template;
      }
      const created = await api.createWorkflow({
        name,
        action_type: actionType,
        config: payload,
        enabled,
        require_signature: requireSignature,
      });
      onCreated(created);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-5">
      {error ? <ErrorNote message={error} /> : null}

      <Field label="Workflow name">
        <Input
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Order created → Discord"
          maxLength={80}
        />
      </Field>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Trigger" hint="Each workflow gets its own webhook URL.">
          <Select value="incoming_webhook" disabled>
            <option value="incoming_webhook">Incoming webhook</option>
          </Select>
        </Field>
        <Field label="Action">
          <Select
            value={actionType}
            onChange={(event) => changeAction(event.target.value as ActionType)}
          >
            <option value="discord_webhook">Discord message</option>
            <option value="telegram_message">Telegram message</option>
            <option value="http_request">HTTP request</option>
          </Select>
        </Field>
      </div>

      {actionType === "discord_webhook" ? (
        <>
          <Field label="Discord webhook URL" hint="Server settings → Integrations → Webhooks.">
            <Input
              value={String(config.webhook_url ?? "")}
              onChange={(event) => set("webhook_url", event.target.value)}
              placeholder="https://discord.com/api/webhooks/…"
            />
          </Field>
          <Field label="Message template" hint={PLACEHOLDER_HINT}>
            <Textarea
              value={String(config.message_template ?? "")}
              onChange={(event) => set("message_template", event.target.value)}
            />
          </Field>
        </>
      ) : null}

      {actionType === "telegram_message" ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Bot token" hint="Stored encrypted; never returned by the API.">
              <Input
                type="password"
                value={String(config.bot_token ?? "")}
                onChange={(event) => set("bot_token", event.target.value)}
                placeholder="123456:ABC-DEF…"
              />
            </Field>
            <Field label="Chat ID" hint="A numeric ID or @channelname.">
              <Input
                value={String(config.chat_id ?? "")}
                onChange={(event) => set("chat_id", event.target.value)}
                placeholder="-1001234567890"
              />
            </Field>
          </div>
          <Field label="Message template" hint={PLACEHOLDER_HINT}>
            <Textarea
              value={String(config.message_template ?? "")}
              onChange={(event) => set("message_template", event.target.value)}
            />
          </Field>
        </>
      ) : null}

      {actionType === "http_request" ? (
        <>
          <div className="grid gap-4 sm:grid-cols-[8rem_1fr]">
            <Field label="Method">
              <Select
                value={String(config.method ?? "POST")}
                onChange={(event) => set("method", event.target.value)}
              >
                {["GET", "POST", "PUT", "PATCH", "DELETE"].map((method) => (
                  <option key={method}>{method}</option>
                ))}
              </Select>
            </Field>
            <Field label="URL" hint="Public hosts only — private addresses are refused.">
              <Input
                value={String(config.url ?? "")}
                onChange={(event) => set("url", event.target.value)}
                placeholder="https://api.example.com/events"
              />
            </Field>
          </div>
          <Field label="Headers (JSON)" hint="Header values are stored encrypted.">
            <Textarea
              value={String(config.headers_text ?? "{}")}
              onChange={(event) => set("headers_text", event.target.value)}
            />
          </Field>
          {config.method !== "GET" && config.method !== "DELETE" ? (
            <Field label="Body template" hint={PLACEHOLDER_HINT}>
              <Textarea
                value={String(config.body_template ?? "")}
                onChange={(event) => set("body_template", event.target.value)}
              />
            </Field>
          ) : null}
        </>
      ) : null}

      <div className="space-y-3 border-t border-[var(--color-border)] pt-5">
        <Toggle
          label="Enabled"
          description="A disabled workflow answers 409 and runs nothing."
          checked={enabled}
          onChange={setEnabled}
        />
        <Toggle
          label="Require signed requests"
          description="Callers must send an X-Hub-Signature-256 HMAC of the body."
          checked={requireSignature}
          onChange={setRequireSignature}
        />
      </div>

      <div className="flex justify-end gap-2">
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button variant="primary" onClick={submit} loading={saving} disabled={!name}>
          Create workflow
        </Button>
      </div>
    </div>
  );
}
