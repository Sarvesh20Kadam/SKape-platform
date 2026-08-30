import {
    useCallback,
    useEffect,
    useState,
  } from "react";
  
  import {
    getAlerts,
    resolveAlert,
  } from "../services/alert.service";
  
  import type { Alert } from "../types/alert.types";
  
  const ALERT_REFRESH_INTERVAL = 5000;
  
  export function useAlerts(
    unresolvedOnly = false,
  ) {
    const [alerts, setAlerts] =
      useState<Alert[]>([]);
  
    const [loading, setLoading] =
      useState(true);
  
    const [error, setError] =
      useState<string | null>(null);
  
    const loadAlerts = useCallback(
      async (showLoading = true) => {
        try {
          if (showLoading) {
            setLoading(true);
          }
  
          const data = await getAlerts(
            unresolvedOnly,
          );
  
          setAlerts(data);
          setError(null);
        } catch (err: any) {
          console.error(
            "Failed to load alerts:",
            err,
          );
  
          setError(
            err?.response?.data?.detail ||
              "Unable to load alerts.",
          );
        } finally {
          if (showLoading) {
            setLoading(false);
          }
        }
      },
      [unresolvedOnly],
    );
  
    const handleResolve = useCallback(
      async (alertId: number) => {
        try {
          await resolveAlert(alertId);
  
          await loadAlerts(false);
        } catch (err: any) {
          console.error(
            "Failed to resolve alert:",
            err,
          );
  
          setError(
            err?.response?.data?.detail ||
              "Unable to resolve alert.",
          );
  
          throw err;
        }
      },
      [loadAlerts],
    );
  
    useEffect(() => {
      void loadAlerts(true);
    }, [loadAlerts]);
  
    useEffect(() => {
      const intervalId =
        window.setInterval(() => {
          void loadAlerts(false);
        }, ALERT_REFRESH_INTERVAL);
  
      return () => {
        window.clearInterval(intervalId);
      };
    }, [loadAlerts]);
  
    return {
      alerts,
      loading,
      error,
      refresh: loadAlerts,
      resolve: handleResolve,
    };
  }