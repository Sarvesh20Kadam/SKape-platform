import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";

import { login } from "../../../services/auth.service";
import { useAuth } from "../../../context/AuthContext";

import {
  loginSchema,
  type LoginFormData,
} from "../schemas/login.schema";

function LoginForm() {
  const navigate = useNavigate();

  // AuthContext is now responsible for storing
  // and managing the authentication token.
  const { login: loginUser } = useAuth();

  const [serverError, setServerError] = useState("");
  const [loading, setLoading] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (data: LoginFormData) => {
    try {
      setServerError("");
      setLoading(true);

      const response = await login(
        data.email,
        data.password
      );

      console.log("LOGIN RESPONSE:", response);

      // Store authentication through AuthContext.
      // Do NOT use localStorage directly here.
      loginUser(response.access_token);

      console.log("TOKEN SAVED");

      navigate("/dashboard");

      console.log("NAVIGATED");
    } catch (error: any) {
      console.error("LOGIN ERROR:", error);

      setServerError(
        error.response?.data?.detail ??
          error.message ??
          "Login failed. Please try again."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <form
      noValidate
      onSubmit={handleSubmit(onSubmit)}
      className="mt-8 space-y-5"
    >
      {serverError && (
        <div
          role="alert"
          className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400"
        >
          {serverError}
        </div>
      )}

      {/* Email */}

      <div>
        <label
          htmlFor="email"
          className="mb-2 block text-sm text-zinc-400"
        >
          Email
        </label>

        <input
          id="email"
          {...register("email")}
          type="email"
          autoComplete="email"
          placeholder="john@example.com"
          aria-invalid={!!errors.email}
          className={`w-full rounded-lg border bg-zinc-800 px-4 py-3 text-white outline-none transition ${
            errors.email
              ? "border-red-500 focus:border-red-500"
              : "border-zinc-700 focus:border-emerald-500"
          }`}
        />

        {errors.email && (
          <p
            role="alert"
            className="mt-2 text-sm text-red-400"
          >
            {errors.email.message}
          </p>
        )}
      </div>

      {/* Password */}

      <div>
        <label
          htmlFor="password"
          className="mb-2 block text-sm text-zinc-400"
        >
          Password
        </label>

        <input
          id="password"
          {...register("password")}
          type="password"
          autoComplete="current-password"
          placeholder="••••••••"
          aria-invalid={!!errors.password}
          className={`w-full rounded-lg border bg-zinc-800 px-4 py-3 text-white outline-none transition ${
            errors.password
              ? "border-red-500 focus:border-red-500"
              : "border-zinc-700 focus:border-emerald-500"
          }`}
        />

        {errors.password && (
          <p
            role="alert"
            className="mt-2 text-sm text-red-400"
          >
            {errors.password.message}
          </p>
        )}
      </div>

      {/* Submit */}

      <button
        type="submit"
        disabled={loading}
        className="w-full rounded-lg bg-emerald-600 py-3 font-semibold text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {loading ? "Signing In..." : "Sign In"}
      </button>
    </form>
  );
}

export default LoginForm;