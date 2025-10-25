import { FormEvent, useState } from 'react';
import { Layout } from '@/components/Layout';
import { useAuth } from '@/hooks/useAuth';
import styles from './index.module.css';

const LoginPage = () => {
  const { login, register, isAuthenticated } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    try {
      if (mode === 'login') {
        await login(email, password);
      } else {
        await register({ email, password, full_name: fullName });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể đăng nhập.');
    }
  };

  return (
    <Layout title="Đăng nhập">
      <section className={styles.hero}>
        <div className={styles.copy}>
          <h2>Tự động hóa OCR tài liệu PDF</h2>
          <p>
            Theo dõi tiến độ xử lý, cấu hình pipeline và nhận thông báo real-time qua WebSocket. Dành cho đội
            ngũ vận hành tài liệu nội bộ.
          </p>
        </div>
        <form className={styles.form} onSubmit={handleSubmit}>
          <div className={styles.switcher}>
            <button
              type="button"
              className={mode === 'login' ? styles.active : ''}
              onClick={() => setMode('login')}
            >
              Đăng nhập
            </button>
            <button
              type="button"
              className={mode === 'register' ? styles.active : ''}
              onClick={() => setMode('register')}
            >
              Tạo tài khoản
            </button>
          </div>
          <label>
            Email
            <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
          </label>
          {mode === 'register' && (
            <label>
              Họ tên
              <input type="text" value={fullName} onChange={(event) => setFullName(event.target.value)} />
            </label>
          )}
          <label>
            Mật khẩu
            <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required />
          </label>
          <button type="submit">{mode === 'login' ? 'Tiếp tục' : 'Đăng ký & đăng nhập'}</button>
          {error && <p className={styles.error}>{error}</p>}
          {isAuthenticated && <p className={styles.success}>Đăng nhập thành công! Điều hướng tới Jobs...</p>}
        </form>
      </section>
    </Layout>
  );
};

export default LoginPage;
