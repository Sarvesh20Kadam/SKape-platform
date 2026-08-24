import {
    ArrowLeft,
    Cpu,
    Database,
    Link2,
    MapPin,
    Radio,
    RefreshCw,
    Server,
  } from "lucide-react";
  import { useEffect, useState } from "react";
  import { useNavigate, useParams } from "react-router-dom";
  
  import DashboardLayout from "../components/Layout/DashboardLayout";
  import { getDevice } from "../features/devices/services/device.service";
  
  import type { Device } from "../features/devices/types/device.types";
  
  function DeviceDetailPage() {
    const navigate = useNavigate();
    const { deviceId } = useParams<{ deviceId: string }>();
  
    const [device, setDevice] = useState<Device | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
  
    const loadDevice = async () => {
      if (!deviceId) {
        setError("Device ID is missing.");
        setLoading(false);
        return;
      }
  
      try {
        setLoading(true);
        setError(null);
  
        const data = await getDevice(Number(deviceId));
        setDevice(data);
      } catch (err: any) {
        console.error("Failed to load device:", err);
  
        const detail =
          err?.response?.data?.detail;
  
        setError(
          detail ||
            "Unable to load device. Please try again.",
        );
      } finally {
        setLoading(false);
      }
    };
  
    useEffect(() => {
      void loadDevice();
    }, [deviceId]);
  
    const formatDate = (
      value: string | null,
    ) => {
      if (!value) {
        return "Never";
      }
  
      return new Date(value).toLocaleString();
    };
  
    const statusLabel = device?.status
      ? device.status.charAt(0).toUpperCase() +
        device.status.slice(1)
      : "Unknown";
  
    return (
      <DashboardLayout>
        <section className="space-y-8">
  
          {/* HEADER */}
  
          <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
  
            <div>
              <button
                type="button"
                onClick={() => navigate("/devices")}
                className="
                  mb-5
                  inline-flex
                  items-center
                  gap-2
                  text-sm
                  text-zinc-500
                  transition
                  hover:text-zinc-200
                "
              >
                <ArrowLeft size={16} />
                Back to devices
              </button>
  
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-emerald-400">
                Device
              </p>
  
              <h1 className="mt-2 text-3xl font-bold tracking-[-0.04em] text-zinc-100">
                {loading
                  ? "Loading..."
                  : device?.name || "Device"}
              </h1>
  
              <p className="mt-2 text-sm text-zinc-500">
                Device ID:{" "}
                <span className="font-mono text-zinc-400">
                  {device?.device_id || "—"}
                </span>
              </p>
            </div>
  
            {!loading && device && (
              <div
                className={`
                  inline-flex
                  items-center
                  gap-2
                  rounded-full
                  border
                  px-3
                  py-1.5
                  text-xs
                  font-semibold
                  ${
                    device.status === "online"
                      ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-400"
                      : device.status === "maintenance"
                        ? "border-amber-500/20 bg-amber-500/10 text-amber-400"
                        : "border-zinc-700 bg-zinc-900 text-zinc-400"
                  }
                `}
              >
                <span
                  className={`
                    h-1.5
                    w-1.5
                    rounded-full
                    ${
                      device.status === "online"
                        ? "bg-emerald-400"
                        : device.status === "maintenance"
                          ? "bg-amber-400"
                          : "bg-zinc-500"
                    }
                  `}
                />
  
                {statusLabel}
              </div>
            )}
          </div>
  
          {/* LOADING */}
  
          {loading && (
            <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-8 text-center">
              <RefreshCw
                className="mx-auto animate-spin text-zinc-500"
                size={22}
              />
  
              <p className="mt-3 text-sm text-zinc-500">
                Loading device information...
              </p>
            </div>
          )}
  
          {/* ERROR */}
  
          {!loading && error && (
            <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-6">
              <p className="text-sm font-semibold text-red-400">
                Unable to load device
              </p>
  
              <p className="mt-1 text-sm text-zinc-500">
                {error}
              </p>
  
              <button
                type="button"
                onClick={() => void loadDevice()}
                className="
                  mt-4
                  inline-flex
                  items-center
                  gap-2
                  rounded-lg
                  border
                  border-zinc-800
                  bg-zinc-900
                  px-3
                  py-2
                  text-sm
                  font-medium
                  text-zinc-300
                  hover:bg-zinc-800
                "
              >
                <RefreshCw size={15} />
                Retry
              </button>
            </div>
          )}
  
          {/* DEVICE */}
  
          {!loading && !error && device && (
            <>
              {/* OVERVIEW CARDS */}
  
              <div className="grid gap-4 md:grid-cols-3">
  
                <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-5">
                  <div className="flex items-center gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-zinc-900 text-zinc-400">
                      <Cpu size={18} />
                    </div>
  
                    <div>
                      <p className="text-xs text-zinc-500">
                        Device type
                      </p>
  
                      <p className="mt-1 text-sm font-semibold text-zinc-200">
                        {device.device_type}
                      </p>
                    </div>
                  </div>
                </div>
  
                <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-5">
                  <div className="flex items-center gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-zinc-900 text-zinc-400">
                      <Radio size={18} />
                    </div>
  
                    <div>
                      <p className="text-xs text-zinc-500">
                        Current status
                      </p>
  
                      <p className="mt-1 text-sm font-semibold text-zinc-200">
                        {statusLabel}
                      </p>
                    </div>
                  </div>
                </div>
  
                <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-5">
                  <div className="flex items-center gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-zinc-900 text-zinc-400">
                      <Server size={18} />
                    </div>
  
                    <div>
                      <p className="text-xs text-zinc-500">
                        Active
                      </p>
  
                      <p className="mt-1 text-sm font-semibold text-zinc-200">
                        {device.is_active
                          ? "Yes"
                          : "No"}
                      </p>
                    </div>
                  </div>
                </div>
  
              </div>
  
              {/* DETAILS */}
  
              <div className="grid gap-6 lg:grid-cols-2">
  
                <div className="rounded-xl border border-zinc-800 bg-zinc-950">
  
                  <div className="border-b border-zinc-800 px-6 py-5">
                    <h2 className="text-sm font-semibold text-zinc-100">
                      Device information
                    </h2>
  
                    <p className="mt-1 text-xs text-zinc-500">
                      Core information registered in SKape OS.
                    </p>
                  </div>
  
                  <div className="divide-y divide-zinc-800/70">
  
                    <div className="flex items-center justify-between px-6 py-4">
                      <span className="text-sm text-zinc-500">
                        Device ID
                      </span>
  
                      <span className="font-mono text-sm text-zinc-300">
                        {device.device_id}
                      </span>
                    </div>
  
                    <div className="flex items-center justify-between px-6 py-4">
                      <span className="text-sm text-zinc-500">
                        Type
                      </span>
  
                      <span className="text-sm text-zinc-300">
                        {device.device_type}
                      </span>
                    </div>
  
                    <div className="flex items-center justify-between px-6 py-4">
                      <span className="text-sm text-zinc-500">
                        Organization
                      </span>
  
                      <span className="text-sm text-zinc-300">
                        #{device.organization_id}
                      </span>
                    </div>
  
                    <div className="flex items-center justify-between px-6 py-4">
                      <span className="text-sm text-zinc-500">
                        Linked asset
                      </span>
  
                      <span className="inline-flex items-center gap-2 text-sm text-zinc-300">
                        <Link2 size={14} />
  
                        {device.asset_id
                          ? `Asset #${device.asset_id}`
                          : "Not linked"}
                      </span>
                    </div>
  
                  </div>
                </div>
  
                {/* HEALTH / CONNECTIVITY */}
  
                <div className="rounded-xl border border-zinc-800 bg-zinc-950">
  
                  <div className="border-b border-zinc-800 px-6 py-5">
                    <h2 className="text-sm font-semibold text-zinc-100">
                      Connectivity
                    </h2>
  
                    <p className="mt-1 text-xs text-zinc-500">
                      Current device communication information.
                    </p>
                  </div>
  
                  <div className="space-y-5 p-6">
  
                    <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-4">
                      <div className="flex items-center gap-3">
                        <Radio
                          size={18}
                          className={
                            device.status === "online"
                              ? "text-emerald-400"
                              : "text-zinc-500"
                          }
                        />
  
                        <div>
                          <p className="text-sm font-semibold text-zinc-200">
                            Connection status
                          </p>
  
                          <p className="mt-1 text-xs text-zinc-500">
                            {device.status === "online"
                              ? "Device is currently marked online."
                              : "No active connection signal has been recorded yet."}
                          </p>
                        </div>
                      </div>
                    </div>
  
                    <div className="flex items-center gap-3">
                      <MapPin
                        size={17}
                        className="text-zinc-500"
                      />
  
                      <div>
                        <p className="text-xs text-zinc-500">
                          Last seen
                        </p>
  
                        <p className="mt-1 text-sm text-zinc-300">
                          {formatDate(
                            device.last_seen_at,
                          )}
                        </p>
                      </div>
                    </div>
  
                    <div className="flex items-center gap-3">
                      <Database
                        size={17}
                        className="text-zinc-500"
                      />
  
                      <div>
                        <p className="text-xs text-zinc-500">
                          Registered
                        </p>
  
                        <p className="mt-1 text-sm text-zinc-300">
                          {formatDate(
                            device.created_at,
                          )}
                        </p>
                      </div>
                    </div>
  
                  </div>
                </div>
  
              </div>
            </>
          )}
        </section>
      </DashboardLayout>
    );
  }
  
  export default DeviceDetailPage;