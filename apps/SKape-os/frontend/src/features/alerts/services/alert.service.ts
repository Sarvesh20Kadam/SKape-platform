import api from "../../../api/client";

import type { Alert } from "../types/alert.types";

export async function getAlerts(
  unresolvedOnly = false,
  limit = 50,
): Promise<Alert[]> {
  const response = await api.get<Alert[]>(
    "/alerts/",
    {
      params: {
        unresolved_only: unresolvedOnly,
        limit,
      },
    },
  );

  return response.data;
}

export async function getAlert(
  alertId: number,
): Promise<Alert> {
  const response = await api.get<Alert>(
    `/alerts/${alertId}`,
  );

  return response.data;
}

export async function resolveAlert(
  alertId: number,
): Promise<Alert> {
  const response = await api.patch<Alert>(
    `/alerts/${alertId}/resolve`,
  );

  return response.data;
}