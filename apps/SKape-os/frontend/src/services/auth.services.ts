import api from "../api/client";
import type {
    LoginRequest,
    LoginResponse,
} from "../types/auth";

export async function login(
    data: LoginRequest
): Promise<LoginResponse> {

    const response = await api.post<LoginResponse>(
        "/users/login",
        data
    );

    return response.data;
}