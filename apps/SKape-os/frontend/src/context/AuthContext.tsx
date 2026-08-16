import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  getCurrentUser,
  type CurrentUser,
} from "../services/auth.service";

type AuthContextValue = {
  token: string | null;
  user: CurrentUser | null;
  isAuthenticated: boolean;
  isInitializing: boolean;

  login: (token: string) => void;
  logout: () => void;
  refreshUser: () => Promise<CurrentUser | null>;
};

const AuthContext =
  createContext<AuthContextValue | undefined>(
    undefined,
  );

type AuthProviderProps = {
  children: ReactNode;
};

const ACCESS_TOKEN_KEY = "access_token";

export function AuthProvider({
  children,
}: AuthProviderProps) {
  const [token, setToken] =
    useState<string | null>(null);

  const [user, setUser] =
    useState<CurrentUser | null>(null);

  const [isInitializing, setIsInitializing] =
    useState(true);

  /*
   * =========================================================
   * LOAD CURRENT USER
   * =========================================================
   */

  const refreshUser = async (): Promise<CurrentUser | null> => {
    try {
      const currentUser =
        await getCurrentUser();

      setUser(currentUser);

      return currentUser;
    } catch (error) {
      console.error(
        "Failed to load current user:",
        error,
      );

      setUser(null);

      return null;
    }
  };

  /*
   * =========================================================
   * RESTORE AUTHENTICATION
   * =========================================================
   */

  useEffect(() => {
    const restoreAuthentication =
      async () => {
        try {
          const storedToken =
            localStorage.getItem(
              ACCESS_TOKEN_KEY,
            );

          if (!storedToken) {
            return;
          }

          setToken(storedToken);

          const currentUser =
            await getCurrentUser();

          setUser(currentUser);
        } catch (error) {
          console.error(
            "Failed to restore authentication state:",
            error,
          );

          localStorage.removeItem(
            ACCESS_TOKEN_KEY,
          );

          setToken(null);
          setUser(null);
        } finally {
          setIsInitializing(false);
        }
      };

    void restoreAuthentication();
  }, []);

  /*
   * =========================================================
   * HANDLE UNAUTHORIZED RESPONSE
   * =========================================================
   */

  useEffect(() => {
    const handleUnauthorized = () => {
      localStorage.removeItem(
        ACCESS_TOKEN_KEY,
      );

      setToken(null);
      setUser(null);
    };

    window.addEventListener(
      "auth:unauthorized",
      handleUnauthorized,
    );

    return () => {
      window.removeEventListener(
        "auth:unauthorized",
        handleUnauthorized,
      );
    };
  }, []);

  /*
   * =========================================================
   * LOGIN
   * =========================================================
   */

  const login = (newToken: string) => {
    if (!newToken) {
      throw new Error(
        "Cannot authenticate without a token.",
      );
    }

    localStorage.setItem(
      ACCESS_TOKEN_KEY,
      newToken,
    );

    setToken(newToken);
  };

  /*
   * =========================================================
   * LOGOUT
   * =========================================================
   */

  const logout = () => {
    localStorage.removeItem(
      ACCESS_TOKEN_KEY,
    );

    setToken(null);
    setUser(null);
  };

  const value = useMemo(
    () => ({
      token,
      user,
      isAuthenticated: Boolean(token),
      isInitializing,
      login,
      logout,
      refreshUser,
    }),
    [
      token,
      user,
      isInitializing,
    ],
  );

  return (
    <AuthContext.Provider
      value={value}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context =
    useContext(AuthContext);

  if (!context) {
    throw new Error(
      "useAuth must be used inside AuthProvider.",
    );
  }

  return context;
}