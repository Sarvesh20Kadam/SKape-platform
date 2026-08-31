import {
  Bell,
  Menu,
  Search,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getAlerts } from "../../features/alerts/services/alert.service";

type TopbarProps = {
  onMenuClick: () => void;
};

function Topbar({
  onMenuClick,
}: TopbarProps) {
  const navigate = useNavigate();

  const [openAlertCount, setOpenAlertCount] =
    useState(0);

  useEffect(() => {
    let mounted = true;

    const loadOpenAlerts = async () => {
      try {
        const alerts = await getAlerts(
          true,
          50,
        );

        if (mounted) {
          setOpenAlertCount(alerts.length);
        }
      } catch (error) {
        console.error(
          "Failed to load notification count:",
          error,
        );
      }
    };

    void loadOpenAlerts();

    const intervalId =
      window.setInterval(
        () => {
          void loadOpenAlerts();
        },
        5000,
      );

    return () => {
      mounted = false;
      window.clearInterval(
        intervalId,
      );
    };
  }, []);

  return (
    <header className="sticky top-0 z-30 flex h-[72px] shrink-0 items-center justify-between border-b border-zinc-800/70 bg-zinc-950/90 px-4 backdrop-blur-xl sm:px-6 lg:px-8">

      {/* Mobile menu */}

      <button
        type="button"
        aria-label="Open navigation"
        onClick={onMenuClick}
        className="
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
          lg:hidden
        "
      >
        <Menu
          size={19}
          strokeWidth={1.8}
        />
      </button>


      {/* Desktop search */}

      <div className="relative hidden w-full max-w-sm md:block">

        <Search
          size={16}
          strokeWidth={1.8}
          className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-600"
        />

        <input
          type="search"
          placeholder="Search anything..."
          aria-label="Search"
          className="
            h-9
            w-full
            rounded-lg
            border
            border-zinc-800
            bg-zinc-900/50
            pl-10
            pr-12
            text-sm
            text-zinc-200
            outline-none
            placeholder:text-zinc-600
            transition-all
            focus:border-zinc-700
            focus:bg-zinc-900
            focus:ring-1
            focus:ring-emerald-500/20
          "
        />

        <span className="pointer-events-none absolute right-3 top-1/2 hidden -translate-y-1/2 rounded border border-zinc-800 px-1.5 py-0.5 font-mono text-[10px] text-zinc-600 sm:block">
          /
        </span>

      </div>


      {/* Mobile brand */}

      <div className="absolute left-1/2 -translate-x-1/2 lg:hidden">
        <span className="text-[16px] font-bold tracking-[-0.045em] text-zinc-100">
          SKape
        </span>
      </div>


      {/* Right controls */}

      <div className="ml-auto flex items-center gap-2 sm:gap-3">

        {/* Notifications */}

        <button
          type="button"
          aria-label={
            openAlertCount > 0
              ? `${openAlertCount} open alerts`
              : "Notifications"
          }
          onClick={() =>
            navigate("/alerts")
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

          {openAlertCount > 0 && (
            <span
              aria-hidden="true"
              className="
                absolute
                -right-1
                -top-1
                flex
                min-h-4
                min-w-4
                items-center
                justify-center
                rounded-full
                border
                border-zinc-950
                bg-red-500
                px-1
                text-[9px]
                font-bold
                leading-none
                text-white
              "
            >
              {openAlertCount > 99
                ? "99+"
                : openAlertCount}
            </span>
          )}

        </button>


        <div className="hidden h-6 w-px bg-zinc-800 sm:block" />


        {/* Account */}

        <button
          type="button"
          className="group flex items-center gap-2 rounded-lg px-1.5 py-1 transition-colors hover:bg-zinc-900"
        >
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-emerald-500 text-xs font-bold text-zinc-950">
            S
          </span>

          <div className="hidden text-left sm:block">

            <p className="text-xs font-semibold text-zinc-300">
              Account
            </p>

            <p className="text-[10px] text-zinc-600">
              Workspace member
            </p>

          </div>

        </button>

      </div>

    </header>
  );
}

export default Topbar;