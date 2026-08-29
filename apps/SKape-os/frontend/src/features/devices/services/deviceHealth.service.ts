import api from "../../../api/client";

export type DeviceHealth = {
  status: "healthy" | "warning" | "critical";
  reason: string;
};

export async function getDeviceHealth(
  deviceId: number,
): Promise<DeviceHealth> {
  const response = await api.get<DeviceHealth>(
    `/devices/${deviceId}/health`,
  );

  return response.data;
}