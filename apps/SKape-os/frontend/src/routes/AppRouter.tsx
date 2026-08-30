import {
  Navigate,
  Route,
  Routes,
} from "react-router-dom";

import LoginPage from "../pages/LoginPage";
import AcceptInvitationPage from "../pages/AcceptInvitationPage";
import DashboardPage from "../pages/DashboardPage";
import OrganizationPage from "../pages/OrganizationPage";
import ProjectsPage from "../pages/ProjectsPage";
import ProjectDetailPage from "../pages/ProjectDetailPage";
import TasksPage from "../pages/TasksPage";
import TaskDetailPage from "../pages/TaskDetailPage";
import AssetsPage from "../pages/AssetsPage";
import DevicesPage from "../pages/DevicesPage";
import DeviceDetailPage from "../pages/DeviceDetailPage";
import AlertsPage from "../pages/AlertsPage";

import ProtectedRoute from "./ProtectedRoute";

function AppRouter() {
  return (
    <Routes>
      {/* =====================================================
          PUBLIC ROUTES
          ===================================================== */}

      <Route
        path="/login"
        element={<LoginPage />}
      />

      <Route
        path="/accept-invitation"
        element={<AcceptInvitationPage />}
      />

      {/* =====================================================
          PROTECTED ROUTES
          ===================================================== */}

      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        }
      />

      {/* =====================================================
          ORGANIZATION
          ===================================================== */}

      <Route
        path="/organization"
        element={
          <ProtectedRoute>
            <OrganizationPage />
          </ProtectedRoute>
        }
      />

      {/* =====================================================
          PROJECTS
          ===================================================== */}

      <Route
        path="/projects"
        element={
          <ProtectedRoute>
            <ProjectsPage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/assets"
        element={
          <ProtectedRoute>
             <AssetsPage />
         </ProtectedRoute>
        }
      />
      
      <Route
        path="/devices"
        element={
          <ProtectedRoute>
            <DevicesPage />
          </ProtectedRoute>
  }
  />

       <Route
         path="/alerts"
         element={
          <ProtectedRoute>
            <AlertsPage />
         </ProtectedRoute>
        }
      />
      
      <Route
        path="/devices/:deviceId"
        element={
          <ProtectedRoute>
            <DeviceDetailPage />
         </ProtectedRoute>
        }
      />

      <Route
        path="/projects/:projectId"
        element={
          <ProtectedRoute>
            <ProjectDetailPage />
          </ProtectedRoute>
        }
      />

      {/* =====================================================
          TASKS
          ===================================================== */}

      <Route
        path="/tasks"
        element={
          <ProtectedRoute>
            <TasksPage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/tasks/:taskId"
        element={
          <ProtectedRoute>
            <TaskDetailPage />
          </ProtectedRoute>
        }
      />

      {/* =====================================================
          DEFAULT ROUTE
          ===================================================== */}

      <Route
        path="/"
        element={
          <Navigate
            to="/dashboard"
            replace
          />
        }
      />

      {/* =====================================================
          UNKNOWN ROUTES
          ===================================================== */}

      <Route
        path="*"
        element={
          <Navigate
            to="/dashboard"
            replace
          />
        }
      />
    </Routes>
  );
}

export default AppRouter;