import {
  Route,
  Routes,
} from "react-router-dom";

import LoginPage from "../pages/LoginPage";
import DashboardPage from "../pages/DashboardPage";
import ProtectedRoute from "./ProtectedRoute";

function AppRouter() {
  return (
      <Routes>

          <Route
              path="/"
              element={<LoginPage />}
          />

          <Route element={<ProtectedRoute />}>

              <Route
                  path="/dashboard"
                  element={<DashboardPage />}
              />

          </Route>

      </Routes>
  );
}

export default AppRouter;