import { useCallback, useEffect, useState } from 'react';
import { fetchAdminLLMStatus, LLMStatusResponse } from '@/lib/api';
import { useAuth } from '@/hooks/useAuth';
import styles from './AdminLLMStatus.module.css';

export const AdminLLMStatus: React.FC = () => {
  const { token, user } = useAuth();
  const [status, setStatus] = useState<LLMStatusResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!token) return;
    if (!user?.is_admin) {
      setError('Bạn cần quyền quản trị để xem trạng thái LLM.');
      return;
    }
    setIsLoading(true);
    try {
      const data = await fetchAdminLLMStatus(token);
      setStatus(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể tải trạng thái LLM.');
    } finally {
      setIsLoading(false);
    }
  }, [token, user]);

  useEffect(() => {
    if (token) {
      void refresh();
    }
  }, [token, refresh]);

  if (!token) {
    return <p>Đăng nhập để truy cập trang này.</p>;
  }

  if (!user?.is_admin) {
    return <p className={styles.error}>{error ?? 'Không có quyền truy cập.'}</p>;
  }

  return (
    <section className={styles.panel}>
      <header className={styles.header}>
        <div>
          <h2>Giám sát LLM</h2>
          <p>Theo dõi tình trạng dịch vụ Ollama và cấu hình fallback.</p>
        </div>
        <button type="button" className={styles.refresh} onClick={() => void refresh()} disabled={isLoading}>
          {isLoading ? 'Đang kiểm tra...' : 'Kiểm tra lại'}
        </button>
      </header>
      {error && <p className={styles.error}>{error}</p>}
      {status && (
        <div className={styles.statusGrid}>
          <div className={styles.card}>
            <span className={styles.label}>Nhà cung cấp chính</span>
            <strong>{status.primary_provider ?? 'Không cấu hình'}</strong>
          </div>
          <div className={styles.card}>
            <span className={styles.label}>Fallback bật</span>
            <strong>{status.fallback_enabled ? 'Có' : 'Không'}</strong>
          </div>
          <div className={styles.card}>
            <span className={styles.label}>Ollama serve</span>
            <strong className={status.ollama_online ? styles.ok : styles.ko}>
              {status.ollama_online ? 'Đang trực tuyến' : 'Không phản hồi'}
            </strong>
            <code>{status.ollama_url ?? 'Không kiểm tra được'}</code>
            {!status.ollama_online && status.ollama_error && (
              <small className={styles.hint}>{status.ollama_error}</small>
            )}
          </div>
        </div>
      )}
      {status?.using_external_api && (
        <div className={styles.warning}>
          <strong>Cảnh báo:</strong> Cấu hình hiện tại có thể gửi dữ liệu OCR qua API bên ngoài.
          Hãy đảm bảo tường lửa cho phép truy cập HTTPS ra ngoài và các điều khoản bảo mật được tuân thủ.
        </div>
      )}
      {status && !status.using_external_api && (
        <div className={styles.note}>
          <strong>Lưu ý:</strong> Toàn bộ xử lý AI đang giới hạn trong hạ tầng nội bộ.
        </div>
      )}
    </section>
  );
};
