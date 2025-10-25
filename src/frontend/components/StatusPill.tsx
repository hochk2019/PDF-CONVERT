import styles from './StatusPill.module.css';

type Props = {
  status: string;
};

const labels: Record<string, string> = {
  pending: 'Đang chờ',
  processing: 'Đang xử lý',
  completed: 'Hoàn tất',
  failed: 'Thất bại',
};

export const StatusPill: React.FC<Props> = ({ status }) => {
  const normalized = status.toLowerCase();
  return <span className={`${styles.pill} ${styles[normalized] ?? ''}`}>{labels[normalized] ?? status}</span>;
};
