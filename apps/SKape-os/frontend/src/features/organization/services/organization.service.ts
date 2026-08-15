import api from "../../../api/client";

import type {
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
  const response = await api.get<OrganizationMember[]>(
    "/organizations/members",
  );

  return response.data;
}

/*
 * =========================================================
 * INVITATIONS
 * =========================================================
 */

export async function getOrganizationInvitations(): Promise<
  Invitation[]
> {
  const response = await api.get<Invitation[]>(
    "/invitations/",
  );

  return response.data;
}

export async function createInvitation(
  data: CreateInvitationPayload,
): Promise<Invitation> {
  const response = await api.post<Invitation>(
    "/invitations/",
    data,
  );

  return response.data;
}

export async function revokeInvitation(
  invitationId: number,
): Promise<void> {
  await api.delete(
    `/invitations/${invitationId}`,
  );
}

export async function resendInvitation(
  invitationId: number,
): Promise<Invitation> {
  const response = await api.post<Invitation>(
    `/invitations/${invitationId}/resend`,
  );

  return response.data;
}

export async function acceptInvitation(
  data: {
    token: string;
    name: string;
    password: string;
  },
): Promise<{
  message: string;
  user_id: number;
  organization_id: number;
  role: string;
}> {
  const response = await api.post<{
    message: string;
    user_id: number;
    organization_id: number;
    role: string;
  }>(
    "/invitations/accept",
    data,
  );

  return response.data;
}

export async function acceptExistingInvitation(
  token: string,
): Promise<{
  message: string;
  user_id: number;
  organization_id: number;
  role: string;
}> {
  const response = await api.post<{
    message: string;
    user_id: number;
    organization_id: number;
    role: string;
  }>(
    "/invitations/accept-existing",
    {
      token,
    },
  );

  return response.data;
}

/*
 * =========================================================
 * MEMBER ROLE MANAGEMENT
 * =========================================================
 */

export async function updateMemberRole(
  userId: number,
  role: string,
): Promise<OrganizationMember> {
  const response = await api.patch<OrganizationMember>(
    `/users/${userId}/role`,
    {
      role,
    },
  );

  return response.data;
}