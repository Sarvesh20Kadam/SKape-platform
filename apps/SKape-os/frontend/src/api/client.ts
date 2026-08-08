import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  timeout: 10000,

  headers: {
    Accept: "application/json",
  },
});

/*
 * Attach authentication credentials to every API request.
 *
 * We intentionally read the token at request time rather than
 * when the axios instance is created. This ensures a newly
 * authenticated session is immediately recognized without
 * recreating the axios client.
 */
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("access_token");

    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

/*
 * Centralized authentication failure handling.
 *
 * A 401 means the current authentication state is no longer
 * accepted by the backend. Remove the stale token so the
 * ProtectedRoute can send the user back to login.
 */
api.interceptors.response.use(
  (response) => response,

  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("access_token");
    }

    return Promise.reject(error);
  }
);

export default api;