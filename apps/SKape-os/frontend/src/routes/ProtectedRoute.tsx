import {
    Navigate,
    Outlet,
} from "react-router-dom";

import { isAuthenticated } from "../utils/auth";

function ProtectedRoute() {

    if (!isAuthenticated()) {
        return <Navigate to="/" replace />;
    }

    return <Outlet />;
}

export default ProtectedRoute;