import api from "../api/client";

export type CurrentUser = {
  id: number;
  name: string;
  email: string;
  role: string;
  organization_id: number | null;
  is_active: boolean;
};

export async function login(
  email: string,
  password: string,
) {
  const formData = new URLSearchParams();

  formData.append("username", email);
  formData.append("password", password);

  const response = await api.post(
    "/users/login",
    formData,
    {
      headers: {
        "Content-Type":
          "application/x-www-form-urlencoded",
      },
    },
  );

  return response.data;
}

export async function getCurrentUser(): Promise<CurrentUser> {
  const response = await api.get<CurrentUser>(
    "/users/me",
  );

  return response.data;
}