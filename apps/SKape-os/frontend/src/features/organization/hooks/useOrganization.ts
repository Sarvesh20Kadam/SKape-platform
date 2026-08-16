import {
  useCallback,
  useEffect,
  useState,
} from "react";

import { useAuth } from "../../../context/AuthContext";

import {
  createInvitation as createInvitationRequest,
  getCurrentOrganization,
  getOrganizationInvitations,
  getOrganizationMembers,
  updateCurrentOrganization,
  updateMemberRole as updateMemberRoleRequest,
  revokeInvitation as revokeInvitationRequest,
  resendInvitation as resendInvitationRequest,
} from "../services/organization.service";

import type {
  CreateInvitationPayload,
  Invitation,
  Organization,
  OrganizationMember,
  UpdateOrganizationPayload,
} from "../types/organization.types";

type UseOrganizationResult = {
  organization: Organization | null;
  members: OrganizationMember[];
  invitations: Invitation[];

  loading: boolean;
  updating: boolean;
  inviting: boolean;
  revoking: boolean;
  resending: boolean;

  error: string | null;

  refresh: () => Promise<void>;

  updateOrganization: (
    data: UpdateOrganizationPayload,
  ) => Promise<Organization>;

  createInvitation: (
    data: CreateInvitationPayload,
  ) => Promise<void>;

  updateMemberRole: (
    userId: number,
    role: string,
  ) => Promise<OrganizationMember>;

  revokeInvitation: (
    invitationId: number,
  ) => Promise<void>;

  resendInvitation: (
    invitationId: number,
  ) => Promise<Invitation>;
};

export function useOrganization(): UseOrganizationResult {
  const { user } = useAuth();

  const [organization, setOrganization] =
    useState<Organization | null>(null);

  const [members, setMembers] =
    useState<OrganizationMember[]>([]);

  const [invitations, setInvitations] =
    useState<Invitation[]>([]);

  const [loading, setLoading] =
    useState(true);

  const [updating, setUpdating] =
    useState(false);

  const [inviting, setInviting] =
    useState(false);

  const [revoking, setRevoking] =
    useState(false);

  const [resending, setResending] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);

  /*
   * =========================================================
   * LOAD ORGANIZATION
   * =========================================================
   */

  const refresh = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const [
        organizationData,
        membersData,
      ] = await Promise.all([
        getCurrentOrganization(),
        getOrganizationMembers(),
      ]);

      setOrganization(organizationData);
      setMembers(membersData);

      /*
       * Only users who can manage invitations
       * should request the invitations endpoint.
       *
       * Backend permissions:
       * owner   -> allowed
       * admin   -> allowed
       * manager -> allowed
       * employee -> forbidden
       */

      const canManageInvitations =
        user?.role === "owner" ||
        user?.role === "admin" ||
        user?.role === "manager";

      if (canManageInvitations) {
        const invitationsData =
          await getOrganizationInvitations();

        setInvitations(invitationsData);
      } else {
        setInvitations([]);
      }
    } catch (err) {
      console.error(
        "Failed to load organization:",
        err,
      );

      setError(
        "Unable to load organization information. Please try again.",
      );
    } finally {
      setLoading(false);
    }
  }, [user?.role]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  /*
   * =========================================================
   * UPDATE ORGANIZATION
   * =========================================================
   */

  const updateOrganization = useCallback(
    async (
      data: UpdateOrganizationPayload,
    ): Promise<Organization> => {
      try {
        setUpdating(true);
        setError(null);

        const updated =
          await updateCurrentOrganization(data);

        setOrganization(updated);

        return updated;
      } catch (err) {
        console.error(
          "Failed to update organization:",
          err,
        );

        setError(
          "Unable to update organization. Please try again.",
        );

        throw err;
      } finally {
        setUpdating(false);
      }
    },
    [],
  );

  /*
   * =========================================================
   * CREATE INVITATION
   * =========================================================
   */

  const createInvitation = useCallback(
    async (
      data: CreateInvitationPayload,
    ): Promise<void> => {
      try {
        setInviting(true);
        setError(null);

        const created =
          await createInvitationRequest(data);

        setInvitations(
          (current) => [
            created,
            ...current,
          ],
        );
      } catch (err) {
        console.error(
          "Failed to create invitation:",
          err,
        );

        setError(
          "Unable to create invitation. Please try again.",
        );

        throw err;
      } finally {
        setInviting(false);
      }
    },
    [],
  );

  /*
   * =========================================================
   * UPDATE MEMBER ROLE
   * =========================================================
   */

  const updateMemberRole = useCallback(
    async (
      userId: number,
      role: string,
    ): Promise<OrganizationMember> => {
      try {
        setError(null);

        const updated =
          await updateMemberRoleRequest(
            userId,
            role,
          );

        setMembers((current) =>
          current.map((member) =>
            member.id === userId
              ? updated
              : member,
          ),
        );

        return updated;
      } catch (err) {
        console.error(
          "Failed to update member role:",
          err,
        );

        setError(
          "Unable to update member role. Please try again.",
        );

        throw err;
      }
    },
    [],
  );

  /*
   * =========================================================
   * REVOKE INVITATION
   * =========================================================
   */

  const revokeInvitation = useCallback(
    async (
      invitationId: number,
    ): Promise<void> => {
      try {
        setRevoking(true);
        setError(null);

        await revokeInvitationRequest(
          invitationId,
        );

        await refresh();
      } catch (err) {
        console.error(
          "Failed to revoke invitation:",
          err,
        );

        setError(
          "Unable to revoke invitation. Please try again.",
        );

        throw err;
      } finally {
        setRevoking(false);
      }
    },
    [refresh],
  );

 /*
 * =========================================================
 * RESEND INVITATION
 * =========================================================
 */

const resendInvitation = useCallback(
  async (
    invitationId: number,
  ): Promise<Invitation> => {
    try {
      setResending(true);
      setError(null);

      const updated =
        await resendInvitationRequest(
          invitationId,
        );

      await refresh();

      return updated;
    } catch (err: any) {
      console.error(
        "Failed to resend invitation:",
        err,
      );

      const detail =
        err?.response?.data?.detail;

      setError(
        detail ||
          "Unable to resend invitation. Please try again.",
      );

      throw err;
    } finally {
      setResending(false);
    }
  },
  [refresh],
);

/*
 * =========================================================
 * RETURN
 * =========================================================
 */

return {
  organization,
  members,
  invitations,

  loading,
  updating,
  inviting,
  revoking,
  resending,

  error,

  refresh,
  updateOrganization,
  createInvitation,
  updateMemberRole,
  revokeInvitation,
  resendInvitation,
};
}