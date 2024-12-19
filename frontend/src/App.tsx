import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import MainLayout from './layouts/MainLayout';
import Sites from './pages/Sites';
import Statistics from './pages/Statistics';
import Test from './pages/Test';
import Settings from './pages/Settings';

const App: React.FC = () => {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<MainLayout />}>
          <Route index element={<Navigate to="/sites" replace />} />
          <Route path="sites" element={<Sites />} />
          <Route path="statistics" element={<Statistics />} />
          <Route path="test" element={<Test />} />
          <Route path="settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/sites" replace />} />
        </Route>
      </Routes>
    </Router>
  );
};

export default App; 
