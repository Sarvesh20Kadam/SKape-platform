export type DeviceStatus =
  | "online"
  | "offline"
  | "maintenance";

export type Device = {
  id: number;
  device_id: string;
  name: string;
  device_type: string;
  status: DeviceStatus;
  organization_id: number;
  asset_id: number | null;
  last_seen_at: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string | null;
};

export type CreateDevicePayload = {
  device_id: string;
  name: string;
  device_type: string;
  status?: DeviceStatus;
  asset_id?: number | null;
};

export type UpdateDevicePayload = {
  name?: string;
  device_type?: string;
  status?: DeviceStatus;
  asset_id?: number | null;
  last_seen_at?: string | null;
  is_active?: boolean;
};