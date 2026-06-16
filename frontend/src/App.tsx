import { Navigate, Route, Routes } from 'react-router-dom';
import { AppLayout } from './components/layout/AppLayout';
import { AuthPage } from './pages/Auth/AuthPage';
import { HomePage } from './pages/HomePage';
import { BidEditorPage } from './pages/BidEditor';
import { OnlyOfficeEditorPage } from './pages/OnlyOfficeEditor';
import { InterpretationPage } from './pages/Interpretation';
import { KnowledgeBasePage } from './pages/KnowledgeBase';
import { ProductBasePage } from './pages/ProductBase';
import { QualificationBasePage } from './pages/QualificationBase';
import { BidPrefillPage } from './pages/BidPrefill';
import { SettingsPage } from './pages/Settings';
import { HistoryPage } from './pages/History';
import { UsageCostPage } from './pages/UsageCost';
import { useAuthStore } from './stores/authStore';

function RequireAuth({ children }: { children: JSX.Element }): JSX.Element {
  const token = useAuthStore(state => state.token);
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return children;
}

export function App(): JSX.Element {
  return (
    <Routes>
      <Route path="/login" element={<AuthPage mode="login" />} />
      <Route path="/register" element={<AuthPage mode="register" />} />
      <Route path="/bid-editor" element={<RequireAuth><BidEditorPage /></RequireAuth>} />
      <Route path="/onlyoffice-editor" element={<RequireAuth><OnlyOfficeEditorPage /></RequireAuth>} />
      <Route
        path="/*"
        element={
          <RequireAuth>
            <AppLayout>
              <Routes>
                <Route path="/" element={<HomePage />} />
                <Route path="/bidding" element={<HomePage />} />
                <Route path="/interpretation" element={<InterpretationPage />} />
                <Route path="/prefill" element={<BidPrefillPage />} />
                <Route path="/knowledge" element={<KnowledgeBasePage />} />
                <Route path="/qualification" element={<QualificationBasePage />} />
                <Route path="/products" element={<ProductBasePage />} />
                <Route path="/usage-cost" element={<UsageCostPage />} />
                <Route path="/settings" element={<SettingsPage />} />
                <Route path="/history" element={<HistoryPage />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </AppLayout>
          </RequireAuth>
        }
      />
    </Routes>
  );
}
