import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

type AuthContextType = {
  token: string | null;
  isAuthenticated: boolean;
  login: (token: string) => void;
  logout: () => void;
};

const AuthContext =
  createContext<AuthContextType | null>(null);

type Props = {
  children: ReactNode;
};

export function AuthProvider({
  children,
}: Props) {
  const [token, setToken] =
    useState<string | null>(null);

  useEffect(() => {
    const stored =
      localStorage.getItem("access_token");

    if (stored) {
      setToken(stored);
    }
  }, []);

  function login(token: string) {
    localStorage.setItem(
      "access_token",
      token
    );

    setToken(token);
  }

  function logout() {
    localStorage.removeItem(
      "access_token"
    );

    setToken(null);
  }

  return (
    <AuthContext.Provider
      value={{
        token,
        isAuthenticated: !!token,
        login,
        logout,
      }}
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
      "useAuth must be used inside AuthProvider"
    );
  }

  return context;
}