import api from "../../../api/client";

export type DeviceTelemetry = {
  id: number;
  device_id: number;
  temperature: number | null;
  sensor_1: number | null;
  sensor_2: number | null;
  sensor_3: number | null;
  created_at: string;
};

export async function getLatestTelemetry(
  deviceId: number,
): Promise<DeviceTelemetry> {
  const response = await api.get<DeviceTelemetry>(
    `/devices/${deviceId}/telemetry/latest`,
  );

  return response.data;
}

export async function getTelemetryHistory(
  deviceId: number,
  limit = 50,
): Promise<DeviceTelemetry[]> {
  const response = await api.get<DeviceTelemetry[]>(
    `/devices/${deviceId}/telemetry`,
    {
      params: {
        limit,
      },
    },
  );

  return response.data;
}