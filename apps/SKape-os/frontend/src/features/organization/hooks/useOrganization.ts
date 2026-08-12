import {
    useCallback,
    useEffect,
    useState,
  } from "react";

  import {
    createInvitation as createInvitationRequest,
    getCurrentOrganization,
    getOrganizationMembers,
    updateCurrentOrganization,
  } from "../services/organization.service";

  import type {
    CreateInvitationPayload,
    Organization,
    OrganizationMember,
    UpdateOrganizationPayload,
  } from "../types/organization.types";

  type UseOrganizationResult = {
    organization: Organization | null;
    members: OrganizationMember[];

    loading: boolean;
    updating: boolean;
    inviting: boolean;

    error: string | null;

    refresh: () => Promise<void>;

    updateOrganization: (
      data: UpdateOrganizationPayload,
    ) => Promise<Organization>;

    createInvitation: (
      data: CreateInvitationPayload,
    ) => Promise<void>;
  };

  export function useOrganization(): UseOrganizationResult {
    const [organization, setOrganization] =
      useState<Organization | null>(null);

    const [members, setMembers] =
      useState<OrganizationMember[]>([]);

    const [loading, setLoading] =
      useState(true);

    const [updating, setUpdating] =
      useState(false);

    const [inviting, setInviting] =
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

        setOrganization(
          organizationData,
        );

        setMembers(
          membersData,
        );
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
    }, []);

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
            await updateCurrentOrganization(
              data,
            );

          setOrganization(
            updated,
          );

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

          await createInvitationRequest(
            data,
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

    return {
      organization,
      members,

      loading,
      updating,
      inviting,

      error,

      refresh,
      updateOrganization,
      createInvitation,
    };
  }
