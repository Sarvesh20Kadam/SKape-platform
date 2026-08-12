import api from "../../../api/client";

import type {
  AcceptInvitationPayload,
  AcceptInvitationResponse,
  CreateInvitationPayload,
  Invitation,
  Organization,
  OrganizationMember,
  UpdateOrganizationPayload,
} from "../types/organization.types";

/*
 * =========================================================
 * ORGANIZATION
 * =========================================================
 */

export async function getCurrentOrganization(): Promise<Organization> {
  const response = await api.get<Organization>(
    "/organizations/current",
  );

  return response.data;
}

export async function updateCurrentOrganization(
  data: UpdateOrganizationPayload,
): Promise<Organization> {
  const response = await api.put<Organization>(
    "/organizations/current",
    data,
  );

  return response.data;
}

/*
 * =========================================================
 * MEMBERS
 * =========================================================
 */

export async function getOrganizationMembers(): Promise<
  OrganizationMember[]
> {
  const response =
    await api.get<OrganizationMember[]>(
      "/organizations/members",
    );

  return response.data;
}

/*
 * =========================================================
 * INVITATIONS
 * =========================================================
 */

export async function createInvitation(
  data: CreateInvitationPayload,
): Promise<Invitation> {
  const response =
    await api.post<Invitation>(
      "/invitations/",
      data,
    );

  return response.data;
}

export async function getOrganizationInvitations(): Promise<
  Invitation[]
> {
  const response =
    await api.get<Invitation[]>(
      "/invitations/",
    );

  return response.data;
}

export async function acceptInvitation(
  data: AcceptInvitationPayload,
): Promise<AcceptInvitationResponse> {
  const response =
    await api.post<AcceptInvitationResponse>(
      "/invitations/accept",
      data,
    );

  return response.data;
}