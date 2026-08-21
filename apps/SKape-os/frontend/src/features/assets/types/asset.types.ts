export type AssetStatus =
  | "active"
  | "maintenance"
  | "inactive";

export type Asset = {
  id: number;
  name: string;
  asset_type: string;
  description: string | null;
  location: string | null;
  status: AssetStatus;
  organization_id: number;
  assigned_to: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type CreateAssetPayload = {
  name: string;
  asset_type: string;
  description?: string | null;
  location?: string | null;
  status?: AssetStatus;
  assigned_to?: number | null;
};

export type UpdateAssetPayload = {
  name?: string;
  asset_type?: string;
  description?: string | null;
  location?: string | null;
  status?: AssetStatus;
  assigned_to?: number | null;
  is_active?: boolean;
};