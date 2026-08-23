import { useState } from "react";
import { X } from "lucide-react";

import type {
  CreateDevicePayload,
  DeviceStatus,
} from "../../features/devices/types/device.types";

type CreateDeviceModalProps = {
  open: boolean;
  creating: boolean;
  onClose: () => void;
  onSubmit: (data: CreateDevicePayload) => Promise<void>;
};

function CreateDeviceModal({
  open,
  creating,
  onClose,
  onSubmit,
}: CreateDeviceModalProps) {
  const [deviceId, setDeviceId] = useState("");
  const [name, setName] = useState("");
  const [deviceType, setDeviceType] = useState("");
  const [status, setStatus] =
    useState<DeviceStatus>("offline");

  if (!open) {
    return null;
  }

  const handleSubmit = async (
    event: React.FormEvent<HTMLFormElement>,
  ) => {
    event.preventDefault();

    if (!deviceId.trim() || !name.trim() || !deviceType.trim()) {
      return;
    }

    await onSubmit({
      device_id: deviceId.trim(),
      name: name.trim(),
      device_type: deviceType.trim(),
      status,
    });

    setDeviceId("");
    setName("");
    setDeviceType("");
    setStatus("offline");
  };

  return (
    <div
      className="
        fixed inset-0 z-[100]
        flex items-center justify-center
        bg-black/70 px-4
        backdrop-blur-sm
      "
      onMouseDown={onClose}
    >
      <div
        className="
          w-full max-w-lg
          rounded-xl border border-zinc-800
          bg-zinc-950 shadow-2xl
        "
        onMouseDown={(event) =>
          event.stopPropagation()
        }
      >
        <div className="flex items-center justify-between border-b border-zinc-800/80 px-6 py-5">
          <div>
            <h2 className="text-lg font-semibold text-zinc-100">
              Add device
            </h2>

            <p className="mt-1 text-xs text-zinc-500">
              Register a connected device in your workspace.
            </p>
          </div>

          <button
            type="button"
            onClick={onClose}
            aria-label="Close modal"
            className="
              flex h-8 w-8 items-center justify-center
              rounded-lg text-zinc-500
              transition hover:bg-zinc-900
              hover:text-zinc-200
            "
          >
            <X size={17} />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="space-y-5 px-6 py-6">

            <div>
              <label className="mb-2 block text-xs font-semibold text-zinc-400">
                Device ID
              </label>

              <input
                value={deviceId}
                onChange={(event) =>
                  setDeviceId(event.target.value)
                }
                placeholder="e.g. ESP32-001"
                required
                className="
                  h-10 w-full rounded-lg
                  border border-zinc-800
                  bg-zinc-900/50 px-3
                  text-sm text-zinc-200
                  outline-none
                  placeholder:text-zinc-600
                  focus:border-zinc-600
                "
              />
            </div>

            <div>
              <label className="mb-2 block text-xs font-semibold text-zinc-400">
                Device name
              </label>

              <input
                value={name}
                onChange={(event) =>
                  setName(event.target.value)
                }
                placeholder="e.g. Production Sensor 01"
                required
                className="
                  h-10 w-full rounded-lg
                  border border-zinc-800
                  bg-zinc-900/50 px-3
                  text-sm text-zinc-200
                  outline-none
                  placeholder:text-zinc-600
                  focus:border-zinc-600
                "
              />
            </div>

            <div>
              <label className="mb-2 block text-xs font-semibold text-zinc-400">
                Device type
              </label>

              <input
                value={deviceType}
                onChange={(event) =>
                  setDeviceType(event.target.value)
                }
                placeholder="e.g. Sensor, ESP32, Gateway"
                required
                className="
                  h-10 w-full rounded-lg
                  border border-zinc-800
                  bg-zinc-900/50 px-3
                  text-sm text-zinc-200
                  outline-none
                  placeholder:text-zinc-600
                  focus:border-zinc-600
                "
              />
            </div>

            <div>
              <label className="mb-2 block text-xs font-semibold text-zinc-400">
                Initial status
              </label>

              <select
                value={status}
                onChange={(event) =>
                  setStatus(
                    event.target.value as DeviceStatus,
                  )
                }
                className="
                  h-10 w-full rounded-lg
                  border border-zinc-800
                  bg-zinc-900/50 px-3
                  text-sm text-zinc-300
                  outline-none
                  focus:border-zinc-600
                "
              >
                <option value="offline">Offline</option>
                <option value="online">Online</option>
                <option value="maintenance">
                  Maintenance
                </option>
              </select>
            </div>

          </div>

          <div className="flex justify-end gap-3 border-t border-zinc-800/80 px-6 py-4">
            <button
              type="button"
              onClick={onClose}
              disabled={creating}
              className="
                h-10 rounded-lg
                border border-zinc-800
                px-4 text-sm font-semibold
                text-zinc-400
                transition
                hover:bg-zinc-900
                hover:text-zinc-200
                disabled:opacity-50
              "
            >
              Cancel
            </button>

            <button
              type="submit"
              disabled={
                creating ||
                !deviceId.trim() ||
                !name.trim() ||
                !deviceType.trim()
              }
              className="
                h-10 rounded-lg
                bg-emerald-500
                px-4 text-sm font-semibold
                text-zinc-950
                transition
                hover:bg-emerald-400
                disabled:cursor-not-allowed
                disabled:opacity-50
              "
            >
              {creating ? "Adding..." : "Add device"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default CreateDeviceModal;
