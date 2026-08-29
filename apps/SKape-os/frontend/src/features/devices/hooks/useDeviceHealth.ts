import {
    useCallback,
    useEffect,
    useState,
  } from "react";
  
  import {
    getDeviceHealth,
    type DeviceHealth,
  } from "../services/deviceHealth.service";
  
  const HEALTH_REFRESH_INTERVAL = 5000;
  
  export function useDeviceHealth(
    deviceId: number,
  ) {
    const [health, setHealth] =
      useState<DeviceHealth | null>(null);
  
    const [loading, setLoading] =
      useState(true);
  
    const [error, setError] =
      useState<string | null>(null);
  
    const loadHealth = useCallback(
      async (showLoading = true) => {
        if (
          Number.isNaN(deviceId) ||
          deviceId <= 0
        ) {
          setLoading(false);
          setError("Invalid device ID.");
          return;
        }
  
        try {
          if (showLoading) {
            setLoading(true);
          }
  
          const data =
            await getDeviceHealth(deviceId);
  
          setHealth(data);
          setError(null);
        } catch (err: any) {
          console.error(
            "Failed to load device health:",
            err,
          );
  
          setError(
            err?.response?.data?.detail ||
              "Unable to load device health.",
          );
        } finally {
          if (showLoading) {
            setLoading(false);
          }
        }
      },
      [deviceId],
    );
  
    useEffect(() => {
      void loadHealth(true);
    }, [loadHealth]);
  
    useEffect(() => {
      const intervalId =
        window.setInterval(() => {
          void loadHealth(false);
        }, HEALTH_REFRESH_INTERVAL);
  
      return () => {
        window.clearInterval(intervalId);
      };
    }, [loadHealth]);
  
    return {
      health,
      loading,
      error,
      refresh: loadHealth,
    };
  }