import { useEffect, useMemo, useState } from 'react';
import { buildJobWebSocket, downloadResult, fetchJobs, JobSummary } from '@/lib/api';
import { useAuth } from '@/hooks/useAuth';
import { StatusPill } from './StatusPill';
import styles from './JobList.module.css';

type Props = {
  refreshSignal: number;
};

type JobWithRealtime = JobSummary & {
  websocket?: WebSocket;
};

export const JobList: React.FC<Props> = ({ refreshSignal }) => {
  const { token } = useAuth();
  const [jobs, setJobs] = useState<JobWithRealtime[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refreshJobs = useMemo(
    () => async () => {
      if (!token) return;
      try {
        const data = await fetchJobs(token);
        setJobs((prev) => {
          const byId = new Map(prev.map((job) => [job.id, job]));
          return data.map((job) => ({ ...job, websocket: byId.get(job.id)?.websocket }));
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Không thể tải danh sách jobs.');
      }
    },
    [token],
  );

  useEffect(() => {
    refreshJobs();
  }, [refreshSignal, refreshJobs]);

  useEffect(() => {
    if (!token) return;
    const sockets = jobs.map((job) => {
      if (job.status.toLowerCase() === 'completed' || job.status.toLowerCase() === 'failed') {
        return job.websocket;
      }
      const socket = buildJobWebSocket(job.id, token);
      socket.onmessage = (event) => {
        const payload = JSON.parse(event.data);
        if (payload.status) {
          setJobs((prev) =>
            prev.map((item) => (item.id === job.id ? { ...item, status: payload.status, error_message: payload.error_message } : item)),
          );
        }
      };
      return socket;
    });
    setJobs((prev) => prev.map((job, index) => ({ ...job, websocket: sockets[index] })));
    return () => {
      sockets.forEach((socket) => socket?.close());
    };
  }, [jobs.length, token]);

  const handleDownload = async (job: JobSummary) => {
    if (!token) return;
    try {
      const blob = await downloadResult(token, job.id);
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `${job.id}.json`;
      anchor.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể tải kết quả.');
    }
  };

  if (!token) {
    return <p>Đăng nhập để xem danh sách jobs.</p>;
  }

  return (
    <section className={styles.section}>
      <header className={styles.header}>
        <div>
          <h2>Danh sách xử lý gần đây</h2>
          <p>Theo dõi trạng thái jobs theo thời gian thực và tải kết quả JSON.</p>
        </div>
        <button className={styles.refresh} type="button" onClick={refreshJobs}>
          Làm mới
        </button>
      </header>
      {error && <p className={styles.error}>{error}</p>}
      <div className={styles.tableWrapper}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Tên tệp</th>
              <th>Trạng thái</th>
              <th>Khởi tạo</th>
              <th>Cập nhật</th>
              <th>Kết quả</th>
            </tr>
          </thead>
          <tbody>
            {jobs.length === 0 && (
              <tr>
                <td colSpan={5} className={styles.empty}>
                  Chưa có job nào. Hãy tải lên tệp PDF đầu tiên của bạn.
                </td>
              </tr>
            )}
            {jobs.map((job) => (
              <tr key={job.id}>
                <td>{job.input_filename}</td>
                <td>
                  <StatusPill status={job.status} />
                </td>
                <td>{new Date(job.created_at).toLocaleString('vi-VN')}</td>
                <td>{new Date(job.updated_at).toLocaleString('vi-VN')}</td>
                <td>
                  <button
                    type="button"
                    className={styles.download}
                    onClick={() => handleDownload(job)}
                    disabled={job.status.toLowerCase() !== 'completed'}
                  >
                    Tải kết quả
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
};
