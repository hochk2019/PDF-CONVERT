import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { useAuth } from '@/hooks/useAuth';
import styles from './Layout.module.css';

const navLinks = [
  { href: '/jobs', label: 'Jobs' },
  { href: '/admin', label: 'Admin' },
  { href: '/admin/llm', label: 'LLM' },
];

export const Layout: React.FC<{ children: React.ReactNode; title?: string }> = ({ children, title }) => {
  const router = useRouter();
  const { logout, isAuthenticated } = useAuth();

  return (
    <div className={styles.container}>
      <Head>
        <title>{title ? `${title} · PDF Convert` : 'PDF Convert Platform'}</title>
      </Head>
      <header className={styles.header}>
        <div>
          <h1 className={styles.logo}>PDF Convert</h1>
          <p className={styles.subtitle}>Smart OCR orchestration for teams</p>
        </div>
        {isAuthenticated && (
          <nav className={styles.nav}>
            {navLinks.map((link) => (
              <Link key={link.href} href={link.href} className={router.pathname === link.href ? styles.active : ''}>
                {link.label}
              </Link>
            ))}
            <button type="button" className={styles.logout} onClick={logout}>
              Đăng xuất
            </button>
          </nav>
        )}
      </header>
      <main className={styles.main}>{children}</main>
    </div>
  );
};
