import CreateAssetModal from "../components/assets/CreateAssetModal";
import {
    useMemo,
    useState,
  } from "react";
  import {
    Boxes,
    Plus,
    Search,
    MapPin,
    UserRound,
  } from "lucide-react";
  
  import DashboardLayout from "../components/Layout/DashboardLayout";
  import { useAsset } from "../features/assets/hooks/useAsset";
  
  import type {
    AssetStatus,
  } from "../features/assets/types/asset.types";
  
  type StatusFilter =
    | "all"
    | AssetStatus;
  
  const statusOptions: Array<{
    label: string;
    value: StatusFilter;
  }> = [
    {
      label: "All assets",
      value: "all",
    },
    {
      label: "Active",
      value: "active",
    },
    {
      label: "Maintenance",
      value: "maintenance",
    },
    {
      label: "Inactive",
      value: "inactive",
    },
  ];
  
  function AssetsPage() {
    const {
        assets,
        loading,
        error,
      } = useAsset();
      
      const [
        createModalOpen,
        setCreateModalOpen,
      ] = useState(false);
  
    const [search, setSearch] =
      useState("");
  
    const [status, setStatus] =
      useState<StatusFilter>("all");
  
    const filteredAssets =
      useMemo(() => {
        const normalizedSearch =
          search.trim().toLowerCase();
  
        return assets.filter((asset) => {
          const matchesSearch =
            normalizedSearch.length === 0 ||
            asset.name
              .toLowerCase()
              .includes(normalizedSearch) ||
            asset.asset_type
              .toLowerCase()
              .includes(normalizedSearch) ||
            asset.location
              ?.toLowerCase()
              .includes(normalizedSearch);
  
          const matchesStatus =
            status === "all" ||
            asset.status === status;
  
          return (
            matchesSearch &&
            matchesStatus
          );
        });
      }, [
        assets,
        search,
        status,
      ]);
  
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
                Assets
              </h1>
  
              <p className="mt-2 max-w-2xl text-sm leading-6 text-zinc-500">
                Manage your organization's equipment,
                machines, devices, and operational assets.
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
  
              Add asset
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
                  left-3.5
                  top-1/2
                  -translate-y-1/2
                  text-zinc-600
                "
              />
  
              <input
                value={search}
                onChange={(event) =>
                  setSearch(event.target.value)
                }
                placeholder="Search assets..."
                aria-label="Search assets"
                className="
                  h-11
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
                  event.target
                    .value as StatusFilter,
                )
              }
              aria-label="Filter assets by status"
              className="
                h-11
                rounded-lg
                border
                border-zinc-800
                bg-zinc-950
                px-3
                text-sm
                text-zinc-300
                outline-none
                focus:border-zinc-700
              "
            >
              {statusOptions.map(
                (option) => (
                  <option
                    key={option.value}
                    value={option.value}
                  >
                    {option.label}
                  </option>
                ),
              )}
            </select>
          </div>
  
          {/* ===================================================
              CONTENT
              =================================================== */}
  
          {loading ? (
            <div className="rounded-xl border border-zinc-800/80 bg-zinc-950 p-12 text-center">
              <p className="text-sm text-zinc-500">
                Loading assets...
              </p>
            </div>
          ) : error ? (
            <div className="rounded-xl border border-red-900/40 bg-red-950/20 p-6">
              <p className="text-sm font-medium text-red-400">
                {error}
              </p>
            </div>
          ) : filteredAssets.length === 0 ? (
            <div className="rounded-xl border border-zinc-800/80 bg-zinc-950 p-12 text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-zinc-900 text-zinc-600">
                <Boxes
                  size={22}
                  strokeWidth={1.7}
                />
              </div>
  
              <h2 className="mt-4 text-sm font-semibold text-zinc-300">
                {assets.length === 0
                  ? "No assets yet"
                  : "No assets found"}
              </h2>
  
              <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-zinc-600">
                {assets.length === 0
                  ? "Add your first machine, device, equipment, or operational asset."
                  : "Try changing your search or status filter."}
              </p>
            </div>
          ) : (
            <div className="overflow-hidden rounded-xl border border-zinc-800/80 bg-zinc-950">
              <div className="grid grid-cols-[minmax(220px,1.5fr)_160px_180px_160px_120px] border-b border-zinc-800/80 px-5 py-3 text-[10px] font-bold uppercase tracking-[0.14em] text-zinc-600">
                <span>Asset</span>
                <span>Type</span>
                <span>Location</span>
                <span>Assigned</span>
                <span>Status</span>
              </div>
  
              {filteredAssets.map(
                (asset) => (
                  <div
                    key={asset.id}
                    className="
                      grid
                      grid-cols-[minmax(220px,1.5fr)_160px_180px_160px_120px]
                      items-center
                      border-b
                      border-zinc-900
                      px-5
                      py-4
                      last:border-b-0
                      hover:bg-zinc-900/40
                    "
                  >
                    <div className="flex min-w-0 items-center gap-3">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-zinc-900 text-zinc-500">
                        <Boxes
                          size={17}
                          strokeWidth={1.7}
                        />
                      </div>
  
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-zinc-200">
                          {asset.name}
                        </p>
  
                        {asset.description && (
                          <p className="mt-0.5 truncate text-xs text-zinc-600">
                            {asset.description}
                          </p>
                        )}
                      </div>
                    </div>
  
                    <span className="text-sm text-zinc-400">
                      {asset.asset_type}
                    </span>
  
                    <div className="flex items-center gap-1.5 text-sm text-zinc-500">
                      <MapPin
                        size={14}
                        strokeWidth={1.7}
                      />
  
                      <span className="truncate">
                        {asset.location || "—"}
                      </span>
                    </div>
  
                    <div className="flex items-center gap-1.5 text-sm text-zinc-500">
                      <UserRound
                        size={14}
                        strokeWidth={1.7}
                      />
  
                      {asset.assigned_to
                        ? `User #${asset.assigned_to}`
                        : "Unassigned"}
                    </div>
  
                    <span
                      className={`
                        inline-flex
                        w-fit
                        rounded-full
                        px-2.5
                        py-1
                        text-[11px]
                        font-semibold
                        ${
                          asset.status ===
                          "active"
                            ? "bg-emerald-500/10 text-emerald-400"
                            : asset.status ===
                                "maintenance"
                              ? "bg-amber-500/10 text-amber-400"
                              : "bg-zinc-800 text-zinc-500"
                        }
                      `}
                    >
                      {asset.status}
                    </span>
                  </div>
                ),
              )}
            </div>
          )}
  
        </section>
        <CreateAssetModal
           open={createModalOpen}
            onClose={() =>
            setCreateModalOpen(false)
          }
         />
      </DashboardLayout>
    );
  }
  
  export default AssetsPage;