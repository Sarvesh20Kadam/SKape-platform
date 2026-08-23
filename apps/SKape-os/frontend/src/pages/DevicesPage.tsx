import {
    useMemo,
    useState,
  } from "react";
  
  import {
    Boxes,
    Plus,
    Search,
    Wifi,
    WifiOff,
    Wrench,
  } from "lucide-react";
  
  import DashboardLayout from "../components/Layout/DashboardLayout";
  import CreateDeviceModal from "../components/devices/CreateDeviceModal";
  
  import { useDevices } from "../features/devices/hooks/useDevices";
  
  import type {
    CreateDevicePayload,
    DeviceStatus,
  } from "../features/devices/types/device.types";
  
  type StatusFilter =
    | "all"
    | DeviceStatus;
  
  const statusOptions: Array<{
    label: string;
    value: StatusFilter;
  }> = [
    {
      label: "All devices",
      value: "all",
    },
    {
      label: "Online",
      value: "online",
    },
    {
      label: "Offline",
      value: "offline",
    },
    {
      label: "Maintenance",
      value: "maintenance",
    },
  ];
  
  function DevicesPage() {
    const {
      devices,
      loading,
      creating,
      error,
      createDevice,
    } = useDevices();
  
    const [
      createModalOpen,
      setCreateModalOpen,
    ] = useState(false);
  
    const [search, setSearch] =
      useState("");
  
    const [status, setStatus] =
      useState<StatusFilter>("all");
  
    /*
     * =========================================================
     * FILTER DEVICES
     * =========================================================
     */
  
    const filteredDevices = useMemo(() => {
      const normalizedSearch =
        search.trim().toLowerCase();
  
      return devices.filter((device) => {
        const matchesSearch =
          normalizedSearch.length === 0 ||
          device.name
            .toLowerCase()
            .includes(normalizedSearch) ||
          device.device_id
            .toLowerCase()
            .includes(normalizedSearch) ||
          device.device_type
            .toLowerCase()
            .includes(normalizedSearch);
  
        const matchesStatus =
          status === "all" ||
          device.status === status;
  
        return (
          matchesSearch &&
          matchesStatus
        );
      });
    }, [
      devices,
      search,
      status,
    ]);
  
    /*
     * =========================================================
     * CREATE DEVICE
     * =========================================================
     */
  
    const handleCreateDevice = async (
      data: CreateDevicePayload,
    ) => {
      await createDevice(data);
  
      setCreateModalOpen(false);
    };
  
    /*
     * =========================================================
     * STATUS ICON
     * =========================================================
     */
  
    const getStatusIcon = (
      deviceStatus: DeviceStatus,
    ) => {
      if (deviceStatus === "online") {
        return (
          <Wifi
            size={14}
            strokeWidth={1.8}
          />
        );
      }
  
      if (deviceStatus === "maintenance") {
        return (
          <Wrench
            size={14}
            strokeWidth={1.8}
          />
        );
      }
  
      return (
        <WifiOff
          size={14}
          strokeWidth={1.8}
        />
      );
    };
  
    /*
     * =========================================================
     * STATUS STYLE
     * =========================================================
     */
  
    const getStatusClass = (
      deviceStatus: DeviceStatus,
    ) => {
      if (deviceStatus === "online") {
        return "bg-emerald-500/10 text-emerald-400";
      }
  
      if (deviceStatus === "maintenance") {
        return "bg-amber-500/10 text-amber-400";
      }
  
      return "bg-zinc-800 text-zinc-500";
    };
  
    return (
      <DashboardLayout>
        <section className="space-y-8">
  
          {/* ===================================================
              PAGE HEADER
              =================================================== */}
  
          <div className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
  
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-emerald-400">
                Workspace
              </p>
  
              <h1 className="mt-2 text-3xl font-bold tracking-[-0.04em] text-zinc-100">
                Devices
              </h1>
  
              <p className="mt-2 max-w-2xl text-sm leading-6 text-zinc-500">
                Monitor and manage connected devices across your organization.
              </p>
            </div>
  
            <button
              type="button"
              onClick={() =>
                setCreateModalOpen(true)
              }
              className="
                inline-flex
                h-10
                items-center
                justify-center
                gap-2
                rounded-lg
                bg-emerald-500
                px-4
                text-sm
                font-semibold
                text-zinc-950
                transition
                hover:bg-emerald-400
              "
            >
              <Plus
                size={17}
                strokeWidth={2}
              />
  
              Add device
            </button>
          </div>
  
          {/* ===================================================
              TOOLBAR
              =================================================== */}
  
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
  
            <div className="relative flex-1">
  
              <Search
                size={17}
                strokeWidth={1.8}
                className="
                  pointer-events-none
                  absolute
                  left-3
                  top-1/2
                  -translate-y-1/2
                  text-zinc-600
                "
              />
  
              <input
                type="text"
                value={search}
                onChange={(event) =>
                  setSearch(event.target.value)
                }
                placeholder="Search devices..."
                aria-label="Search devices"
                className="
                  h-10
                  w-full
                  rounded-lg
                  border
                  border-zinc-800
                  bg-zinc-950
                  pl-10
                  pr-4
                  text-sm
                  text-zinc-200
                  outline-none
                  placeholder:text-zinc-600
                  focus:border-zinc-700
                "
              />
            </div>
  
            <select
              value={status}
              onChange={(event) =>
                setStatus(
                  event.target.value as StatusFilter,
                )
              }
              aria-label="Filter devices by status"
              className="
                h-10
                rounded-lg
                border
                border-zinc-800
                bg-zinc-950
                px-3
                text-sm
                text-zinc-400
                outline-none
                focus:border-zinc-700
              "
            >
              {statusOptions.map((option) => (
                <option
                  key={option.value}
                  value={option.value}
                >
                  {option.label}
                </option>
              ))}
            </select>
          </div>
  
          {/* ===================================================
              CONTENT
              =================================================== */}
  
          <div className="overflow-hidden rounded-xl border border-zinc-800/80 bg-zinc-950">
  
            {loading ? (
              <div className="flex min-h-[280px] items-center justify-center">
  
                <p className="text-sm text-zinc-600">
                  Loading devices...
                </p>
  
              </div>
            ) : error ? (
              <div className="flex min-h-[280px] items-center justify-center px-6">
  
                <p className="text-sm text-red-400">
                  {error}
                </p>
  
              </div>
            ) : filteredDevices.length === 0 ? (
              <div className="flex min-h-[280px] flex-col items-center justify-center px-6 text-center">
  
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-zinc-900 text-zinc-600">
  
                  <Boxes
                    size={22}
                    strokeWidth={1.6}
                  />
  
                </div>
  
                <h2 className="mt-4 text-sm font-semibold text-zinc-300">
  
                  {devices.length === 0
                    ? "No devices yet"
                    : "No devices found"}
  
                </h2>
  
                <p className="mt-1 max-w-sm text-xs leading-5 text-zinc-600">
  
                  {devices.length === 0
                    ? "Connected devices will appear here once they are registered."
                    : "Try changing your search or status filter."}
  
                </p>
  
              </div>
            ) : (
              <div className="overflow-x-auto">
  
                <table className="w-full min-w-[800px]">
  
                  <thead>
  
                    <tr className="border-b border-zinc-800/80 text-left">
  
                      <th className="px-5 py-4 text-[10px] font-bold uppercase tracking-[0.14em] text-zinc-600">
                        Device
                      </th>
  
                      <th className="px-5 py-4 text-[10px] font-bold uppercase tracking-[0.14em] text-zinc-600">
                        Device ID
                      </th>
  
                      <th className="px-5 py-4 text-[10px] font-bold uppercase tracking-[0.14em] text-zinc-600">
                        Type
                      </th>
  
                      <th className="px-5 py-4 text-[10px] font-bold uppercase tracking-[0.14em] text-zinc-600">
                        Asset
                      </th>
  
                      <th className="px-5 py-4 text-[10px] font-bold uppercase tracking-[0.14em] text-zinc-600">
                        Status
                      </th>
  
                    </tr>
  
                  </thead>
  
                  <tbody>
  
                    {filteredDevices.map((device) => (
  
                      <tr
                        key={device.id}
                        className="
                          border-b
                          border-zinc-900
                          transition-colors
                          last:border-b-0
                          hover:bg-zinc-900/40
                        "
                      >
  
                        {/* DEVICE */}
  
                        <td className="px-5 py-4">
  
                          <div className="flex items-center gap-3">
  
                            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-zinc-900 text-zinc-500">
  
                              <Boxes
                                size={17}
                                strokeWidth={1.7}
                              />
  
                            </div>
  
                            <div>
  
                              <p className="text-sm font-semibold text-zinc-200">
                                {device.name}
                              </p>
  
                              <p className="mt-0.5 text-xs text-zinc-600">
                                Device #{device.id}
                              </p>
  
                            </div>
  
                          </div>
  
                        </td>
  
                        {/* DEVICE ID */}
  
                        <td className="px-5 py-4">
  
                          <span className="font-mono text-xs text-zinc-400">
                            {device.device_id}
                          </span>
  
                        </td>
  
                        {/* TYPE */}
  
                        <td className="px-5 py-4">
  
                          <span className="text-sm text-zinc-400">
                            {device.device_type}
                          </span>
  
                        </td>
  
                        {/* ASSET */}
  
                        <td className="px-5 py-4">
  
                          <span className="text-sm text-zinc-500">
  
                            {device.asset_id
                              ? `Asset #${device.asset_id}`
                              : "Unassigned"}
  
                          </span>
  
                        </td>
  
                        {/* STATUS */}
  
                        <td className="px-5 py-4">
  
                          <span
                            className={`
                              inline-flex
                              items-center
                              gap-1.5
                              rounded-md
                              px-2.5
                              py-1
                              text-xs
                              font-semibold
                              ${getStatusClass(device.status)}
                            `}
                          >
  
                            {getStatusIcon(
                              device.status,
                            )}
  
                            {device.status
                              .charAt(0)
                              .toUpperCase() +
                              device.status.slice(1)}
  
                          </span>
  
                        </td>
  
                      </tr>
  
                    ))}
  
                  </tbody>
  
                </table>
  
              </div>
            )}
  
          </div>
  
        </section>
  
        {/* =====================================================
            CREATE DEVICE MODAL
            ===================================================== */}
  
        <CreateDeviceModal
          open={createModalOpen}
          creating={creating}
          onClose={() =>
            setCreateModalOpen(false)
          }
          onSubmit={handleCreateDevice}
        />
  
      </DashboardLayout>
    );
  }
  
  export default DevicesPage;