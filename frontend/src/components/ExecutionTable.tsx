import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { StatusBadge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/Feedback";
import { absoluteTime, duration, relativeTime } from "@/lib/utils";
import type { Execution } from "@/lib/types";

/** The execution feed, shared by the dashboard, a workflow and the logs page. */
export function ExecutionTable({
  executions,
  showWorkflow = false,
  workflowNames = {},
}: {
  executions: Execution[];
  showWorkflow?: boolean;
  workflowNames?: Record<number, string>;
}) {
  const [expanded, setExpanded] = useState<number | null>(null);

  if (executions.length === 0) {
    return (
      <EmptyState
        title="No executions yet"
        hint="Trigger a workflow's webhook URL and the run will appear here."
      />
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[36rem] border-collapse text-sm">
        <thead>
          <tr className="text-left text-[11px] uppercase tracking-wide text-[var(--color-ink-subtle)]">
            <th className="w-8 px-3 py-2.5" />
            <th className="px-3 py-2.5 font-medium">Status</th>
            {showWorkflow ? <th className="px-3 py-2.5 font-medium">Workflow</th> : null}
            <th className="px-3 py-2.5 font-medium">Result</th>
            <th className="px-3 py-2.5 font-medium">Attempts</th>
            <th className="px-3 py-2.5 font-medium">Took</th>
            <th className="px-3 py-2.5 text-right font-medium">When</th>
          </tr>
        </thead>
        <tbody>
          {executions.map((execution) => {
            const open = expanded === execution.id;
            const detail =
              execution.error ??
              (execution.action_result?.detail as string | undefined) ??
              "—";
            return (
              <>
                <tr
                  key={execution.id}
                  onClick={() => setExpanded(open ? null : execution.id)}
                  className="cursor-pointer border-t border-[var(--color-border)] transition-colors hover:bg-[var(--color-surface-raised)]/40"
                >
                  <td className="px-3 py-3 text-[var(--color-ink-subtle)]">
                    {open ? (
                      <ChevronDown className="h-3.5 w-3.5" />
                    ) : (
                      <ChevronRight className="h-3.5 w-3.5" />
                    )}
                  </td>
                  <td className="px-3 py-3">
                    <StatusBadge status={execution.status} />
                  </td>
                  {showWorkflow ? (
                    <td className="max-w-[12rem] truncate px-3 py-3 text-[var(--color-ink)]">
                      {workflowNames[execution.workflow_id] ?? `#${execution.workflow_id}`}
                    </td>
                  ) : null}
                  <td className="max-w-[16rem] truncate px-3 py-3 text-[var(--color-ink-muted)]">
                    {detail}
                  </td>
                  <td className="px-3 py-3 font-mono text-xs tabular-nums">
                    {execution.attempts}
                  </td>
                  <td className="px-3 py-3 font-mono text-xs tabular-nums text-[var(--color-ink-muted)]">
                    {duration(execution.duration_ms)}
                  </td>
                  <td
                    className="whitespace-nowrap px-3 py-3 text-right text-xs text-[var(--color-ink-muted)]"
                    title={absoluteTime(execution.started_at)}
                  >
                    {relativeTime(execution.started_at)}
                  </td>
                </tr>
                {open ? (
                  <tr key={`${execution.id}-detail`} className="bg-[var(--color-canvas)]/60">
                    <td colSpan={showWorkflow ? 7 : 6} className="px-3 pb-4">
                      <div className="grid gap-3 md:grid-cols-2">
                        <Payload title="Trigger payload" value={execution.trigger_payload} />
                        <Payload title="Action result" value={execution.action_result} />
                      </div>
                    </td>
                  </tr>
                ) : null}
              </>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Payload({ title, value }: { title: string; value: unknown }) {
  return (
    <div>
      <p className="mb-1 text-[11px] uppercase tracking-wide text-[var(--color-ink-subtle)]">
        {title}
      </p>
      <pre className="max-h-48 overflow-auto rounded-lg border border-[var(--color-border)] bg-[var(--color-canvas)] p-3 font-mono text-[11px] leading-relaxed text-[var(--color-ink-muted)]">
        {value ? JSON.stringify(value, null, 2) : "—"}
      </pre>
    </div>
  );
}
