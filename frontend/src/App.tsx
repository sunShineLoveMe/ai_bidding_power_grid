import { Navigate, Route, Routes } from 'react-router-dom';
import { AppLayout } from './components/layout/AppLayout';
import { EmptyRoutePage } from './components/common/EmptyRoutePage';
import { HomePage } from './pages/HomePage';
import { BidEditorPage } from './pages/BidEditor';
import { OnlyOfficeEditorPage } from './pages/OnlyOfficeEditor';
import { InterpretationPage } from './pages/Interpretation';
import { KnowledgeBasePage } from './pages/KnowledgeBase';
import { ProductBasePage } from './pages/ProductBase';
import { QualificationBasePage } from './pages/QualificationBase';
import { SettingsPage } from './pages/Settings';
import { HistoryPage } from './pages/History';
import { UsageCostPage } from './pages/UsageCost';

export function App(): JSX.Element {
  return (
    <Routes>
      <Route path="/bid-editor" element={<BidEditorPage />} />
      <Route path="/onlyoffice-editor" element={<OnlyOfficeEditorPage />} />
      <Route
        path="/*"
        element={
          <AppLayout>
            <Routes>
              <Route path="/" element={<HomePage />} />
              <Route path="/bidding" element={<HomePage />} />
              <Route path="/interpretation" element={<InterpretationPage />} />
              <Route path="/knowledge" element={<KnowledgeBasePage />} />
              <Route path="/qualification" element={<QualificationBasePage />} />
              <Route path="/products" element={<ProductBasePage />} />
              <Route path="/usage-cost" element={<UsageCostPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/history" element={<HistoryPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </AppLayout>
        }
      />
    </Routes>
  );
}
