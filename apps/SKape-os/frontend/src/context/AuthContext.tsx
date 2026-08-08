import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

type AuthContextValue = {
  token: string | null;
  isAuthenticated: boolean;
  isInitializing: boolean;
  login: (token: string) => void;
  logout: () => void;
};

const AuthContext =
  createContext<AuthContextValue | undefined>(
    undefined
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

  const [isInitializing, setIsInitializing] =
    useState(true);

  // Restore authentication when the application starts
  useEffect(() => {
    try {
      const storedToken =
        localStorage.getItem(ACCESS_TOKEN_KEY);

      if (storedToken) {
        setToken(storedToken);
      }
    } catch (error) {
      console.error(
        "Failed to restore authentication state:",
        error
      );
    } finally {
      setIsInitializing(false);
    }
  }, []);

  // Handle a 401 response from Axios
  useEffect(() => {
    const handleUnauthorized = () => {
      localStorage.removeItem(
        ACCESS_TOKEN_KEY
      );

      setToken(null);
    };

    window.addEventListener(
      "auth:unauthorized",
      handleUnauthorized
    );

    return () => {
      window.removeEventListener(
        "auth:unauthorized",
        handleUnauthorized
      );
    };
  }, []);

  // Login
  const login = (newToken: string) => {
    if (!newToken) {
      throw new Error(
        "Cannot authenticate without a token."
      );
    }

    localStorage.setItem(
      ACCESS_TOKEN_KEY,
      newToken
    );

    setToken(newToken);
  };

  // Logout
  const logout = () => {
    localStorage.removeItem(
      ACCESS_TOKEN_KEY
    );

    setToken(null);
  };

  const value = useMemo(
    () => ({
      token,
      isAuthenticated: Boolean(token),
      isInitializing,
      login,
      logout,
    }),
    [token, isInitializing]
  );

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context =
    useContext(AuthContext);

  if (!context) {
    throw new Error(
      "useAuth must be used inside AuthProvider."
    );
  }

  return context;
}