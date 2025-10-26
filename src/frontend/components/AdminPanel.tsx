import { useEffect, useState } from 'react';
import { AuditLogEntry, fetchAdminAuditLogs, fetchAdminConfig, OCRConfigResponse } from '@/lib/api';
import { useAuth } from '@/hooks/useAuth';
import styles from './AdminPanel.module.css';

export const AdminPanel: React.FC = () => {
  const { token, user } = useAuth();
  const [config, setConfig] = useState<OCRConfigResponse | null>(null);
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    if (!user?.is_admin) {
      setError('Bạn cần quyền quản trị để xem trang này.');
      return;
    }
    const load = async () => {
      try {
        const [configResponse, logResponse] = await Promise.all([
          fetchAdminConfig(token),
          fetchAdminAuditLogs(token),
        ]);
        setConfig(configResponse);
        setLogs(logResponse);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Không thể tải dữ liệu quản trị.');
      }
    };
    void load();
  }, [token, user]);

  if (!token) {
    return <p>Đăng nhập để truy cập trang quản trị.</p>;
  }

  if (!user?.is_admin) {
    return <p className={styles.error}>{error ?? 'Không có quyền truy cập.'}</p>;
  }

  return (
    <section className={styles.panel}>
      <header className={styles.header}>
        <div>
          <h2>Điều khiển OCR</h2>
          <p>Cấu hình đường dẫn lưu trữ, thông số LLM và theo dõi audit logs.</p>
        </div>
        {error && <p className={styles.error}>{error}</p>}
      </header>
      {config && (
        <div className={styles.configGrid}>
          <div>
            <span className={styles.label}>Đường dẫn lưu trữ</span>
            <code>{config.storage_path}</code>
          </div>
          <div>
            <span className={styles.label}>Đường dẫn kết quả</span>
            <code>{config.results_path}</code>
          </div>
          <div>
            <span className={styles.label}>Redis</span>
            <code>{config.redis_url}</code>
          </div>
          <div>
            <span className={styles.label}>Celery Queue</span>
            <code>{config.celery_task_queue}</code>
          </div>
          <div>
            <span className={styles.label}>LLM Provider</span>
            <code>{config.llm_provider ?? 'Không cấu hình'}</code>
          </div>
          <div>
            <span className={styles.label}>LLM Model</span>
            <code>{config.llm_model ?? 'Không đặt trước'}</code>
          </div>
          <div>
            <span className={styles.label}>LLM Endpoint</span>
            <code>{config.llm_base_url ?? 'Sử dụng mặc định'}</code>
          </div>
          <div>
            <span className={styles.label}>Fallback</span>
            <code>{config.llm_fallback_enabled ? 'Đang bật' : 'Đang tắt'}</code>
          </div>
        </div>
      )}
      <div className={styles.logWrapper}>
        <h3>Audit gần đây</h3>
        <ul className={styles.logList}>
          {logs.map((log, index) => (
            <li key={`${log.created_at}-${index}`}>
              <span>{new Date(log.created_at).toLocaleString('vi-VN')}</span>
              <strong>{log.action}</strong>
              {log.details && <code>{JSON.stringify(log.details)}</code>}
            </li>
          ))}
          {logs.length === 0 && <li className={styles.empty}>Chưa có log nào.</li>}
        </ul>
      </div>
    </section>
  );
};
