import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ScrollText } from "lucide-react";
import { api } from "@/lib/api";
import { useAsync } from "@/hooks/useAsync";
import { PageHeader } from "@/components/PageHeader";
import { ExecutionTable } from "@/components/ExecutionTable";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { ErrorNote, Spinner } from "@/components/ui/Feedback";
import { Select } from "@/components/ui/Field";

const PAGE_SIZE = 25;

export function Logs() {
  const [params, setParams] = useSearchParams();
  const workflowFilter = params.get("workflow") ?? "";
  const [status, setStatus] = useState("");
  const [offset, setOffset] = useState(0);

  const workflows = useAsync(() => api.workflows(), []);
  const page = useAsync(
    () =>
      api.executions({
        limit: PAGE_SIZE,
        offset,
        status: status || undefined,
        workflow_id: workflowFilter ? Number(workflowFilter) : undefined,
      }),
    [offset, status, workflowFilter],
  );

  const names = Object.fromEntries(
    (workflows.data ?? []).map((workflow) => [workflow.id, workflow.name]),
  );
  const total = page.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const current = Math.floor(offset / PAGE_SIZE) + 1;

  return (
    <>
      <PageHeader
        title="Execution logs"
        description="Every run, newest first — with the payload that triggered it."
        actions={
          <div className="flex gap-2">
            <Select
              aria-label="Filter by workflow"
              className="w-44"
              value={workflowFilter}
              onChange={(event) => {
                const value = event.target.value;
                setParams(value ? { workflow: value } : {});
                setOffset(0);
              }}
            >
              <option value="">All workflows</option>
              {workflows.data?.map((workflow) => (
                <option key={workflow.id} value={workflow.id}>
                  {workflow.name}
                </option>
              ))}
            </Select>
            <Select
              aria-label="Filter by status"
              className="w-36"
              value={status}
              onChange={(event) => {
                setStatus(event.target.value);
                setOffset(0);
              }}
            >
              <option value="">Any status</option>
              <option value="success">Success</option>
              <option value="failed">Failed</option>
              <option value="processing">Processing</option>
            </Select>
          </div>
        }
      />

      {page.error ? <ErrorNote message={page.error} /> : null}

      <Card>
        <CardHeader
          title={`${total} execution${total === 1 ? "" : "s"}`}
          icon={<ScrollText className="h-4 w-4" />}
        />
        {page.loading ? (
          <Spinner />
        ) : (
          <ExecutionTable
            executions={page.data?.items ?? []}
            showWorkflow
            workflowNames={names}
          />
        )}
      </Card>

      {pages > 1 ? (
        <div className="mt-4 flex items-center justify-between text-xs text-[var(--color-ink-muted)]">
          <span>
            Page {current} of {pages}
          </span>
          <div className="flex gap-2">
            <Button
              size="sm"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            >
              Previous
            </Button>
            <Button
              size="sm"
              disabled={offset + PAGE_SIZE >= total}
              onClick={() => setOffset(offset + PAGE_SIZE)}
            >
              Next
            </Button>
          </div>
        </div>
      ) : null}
    </>
  );
}
