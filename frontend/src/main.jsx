import React, { Suspense, lazy } from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Link, NavLink, Route, Routes } from 'react-router-dom';
import { AuthProvider, RequireAuth, useAuth } from './auth';
import Catalog from './views/Catalog';
import ResourcePage from './views/ResourcePage';
import { Login, Register } from './views/Auth';
import OrderStatus from './views/OrderStatus';
import Library from './views/Library';
import '@fontsource-variable/schibsted-grotesk';
import './styles.css';

const Reader = lazy(() => import('./views/Reader'));
const Admin = lazy(() => import('./views/Admin'));

function Header() {
  const { user, logout } = useAuth();
  return (
    <header className="site-header">
      <Link to="/" className="brand">Invonics</Link>
      <nav>
        {user && <NavLink to="/library">My library</NavLink>}
        {user?.is_admin && <NavLink to="/admin">Manage</NavLink>}
        {user === null && <NavLink to="/login">Log in</NavLink>}
        {user && <button className="link" onClick={logout}>Log out</button>}
      </nav>
    </header>
  );
}

function App() {
  return (
    <>
      <Header />
      <main>
        <Suspense fallback={null}>
        <Routes>
          <Route path="/" element={<Catalog />} />
          <Route path="/r/:id" element={<ResourcePage />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/orders/:id" element={<RequireAuth><OrderStatus /></RequireAuth>} />
          <Route path="/library" element={<RequireAuth><Library /></RequireAuth>} />
          <Route path="/read/:id" element={<RequireAuth><Reader /></RequireAuth>} />
          <Route path="/admin" element={<RequireAuth admin><Admin /></RequireAuth>} />
          <Route path="*" element={<p className="empty">That page doesn't exist. <Link to="/">Browse resources</Link></p>} />
        </Routes>
        </Suspense>
      </main>
    </>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
