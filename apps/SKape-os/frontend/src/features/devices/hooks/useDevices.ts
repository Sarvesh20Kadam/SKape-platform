import {
    useCallback,
    useEffect,
    useState,
  } from "react";
  
  import {
    createDevice as createDeviceRequest,
    deleteDevice as deleteDeviceRequest,
    getDevices,
    updateDevice as updateDeviceRequest,
  } from "../services/device.service";
  
  import type {
    Device,
    CreateDevicePayload,
    UpdateDevicePayload,
  } from "../types/device.types";
  
  type UseDevicesResult = {
    devices: Device[];
    loading: boolean;
    creating: boolean;
    updating: boolean;
    deleting: boolean;
    error: string | null;
  
    refresh: () => Promise<void>;
  
    createDevice: (
      data: CreateDevicePayload,
    ) => Promise<Device>;
  
    updateDevice: (
      deviceId: number,
      data: UpdateDevicePayload,
    ) => Promise<Device>;
  
    deleteDevice: (
      deviceId: number,
    ) => Promise<Device>;
  };
  
  export function useDevices(): UseDevicesResult {
    const [devices, setDevices] =
      useState<Device[]>([]);
  
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
  
    const refresh = useCallback(async () => {
      try {
        setLoading(true);
        setError(null);
  
        const data = await getDevices();
  
        setDevices(data);
      } catch (err: any) {
        console.error(
          "Failed to load devices:",
          err,
        );
  
        const detail =
          err?.response?.data?.detail;
  
        setError(
          detail ||
            "Unable to load devices. Please try again.",
        );
      } finally {
        setLoading(false);
      }
    }, []);
  
    useEffect(() => {
      void refresh();
    }, [refresh]);
  
    const createDevice = useCallback(
      async (
        data: CreateDevicePayload,
      ): Promise<Device> => {
        try {
          setCreating(true);
          setError(null);
  
          const created =
            await createDeviceRequest(data);
  
          setDevices((current) => [
            created,
            ...current,
          ]);
  
          return created;
        } catch (err: any) {
          console.error(
            "Failed to create device:",
            err,
          );
  
          const detail =
            err?.response?.data?.detail;
  
          setError(
            detail ||
              "Unable to create device. Please try again.",
          );
  
          throw err;
        } finally {
          setCreating(false);
        }
      },
      [],
    );
  
    const updateDevice = useCallback(
      async (
        deviceId: number,
        data: UpdateDevicePayload,
      ): Promise<Device> => {
        try {
          setUpdating(true);
          setError(null);
  
          const updated =
            await updateDeviceRequest(
              deviceId,
              data,
            );
  
          setDevices((current) =>
            current.map((device) =>
              device.id === deviceId
                ? updated
                : device,
            ),
          );
  
          return updated;
        } catch (err: any) {
          console.error(
            "Failed to update device:",
            err,
          );
  
          const detail =
            err?.response?.data?.detail;
  
          setError(
            detail ||
              "Unable to update device. Please try again.",
          );
  
          throw err;
        } finally {
          setUpdating(false);
        }
      },
      [],
    );
  
    const deleteDevice = useCallback(
      async (
        deviceId: number,
      ): Promise<Device> => {
        try {
          setDeleting(true);
          setError(null);
  
          const deleted =
            await deleteDeviceRequest(
              deviceId,
            );
  
          setDevices((current) =>
            current.filter(
              (device) =>
                device.id !== deviceId,
            ),
          );
  
          return deleted;
        } catch (err: any) {
          console.error(
            "Failed to delete device:",
            err,
          );
  
          const detail =
            err?.response?.data?.detail;
  
          setError(
            detail ||
              "Unable to delete device. Please try again.",
          );
  
          throw err;
        } finally {
          setDeleting(false);
        }
      },
      [],
    );
  
    return {
      devices,
      loading,
      creating,
      updating,
      deleting,
      error,
      refresh,
      createDevice,
      updateDevice,
      deleteDevice,
    };
  }