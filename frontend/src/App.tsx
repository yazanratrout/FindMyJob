import { Navigate, Route, Routes } from "react-router-dom";
import { useAuthStatus, useSettings } from "@/api/hooks";
import { LoginScreen, SetupScreen } from "@/auth/AuthScreens";
import { Layout } from "@/components/Layout";
import { Spinner } from "@/components/ui";
import { OnboardingWizard } from "@/onboarding/Wizard";
import { DashboardPage } from "@/pages/DashboardPage";
import { PlaceholderPage } from "@/pages/Placeholder";
import { RunsPage } from "@/pages/RunsPage";
import { SettingsPage } from "@/pages/SettingsPage";

function FullScreen({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center">{children}</div>
  );
}

function AuthedApp() {
  const settings = useSettings();

  if (settings.isLoading) return <FullScreen>{<Spinner />}</FullScreen>;
  if (settings.data && !settings.data.onboarding_completed) {
    return <OnboardingWizard />;
  }

  return (
    <Layout>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/runs" element={<RunsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route
          path="/tracker"
          element={
            <PlaceholderPage
              title="Tracker"
              note="Application status board — arrives in CP20."
            />
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}

export default function App() {
  const status = useAuthStatus();

  if (status.isLoading) return <FullScreen>{<Spinner />}</FullScreen>;
  if (!status.data?.configured) return <SetupScreen />;
  if (!status.data.authenticated) return <LoginScreen />;
  return <AuthedApp />;
}
