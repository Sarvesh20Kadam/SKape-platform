export type Organization = {
  id: number;
  name: string;
  slug: string;
  email: string | null;
  phone: string | null;
  website: string | null;
  logo: string | null;
  industry: string | null;
  address: string | null;
  is_active: boolean;
};

export type OrganizationMember = {
  id: number;
  name: string;
  email: string;
  role: string;
  is_active: boolean;
};

export type UpdateOrganizationPayload = {
  name?: string;
  email?: string | null;
  phone?: string | null;
  website?: string | null;
  logo?: string | null;
  industry?: string | null;
  address?: string | null;
  is_active?: boolean;
};

export type CreateInvitationPayload = {
  email: string;
  role: string;
};

export type Invitation = {
  id: number;
  email: string;
  role: string;
  status: string;
  organization_id: number;
  expires_at: string;
  created_at: string;
};

export type AcceptInvitationPayload = {
  token: string;
  name: string;
  password: string;
};

export type AcceptInvitationResponse = {
  message: string;
  user_id: number;
  organization_id: number;
  role: string;
};