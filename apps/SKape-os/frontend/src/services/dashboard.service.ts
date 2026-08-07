import api from "../api/client";
import type { DashboardResponse } from "../types/dashboard";

export async function getDashboard() {
  const response =
    await api.get<DashboardResponse>(
      "/dashboard/"
    );

  return response.data;
}