// Маршрутизация MedPartners. Страницы создаются отдельными агентами в src/pages.
// Используем ленивые импорты, чтобы маршруты подключались по требованию.

import { Suspense, lazy } from "react";
import { Routes, Route } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Spinner, EmptyState } from "./components/ui";

const SearchPage = lazy(() => import("./pages/SearchPage"));
const PartnersPage = lazy(() => import("./pages/PartnersPage"));
const PartnerDetailPage = lazy(() => import("./pages/PartnerDetailPage"));
const AdminPage = lazy(() => import("./pages/AdminPage"));
const VerificationPage = lazy(() => import("./pages/VerificationPage"));
const UnmatchedPage = lazy(() => import("./pages/UnmatchedPage"));
const DashboardPage = lazy(() => import("./pages/DashboardPage"));

function PageFallback() {
  return (
    <div className="py-24">
      <Spinner label="Загрузка раздела" className="justify-center" />
    </div>
  );
}

function NotFound() {
  return (
    <EmptyState
      title="Страница не найдена"
      description="Проверьте адрес или вернитесь к поиску."
    />
  );
}

export default function App() {
  return (
    <Layout>
      <Suspense fallback={<PageFallback />}>
        <Routes>
          <Route path="/" element={<SearchPage />} />
          <Route path="/partners" element={<PartnersPage />} />
          <Route path="/partners/:id" element={<PartnerDetailPage />} />
          <Route path="/admin" element={<AdminPage />} />
          <Route path="/verification" element={<VerificationPage />} />
          <Route path="/unmatched" element={<UnmatchedPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Suspense>
    </Layout>
  );
}
