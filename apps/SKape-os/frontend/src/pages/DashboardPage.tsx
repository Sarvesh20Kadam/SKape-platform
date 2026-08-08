import DashboardLayout from "../components/layout/DashboardLayout";

import DashboardHeader from "../components/dashboard/DashboardHeader";
import StatCard from "../components/dashboard/StatCard";
import QuickActions from "../components/dashboard/QuickActions";
import RecentProjects from "../components/dashboard/RecentProjects";
import RecentActivity from "../components/dashboard/RecentActivity";

import { useDashboard } from "../hooks/useDashboard";

function DashboardPage() {
  const { stats, loading } = useDashboard();

  if (loading) {
    return (
      <DashboardLayout>
        <div className="mx-auto w-full max-w-[1600px] space-y-8">
          {/* Page heading skeleton */}
          <div className="space-y-3">
            <div className="h-8 w-48 animate-pulse rounded-md bg-zinc-800" />
            <div className="h-4 w-72 animate-pulse rounded-md bg-zinc-900" />
          </div>

          {/* Statistics skeleton */}
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {Array.from({ length: 4 }).map((_, index) => (
              <div
                key={index}
                className="h-32 animate-pulse rounded-xl border border-zinc-800 bg-zinc-900/70"
              />
            ))}
          </div>

          {/* Content skeleton */}
          <div className="grid gap-6 xl:grid-cols-2">
            <div className="h-80 animate-pulse rounded-xl border border-zinc-800 bg-zinc-900/70" />

            <div className="h-80 animate-pulse rounded-xl border border-zinc-800 bg-zinc-900/70" />
          </div>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <main className="mx-auto w-full max-w-[1600px] space-y-8">
        {/* =====================================================
            PAGE HEADER
            ===================================================== */}

        <DashboardHeader />

        {/* =====================================================
            OVERVIEW
            ===================================================== */}

        <section
          aria-label="Workspace overview"
          className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"
        >
          <StatCard
            title="Projects"
            value={stats?.total_projects ?? 0}
          />

          <StatCard
            title="Tasks"
            value={stats?.total_tasks ?? 0}
          />

          <StatCard
            title="Team members"
            value={stats?.total_members ?? 0}
          />

          <StatCard
            title="Completed"
            value={stats?.completed_tasks ?? 0}
          />
        </section>

        {/* =====================================================
            QUICK ACTIONS
            ===================================================== */}

        <section aria-label="Quick actions">
          <QuickActions />
        </section>

        {/* =====================================================
            RECENT WORKSPACE ACTIVITY
            ===================================================== */}

        <section
          aria-label="Recent workspace activity"
          className="grid gap-6 xl:grid-cols-2"
        >
          <RecentProjects />

          <RecentActivity />
        </section>
      </main>
    </DashboardLayout>
  );
}

export default DashboardPage;