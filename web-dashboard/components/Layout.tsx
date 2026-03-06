import Link from 'next/link';
import { useRouter } from 'next/router';
import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import OpenTrainLogo from './OpenTrainLogo';

interface LayoutProps {
  children: React.ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  const router = useRouter();
  const [online, setOnline] = useState<boolean | null>(null);
  const [theme, setTheme] = useState<'light'|'dark'>(() => {
    if (typeof window === 'undefined') return 'dark';
    const stored = localStorage.getItem('theme');
    if (stored === 'light' || stored === 'dark') return stored as 'light'|'dark';
    // default to system preference
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches
      ? 'light' : 'dark';
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  useEffect(() => {
    api.health.check()
      .then(() => setOnline(true))
      .catch(() => setOnline(false));
  }, []);

  const nav = [
    { href: '/',         label: 'Jobs' },
    { href: '/workers',  label: 'Workers' },
    { href: '/submit',   label: '+ Submit' },
  ];

  return (
    <div className="layout">
      <header className="topbar">
        <Link href="/" className="topbar-logo">
          <OpenTrainLogo />
          <h1>
            OPENTRAIN
          </h1>
        </Link>

        <nav className="topbar-nav">
          {nav.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className={router.pathname === href ? 'active' : ''}
            >
              {label}
            </Link>
          ))}
        </nav>

        <div className="topbar-status">
          {online === null ? (
            <><div className="spinner" style={{ width: 8, height: 8, borderWidth: 1.5 }} /> connecting</>
          ) : online ? (
            <><div className="status-dot" /> coordinator online</>
          ) : (
            <><div className="status-dot" style={{ background: 'var(--red)', animation: 'none' }} /> coordinator offline</>
          )}
        </div>
        <button
          className="theme-toggle"
          onClick={() => setTheme(prev => (prev === 'dark' ? 'light' : 'dark'))}
          aria-label="Toggle theme"
          title="Toggle light/dark theme"
        >
          {theme === 'dark' ? '☀️' : '🌙'}
        </button>
      </header>

      <main>
        {children}
      </main>
    </div>
  );
}