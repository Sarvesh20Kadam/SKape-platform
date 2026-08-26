import {
    useCallback,
    useEffect,
    useState,
  } from "react";
  
  import {
    getLatestTelemetry,
    type DeviceTelemetry,
  } from "../services/telemetry.service";
  
  type UseDeviceTelemetryResult = {
    telemetry: DeviceTelemetry | null;
    loading: boolean;
    error: string | null;
    refresh: () => Promise<void>;
  };
  
  const TELEMETRY_REFRESH_INTERVAL = 5000;
  
  export function useDeviceTelemetry(
    deviceId: number,
  ): UseDeviceTelemetryResult {
    const [telemetry, setTelemetry] =
      useState<DeviceTelemetry | null>(null);
  
    const [loading, setLoading] =
      useState(true);
  
    const [error, setError] =
      useState<string | null>(null);
  
    const refresh = useCallback(async () => {
      try {
        setError(null);
  
        const data =
          await getLatestTelemetry(deviceId);
  
        setTelemetry(data);
      } catch (err: any) {
        const status = err?.response?.status;
  
        if (status === 404) {
          setTelemetry(null);
          setError("No telemetry available yet.");
        } else {
          console.error(
            "Failed to load device telemetry:",
            err,
          );
  
          setError(
            "Unable to load device telemetry.",
          );
        }
      } finally {
        setLoading(false);
      }
    }, [deviceId]);
  
    useEffect(() => {
      void refresh();
  
      const interval = window.setInterval(() => {
        void refresh();
      }, TELEMETRY_REFRESH_INTERVAL);
  
      return () => {
        window.clearInterval(interval);
      };
    }, [refresh]);
  
    return {
      telemetry,
      loading,
      error,
      refresh,
    };
  }