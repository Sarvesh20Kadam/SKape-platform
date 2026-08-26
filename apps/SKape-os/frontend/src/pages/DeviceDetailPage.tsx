import {
  ArrowLeft,
  Cpu,
  Database,
  Link2,
  MapPin,
  Radio,
  RefreshCw,
  Server,
  Thermometer,
  Activity,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useState,
} from "react";
import {
  useNavigate,
  useParams,
} from "react-router-dom";

import DashboardLayout from "../components/Layout/DashboardLayout";

import { getDevice } from "../features/devices/services/device.service";

import {
  getLatestTelemetry,
  type DeviceTelemetry,
} from "../features/devices/services/telemetry.service";

import type { Device } from "../features/devices/types/device.types";

const DEVICE_REFRESH_INTERVAL = 5000;
const TELEMETRY_REFRESH_INTERVAL = 5000;

function DeviceDetailPage() {
  const navigate = useNavigate();

  const { deviceId } =
    useParams<{ deviceId: string }>();

  const numericDeviceId = Number(deviceId);

  const [device, setDevice] =
    useState<Device | null>(null);

  const [telemetry, setTelemetry] =
    useState<DeviceTelemetry | null>(null);

  const [loading, setLoading] =
    useState(true);

  const [telemetryLoading, setTelemetryLoading] =
    useState(true);

  const [error, setError] =
    useState<string | null>(null);

  const [telemetryError, setTelemetryError] =
    useState<string | null>(null);

  /*
   * --------------------------------------------------------
   * LOAD DEVICE
   * --------------------------------------------------------
   */

  const loadDevice = useCallback(
    async (showLoading = true) => {
      if (!deviceId || Number.isNaN(numericDeviceId)) {
        setError("Device ID is missing.");
        setLoading(false);
        return;
      }

      try {
        if (showLoading) {
          setLoading(true);
          setError(null);
        }

        const data = await getDevice(
          numericDeviceId,
        );

        setDevice(data);
        setError(null);
      } catch (err: any) {
        console.error(
          "Failed to load device:",
          err,
        );

        const detail =
          err?.response?.data?.detail;

        if (showLoading) {
          setError(
            detail ||
              "Unable to load device. Please try again.",
          );
        }
      } finally {
        if (showLoading) {
          setLoading(false);
        }
      }
    },
    [deviceId, numericDeviceId],
  );

  /*
   * --------------------------------------------------------
   * LOAD TELEMETRY
   * --------------------------------------------------------
   *
   * Background refresh does NOT touch the main loading
   * state. This prevents page blinking/stuttering.
   */

  const loadTelemetry = useCallback(
    async (showLoading = true) => {
      if (
        !deviceId ||
        Number.isNaN(numericDeviceId)
      ) {
        setTelemetryLoading(false);
        return;
      }

      try {
        if (showLoading) {
          setTelemetryLoading(true);
        }

        const data =
          await getLatestTelemetry(
            numericDeviceId,
          );

        setTelemetry(data);
        setTelemetryError(null);
      } catch (err: any) {
        console.error(
          "Failed to load telemetry:",
          err,
        );

        const status =
          err?.response?.status;

        if (status === 404) {
          setTelemetry(null);
          setTelemetryError(
            "No telemetry available yet.",
          );
        } else if (showLoading) {
          setTelemetryError(
            "Unable to load telemetry.",
          );
        }
      } finally {
        if (showLoading) {
          setTelemetryLoading(false);
        }
      }
    },
    [deviceId, numericDeviceId],
  );

  /*
   * --------------------------------------------------------
   * INITIAL LOAD
   * --------------------------------------------------------
   */

  useEffect(() => {
    void loadDevice(true);
    void loadTelemetry(true);
  }, [loadDevice, loadTelemetry]);

  /*
   * --------------------------------------------------------
   * DEVICE STATUS POLLING
   * --------------------------------------------------------
   */

  useEffect(() => {
    if (!deviceId) {
      return;
    }

    const intervalId =
      window.setInterval(() => {
        void loadDevice(false);
      }, DEVICE_REFRESH_INTERVAL);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [deviceId, loadDevice]);

  /*
   * --------------------------------------------------------
   * TELEMETRY POLLING
   * --------------------------------------------------------
   */

  useEffect(() => {
    if (!deviceId) {
      return;
    }

    const intervalId =
      window.setInterval(() => {
        void loadTelemetry(false);
      }, TELEMETRY_REFRESH_INTERVAL);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [deviceId, loadTelemetry]);

  /*
   * --------------------------------------------------------
   * DATE FORMATTER
   * --------------------------------------------------------
   */

  const formatDate = (
    value: string | null,
  ) => {
    if (!value) {
      return "Never";
    }

    return new Date(value).toLocaleString();
  };

  /*
   * --------------------------------------------------------
   * TELEMETRY DATE
   * --------------------------------------------------------
   */

  const formatTelemetryTime = (
    value: string | null | undefined,
  ) => {
    if (!value) {
      return "Never";
    }

    return new Date(value).toLocaleString();
  };

  /*
   * --------------------------------------------------------
   * DEVICE STATUS
   * --------------------------------------------------------
   */

  const statusLabel = device?.status
    ? device.status.charAt(0).toUpperCase() +
      device.status.slice(1)
    : "Unknown";

  const isOnline =
    device?.status === "online";

  const isMaintenance =
    device?.status === "maintenance";

  return (
    <DashboardLayout>
      <section className="space-y-8">

        {/* ==================================================
            HEADER
        ================================================== */}

        <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">

          <div>

            <button
              type="button"
              onClick={() =>
                navigate("/devices")
              }
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

          {/* STATUS BADGE */}

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
                  isOnline
                    ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-400"
                    : isMaintenance
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
                    isOnline
                      ? "bg-emerald-400"
                      : isMaintenance
                        ? "bg-amber-400"
                        : "bg-zinc-500"
                  }
                `}
              />

              {statusLabel}

            </div>
          )}

        </div>

        {/* ==================================================
            INITIAL LOADING
        ================================================== */}

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

        {/* ==================================================
            ERROR
        ================================================== */}

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
              onClick={() =>
                void loadDevice(true)
              }
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
                transition
                hover:bg-zinc-800
              "
            >
              <RefreshCw size={15} />
              Retry
            </button>

          </div>
        )}

        {!loading &&
          !error &&
          device && (
            <>

              {/* ==================================================
                  OVERVIEW
              ================================================== */}

              <div className="grid gap-4 md:grid-cols-3">

                {/* DEVICE TYPE */}

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

                {/* CURRENT STATUS */}

                <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-5">

                  <div className="flex items-center gap-3">

                    <div
                      className={`
                        flex
                        h-9
                        w-9
                        items-center
                        justify-center
                        rounded-lg
                        bg-zinc-900

                        ${
                          isOnline
                            ? "text-emerald-400"
                            : "text-zinc-400"
                        }
                      `}
                    >
                      <Radio size={18} />
                    </div>

                    <div>

                      <p className="text-xs text-zinc-500">
                        Current status
                      </p>

                      <p
                        className={`
                          mt-1
                          text-sm
                          font-semibold

                          ${
                            isOnline
                              ? "text-emerald-400"
                              : "text-zinc-200"
                          }
                        `}
                      >
                        {statusLabel}
                      </p>

                    </div>

                  </div>

                </div>

                {/* ACTIVE */}

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

              {/* ==================================================
                  TELEMETRY
              ================================================== */}

              <div className="rounded-xl border border-zinc-800 bg-zinc-950">

                <div className="border-b border-zinc-800 px-6 py-5">

                  <div className="flex items-center justify-between">

                    <div>

                      <h2 className="text-sm font-semibold text-zinc-100">
                        Live telemetry
                      </h2>

                      <p className="mt-1 text-xs text-zinc-500">
                        Latest sensor readings reported by this device.
                      </p>

                    </div>

                    <Activity
                      size={18}
                      className="text-emerald-400"
                    />

                  </div>

                </div>

                <div className="p-6">

                  {telemetryLoading &&
                    !telemetry && (
                      <div className="flex items-center gap-3 text-sm text-zinc-500">
                        <RefreshCw
                          size={16}
                          className="animate-spin"
                        />

                        Loading telemetry...
                      </div>
                    )}

                  {!telemetryLoading &&
                    !telemetry && (
                      <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-5">

                        <p className="text-sm font-medium text-zinc-300">
                          No telemetry available
                        </p>

                        <p className="mt-1 text-xs text-zinc-500">
                          This device has not reported any sensor readings yet.
                        </p>

                      </div>
                    )}

                  {telemetry && (
                    <>

                      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">

                        {/* TEMPERATURE */}

                        <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-4">

                          <div className="flex items-center gap-2">

                            <Thermometer
                              size={16}
                              className="text-zinc-500"
                            />

                            <p className="text-xs text-zinc-500">
                              Temperature
                            </p>

                          </div>

                          <p className="mt-3 text-2xl font-semibold text-zinc-100">

                            {telemetry.temperature !== null
                              ? `${telemetry.temperature.toFixed(1)} °C`
                              : "—"}

                          </p>

                        </div>

                        {/* SENSOR 1 */}

                        <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-4">

                          <p className="text-xs text-zinc-500">
                            Sensor 1
                          </p>

                          <p className="mt-3 text-2xl font-semibold text-zinc-100">

                            {telemetry.sensor_1 !== null
                              ? telemetry.sensor_1.toFixed(1)
                              : "—"}

                          </p>

                        </div>

                        {/* SENSOR 2 */}

                        <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-4">

                          <p className="text-xs text-zinc-500">
                            Sensor 2
                          </p>

                          <p className="mt-3 text-2xl font-semibold text-zinc-100">

                            {telemetry.sensor_2 !== null
                              ? telemetry.sensor_2.toFixed(1)
                              : "—"}

                          </p>

                        </div>

                        {/* SENSOR 3 */}

                        <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-4">

                          <p className="text-xs text-zinc-500">
                            Sensor 3
                          </p>

                          <p className="mt-3 text-2xl font-semibold text-zinc-100">

                            {telemetry.sensor_3 !== null
                              ? telemetry.sensor_3.toFixed(1)
                              : "—"}

                          </p>

                        </div>

                      </div>

                      <div className="mt-5 flex items-center justify-between border-t border-zinc-800 pt-4">

                        <p className="text-xs text-zinc-500">
                          Last telemetry update
                        </p>

                        <p className="text-xs text-zinc-400">
                          {formatTelemetryTime(
                            telemetry.created_at,
                          )}
                        </p>

                      </div>

                    </>
                  )}

                  {telemetryError &&
                    telemetry && (
                      <p className="mt-3 text-xs text-zinc-600">
                        {telemetryError}
                      </p>
                    )}

                </div>

              </div>

              {/* ==================================================
                  INFORMATION + CONNECTIVITY
              ================================================== */}

              <div className="grid gap-6 lg:grid-cols-2">

                {/* DEVICE INFORMATION */}

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

                {/* CONNECTIVITY */}

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

                    <div
                      className={`
                        rounded-lg
                        border
                        p-4

                        ${
                          isOnline
                            ? "border-emerald-500/20 bg-emerald-500/5"
                            : "border-zinc-800 bg-zinc-900/40"
                        }
                      `}
                    >

                      <div className="flex items-center gap-3">

                        <Radio
                          size={18}
                          className={
                            isOnline
                              ? "text-emerald-400"
                              : "text-zinc-500"
                          }
                        />

                        <div>

                          <p className="text-sm font-semibold text-zinc-200">
                            Connection status
                          </p>

                          <p className="mt-1 text-xs text-zinc-500">

                            {isOnline
                              ? "Device is currently connected and sending heartbeats."
                              : "No active connection signal has been recorded recently."}

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