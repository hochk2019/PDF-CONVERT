import { useState } from 'react';
import { uploadJob } from '@/lib/api';
import { useAuth } from '@/hooks/useAuth';
import styles from './UploadCard.module.css';

type Props = {
  onJobCreated: (jobId: string) => void;
};

export const UploadCard: React.FC<Props> = ({ onJobCreated }) => {
  const { token } = useAuth();
  const [file, setFile] = useState<File | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (!event.target.files?.length) return;
    setFile(event.target.files[0]);
    setSuccessMessage(null);
    setError(null);
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file || !token) {
      setError('Vui lòng chọn tập tin PDF và đăng nhập.');
      return;
    }
    setIsSubmitting(true);
    setError(null);
    try {
      const response = await uploadJob(token, file);
      setSuccessMessage(`Job #${response.id} đã được tạo.`);
      onJobCreated(response.id);
      setFile(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể tải lên.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form className={styles.card} onSubmit={handleSubmit}>
      <div>
        <h2>Đăng tải tài liệu</h2>
        <p>Nhận diện bảng biểu, văn bản và hình ảnh từ PDF dung lượng tối đa 50MB.</p>
      </div>
      <label className={styles.uploadBox}>
        <input type="file" accept="application/pdf" onChange={handleFileChange} disabled={isSubmitting} />
        {file ? <strong>{file.name}</strong> : <span>Kéo và thả hoặc nhấn để chọn file PDF</span>}
      </label>
      <button className={styles.submit} type="submit" disabled={isSubmitting}>
        {isSubmitting ? 'Đang tải...' : 'Bắt đầu xử lý'}
      </button>
      {successMessage && <p className={styles.success}>{successMessage}</p>}
      {error && <p className={styles.error}>{error}</p>}
    </form>
  );
};
