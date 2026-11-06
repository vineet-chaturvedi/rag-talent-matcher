import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { Health } from "@/lib/api/types";

import { MODEL_LABEL } from "../labels";
import { getHealth } from "../queries";

const STATUS_TONE = { ok: "success", degraded: "warning", error: "danger" } as const;

/** Is everything the AI pipeline needs running? (GET /api/health: database, Ollama, the 3 models) */
export async function HealthCard() {
  const health = await getHealth();
  return (
    <Card>
      <CardHeader>
        <CardTitle>System health</CardTitle>
        {health.ok && (
          <CardAction>
            <Badge tone={STATUS_TONE[health.data.status]}>{health.data.status}</Badge>
          </CardAction>
        )}
      </CardHeader>
      <CardContent>{health.ok ? <HealthDetails health={health.data} /> : <Alert>{health.message}</Alert>}</CardContent>
    </Card>
  );
}

function HealthDetails({ health }: { health: Health }) {
  const { database, ollama } = health;
  return (
    <dl className="space-y-2.5 text-sm">
      <Row label="API" ok value={`${health.app} (${health.environment})`} />
      <Row label="Database" ok={database.reachable} value={database.reachable ? "reachable" : "unreachable"} />
      <Row
        label="Ollama"
        ok={ollama.reachable}
        value={ollama.reachable ? `running, version ${ollama.version ?? "?"}` : "not reachable"}
      />
      {Object.entries(ollama.models ?? {}).map(([role, model]) => (
        <Row
          key={role}
          label={MODEL_LABEL[role] ?? role}
          ok={model.installed}
          value={
            model.installed
              ? `${model.name}${model.provider && model.provider !== "Ollama" ? ` · ${model.provider}` : ""}`
              : `${model.name} (${model.problem ?? "not installed"})`
          }
        />
      ))}
    </dl>
  );
}

function Row({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="flex min-w-0 items-center gap-2 text-right">
        <span className="truncate">{value}</span>
        <span
          className={ok ? "size-2 shrink-0 rounded-full bg-success" : "size-2 shrink-0 rounded-full bg-destructive"}
        />
        <span className="sr-only">{ok ? "OK" : "problem"}</span>
      </dd>
    </div>
  );
}

export function HealthCardSkeleton() {
  return (
    <Card role="status" aria-label="Loading system health">
      <CardHeader>
        <CardTitle>System health</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {Array.from({ length: 6 }, (_, i) => (
          <Skeleton key={i} className="h-4 w-full" />
        ))}
      </CardContent>
    </Card>
  );
}
