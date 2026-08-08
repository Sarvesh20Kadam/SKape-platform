import {
    Navigate,
    Outlet,
    useLocation,
  } from "react-router-dom";
  
  import { useAuth } from "../context/AuthContext";
  
  function ProtectedRoute() {
    const {
      isAuthenticated,
      isInitializing,
    } = useAuth();
  
    const location = useLocation();
  
    if (isInitializing) {
      return (
        <div className="flex min-h-screen items-center justify-center bg-zinc-950 text-zinc-400">
          Loading SKape...
        </div>
      );
    }
  
    if (!isAuthenticated) {
      return (
        <Navigate
          to="/"
          replace
          state={{
            from: location.pathname,
          }}
        />
      );
    }
  
    return <Outlet />;
  }
  
  export default ProtectedRoute;