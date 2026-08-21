import {
    X,
  } from "lucide-react";
  
  type CreateAssetModalProps = {
    open: boolean;
    onClose: () => void;
  };
  
  function CreateAssetModal({
    open,
    onClose,
  }: CreateAssetModalProps) {
    if (!open) {
      return null;
    }
  
    return (
      <div
        className="
          fixed
          inset-0
          z-[100]
          flex
          items-center
          justify-center
          bg-black/70
          px-4
          backdrop-blur-sm
        "
        onMouseDown={onClose}
      >
        <div
          className="
            w-full
            max-w-lg
            rounded-xl
            border
            border-zinc-800
            bg-zinc-950
            shadow-2xl
          "
          onMouseDown={(event) =>
            event.stopPropagation()
          }
        >
          {/* Header */}
  
          <div className="flex items-center justify-between border-b border-zinc-800/80 px-6 py-5">
            <div>
              <h2 className="text-lg font-semibold text-zinc-100">
                Add asset
              </h2>
  
              <p className="mt-1 text-xs text-zinc-500">
                Add an operational asset to your workspace.
              </p>
            </div>
  
            <button
              type="button"
              onClick={onClose}
              aria-label="Close modal"
              className="
                flex
                h-8
                w-8
                items-center
                justify-center
                rounded-lg
                text-zinc-500
                transition
                hover:bg-zinc-900
                hover:text-zinc-200
              "
            >
              <X size={17} />
            </button>
          </div>
  
          {/* Form */}
  
          <div className="space-y-5 px-6 py-6">
  
            <div>
              <label className="mb-2 block text-xs font-semibold text-zinc-400">
                Asset name
              </label>
  
              <input
                type="text"
                placeholder="e.g. Reception AC"
                className="
                  h-10
                  w-full
                  rounded-lg
                  border
                  border-zinc-800
                  bg-zinc-900/50
                  px-3
                  text-sm
                  text-zinc-200
                  outline-none
                  placeholder:text-zinc-600
                  focus:border-zinc-600
                "
              />
            </div>
  
            <div>
              <label className="mb-2 block text-xs font-semibold text-zinc-400">
                Asset type
              </label>
  
              <input
                type="text"
                placeholder="e.g. HVAC, Machine, Computer"
                className="
                  h-10
                  w-full
                  rounded-lg
                  border
                  border-zinc-800
                  bg-zinc-900/50
                  px-3
                  text-sm
                  text-zinc-200
                  outline-none
                  placeholder:text-zinc-600
                  focus:border-zinc-600
                "
              />
            </div>
  
            <div>
              <label className="mb-2 block text-xs font-semibold text-zinc-400">
                Description
              </label>
  
              <textarea
                rows={3}
                placeholder="Describe the asset..."
                className="
                  w-full
                  resize-none
                  rounded-lg
                  border
                  border-zinc-800
                  bg-zinc-900/50
                  px-3
                  py-2.5
                  text-sm
                  text-zinc-200
                  outline-none
                  placeholder:text-zinc-600
                  focus:border-zinc-600
                "
              />
            </div>
  
            <div>
              <label className="mb-2 block text-xs font-semibold text-zinc-400">
                Location
              </label>
  
              <input
                type="text"
                placeholder="e.g. Reception, Workshop"
                className="
                  h-10
                  w-full
                  rounded-lg
                  border
                  border-zinc-800
                  bg-zinc-900/50
                  px-3
                  text-sm
                  text-zinc-200
                  outline-none
                  placeholder:text-zinc-600
                  focus:border-zinc-600
                "
              />
            </div>
  
            <div>
              <label className="mb-2 block text-xs font-semibold text-zinc-400">
                Status
              </label>
  
              <select
                defaultValue="active"
                className="
                  h-10
                  w-full
                  rounded-lg
                  border
                  border-zinc-800
                  bg-zinc-900/50
                  px-3
                  text-sm
                  text-zinc-300
                  outline-none
                  focus:border-zinc-600
                "
              >
                <option value="active">
                  Active
                </option>
  
                <option value="maintenance">
                  Maintenance
                </option>
  
                <option value="inactive">
                  Inactive
                </option>
              </select>
            </div>
  
            {/* Footer */}
  
            <div className="flex justify-end gap-3 border-t border-zinc-800/80 pt-5">
              <button
                type="button"
                onClick={onClose}
                className="
                  h-10
                  rounded-lg
                  border
                  border-zinc-800
                  px-4
                  text-sm
                  font-medium
                  text-zinc-400
                  transition
                  hover:bg-zinc-900
                  hover:text-zinc-200
                "
              >
                Cancel
              </button>
  
              <button
                type="button"
                className="
                  h-10
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
                Create asset
              </button>
            </div>
  
          </div>
        </div>
      </div>
    );
  }
  
  export default CreateAssetModal;