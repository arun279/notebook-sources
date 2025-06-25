import React from 'react';
import { Routes, Route, Navigate, Link } from 'react-router-dom';
import HomePage from './pages/HomePage';
import ReferencesPage from './pages/ReferencesPage';

const App: React.FC = () => {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="px-4 py-2 bg-primary text-white flex items-center">
        <h1 className="text-lg font-semibold mr-auto">Notebook References</h1>
        <nav className="space-x-4">
          <Link to="/" className="hover:underline">
            Home
          </Link>
          <Link to="/references" className="hover:underline">
            References
          </Link>
        </nav>
      </header>
      <main className="flex-1 p-4">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/references" element={<ReferencesPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
};

export default App; 