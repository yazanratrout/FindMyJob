import { Navigate, Route, Routes } from "react-router-dom";
import { useAuthStatus } from "@/api/hooks";
import { LoginScreen, SetupScreen } from "@/auth/AuthScreens";
import { Layout } from "@/components/Layout";
import { Spinner } from "@/components/ui";
import { DashboardPage } from "@/pages/DashboardPage";
import { PlaceholderPage } from "@/pages/Placeholder";
import { RunsPage } from "@/pages/RunsPage";

export default function App() {
  const status = useAuthStatus();

  if (status.isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner />
      </div>
    );
  }
  if (!status.data?.configured) return <SetupScreen />;
  if (!status.data.authenticated) return <LoginScreen />;

  return (
    <Layout>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/runs" element={<RunsPage />} />
        <Route
          path="/tracker"
          element={
            <PlaceholderPage
              title="Tracker"
              note="Application status board — arrives in CP20."
            />
          }
        />
        <Route
          path="/settings"
          element={
            <PlaceholderPage
              title="Settings"
              note="The full settings editor arrives with the onboarding wizard in CP16."
            />
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}
