import { useState } from "react";
import {
  Building2,
  Check,
  Edit3,
  Globe,
  Mail,
  MapPin,
  Phone,
  Save,
  ShieldCheck,
  UserPlus,
  Users,
  X,
} from "lucide-react";

import DashboardLayout from "../components/Layout/DashboardLayout";

import { useOrganization } from "../features/organization/hooks/useOrganization";

import type {
  CreateInvitationPayload,
  UpdateOrganizationPayload,
} from "../features/organization/types/organization.types";

function OrganizationPage() {
    const {
        organization,
        members,
        invitations,
        loading,
        updating,
        inviting,
        error,
        updateOrganization,
        createInvitation,
      } = useOrganization();

  const [editing, setEditing] =
    useState(false);

  const [inviteOpen, setInviteOpen] =
    useState(false);

  const [form, setForm] =
    useState<UpdateOrganizationPayload>({});

  const [inviteForm, setInviteForm] =
    useState<CreateInvitationPayload>({
      email: "",
      role: "employee",
    });

  const [actionError, setActionError] =
    useState<string | null>(null);

  const [inviteSuccess, setInviteSuccess] =
    useState(false);

  /*
   * =========================================================
   * EDIT ORGANIZATION
   * =========================================================
   */

  const startEditing = () => {
    if (!organization) {
      return;
    }

    setActionError(null);

    setForm({
      name: organization.name,
      email: organization.email,
      phone: organization.phone,
      website: organization.website,
      industry: organization.industry,
      address: organization.address,
    });

    setEditing(true);
  };

  const cancelEditing = () => {
    if (updating) {
      return;
    }

    setEditing(false);
    setActionError(null);
  };

  const handleSave = async () => {
    if (!form.name?.trim()) {
      setActionError(
        "Organization name is required.",
      );
      return;
    }

    try {
      setActionError(null);

      await updateOrganization({
        ...form,
        name: form.name.trim(),
        email:
          form.email?.trim() || null,
        phone:
          form.phone?.trim() || null,
        website:
          form.website?.trim() || null,
        industry:
          form.industry?.trim() || null,
        address:
          form.address?.trim() || null,
      });

      setEditing(false);
    } catch {
      setActionError(
        "Unable to update organization. Please try again.",
      );
    }
  };

  /*
   * =========================================================
   * INVITATION
   * =========================================================
   */

  const openInvite = () => {
    setInviteForm({
      email: "",
      role: "employee",
    });

    setInviteSuccess(false);
    setActionError(null);
    setInviteOpen(true);
  };

  const closeInvite = () => {
    if (inviting) {
      return;
    }

    setInviteOpen(false);
    setActionError(null);
    setInviteSuccess(false);
  };

  const handleInvite = async () => {
    const email =
      inviteForm.email.trim();

    if (!email) {
      setActionError(
        "Email address is required.",
      );
      return;
    }

    try {
      setActionError(null);
      setInviteSuccess(false);

      await createInvitation({
        email,
        role: inviteForm.role,
      });

      setInviteSuccess(true);

      setInviteForm({
        email: "",
        role: "employee",
      });
    } catch {
      setActionError(
        "Unable to create invitation. Please try again.",
      );
    }
  };

  /*
   * =========================================================
   * LOADING
   * =========================================================
   */

  if (loading) {
    return (
      <DashboardLayout>
        <div className="mx-auto w-full max-w-[1480px] space-y-6">
          <div className="h-6 w-40 animate-pulse rounded bg-zinc-900" />

          <div className="h-52 animate-pulse rounded-2xl border border-zinc-800 bg-zinc-950" />

          <div className="h-96 animate-pulse rounded-2xl border border-zinc-800 bg-zinc-950" />
        </div>
      </DashboardLayout>
    );
  }

  /*
   * =========================================================
   * ERROR
   * =========================================================
   */

  if (!organization) {
    return (
      <DashboardLayout>
        <div className="mx-auto w-full max-w-[1480px]">
          <div className="rounded-2xl border border-red-500/20 bg-red-500/5 p-6">
            <h1 className="text-lg font-semibold text-zinc-200">
              Unable to load organization
            </h1>

            <p className="mt-2 text-sm leading-6 text-zinc-500">
              {error ||
                "Organization information could not be loaded."}
            </p>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="mx-auto w-full max-w-[1480px] space-y-7">

        {/* =====================================================
            PAGE HEADER
            ===================================================== */}

        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-emerald-400">
              Workspace
            </p>

            <h1 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-zinc-100 sm:text-3xl">
              Organization
            </h1>

            <p className="mt-2 text-sm leading-6 text-zinc-500">
              Manage your organization and
              workspace members.
            </p>
          </div>

          <div className="flex items-center gap-3">
            {!editing && (
              <button
                type="button"
                onClick={startEditing}
                className="
                  inline-flex
                  h-10
                  items-center
                  gap-2
                  rounded-lg
                  border
                  border-zinc-800
                  bg-zinc-950
                  px-4
                  text-sm
                  font-medium
                  text-zinc-400
                  transition-colors
                  hover:border-zinc-700
                  hover:bg-zinc-900
                  hover:text-zinc-100
                "
              >
                <Edit3 size={15} />
                Edit organization
              </button>
            )}

            <button
              type="button"
              onClick={openInvite}
              className="
                inline-flex
                h-10
                items-center
                gap-2
                rounded-lg
                bg-emerald-500
                px-4
                text-sm
                font-semibold
                text-zinc-950
                transition-colors
                hover:bg-emerald-400
              "
            >
              <UserPlus size={15} />
              Invite member
            </button>
          </div>
        </div>

        {/* =====================================================
            ORGANIZATION PROFILE
            ===================================================== */}

        <section className="overflow-hidden rounded-2xl border border-zinc-800 bg-zinc-950">

          {/* Profile header */}

          <div className="border-b border-zinc-800/80 px-6 py-7 sm:px-8">
            <div className="flex flex-col gap-5 sm:flex-row sm:items-center">

              <div
                className="
                  flex
                  h-14
                  w-14
                  shrink-0
                  items-center
                  justify-center
                  rounded-2xl
                  border
                  border-zinc-800
                  bg-zinc-900
                "
              >
                <Building2
                  size={23}
                  strokeWidth={1.7}
                  className="text-emerald-400"
                />
              </div>

              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="break-words text-xl font-semibold text-zinc-100">
                    {organization.name}
                  </h2>

                  <span
                    className={`
                      inline-flex
                      items-center
                      gap-1.5
                      rounded-full
                      border
                      px-2.5
                      py-1
                      text-[10px]
                      font-semibold
                      uppercase
                      tracking-[0.08em]
                      ${
                        organization.is_active
                          ? "border-emerald-500/20 bg-emerald-500/5 text-emerald-400"
                          : "border-red-500/20 bg-red-500/5 text-red-400"
                      }
                    `}
                  >
                    <span
                      className={`
                        h-1.5
                        w-1.5
                        rounded-full
                        ${
                          organization.is_active
                            ? "bg-emerald-400"
                            : "bg-red-400"
                        }
                      `}
                    />

                    {organization.is_active
                      ? "Active"
                      : "Inactive"}
                  </span>
                </div>

                <p className="mt-1 text-xs text-zinc-600">
                  {organization.slug}
                </p>
              </div>

              <div className="hidden sm:block">
                <div className="text-right">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-600">
                    Members
                  </p>

                  <p className="mt-1 text-xl font-semibold text-zinc-200">
                    {members.length}
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Details */}

          <div className="px-6 py-7 sm:px-8">

            {editing ? (
              <div className="space-y-5">

                <OrganizationInput
                  label="Organization name"
                  value={form.name || ""}
                  onChange={(value) =>
                    setForm((current) => ({
                      ...current,
                      name: value,
                    }))
                  }
                  disabled={updating}
                />

                <div className="grid gap-5 md:grid-cols-2">

                  <OrganizationInput
                    label="Email"
                    type="email"
                    value={form.email || ""}
                    onChange={(value) =>
                      setForm((current) => ({
                        ...current,
                        email: value,
                      }))
                    }
                    disabled={updating}
                  />

                  <OrganizationInput
                    label="Phone"
                    value={form.phone || ""}
                    onChange={(value) =>
                      setForm((current) => ({
                        ...current,
                        phone: value,
                      }))
                    }
                    disabled={updating}
                  />

                  <OrganizationInput
                    label="Website"
                    value={form.website || ""}
                    onChange={(value) =>
                      setForm((current) => ({
                        ...current,
                        website: value,
                      }))
                    }
                    disabled={updating}
                  />

                  <OrganizationInput
                    label="Industry"
                    value={form.industry || ""}
                    onChange={(value) =>
                      setForm((current) => ({
                        ...current,
                        industry: value,
                      }))
                    }
                    disabled={updating}
                  />

                </div>

                <OrganizationInput
                  label="Address"
                  value={form.address || ""}
                  onChange={(value) =>
                    setForm((current) => ({
                      ...current,
                      address: value,
                    }))
                  }
                  disabled={updating}
                />

                {actionError && (
                  <ErrorMessage
                    message={actionError}
                  />
                )}

                <div className="flex justify-end gap-3 border-t border-zinc-800/80 pt-5">

                  <button
                    type="button"
                    onClick={cancelEditing}
                    disabled={updating}
                    className="
                      inline-flex
                      h-10
                      items-center
                      gap-2
                      rounded-lg
                      px-4
                      text-sm
                      font-medium
                      text-zinc-500
                      transition-colors
                      hover:bg-zinc-900
                      hover:text-zinc-200
                      disabled:opacity-40
                    "
                  >
                    <X size={15} />
                    Cancel
                  </button>

                  <button
                    type="button"
                    onClick={handleSave}
                    disabled={updating}
                    className="
                      inline-flex
                      h-10
                      items-center
                      gap-2
                      rounded-lg
                      bg-emerald-500
                      px-4
                      text-sm
                      font-semibold
                      text-zinc-950
                      transition-colors
                      hover:bg-emerald-400
                      disabled:cursor-not-allowed
                      disabled:opacity-50
                    "
                  >
                    <Save size={15} />

                    {updating
                      ? "Saving..."
                      : "Save changes"}
                  </button>

                </div>
              </div>
            ) : (
              <div className="grid gap-x-10 gap-y-7 md:grid-cols-2">

                <InfoItem
                  icon={<Mail size={15} />}
                  label="Email"
                  value={
                    organization.email
                  }
                />

                <InfoItem
                  icon={<Phone size={15} />}
                  label="Phone"
                  value={
                    organization.phone
                  }
                />

                <InfoItem
                  icon={<Globe size={15} />}
                  label="Website"
                  value={
                    organization.website
                  }
                />

                <InfoItem
                  icon={<Building2 size={15} />}
                  label="Industry"
                  value={
                    organization.industry
                  }
                />

                <div className="md:col-span-2">
                  <InfoItem
                    icon={<MapPin size={15} />}
                    label="Address"
                    value={
                      organization.address
                    }
                  />
                </div>

              </div>
            )}
          </div>
        </section>

        {/* =====================================================
            MEMBERS
            ===================================================== */}

        <section className="overflow-hidden rounded-2xl border border-zinc-800 bg-zinc-950">

          <div className="flex items-center justify-between border-b border-zinc-800/80 px-6 py-5 sm:px-8">

            <div className="flex items-center gap-3">

              <div
                className="
                  flex
                  h-9
                  w-9
                  items-center
                  justify-center
                  rounded-lg
                  border
                  border-zinc-800
                  bg-zinc-900
                "
              >
                <Users
                  size={16}
                  className="text-emerald-400"
                />
              </div>

              <div>
                <h2 className="text-sm font-semibold text-zinc-200">
                  Members
                </h2>

                <p className="mt-1 text-xs text-zinc-600">
                  {members.length}{" "}
                  {members.length === 1
                    ? "member"
                    : "members"}{" "}
                  in your organization
                </p>
              </div>

            </div>

            <button
              type="button"
              onClick={openInvite}
              className="
                hidden
                items-center
                gap-2
                rounded-lg
                border
                border-zinc-800
                px-3
                py-2
                text-xs
                font-medium
                text-zinc-500
                transition-colors
                hover:border-zinc-700
                hover:bg-zinc-900
                hover:text-zinc-200
                sm:inline-flex
              "
            >
              <UserPlus size={14} />
              Invite
            </button>
          </div>

          {members.length === 0 ? (
            <div className="flex min-h-[220px] flex-col items-center justify-center px-6 text-center">

              <div
                className="
                  flex
                  h-11
                  w-11
                  items-center
                  justify-center
                  rounded-xl
                  border
                  border-zinc-800
                  bg-zinc-900
                "
              >
                <Users
                  size={18}
                  className="text-zinc-600"
                />
              </div>

              <h3 className="mt-4 text-sm font-semibold text-zinc-200">
                No members found
              </h3>

              <p className="mt-2 max-w-sm text-sm leading-6 text-zinc-600">
                Invite people to start
                building your workspace.
              </p>

            </div>
          ) : (
            <div className="divide-y divide-zinc-800/70">

              {members.map((member) => (
                <MemberRow
                  key={member.id}
                  member={member}
                />
              ))}

            </div>
          )}
                </section>

{/* =======================================================
    PENDING INVITATIONS
    ======================================================= */}

<section
  className="
    overflow-hidden
    rounded-2xl
    border
    border-zinc-800
    bg-zinc-950
  "
>
  <div
    className="
      flex
      flex-col
      gap-4
      border-b
      border-zinc-800/80
      px-6
      py-5
      sm:flex-row
      sm:items-center
      sm:justify-between
      sm:px-8
    "
  >
    <div>
      <div className="flex items-center gap-3">
        <div
          className="
            flex
            h-9
            w-9
            items-center
            justify-center
            rounded-xl
            border
            border-zinc-800
            bg-zinc-900
          "
        >
          <Mail
            size={16}
            className="text-zinc-500"
          />
        </div>

        <div>
          <h2 className="text-sm font-semibold text-zinc-200">
            Pending invitations
          </h2>

          <p className="mt-1 text-xs text-zinc-600">
            Invitations waiting to be accepted.
          </p>
        </div>
      </div>
    </div>

    <span
      className="
        w-fit
        rounded-full
        border
        border-zinc-800
        bg-zinc-900
        px-2.5
        py-1
        text-[10px]
        font-semibold
        uppercase
        tracking-[0.08em]
        text-zinc-500
      "
    >
      {invitations.length}{" "}
      {invitations.length === 1
        ? "invitation"
        : "invitations"}
    </span>
  </div>

  {invitations.length === 0 ? (
    <div
      className="
        flex
        min-h-[160px]
        flex-col
        items-center
        justify-center
        px-6
        text-center
      "
    >
      <div
        className="
          flex
          h-10
          w-10
          items-center
          justify-center
          rounded-xl
          border
          border-zinc-800
          bg-zinc-900
        "
      >
        <Mail
          size={17}
          className="text-zinc-600"
        />
      </div>

      <h3 className="mt-4 text-sm font-semibold text-zinc-300">
        No pending invitations
      </h3>

      <p className="mt-2 max-w-sm text-sm leading-6 text-zinc-600">
        Invitations you send will appear here
        until they are accepted.
      </p>
    </div>
  ) : (
    <div className="divide-y divide-zinc-800/70">
      {invitations.map((invitation) => {
        const expiresAt =
          new Date(
            invitation.expires_at,
          );

        const isExpired =
          expiresAt.getTime() <
          Date.now();

        return (
          <div
            key={invitation.id}
            className="
              flex
              flex-col
              gap-4
              px-6
              py-4
              sm:flex-row
              sm:items-center
              sm:px-8
            "
          >
            <div
              className="
                flex
                h-10
                w-10
                shrink-0
                items-center
                justify-center
                rounded-xl
                border
                border-zinc-800
                bg-zinc-900
                text-xs
                font-semibold
                uppercase
                text-zinc-500
              "
            >
              <Mail size={16} />
            </div>

            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-zinc-200">
                {invitation.email}
              </p>

              <p className="mt-1 text-xs text-zinc-600">
                Sent{" "}
                {new Date(
                  invitation.created_at,
                ).toLocaleDateString()}
              </p>
            </div>

            <div className="flex items-center gap-2">
              <span
                className="
                  rounded-full
                  border
                  border-zinc-800
                  bg-zinc-900
                  px-2.5
                  py-1
                  text-[10px]
                  font-semibold
                  uppercase
                  tracking-[0.08em]
                  text-zinc-500
                "
              >
                {invitation.role}
              </span>

              <span
                className={`
                  rounded-full
                  border
                  px-2.5
                  py-1
                  text-[10px]
                  font-semibold
                  uppercase
                  tracking-[0.08em]
                  ${
                    isExpired
                      ? "border-red-500/20 bg-red-500/5 text-red-400"
                      : "border-emerald-500/20 bg-emerald-500/5 text-emerald-400"
                  }
                `}
              >
                {isExpired
                  ? "Expired"
                  : "Pending"}
              </span>
            </div>

            <div className="text-xs text-zinc-600 sm:min-w-[130px] sm:text-right">
              {isExpired
                ? "Invitation expired"
                : `Expires ${expiresAt.toLocaleDateString()}`}
            </div>
          </div>
        );
      })}
    </div>
  )}
</section>

</div>

{/* =======================================================
  INVITE MODAL
  ======================================================= */}

      {inviteOpen && (
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
            backdrop-blur-[3px]
          "
          role="dialog"
          aria-modal="true"
          aria-labelledby="invite-member-title"
        >
          <button
            type="button"
            aria-label="Close invite dialog"
            disabled={inviting}
            onClick={closeInvite}
            className="absolute inset-0 cursor-default"
          />

          <div className="relative z-10 w-full max-w-md overflow-hidden rounded-2xl border border-zinc-800 bg-zinc-950 shadow-2xl shadow-black/50">

            <div className="h-px w-full bg-gradient-to-r from-transparent via-emerald-500/70 to-transparent" />

            <div className="flex items-start justify-between border-b border-zinc-800/80 px-6 py-5">

              <div className="flex items-start gap-4">

                <div
                  className="
                    flex
                    h-10
                    w-10
                    items-center
                    justify-center
                    rounded-xl
                    border
                    border-zinc-800
                    bg-zinc-900
                  "
                >
                  <UserPlus
                    size={18}
                    className="text-emerald-400"
                  />
                </div>

                <div>
                  <h2
                    id="invite-member-title"
                    className="text-base font-semibold text-zinc-100"
                  >
                    Invite member
                  </h2>

                  <p className="mt-1 text-sm text-zinc-500">
                    Add someone to your organization.
                  </p>
                </div>

              </div>

              <button
                type="button"
                disabled={inviting}
                onClick={closeInvite}
                className="
                  rounded-lg
                  p-2
                  text-zinc-600
                  transition-colors
                  hover:bg-zinc-900
                  hover:text-zinc-300
                  disabled:opacity-40
                "
              >
                <X size={18} />
              </button>

            </div>

            <div className="space-y-5 px-6 py-6">

              <OrganizationInput
                label="Email address"
                type="email"
                value={inviteForm.email}
                onChange={(value) => {
                  setInviteForm(
                    (current) => ({
                      ...current,
                      email: value,
                    }),
                  );
                  setActionError(null);
                  setInviteSuccess(false);
                }}
                placeholder="member@company.com"
                disabled={inviting}
              />

              <div>
                <label
                  htmlFor="invite-role"
                  className="
                    mb-2
                    block
                    text-xs
                    font-semibold
                    uppercase
                    tracking-[0.12em]
                    text-zinc-500
                  "
                >
                  Role
                </label>

                <select
                  id="invite-role"
                  value={inviteForm.role}
                  disabled={inviting}
                  onChange={(event) => {
                    setInviteForm(
                      (current) => ({
                        ...current,
                        role: event.target.value,
                      }),
                    );
                    setActionError(null);
                  }}
                  className="
                    h-11
                    w-full
                    rounded-lg
                    border
                    border-zinc-800
                    bg-zinc-900/60
                    px-3
                    text-sm
                    text-zinc-200
                    outline-none
                    transition
                    hover:border-zinc-700
                    focus:border-emerald-500/50
                    focus:ring-2
                    focus:ring-emerald-500/10
                    disabled:opacity-50
                  "
                >
                  <option value="employee">
                    Employee
                  </option>

                  <option value="manager">
                    Manager
                  </option>

                  <option value="admin">
                    Admin
                  </option>
                </select>
              </div>

              {actionError && (
                <ErrorMessage
                  message={actionError}
                />
              )}

              {inviteSuccess && (
                <div
                  role="status"
                  className="
                    flex
                    items-center
                    gap-2
                    rounded-lg
                    border
                    border-emerald-500/20
                    bg-emerald-500/5
                    px-3.5
                    py-3
                    text-sm
                    text-emerald-400
                  "
                >
                  <Check size={16} />

                  Invitation created successfully.
                </div>
              )}

            </div>

            <div className="flex items-center justify-end gap-3 border-t border-zinc-800/80 px-6 py-4">

              <button
                type="button"
                disabled={inviting}
                onClick={closeInvite}
                className="
                  h-10
                  rounded-lg
                  px-4
                  text-sm
                  font-medium
                  text-zinc-500
                  transition-colors
                  hover:bg-zinc-900
                  hover:text-zinc-200
                  disabled:opacity-40
                "
              >
                Cancel
              </button>

              <button
                type="button"
                disabled={inviting}
                onClick={handleInvite}
                className="
                  inline-flex
                  h-10
                  items-center
                  gap-2
                  rounded-lg
                  bg-emerald-500
                  px-5
                  text-sm
                  font-semibold
                  text-zinc-950
                  transition-colors
                  hover:bg-emerald-400
                  disabled:cursor-not-allowed
                  disabled:opacity-50
                "
              >
                <UserPlus size={15} />

                {inviting
                  ? "Sending..."
                  : "Send invitation"}
              </button>

            </div>

          </div>
        </div>
      )}
    </DashboardLayout>
  );
}

/* =========================================================
   ORGANIZATION INPUT
   ========================================================= */

type OrganizationInputProps = {
  label: string;
  value: string;
  type?: string;
  placeholder?: string;
  disabled?: boolean;
  onChange: (value: string) => void;
};

function OrganizationInput({
  label,
  value,
  type = "text",
  placeholder,
  disabled = false,
  onChange,
}: OrganizationInputProps) {
  return (
    <div>
      <label
        className="
          mb-2
          block
          text-xs
          font-semibold
          uppercase
          tracking-[0.12em]
          text-zinc-500
        "
      >
        {label}
      </label>

      <input
        type={type}
        value={value}
        disabled={disabled}
        placeholder={placeholder}
        onChange={(event) =>
          onChange(event.target.value)
        }
        className="
          h-11
          w-full
          rounded-lg
          border
          border-zinc-800
          bg-zinc-900/60
          px-3.5
          text-sm
          text-zinc-100
          outline-none
          transition
          placeholder:text-zinc-600
          hover:border-zinc-700
          focus:border-emerald-500/50
          focus:ring-2
          focus:ring-emerald-500/10
          disabled:cursor-not-allowed
          disabled:opacity-50
        "
      />
    </div>
  );
}

/* =========================================================
   INFO ITEM
   ========================================================= */

type InfoItemProps = {
  icon: React.ReactNode;
  label: string;
  value: string | null;
};

function InfoItem({
  icon,
  label,
  value,
}: InfoItemProps) {
  return (
    <div className="flex min-w-0 items-start gap-3">

      <div
        className="
          mt-0.5
          flex
          h-8
          w-8
          shrink-0
          items-center
          justify-center
          rounded-lg
          border
          border-zinc-800
          bg-zinc-900
          text-zinc-600
        "
      >
        {icon}
      </div>

      <div className="min-w-0">
        <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-zinc-600">
          {label}
        </p>

        <p className="mt-1 break-words text-sm text-zinc-300">
          {value || "Not provided"}
        </p>
      </div>

    </div>
  );
}

/* =========================================================
   MEMBER ROW
   ========================================================= */

type MemberRowProps = {
  member: {
    id: number;
    name: string;
    email: string;
    role: string;
    is_active: boolean;
  };
};

function MemberRow({
  member,
}: MemberRowProps) {
  const initials =
    member.name
      .trim()
      .split(/\s+/)
      .slice(0, 2)
      .map(
        (part) =>
          part.charAt(0).toUpperCase(),
      )
      .join("") || "?";

  return (
    <div className="flex items-center gap-4 px-6 py-4 sm:px-8">

      <div
        className="
          flex
          h-10
          w-10
          shrink-0
          items-center
          justify-center
          rounded-xl
          border
          border-zinc-800
          bg-zinc-900
          text-xs
          font-semibold
          text-zinc-400
        "
      >
        {initials}
      </div>

      <div className="min-w-0 flex-1">

        <p className="truncate text-sm font-medium text-zinc-200">
          {member.name}
        </p>

        <p className="mt-1 truncate text-xs text-zinc-600">
          {member.email}
        </p>

      </div>

      <div className="hidden items-center gap-2 sm:flex">

        <span className="rounded-full border border-zinc-800 bg-zinc-900 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.08em] text-zinc-500">
          {member.role}
        </span>

        <span
          className={`
            rounded-full
            border
            px-2.5
            py-1
            text-[10px]
            font-semibold
            uppercase
            tracking-[0.08em]
            ${
              member.is_active
                ? "border-emerald-500/20 bg-emerald-500/5 text-emerald-400"
                : "border-zinc-800 text-zinc-600"
            }
          `}
        >
          {member.is_active
            ? "Active"
            : "Inactive"}
        </span>

      </div>

      <ShieldCheck
        size={16}
        className={
          member.is_active
            ? "text-emerald-500/60"
            : "text-zinc-700"
        }
      />

    </div>
  );
}

/* =========================================================
   ERROR
   ========================================================= */

function ErrorMessage({
  message,
}: {
  message: string;
}) {
  return (
    <div
      role="alert"
      className="
        rounded-lg
        border
        border-red-500/20
        bg-red-500/5
        px-3.5
        py-3
        text-sm
        text-red-400
      "
    >
      {message}
    </div>
  );
}

export default OrganizationPage;