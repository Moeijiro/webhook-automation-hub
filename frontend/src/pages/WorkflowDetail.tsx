import { useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, KeyRound, Terminal, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { useAsync } from "@/hooks/useAsync";
import { PageHeader } from "@/components/PageHeader";
import { CodeBlock } from "@/components/CodeBlock";
import { ExecutionTable } from "@/components/ExecutionTable";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { ErrorNote, Spinner } from "@/components/ui/Feedback";
import { Toggle } from "@/components/ui/Field";
import { ACTION_LABELS, absoluteTime } from "@/lib/utils";

export function WorkflowDetail() {
  const { workflowId = "" } = useParams();
  const id = Number(workflowId);
  const navigate = useNavigate();
  const location = useLocation();
  const justCreated = (location.state as { created?: boolean } | null)?.created ?? false;

  const workflow = useAsync(() => api.workflow(id), [id]);
  const logs = useAsync(() => api.workflowLogs(id, { limit: 10 }), [id]);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  if (workflow.loading) return <Spinner label="Loading workflow" />;
  if (workflow.error) return <ErrorNote message={workflow.error} />;
  if (!workflow.data) return null;

  const detail = workflow.data;

  const toggleEnabled = async (enabled: boolean) => {
    setBusy(true);
    setActionError(null);
    try {
      await api.updateWorkflow(id, { enabled });
      workflow.setData({ ...detail, enabled });
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!confirm(`Delete "${detail.name}" and its execution history?`)) return;
    setBusy(true);
    try {
      await api.deleteWorkflow(id);
      navigate("/workflows");
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  };

  return (
    <>
      <PageHeader
        eyebrow={
          <Link
            to="/workflows"
            className="flex items-center gap-1.5 text-xs text-[var(--color-ink-muted)] hover:text-[var(--color-ink)]"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            All workflows
          </Link>
        }
        title={detail.name}
        description={`${ACTION_LABELS[detail.action_type]} · created ${absoluteTime(detail.created_at)}`}
        actions={
          <Button variant="danger" size="sm" onClick={remove} loading={busy}>
            <Trash2 className="h-3.5 w-3.5" />
            Delete
          </Button>
        }
      />

      {actionError ? (
        <div className="mb-4">
          <ErrorNote message={actionError} />
        </div>
      ) : null}

      {justCreated && detail.signing_secret ? (
        <Card className="mb-4 border-[#1d5c4c]">
          <CardHeader
            title="Signing secret"
            description="Shown once. Sign the request body with it and send the digest as X-Hub-Signature-256."
            icon={<KeyRound className="h-4 w-4" />}
          />
          <CardBody>
            <CodeBlock value={detail.signing_secret} />
          </CardBody>
        </Card>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-5">
        <Card className="lg:col-span-3">
          <CardHeader
            title="Trigger"
            description="POST JSON here and the action runs in the background."
            icon={<Terminal className="h-4 w-4" />}
          />
          <CardBody className="space-y-4">
            <CodeBlock label="Webhook URL" value={detail.webhook_url} />
            <CodeBlock label="Try it" value={detail.curl_example} />
          </CardBody>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader title="Configuration" />
          <CardBody className="space-y-4">
            <Toggle
              label="Enabled"
              description="Disabled workflows answer 409."
              checked={detail.enabled}
              onChange={toggleEnabled}
              disabled={busy}
            />
            <div className="space-y-2 border-t border-[var(--color-border)] pt-4 text-xs">
              <Row label="Action">{ACTION_LABELS[detail.action_type]}</Row>
              <Row label="Signature">
                {detail.signature_required ? (
                  <Badge tone="accent">required</Badge>
                ) : (
                  <span className="text-[var(--color-ink-muted)]">not required</span>
                )}
              </Row>
              <Row label="Executions">{detail.executions}</Row>
            </div>
            <div>
              <p className="mb-1.5 text-[11px] uppercase tracking-wide text-[var(--color-ink-subtle)]">
                Stored config
              </p>
              <pre className="overflow-x-auto rounded-lg border border-[var(--color-border)] bg-[var(--color-canvas)] p-3 font-mono text-[11px] text-[var(--color-ink-muted)]">
                {JSON.stringify(detail.config, null, 2)}
              </pre>
              <p className="mt-1.5 text-[11px] text-[var(--color-ink-subtle)]">
                Credentials are encrypted at rest and never returned by the API.
              </p>
            </div>
          </CardBody>
        </Card>
      </div>

      <Card className="mt-4">
        <CardHeader
          title="Recent executions"
          action={
            <Link
              to={`/logs?workflow=${detail.id}`}
              className="text-xs text-[var(--color-ink-muted)] hover:text-[var(--color-ink)]"
            >
              All executions
            </Link>
          }
        />
        {logs.loading ? <Spinner /> : <ExecutionTable executions={logs.data?.items ?? []} />}
      </Card>
    </>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-[var(--color-ink-subtle)]">{label}</span>
      <span className="text-right">{children}</span>
    </div>
  );
}
