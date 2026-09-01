import {
    AlertTriangle,
    CheckCircle2,
    CircleAlert,
    ExternalLink,
    Monitor,
    Wifi,
    WifiOff,
  } from "lucide-react";
  
  import { Link } from "react-router-dom";
  
  import { useEffect } from "react";
  
  import { useDevices } from "../../features/devices/hooks/useDevices";
  import { useAlerts } from "../../features/alerts/hooks/useAlerts";
  
  function formatRelativeTime(
    timestamp: string,
  ): string {
    const created = new Date(timestamp).getTime();
    const now = Date.now();
  
    const seconds = Math.max(
      0,
      Math.floor((now - created) / 1000),
    );
  
    if (seconds < 60) {
      return `${seconds}s ago`;
    }
  
    const minutes = Math.floor(seconds / 60);
  
    if (minutes < 60) {
      return `${minutes}m ago`;
    }
  
    const hours = Math.floor(minutes / 60);
  
    if (hours < 24) {
      return `${hours}h ago`;
    }
  
    const days = Math.floor(hours / 24);
  
    return `${days}d ago`;
  }
  
  function getSeverityClasses(
    severity: string,
  ) {
    if (severity === "critical") {
      return {
        icon: "border-red-500/20 bg-red-500/10 text-red-400",
        badge:
          "border-red-500/20 bg-red-500/10 text-red-400",
      };
    }
  
    if (severity === "warning") {
      return {
        icon:
          "border-amber-500/20 bg-amber-500/10 text-amber-400",
        badge:
          "border-amber-500/20 bg-amber-500/10 text-amber-400",
      };
    }
  
    return {
      icon:
        "border-zinc-700 bg-zinc-800/50 text-zinc-400",
      badge:
        "border-zinc-700 bg-zinc-800/50 text-zinc-400",
    };
  }
  
  function OperationsOverview() {
    const {
      devices,
      loading: devicesLoading,
      refresh: refreshDevices,
    } = useDevices();
  
    const {
      alerts,
      loading: alertsLoading,
    } = useAlerts(true);
  
    useEffect(() => {
      const intervalId = window.setInterval(() => {
        void refreshDevices();
      }, 5000);
  
      return () => {
        window.clearInterval(intervalId);
      };
    }, [refreshDevices]);
  
    const onlineDevices = devices.filter(
      (device) => device.status === "online",
    ).length;
  
    const criticalAlerts = alerts.filter(
      (alert) =>
        alert.severity === "critical" &&
        !alert.is_resolved,
    ).length;
  
    const openAlerts = alerts.filter(
      (alert) => !alert.is_resolved,
    ).length;
  
    const recentAlerts = alerts
      .filter((alert) => !alert.is_resolved)
      .slice(0, 3);
  
    const loading =
      devicesLoading || alertsLoading;
  
    return (
      <section
        aria-label="Operations overview"
        className="space-y-5"
      >
        {/* =====================================================
            SECTION HEADER
            ===================================================== */}
  
        <div className="flex items-end justify-between gap-4">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-zinc-600">
              Operations
            </p>
  
            <h2 className="mt-1 text-lg font-semibold tracking-[-0.02em] text-zinc-100">
              Device health
            </h2>
  
            <p className="mt-1 text-sm text-zinc-500">
              Live status across your connected devices.
            </p>
          </div>
  
          <Link
            to="/devices"
            className="
              hidden
              items-center
              gap-1.5
              text-xs
              font-medium
              text-zinc-500
              transition-colors
              hover:text-zinc-200
              sm:flex
            "
          >
            View devices
            <ExternalLink size={13} />
          </Link>
        </div>
  
        {/* =====================================================
            OPERATION STATISTICS
            ===================================================== */}
  
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
  
          {/* Devices */}
  
          <article
            className="
              rounded-xl
              border
              border-zinc-800/80
              bg-zinc-900/60
              p-5
            "
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-zinc-800 bg-zinc-950 text-zinc-500">
                  <Monitor size={15} />
                </div>
  
                <p className="text-sm font-medium text-zinc-500">
                  Devices
                </p>
              </div>
  
              <span className="text-[10px] uppercase tracking-[0.12em] text-zinc-700">
                Total
              </span>
            </div>
  
            <p className="mt-6 font-mono text-3xl font-medium tracking-[-0.04em] text-zinc-100">
              {loading ? "—" : devices.length}
            </p>
          </article>
  
  
          {/* Online */}
  
          <article
            className="
              rounded-xl
              border
              border-zinc-800/80
              bg-zinc-900/60
              p-5
            "
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-emerald-500/20 bg-emerald-500/10 text-emerald-400">
                  <Wifi size={15} />
                </div>
  
                <p className="text-sm font-medium text-zinc-500">
                  Online
                </p>
              </div>
  
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
            </div>
  
            <p className="mt-6 font-mono text-3xl font-medium tracking-[-0.04em] text-zinc-100">
              {loading ? "—" : onlineDevices}
            </p>
  
            {!loading && devices.length > 0 && (
              <p className="mt-2 text-xs text-zinc-600">
                {Math.round(
                  (onlineDevices / devices.length) * 100,
                )}
                % of devices
              </p>
            )}
          </article>
  
  
          {/* Open alerts */}
  
          <article
            className="
              rounded-xl
              border
              border-zinc-800/80
              bg-zinc-900/60
              p-5
            "
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-amber-500/20 bg-amber-500/10 text-amber-400">
                  <CircleAlert size={15} />
                </div>
  
                <p className="text-sm font-medium text-zinc-500">
                  Open alerts
                </p>
              </div>
  
              {openAlerts > 0 && (
                <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
              )}
            </div>
  
            <p className="mt-6 font-mono text-3xl font-medium tracking-[-0.04em] text-zinc-100">
              {loading ? "—" : openAlerts}
            </p>
          </article>
  
  
          {/* Critical */}
  
          <article
            className="
              rounded-xl
              border
              border-zinc-800/80
              bg-zinc-900/60
              p-5
            "
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-red-500/20 bg-red-500/10 text-red-400">
                  <AlertTriangle size={15} />
                </div>
  
                <p className="text-sm font-medium text-zinc-500">
                  Critical
                </p>
              </div>
  
              {criticalAlerts > 0 && (
                <span className="h-1.5 w-1.5 rounded-full bg-red-500" />
              )}
            </div>
  
            <p className="mt-6 font-mono text-3xl font-medium tracking-[-0.04em] text-zinc-100">
              {loading ? "—" : criticalAlerts}
            </p>
          </article>
  
        </div>
  
  
        {/* =====================================================
            DEVICE STATUS + ALERTS
            ===================================================== */}
  
        <div className="grid gap-5 xl:grid-cols-2">
  
          {/* Device status */}
  
          <article
            className="
              overflow-hidden
              rounded-xl
              border
              border-zinc-800/80
              bg-zinc-900/60
            "
          >
            <div className="flex items-center justify-between border-b border-zinc-800/70 px-5 py-4">
              <div>
                <h3 className="text-sm font-semibold text-zinc-200">
                  Device status
                </h3>
  
                <p className="mt-0.5 text-xs text-zinc-600">
                  Current connectivity
                </p>
              </div>
  
              <Link
                to="/devices"
                className="text-xs font-medium text-zinc-500 transition-colors hover:text-zinc-200"
              >
                View all
              </Link>
            </div>
  
            {devices.length === 0 && !devicesLoading ? (
              <div className="flex min-h-[180px] flex-col items-center justify-center px-5 text-center">
                <Monitor
                  size={22}
                  className="text-zinc-700"
                />
  
                <p className="mt-3 text-sm text-zinc-500">
                  No devices registered.
                </p>
  
                <Link
                  to="/devices"
                  className="mt-2 text-xs text-emerald-500 hover:text-emerald-400"
                >
                  Add a device
                </Link>
              </div>
            ) : (
              <div className="divide-y divide-zinc-800/60">
                {devices.slice(0, 4).map((device) => {
                  const isOnline =
                    device.status === "online";
  
                  const isMaintenance =
                    device.status === "maintenance";
  
                  return (
                    <Link
                      key={device.id}
                      to={`/devices/${device.id}`}
                      className="
                        flex
                        items-center
                        justify-between
                        gap-4
                        px-5
                        py-4
                        transition-colors
                        hover:bg-zinc-900
                      "
                    >
                      <div className="flex min-w-0 items-center gap-3">
  
                        <div
                          className={`
                            flex
                            h-8
                            w-8
                            shrink-0
                            items-center
                            justify-center
                            rounded-lg
                            border
                            ${
                              isOnline
                                ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-400"
                                : isMaintenance
                                  ? "border-amber-500/20 bg-amber-500/10 text-amber-400"
                                  : "border-red-500/20 bg-red-500/10 text-red-400"
                            }
                          `}
                        >
                          {isOnline ? (
                            <Wifi size={14} />
                          ) : (
                            <WifiOff size={14} />
                          )}
                        </div>
  
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-zinc-200">
                            {device.name}
                          </p>
  
                          <p className="mt-0.5 truncate font-mono text-[10px] text-zinc-600">
                            {device.device_id}
                          </p>
                        </div>
  
                      </div>
  
                      <div className="flex shrink-0 items-center gap-2">
  
                        <span
                          className={`
                            text-[10px]
                            font-semibold
                            uppercase
                            tracking-[0.1em]
                            ${
                              isOnline
                                ? "text-emerald-400"
                                : isMaintenance
                                  ? "text-amber-400"
                                  : "text-red-400"
                            }
                          `}
                        >
                          {device.status}
                        </span>
  
                      </div>
                    </Link>
                  );
                })}
              </div>
            )}
          </article>
  
  
          {/* Active alerts */}
  
          <article
            className="
              overflow-hidden
              rounded-xl
              border
              border-zinc-800/80
              bg-zinc-900/60
            "
          >
            <div className="flex items-center justify-between border-b border-zinc-800/70 px-5 py-4">
              <div>
                <h3 className="text-sm font-semibold text-zinc-200">
                  Active alerts
                </h3>
  
                <p className="mt-0.5 text-xs text-zinc-600">
                  Requires attention
                </p>
              </div>
  
              <Link
                to="/alerts"
                className="text-xs font-medium text-zinc-500 transition-colors hover:text-zinc-200"
              >
                View all
              </Link>
            </div>
  
            {recentAlerts.length === 0 && !alertsLoading ? (
              <div className="flex min-h-[180px] flex-col items-center justify-center px-5 text-center">
                <CheckCircle2
                  size={22}
                  className="text-emerald-500"
                />
  
                <p className="mt-3 text-sm font-medium text-zinc-300">
                  All systems clear
                </p>
  
                <p className="mt-1 text-xs text-zinc-600">
                  No open alerts require your attention.
                </p>
              </div>
            ) : (
              <div className="divide-y divide-zinc-800/60">
                {recentAlerts.map((alert) => {
                  const classes =
                    getSeverityClasses(
                      alert.severity,
                    );
  
                  return (
                    <Link
                      key={alert.id}
                      to="/alerts"
                      className="
                        flex
                        gap-3
                        px-5
                        py-4
                        transition-colors
                        hover:bg-zinc-900
                      "
                    >
                      <div
                        className={`
                          flex
                          h-8
                          w-8
                          shrink-0
                          items-center
                          justify-center
                          rounded-lg
                          border
                          ${classes.icon}
                        `}
                      >
                        <AlertTriangle size={14} />
                      </div>
  
                      <div className="min-w-0 flex-1">
  
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-sm font-medium text-zinc-200">
                            {alert.title}
                          </p>
  
                          <span
                            className={`
                              rounded-md
                              border
                              px-1.5
                              py-0.5
                              text-[9px]
                              font-bold
                              uppercase
                              tracking-[0.08em]
                              ${classes.badge}
                            `}
                          >
                            {alert.severity}
                          </span>
                        </div>
  
                        <p className="mt-1 truncate text-xs text-zinc-500">
                          {alert.message}
                        </p>
  
                        <div className="mt-2 flex items-center gap-2 text-[10px] text-zinc-700">
                          <span>
                            Device #{alert.device_id}
                          </span>
  
                          <span>•</span>
  
                          <span>
                            {formatRelativeTime(
                              alert.created_at,
                            )}
                          </span>
                        </div>
  
                      </div>
                    </Link>
                  );
                })}
              </div>
            )}
          </article>
  
        </div>
      </section>
    );
  }
  
  export default OperationsOverview;