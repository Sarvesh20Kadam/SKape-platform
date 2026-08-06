import {
    createContext,
    useContext,
    useState,
    type ReactNode,
  } from "react";
  
  type AuthContextType = {
    token: string | null;
    login: (token: string) => void;
    logout: () => void;
  };
  
  const AuthContext = createContext<AuthContextType | null>(
    null
  );
  
  export function AuthProvider({
    children,
  }: {
    children: ReactNode;
  }) {
    const [token, setToken] = useState<string | null>(
      localStorage.getItem("skape_token")
    );
  
    function login(token: string) {
      localStorage.setItem("skape_token", token);
      setToken(token);
    }
  
    function logout() {
      localStorage.removeItem("skape_token");
      setToken(null);
    }
  
    return (
      <AuthContext.Provider
        value={{
          token,
          login,
          logout,
        }}
      >
        {children}
      </AuthContext.Provider>
    );
  }
  
  export function useAuth() {
    const context = useContext(AuthContext);
  
    if (!context) {
      throw new Error(
        "useAuth must be used inside AuthProvider"
      );
    }
  
    return context;
  }