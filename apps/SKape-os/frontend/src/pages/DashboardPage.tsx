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
        <p className="text-white">
          Loading dashboard...
        </p>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <DashboardHeader />

      <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-4">

        <StatCard
          title="Projects"
          value={stats?.total_projects ?? 0}
        />

        <StatCard
          title="Tasks"
          value={stats?.total_tasks ?? 0}
        />

        <StatCard
          title="Members"
          value={stats?.total_members ?? 0}
        />

        <StatCard
          title="Completed"
          value={stats?.completed_tasks ?? 0}
        />

      </div>

      <QuickActions />

      <div className="grid gap-6 xl:grid-cols-2">
        <RecentProjects />
        <RecentActivity />
      </div>

    </DashboardLayout>
  );
}

export default DashboardPage;