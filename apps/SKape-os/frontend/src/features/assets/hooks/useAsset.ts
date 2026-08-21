import {
    useCallback,
    useEffect,
    useState,
  } from "react";
  
  import {
    createAsset as createAssetRequest,
    deleteAsset as deleteAssetRequest,
    getAssets,
    updateAsset as updateAssetRequest,
  } from "../services/asset.service";
  
  import type {
    Asset,
    CreateAssetPayload,
    UpdateAssetPayload,
  } from "../types/asset.types";
  
  type UseAssetResult = {
    assets: Asset[];
    loading: boolean;
    creating: boolean;
    updating: boolean;
    deleting: boolean;
    error: string | null;
  
    refresh: () => Promise<void>;
  
    createAsset: (
      data: CreateAssetPayload,
    ) => Promise<Asset>;
  
    updateAsset: (
      assetId: number,
      data: UpdateAssetPayload,
    ) => Promise<Asset>;
  
    deleteAsset: (
      assetId: number,
    ) => Promise<Asset>;
  };
  
  export function useAsset(): UseAssetResult {
    const [assets, setAssets] =
      useState<Asset[]>([]);
  
    const [loading, setLoading] =
      useState(true);
  
    const [creating, setCreating] =
      useState(false);
  
    const [updating, setUpdating] =
      useState(false);
  
    const [deleting, setDeleting] =
      useState(false);
  
    const [error, setError] =
      useState<string | null>(null);
  
    /*
     * =========================================================
     * LOAD ASSETS
     * =========================================================
     */
  
    const refresh = useCallback(async () => {
      try {
        setLoading(true);
        setError(null);
  
        const data = await getAssets();
  
        setAssets(data);
      } catch (err: any) {
        console.error(
          "Failed to load assets:",
          err,
        );
  
        const detail =
          err?.response?.data?.detail;
  
        setError(
          detail ||
            "Unable to load assets. Please try again.",
        );
      } finally {
        setLoading(false);
      }
    }, []);
  
    /*
     * =========================================================
     * INITIAL LOAD
     * =========================================================
     */
  
    useEffect(() => {
      void refresh();
    }, [refresh]);
  
    /*
     * =========================================================
     * CREATE ASSET
     * =========================================================
     */
  
    const createAsset = useCallback(
      async (
        data: CreateAssetPayload,
      ): Promise<Asset> => {
        try {
          setCreating(true);
          setError(null);
  
          const created =
            await createAssetRequest(data);
  
          setAssets((current) => [
            created,
            ...current,
          ]);
  
          return created;
        } catch (err: any) {
          console.error(
            "Failed to create asset:",
            err,
          );
  
          const detail =
            err?.response?.data?.detail;
  
          setError(
            detail ||
              "Unable to create asset. Please try again.",
          );
  
          throw err;
        } finally {
          setCreating(false);
        }
      },
      [],
    );
  
    /*
     * =========================================================
     * UPDATE ASSET
     * =========================================================
     */
  
    const updateAsset = useCallback(
      async (
        assetId: number,
        data: UpdateAssetPayload,
      ): Promise<Asset> => {
        try {
          setUpdating(true);
          setError(null);
  
          const updated =
            await updateAssetRequest(
              assetId,
              data,
            );
  
          setAssets((current) =>
            current.map((asset) =>
              asset.id === assetId
                ? updated
                : asset,
            ),
          );
  
          return updated;
        } catch (err: any) {
          console.error(
            "Failed to update asset:",
            err,
          );
  
          const detail =
            err?.response?.data?.detail;
  
          setError(
            detail ||
              "Unable to update asset. Please try again.",
          );
  
          throw err;
        } finally {
          setUpdating(false);
        }
      },
      [],
    );
  
    /*
     * =========================================================
     * DELETE ASSET
     * =========================================================
     */
  
    const deleteAsset = useCallback(
      async (
        assetId: number,
      ): Promise<Asset> => {
        try {
          setDeleting(true);
          setError(null);
  
          const deleted =
            await deleteAssetRequest(
              assetId,
            );
  
          setAssets((current) =>
            current.filter(
              (asset) =>
                asset.id !== assetId,
            ),
          );
  
          return deleted;
        } catch (err: any) {
          console.error(
            "Failed to delete asset:",
            err,
          );
  
          const detail =
            err?.response?.data?.detail;
  
          setError(
            detail ||
              "Unable to delete asset. Please try again.",
          );
  
          throw err;
        } finally {
          setDeleting(false);
        }
      },
      [],
    );
  
    return {
      assets,
      loading,
      creating,
      updating,
      deleting,
      error,
      refresh,
      createAsset,
      updateAsset,
      deleteAsset,
    };
  }