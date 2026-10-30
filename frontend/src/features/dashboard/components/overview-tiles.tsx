import { Alert } from "@/components/ui/alert";
import { formatNumber } from "@/lib/utils";

import { getOverview, getQueueStats } from "../queries";
import { StatTile, StatTileSkeleton } from "./stat-tile";

/**
 * The four number tiles. An async Server Component: it awaits its data on the server and sends
 * finished HTML. The two requests run in parallel (Promise.all), not one after the other.
 */
export async function OverviewTiles() {
  const [overview, stats] = await Promise.all([getOverview(), getQueueStats()]);
  if (!overview.ok) return <Alert title="Numbers unavailable">{overview.message}</Alert>;

  const { employees, projects, roles, match_runs } = overview.data;
  return (
    <dl className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      <StatTile
        label="Employees"
        value={formatNumber(employees.active)}
        hint={employees.active === employees.total ? "from the HR import" : `${employees.total} incl. leavers`}
      />
      <StatTile
        label="Searchable resumes"
        value={stats.ok ? formatNumber(stats.data.by_status.ready ?? 0) : "–"}
        hint={stats.ok ? `of ${formatNumber(stats.data.total)} uploaded` : "stats unavailable"}
      />
      <StatTile
        label="Open roles"
        value={formatNumber(roles.by_status.open ?? 0)}
        hint={`in ${projects.total} ${projects.total === 1 ? "project" : "projects"}`}
      />
      <StatTile
        label="Match runs"
        value={formatNumber(match_runs.by_status.completed ?? 0)}
        hint={match_runs.by_status.running ? `${match_runs.by_status.running} running now` : "completed"}
      />
    </dl>
  );
}

export function OverviewTilesSkeleton() {
  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4" role="status" aria-label="Loading numbers">
      {Array.from({ length: 4 }, (_, i) => (
        <StatTileSkeleton key={i} />
      ))}
    </div>
  );
}
