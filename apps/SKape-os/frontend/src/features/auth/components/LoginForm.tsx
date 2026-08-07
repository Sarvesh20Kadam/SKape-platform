import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";

import { login } from "../../../services/auth.service";

import {
  loginSchema,
  type LoginFormData,
} from "../schemas/login.schema";

function LoginForm() {
  const navigate = useNavigate();

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
  
      localStorage.setItem(
        "access_token",
        response.access_token
      );
  
      console.log("TOKEN SAVED");
  
      navigate("/dashboard");
  
      console.log("NAVIGATED");
    } catch (error: any) {
      console.error("LOGIN ERROR:", error);
      console.error("RESPONSE:", error.response);
      console.error("DATA:", error.response?.data);
  
      setServerError(
        error.response?.data?.detail ??
        error.message ??
        "Login failed"
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
        <div className="rounded-lg border border-red-600 bg-red-900/20 p-3 text-sm text-red-400">
          {serverError}
        </div>
      )}

      <div>
        <label className="mb-2 block text-sm text-zinc-400">
          Email
        </label>

        <input
          {...register("email")}
          type="email"
          placeholder="john@example.com"
          className={`w-full rounded-lg border bg-zinc-800 px-4 py-3 outline-none transition ${
            errors.email
              ? "border-red-500"
              : "border-zinc-700 focus:border-emerald-500"
          }`}
        />

        {errors.email && (
          <p className="mt-2 text-sm text-red-400">
            {errors.email.message}
          </p>
        )}
      </div>

      <div>
        <label className="mb-2 block text-sm text-zinc-400">
          Password
        </label>

        <input
          {...register("password")}
          type="password"
          placeholder="••••••••"
          className={`w-full rounded-lg border bg-zinc-800 px-4 py-3 outline-none transition ${
            errors.password
              ? "border-red-500"
              : "border-zinc-700 focus:border-emerald-500"
          }`}
        />

        {errors.password && (
          <p className="mt-2 text-sm text-red-400">
            {errors.password.message}
          </p>
        )}
      </div>

      <button
        type="submit"
        disabled={loading}
        className="w-full rounded-lg bg-emerald-600 py-3 font-semibold transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {loading ? "Signing In..." : "Sign In"}
      </button>
    </form>
  );
}

export default LoginForm;