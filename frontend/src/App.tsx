import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./components/layout/AppShell";
import { ContextPage } from "./pages/ContextPage";
import { HomePage } from "./pages/HomePage";
import { SettingsPage } from "./pages/SettingsPage";
import { StudioPage } from "./pages/StudioPage";
import { StyleguidePage } from "./pages/StyleguidePage";

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<HomePage />} />
        <Route path="context" element={<ContextPage />} />
        <Route path="studio" element={<StudioPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="styleguide" element={<StyleguidePage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
