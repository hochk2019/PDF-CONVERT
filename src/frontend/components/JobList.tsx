import { useEffect, useMemo, useRef, useState } from 'react';
import {
  buildJobWebSocket,
  downloadArtifact,
  downloadResult,
  fetchJobs,
  JobSummary,
} from '@/lib/api';
import { useAuth } from '@/hooks/useAuth';
import { StatusPill } from './StatusPill';
import styles from './JobList.module.css';

type Props = {
  refreshSignal: number;
};

export const JobList: React.FC<Props> = ({ refreshSignal }) => {
  const { token } = useAuth();
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const socketsRef = useRef<Map<string, WebSocket>>(new Map());

  const refreshJobs = useMemo(
    () => async () => {
      if (!token) return;
      try {
        const data = await fetchJobs(token);
        setJobs(data);
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
    if (!token) {
      socketsRef.current.forEach((socket) => socket.close());
      socketsRef.current.clear();
      return;
    }

    jobs.forEach((job) => {
      const jobId = job.id;
      const status = job.status.toLowerCase();
      const existing = socketsRef.current.get(jobId);
      const isTerminal = status === 'completed' || status === 'failed';

      if (isTerminal) {
        if (existing) {
          existing.close();
          socketsRef.current.delete(jobId);
        }
        return;
      }

      if (!existing) {
        const socket = buildJobWebSocket(jobId, token);
        socket.onmessage = (event) => {
          const payload = JSON.parse(event.data);
          if (payload.status) {
            setJobs((prev) =>
              prev.map((item) =>
                item.id === jobId
                  ? { ...item, status: payload.status, error_message: payload.error_message }
                  : item,
              ),
            );
            const normalized = String(payload.status).toLowerCase();
            if (normalized === 'completed' || normalized === 'failed') {
              const active = socketsRef.current.get(jobId);
              active?.close();
              socketsRef.current.delete(jobId);
            }
          }
        };
        socket.onclose = () => {
          socketsRef.current.delete(jobId);
        };
        socketsRef.current.set(jobId, socket);
      }
    });
  }, [jobs, token]);

  useEffect(() => () => {
    socketsRef.current.forEach((socket) => socket.close());
    socketsRef.current.clear();
  }, []);

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

  const handleArtifactDownload = async (job: JobSummary, kind: string) => {
    if (!token) return;
    try {
      const blob = await downloadArtifact(token, job.id, kind);
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `${job.id}.${kind}`;
      anchor.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể tải tệp đính kèm.');
    }
  };

  const extractArtifacts = (payload: JobSummary['result_payload']) => {
    if (!payload || typeof payload !== 'object') return {} as Record<string, string>;
    const raw = (payload as { artifacts?: unknown }).artifacts;
    if (!raw || typeof raw !== 'object') return {} as Record<string, string>;
    return Object.fromEntries(
      Object.entries(raw as Record<string, unknown>).filter(
        ([key, value]) => typeof key === 'string' && typeof value === 'string',
      ),
    ) as Record<string, string>;
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
                  <div className={styles.actions}>
                    <button
                      type="button"
                      className={styles.download}
                      onClick={() => handleDownload(job)}
                      disabled={job.status.toLowerCase() !== 'completed'}
                    >
                      Tải JSON
                    </button>
                    {Object.keys(extractArtifacts(job.result_payload)).map((kind) => (
                      <button
                        key={kind}
                        type="button"
                        className={styles.download}
                        onClick={() => handleArtifactDownload(job, kind)}
                        disabled={job.status.toLowerCase() !== 'completed'}
                      >
                        {kind.toUpperCase()}
                      </button>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
};
