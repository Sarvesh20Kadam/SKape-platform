import { useEffect, useState } from "react";

import { getDashboard } from "../services/dashboard.service";
import type { DashboardResponse } from "../types/dashboard";

export function useDashboard() {
  const [stats, setStats] =
    useState<DashboardResponse | null>(null);

  const [loading, setLoading] =
    useState(true);

  useEffect(() => {
    async function loadDashboard() {
      try {
        const data = await getDashboard();
        setStats(data);
      } finally {
        setLoading(false);
      }
    }

    loadDashboard();
  }, []);

  return {
    stats,
    loading,
  };
}