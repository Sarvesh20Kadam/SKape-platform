import api from "../../../api/client";

import type {
  Asset,
  CreateAssetPayload,
  UpdateAssetPayload,
} from "../types/asset.types";

export async function getAssets(): Promise<Asset[]> {
  const response = await api.get<Asset[]>("/assets/");
  return response.data;
}

export async function getAsset(
  assetId: number,
): Promise<Asset> {
  const response = await api.get<Asset>(
    `/assets/${assetId}`,
  );

  return response.data;
}

export async function createAsset(
  data: CreateAssetPayload,
): Promise<Asset> {
  const response = await api.post<Asset>(
    "/assets/",
    data,
  );

  return response.data;
}

export async function updateAsset(
  assetId: number,
  data: UpdateAssetPayload,
): Promise<Asset> {
  const response = await api.put<Asset>(
    `/assets/${assetId}`,
    data,
  );

  return response.data;
}

export async function deleteAsset(
  assetId: number,
): Promise<Asset> {
  const response = await api.delete<Asset>(
    `/assets/${assetId}`,
  );

  return response.data;
}
