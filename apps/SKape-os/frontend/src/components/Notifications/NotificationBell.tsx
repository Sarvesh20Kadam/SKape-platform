import {
    AlertTriangle,
    Bell,
    CheckCircle2,
    CircleAlert,
    ShieldAlert,
    X,
  } from "lucide-react";
  
  import { useEffect, useRef, useState } from "react";
  import { useNavigate } from "react-router-dom";
  
  import { useAlerts } from "../../features/alerts/hooks/useAlerts";
  import type { AlertSeverity } from "../../features/alerts/types/alert.types";
  
  function severityIcon(severity: AlertSeverity) {
    if (severity === "critical") {
      return (
        <ShieldAlert
          size={15}
          strokeWidth={1.8}
        />
      );
    }
  
    if (severity === "warning") {
      return (
        <AlertTriangle
          size={15}
          strokeWidth={1.8}
        />
      );
    }
  
    return (
      <CircleAlert
        size={15}
        strokeWidth={1.8}
      />
    );
  }
  
  function severityClass(severity: AlertSeverity) {
    if (severity === "critical") {
      return "border-red-500/20 bg-red-500/10 text-red-400";
    }
  
    if (severity === "warning") {
      return "border-amber-500/20 bg-amber-500/10 text-amber-400";
    }
  
    return "border-sky-500/20 bg-sky-500/10 text-sky-400";
  }
  
  function relativeTime(value: string) {
    const diff =
      Date.now() - new Date(value).getTime();
  
    const seconds = Math.max(
      0,
      Math.floor(diff / 1000),
    );
  
    if (seconds < 60) {
      return `${seconds}s ago`;
    }
  
    const minutes = Math.floor(
      seconds / 60,
    );
  
    if (minutes < 60) {
      return `${minutes}m ago`;
    }
  
    const hours = Math.floor(
      minutes / 60,
    );
  
    if (hours < 24) {
      return `${hours}h ago`;
    }
  
    const days = Math.floor(
      hours / 24,
    );
  
    return `${days}d ago`;
  }
  
  function NotificationBell() {
    const navigate = useNavigate();
  
    const [open, setOpen] =
      useState(false);
  
    const containerRef =
      useRef<HTMLDivElement>(null);
  
    const {
      alerts,
      loading,
    } = useAlerts(true);
  
    const openAlerts =
      alerts.filter(
        (alert) => !alert.is_resolved,
      );
  
    const visibleAlerts =
      openAlerts.slice(0, 5);
  
    useEffect(() => {
      if (!open) {
        return;
      }
  
      const handlePointerDown = (
        event: MouseEvent,
      ) => {
        const target =
          event.target as Node;
  
        if (
          containerRef.current &&
          !containerRef.current.contains(
            target,
          )
        ) {
          setOpen(false);
        }
      };
  
      const handleKeyDown = (
        event: KeyboardEvent,
      ) => {
        if (event.key === "Escape") {
          setOpen(false);
        }
      };
  
      document.addEventListener(
        "mousedown",
        handlePointerDown,
      );
  
      document.addEventListener(
        "keydown",
        handleKeyDown,
      );
  
      return () => {
        document.removeEventListener(
          "mousedown",
          handlePointerDown,
        );
  
        document.removeEventListener(
          "keydown",
          handleKeyDown,
        );
      };
    }, [open]);
  
    const handleViewAll = () => {
      setOpen(false);
      navigate("/alerts");
    };
  
    return (
      <div
        ref={containerRef}
        className="relative"
      >
        <button
          type="button"
          aria-label="Notifications"
          aria-expanded={open}
          onClick={() =>
            setOpen((current) => !current)
          }
          className="
            relative
            flex
            h-9
            w-9
            items-center
            justify-center
            rounded-lg
            border
            border-transparent
            text-zinc-500
            transition-colors
            hover:border-zinc-800
            hover:bg-zinc-900
            hover:text-zinc-200
          "
        >
          <Bell
            size={17}
            strokeWidth={1.8}
          />
  
          {openAlerts.length > 0 && (
            <span
              aria-hidden="true"
              className="
                absolute
                right-2
                top-2
                h-1.5
                w-1.5
                rounded-full
                bg-emerald-500
              "
            />
          )}
        </button>
  
        {open && (
          <div
            className="
              absolute
              right-0
              top-12
              z-50
              w-[min(360px,calc(100vw-2rem))]
              overflow-hidden
              rounded-xl
              border
              border-zinc-800
              bg-zinc-950
              shadow-2xl
              shadow-black/40
            "
          >
            <div className="flex items-center justify-between border-b border-zinc-800/80 px-4 py-3">
              <div>
                <h2 className="text-sm font-semibold text-zinc-100">
                  Notifications
                </h2>
  
                <p className="mt-0.5 text-[11px] text-zinc-600">
                  {openAlerts.length} open{" "}
                  {openAlerts.length === 1
                    ? "alert"
                    : "alerts"}
                </p>
              </div>
  
              <button
                type="button"
                aria-label="Close notifications"
                onClick={() =>
                  setOpen(false)
                }
                className="
                  flex
                  h-7
                  w-7
                  items-center
                  justify-center
                  rounded-md
                  text-zinc-600
                  transition-colors
                  hover:bg-zinc-900
                  hover:text-zinc-300
                "
              >
                <X size={15} />
              </button>
            </div>
  
            {loading &&
              openAlerts.length === 0 && (
                <div className="space-y-2 p-3">
                  {[1, 2, 3].map(
                    (item) => (
                      <div
                        key={item}
                        className="
                          h-16
                          animate-pulse
                          rounded-lg
                          bg-zinc-900
                        "
                      />
                    ),
                  )}
                </div>
              )}
  
            {!loading &&
              visibleAlerts.length === 0 && (
                <div className="flex flex-col items-center px-5 py-10 text-center">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full border border-emerald-500/20 bg-emerald-500/10 text-emerald-400">
                    <CheckCircle2
                      size={18}
                    />
                  </div>
  
                  <p className="mt-3 text-sm font-semibold text-zinc-300">
                    All clear
                  </p>
  
                  <p className="mt-1 text-xs text-zinc-600">
                    No open alerts require
                    your attention.
                  </p>
                </div>
              )}
  
            {visibleAlerts.length > 0 && (
              <div className="max-h-[360px] overflow-y-auto p-2">
                {visibleAlerts.map(
                  (alert) => (
                    <button
                      key={alert.id}
                      type="button"
                      onClick={handleViewAll}
                      className="
                        flex
                        w-full
                        gap-3
                        rounded-lg
                        p-3
                        text-left
                        transition-colors
                        hover:bg-zinc-900
                      "
                    >
                      <span
                        className={`
                          mt-0.5
                          flex
                          h-7
                          w-7
                          shrink-0
                          items-center
                          justify-center
                          rounded-md
                          border
                          ${severityClass(
                            alert.severity,
                          )}
                        `}
                      >
                        {severityIcon(
                          alert.severity,
                        )}
                      </span>
  
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-xs font-semibold text-zinc-200">
                          {alert.title}
                        </span>
  
                        <span className="mt-1 block truncate text-[11px] text-zinc-500">
                          {alert.message}
                        </span>
  
                        <span className="mt-1.5 block text-[10px] text-zinc-700">
                          Device #{alert.device_id}
                          {" · "}
                          {relativeTime(
                            alert.created_at,
                          )}
                        </span>
                      </span>
                    </button>
                  ),
                )}
              </div>
            )}
  
            <div className="border-t border-zinc-800/80 p-2">
              <button
                type="button"
                onClick={handleViewAll}
                className="
                  flex
                  w-full
                  items-center
                  justify-center
                  rounded-lg
                  px-3
                  py-2.5
                  text-xs
                  font-semibold
                  text-zinc-400
                  transition-colors
                  hover:bg-zinc-900
                  hover:text-zinc-100
                "
              >
                View all alerts →
              </button>
            </div>
          </div>
        )}
      </div>
    );
  }
  
  export default NotificationBell;