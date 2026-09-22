import { Link } from "react-router-dom";
import { Activity, ArrowRight, Workflow as WorkflowIcon } from "lucide-react";
import { api } from "@/lib/api";
import { useAsync } from "@/hooks/useAsync";
import { PageHeader } from "@/components/PageHeader";
import { StatTile } from "@/components/StatTile";
import { ExecutionTable } from "@/components/ExecutionTable";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { ErrorNote, Spinner } from "@/components/ui/Feedback";

export function Dashboard() {
  const stats = useAsync(() => api.stats(), []);
  const executions = useAsync(() => api.executions({ limit: 8 }), []);
  const workflows = useAsync(() => api.workflows(), []);

  const names = Object.fromEntries(
    (workflows.data ?? []).map((workflow) => [workflow.id, workflow.name]),
  );

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Every number here is a count over your own rows — nothing is seeded."
        actions={
          <Link to="/workflows">
            <Button size="sm">
              Workflows
              <ArrowRight className="h-3.5 w-3.5" />
            </Button>
          </Link>
        }
      />

      {stats.error ? <ErrorNote message={stats.error} /> : null}
      {stats.loading ? <Spinner label="Loading stats" /> : null}

      {stats.data ? (
        <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatTile
            label="Active workflows"
            value={stats.data.active_workflows}
            hint={`${stats.data.workflows} total`}
          />
          <StatTile
            label="Executions"
            value={stats.data.executions}
            hint={`${stats.data.executions_last_24h} in the last 24h`}
          />
          <StatTile
            label="Successful"
            value={stats.data.succeeded}
            hint={
              stats.data.success_rate !== null
                ? `${stats.data.success_rate}% success rate`
                : "no runs yet"
            }
          />
          <StatTile
            label="Failed"
            value={stats.data.failed}
            hint={stats.data.processing ? `${stats.data.processing} in flight` : undefined}
          />
        </div>
      ) : null}

      <Card>
        <CardHeader
          title="Recent events"
          description="The last eight executions across all of your workflows."
          icon={<Activity className="h-4 w-4" />}
          action={
            <Link
              to="/logs"
              className="text-xs text-[var(--color-ink-muted)] hover:text-[var(--color-ink)]"
            >
              All logs
            </Link>
          }
        />
        {executions.loading ? (
          <Spinner />
        ) : (
          <ExecutionTable
            executions={executions.data?.items ?? []}
            showWorkflow
            workflowNames={names}
          />
        )}
      </Card>

      {workflows.data && workflows.data.length === 0 ? (
        <Card className="mt-4">
          <div className="flex flex-col items-center gap-3 px-6 py-10 text-center">
            <WorkflowIcon className="h-6 w-6 text-[var(--color-ink-subtle)]" />
            <div>
              <p className="text-sm font-medium">No workflows yet</p>
              <p className="mt-1 text-xs text-[var(--color-ink-muted)]">
                Create one to get a webhook URL and a ready-to-run curl command.
              </p>
            </div>
            <Link to="/workflows">
              <Button variant="primary" size="sm">
                Create a workflow
              </Button>
            </Link>
          </div>
        </Card>
      ) : null}
    </>
  );
}
