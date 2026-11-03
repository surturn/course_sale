import React, { Suspense, lazy } from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Link, NavLink, Route, Routes } from 'react-router-dom';
import { AuthProvider, RequireAuth, useAuth } from './auth';
import Catalog from './views/Catalog';
import ResourcePage from './views/ResourcePage';
import { Login, Recover, Register } from './views/Auth';
import OrderStatus from './views/OrderStatus';
import Library from './views/Library';
import FreeLibrary from './views/FreeLibrary';
import News from './views/News';
import { DisclaimerGate } from './components/Disclaimer';
import '@fontsource-variable/schibsted-grotesk';
import './styles.css';

const Reader = lazy(() => import('./views/Reader'));
const Admin = lazy(() => import('./views/Admin'));

function Header() {
  const { user, logout } = useAuth();
  return (
    <header className="site-header">
      <div className="bar">
      <Link to="/" className="brand">Invonics</Link>
      <nav>
        <NavLink to="/free">Free library</NavLink>
        <NavLink to="/news">Tech news</NavLink>
        {user && <NavLink to="/library">{user.is_guest ? 'Save my library' : 'My library'}</NavLink>}
        {user?.is_admin && <NavLink to="/admin">Manage</NavLink>}
        {user === null && <NavLink to="/login">Log in</NavLink>}
        {user && !user.is_guest && <button className="link" onClick={logout}>Log out</button>}
      </nav>
      </div>
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
          <Route path="/free" element={<DisclaimerGate><FreeLibrary /></DisclaimerGate>} />
          <Route path="/news" element={<DisclaimerGate><News /></DisclaimerGate>} />
          <Route path="/r/:id" element={<ResourcePage />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/recover" element={<Recover />} />
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
