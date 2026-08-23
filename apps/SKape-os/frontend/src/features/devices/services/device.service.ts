import api from "../../../api/client";

import type {
  Device,
  CreateDevicePayload,
  UpdateDevicePayload,
} from "../types/device.types";

export async function getDevices(): Promise<Device[]> {
  const response = await api.get<Device[]>("/devices/");
  return response.data;
}

export async function getDevice(
  deviceId: number,
): Promise<Device> {
  const response = await api.get<Device>(
    `/devices/${deviceId}`,
  );

  return response.data;
}

export async function createDevice(
  data: CreateDevicePayload,
): Promise<Device> {
  const response = await api.post<Device>(
    "/devices/",
    data,
  );

  return response.data;
}

export async function updateDevice(
  deviceId: number,
  data: UpdateDevicePayload,
): Promise<Device> {
  const response = await api.put<Device>(
    `/devices/${deviceId}`,
    data,
  );

  return response.data;
}

export async function deleteDevice(
  deviceId: number,
): Promise<Device> {
  const response = await api.delete<Device>(
    `/devices/${deviceId}`,
  );

  return response.data;
}