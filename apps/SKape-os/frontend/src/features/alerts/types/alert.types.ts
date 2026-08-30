export type AlertSeverity =
  | "critical"
  | "warning"
  | "info";

export type Alert = {
  id: number;
  device_id: number;
  organization_id: number;

  severity: AlertSeverity;
  alert_type: string;
  title: string;
  message: string;

  is_resolved: boolean;
  resolved_at: string | null;
  created_at: string;
};