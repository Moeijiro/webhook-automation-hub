import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ChevronRight, Plus } from "lucide-react";
import { api } from "@/lib/api";
import { useAsync } from "@/hooks/useAsync";
import { PageHeader } from "@/components/PageHeader";
import { WorkflowForm } from "@/components/WorkflowForm";
import { Badge, StatusDot } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { EmptyState, ErrorNote, Spinner } from "@/components/ui/Feedback";
import { ACTION_LABELS, relativeTime } from "@/lib/utils";

export function Workflows() {
  const { data, error, loading, reload } = useAsync(() => api.workflows(), []);
  const [creating, setCreating] = useState(false);
  const navigate = useNavigate();

  return (
    <>
      <PageHeader
        title="Workflows"
        description="One trigger, one action. Each workflow owns a webhook URL."
        actions={
          <Button variant="primary" size="sm" onClick={() => setCreating(true)}>
            <Plus className="h-3.5 w-3.5" />
            New workflow
          </Button>
        }
      />

      {error ? <ErrorNote message={error} /> : null}

      {creating ? (
        <Card className="mb-4">
          <CardHeader title="New workflow" description="The webhook URL is generated on save." />
          <CardBody>
            <WorkflowForm
              onCancel={() => setCreating(false)}
              onCreated={(workflow) => {
                setCreating(false);
                reload();
                navigate(`/workflows/${workflow.id}`, { state: { created: true } });
              }}
            />
          </CardBody>
        </Card>
      ) : null}

      {loading ? <Spinner label="Loading workflows" /> : null}

      {data && data.length === 0 && !creating ? (
        <Card>
          <EmptyState
            title="No workflows yet"
            hint="A workflow turns an incoming webhook into a Discord, Telegram or HTTP action."
            action={
              <Button variant="primary" size="sm" onClick={() => setCreating(true)}>
                Create the first one
              </Button>
            }
          />
        </Card>
      ) : null}

      <div className="space-y-3">
        {data?.map((workflow) => (
          <Link key={workflow.id} to={`/workflows/${workflow.id}`} className="block">
            <Card className="transition-colors hover:border-[var(--color-border-strong)]">
              <div className="flex items-center gap-4 px-4 py-4">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="truncate text-sm font-medium">{workflow.name}</p>
                    <Badge tone="neutral">{ACTION_LABELS[workflow.action_type]}</Badge>
                    {workflow.signature_required ? <Badge tone="accent">signed</Badge> : null}
                  </div>
                  <p className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-[var(--color-ink-muted)]">
                    <span className="flex items-center gap-1.5">
                      <StatusDot tone={workflow.enabled ? "positive" : "neutral"} />
                      {workflow.enabled ? "Enabled" : "Disabled"}
                    </span>
                    <span>{workflow.executions} executions</span>
                    <span>last run {relativeTime(workflow.last_execution_at)}</span>
                  </p>
                </div>
                <ChevronRight className="h-4 w-4 shrink-0 text-[var(--color-ink-subtle)]" />
              </div>
            </Card>
          </Link>
        ))}
      </div>
    </>
  );
}
