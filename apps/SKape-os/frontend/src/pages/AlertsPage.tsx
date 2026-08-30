import {
    AlertTriangle,
    CheckCircle2,
    CircleAlert,
    Clock3,
    RefreshCw,
    ShieldAlert,
  } from "lucide-react";
  
  import { useState } from "react";
  
  import DashboardLayout from "../components/Layout/DashboardLayout";
  
  import { useAlerts } from "../features/alerts/hooks/useAlerts";
  
  import type {
    AlertSeverity,
  } from "../features/alerts/types/alert.types";
  
  
  type AlertFilter =
    | "all"
    | "open"
    | "resolved";
  
  
  function formatDate(
    value: string,
  ) {
    const date = new Date(value);
  
    return date.toLocaleString(
      undefined,
      {
        dateStyle: "medium",
        timeStyle: "short",
      },
    );
  }
  
  
  function severityIcon(
    severity: AlertSeverity,
  ) {
    if (severity === "critical") {
      return (
        <ShieldAlert
          size={18}
          strokeWidth={1.8}
        />
      );
    }
  
    if (severity === "warning") {
      return (
        <AlertTriangle
          size={18}
          strokeWidth={1.8}
        />
      );
    }
  
    return (
      <CircleAlert
        size={18}
        strokeWidth={1.8}
      />
    );
  }
  
  
  function severityClass(
    severity: AlertSeverity,
  ) {
    if (severity === "critical") {
      return {
        badge:
          "border-red-500/20 bg-red-500/10 text-red-400",
        icon:
          "border-red-500/20 bg-red-500/10 text-red-400",
      };
    }
  
    if (severity === "warning") {
      return {
        badge:
          "border-amber-500/20 bg-amber-500/10 text-amber-400",
        icon:
          "border-amber-500/20 bg-amber-500/10 text-amber-400",
      };
    }
  
    return {
      badge:
        "border-sky-500/20 bg-sky-500/10 text-sky-400",
      icon:
        "border-sky-500/20 bg-sky-500/10 text-sky-400",
    };
  }
  
  
  function AlertsPage() {
    const [filter, setFilter] =
      useState<AlertFilter>("all");
  
    const {
      alerts,
      loading,
      error,
      refresh,
      resolve,
    } = useAlerts(false);
  
    const filteredAlerts =
      alerts.filter((alert) => {
        if (filter === "open") {
          return !alert.is_resolved;
        }
  
        if (filter === "resolved") {
          return alert.is_resolved;
        }
  
        return true;
      });
  
    const openCount =
      alerts.filter(
        (alert) => !alert.is_resolved,
      ).length;
  
    const criticalCount =
      alerts.filter(
        (alert) =>
          alert.severity === "critical" &&
          !alert.is_resolved,
      ).length;
  
    const resolvedCount =
      alerts.filter(
        (alert) => alert.is_resolved,
      ).length;
  
    return (
      <DashboardLayout>
        <div className="mx-auto w-full max-w-[1400px]">
  
          {/* Header */}
  
          <div className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
  
            <div>
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-zinc-600">
                <span>Workspace</span>
                <span>/</span>
                <span className="text-zinc-500">
                  Alerts
                </span>
              </div>
  
              <h1 className="mt-3 text-2xl font-bold tracking-[-0.04em] text-zinc-100 sm:text-3xl">
                Alerts
              </h1>
  
              <p className="mt-2 max-w-2xl text-sm leading-6 text-zinc-500">
                Monitor device incidents and
                operational events across your
                workspace.
              </p>
            </div>
  
            <button
              type="button"
              onClick={() => void refresh(false)}
              disabled={loading}
              className="
                inline-flex
                h-10
                items-center
                justify-center
                gap-2
                rounded-lg
                border
                border-zinc-800
                bg-zinc-900
                px-4
                text-sm
                font-semibold
                text-zinc-300
                transition-colors
                hover:bg-zinc-800
                hover:text-zinc-100
                disabled:cursor-not-allowed
                disabled:opacity-50
              "
            >
              <RefreshCw
                size={15}
                className={
                  loading
                    ? "animate-spin"
                    : ""
                }
              />
  
              Refresh
            </button>
  
          </div>
  
  
          {/* Summary cards */}
  
          <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
  
            <SummaryCard
              label="Total alerts"
              value={alerts.length}
              icon={
                <CircleAlert
                  size={18}
                />
              }
            />
  
            <SummaryCard
              label="Open alerts"
              value={openCount}
              icon={
                <Clock3
                  size={18}
                />
              }
            />
  
            <SummaryCard
              label="Critical"
              value={criticalCount}
              icon={
                <ShieldAlert
                  size={18}
                />
              }
            />
  
            <SummaryCard
              label="Resolved"
              value={resolvedCount}
              icon={
                <CheckCircle2
                  size={18}
                />
              }
            />
  
          </div>
  
  
          {/* Filters */}
  
          <div className="mt-8 flex flex-wrap items-center gap-2 border-b border-zinc-800/80 pb-4">
  
            <FilterButton
              active={filter === "all"}
              onClick={() =>
                setFilter("all")
              }
            >
              All
            </FilterButton>
  
            <FilterButton
              active={filter === "open"}
              onClick={() =>
                setFilter("open")
              }
            >
              Open
            </FilterButton>
  
            <FilterButton
              active={
                filter === "resolved"
              }
              onClick={() =>
                setFilter("resolved")
              }
            >
              Resolved
            </FilterButton>
  
          </div>
  
  
          {/* Error */}
  
          {error && (
            <div className="mt-5 rounded-xl border border-red-500/20 bg-red-500/5 px-4 py-3 text-sm text-red-400">
              {error}
            </div>
          )}
  
  
          {/* Loading */}
  
          {loading && alerts.length === 0 && (
            <div className="mt-6 space-y-3">
  
              {[1, 2, 3].map(
                (item) => (
                  <div
                    key={item}
                    className="h-24 animate-pulse rounded-xl border border-zinc-800/70 bg-zinc-900/40"
                  />
                ),
              )}
  
            </div>
          )}
  
  
          {/* Empty */}
  
          {!loading &&
            filteredAlerts.length === 0 && (
              <div className="mt-6 flex min-h-[280px] flex-col items-center justify-center rounded-xl border border-dashed border-zinc-800 bg-zinc-950/40 px-6 text-center">
  
                <div className="flex h-12 w-12 items-center justify-center rounded-full border border-emerald-500/20 bg-emerald-500/10 text-emerald-400">
                  <CheckCircle2
                    size={22}
                  />
                </div>
  
                <h2 className="mt-4 text-sm font-semibold text-zinc-200">
                  No alerts found
                </h2>
  
                <p className="mt-1 max-w-md text-sm text-zinc-600">
                  There are no alerts matching
                  the selected filter.
                </p>
  
              </div>
            )}
  
  
          {/* Alert list */}
  
          {filteredAlerts.length > 0 && (
            <div className="mt-6 space-y-3">
  
              {filteredAlerts.map(
                (alert) => {
                  const classes =
                    severityClass(
                      alert.severity,
                    );
  
                  return (
                    <div
                      key={alert.id}
                      className="
                        rounded-xl
                        border
                        border-zinc-800/80
                        bg-zinc-900/40
                        p-5
                        transition-colors
                        hover:bg-zinc-900/70
                      "
                    >
  
                      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
  
                        <div className="flex min-w-0 gap-4">
  
                          <div
                            className={`
                              flex
                              h-10
                              w-10
                              shrink-0
                              items-center
                              justify-center
                              rounded-lg
                              border
                              ${classes.icon}
                            `}
                          >
                            {severityIcon(
                              alert.severity,
                            )}
                          </div>
  
  
                          <div className="min-w-0">
  
                            <div className="flex flex-wrap items-center gap-2">
  
                              <h2 className="text-sm font-semibold text-zinc-100">
                                {alert.title}
                              </h2>
  
                              <span
                                className={`
                                  rounded-md
                                  border
                                  px-2
                                  py-0.5
                                  text-[10px]
                                  font-bold
                                  uppercase
                                  tracking-[0.12em]
                                  ${classes.badge}
                                `}
                              >
                                {alert.severity}
                              </span>
  
                              {alert.is_resolved && (
                                <span className="rounded-md border border-emerald-500/20 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.12em] text-emerald-400">
                                  Resolved
                                </span>
                              )}
  
                            </div>
  
  
                            <p className="mt-2 text-sm leading-6 text-zinc-400">
                              {alert.message}
                            </p>
  
  
                            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-zinc-600">
  
                              <span>
                                Device #{alert.device_id}
                              </span>
  
                              <span>
                                {alert.alert_type}
                              </span>
  
                              <span>
                                {formatDate(
                                  alert.created_at,
                                )}
                              </span>
  
                            </div>
  
                          </div>
  
                        </div>
  
  
                        {!alert.is_resolved && (
                          <button
                            type="button"
                            onClick={() =>
                              void resolve(
                                alert.id,
                              )
                            }
                            className="
                              inline-flex
                              h-9
                              shrink-0
                              items-center
                              justify-center
                              gap-2
                              rounded-lg
                              border
                              border-zinc-700
                              px-3
                              text-xs
                              font-semibold
                              text-zinc-300
                              transition-colors
                              hover:border-emerald-500/40
                              hover:bg-emerald-500/10
                              hover:text-emerald-400
                            "
                          >
                            <CheckCircle2
                              size={14}
                            />
                            Resolve
                          </button>
                        )}
  
                      </div>
  
                    </div>
                  );
                },
              )}
  
            </div>
          )}
  
        </div>
      </DashboardLayout>
    );
  }
  
  
  type SummaryCardProps = {
    label: string;
    value: number;
    icon: React.ReactNode;
  };
  
  
  function SummaryCard({
    label,
    value,
    icon,
  }: SummaryCardProps) {
    return (
      <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-5">
  
        <div className="flex items-center justify-between">
  
          <span className="text-xs font-semibold uppercase tracking-[0.12em] text-zinc-600">
            {label}
          </span>
  
          <span className="text-zinc-600">
            {icon}
          </span>
  
        </div>
  
        <p className="mt-3 text-2xl font-bold tracking-[-0.04em] text-zinc-100">
          {value}
        </p>
  
      </div>
    );
  }
  
  
  type FilterButtonProps = {
    active: boolean;
    onClick: () => void;
    children: React.ReactNode;
  };
  
  
  function FilterButton({
    active,
    onClick,
    children,
  }: FilterButtonProps) {
    return (
      <button
        type="button"
        onClick={onClick}
        className={`
          rounded-lg
          px-3
          py-2
          text-xs
          font-semibold
          transition-colors
          ${
            active
              ? "bg-zinc-800 text-zinc-100"
              : "text-zinc-600 hover:bg-zinc-900 hover:text-zinc-300"
          }
        `}
      >
        {children}
      </button>
    );
  }
  
  
  export default AlertsPage;