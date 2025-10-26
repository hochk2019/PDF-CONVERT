import { useMemo, useState } from 'react';
import { uploadJob, LLMOptionsPayload } from '@/lib/api';
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
  const [selectedMode, setSelectedMode] = useState<'auto' | 'local' | 'disabled'>('auto');

  const modePresets = useMemo(
    () =>
      ({
        auto: {
          label: 'Tự động (theo cấu hình máy chủ)',
          description:
            'Giữ nguyên thiết lập mặc định của máy chủ. Có thể sử dụng API ngoài nếu quản trị bật fallback.',
          options: null,
        },
        local: {
          label: 'Chỉ dùng Ollama cục bộ',
          description:
            'Buộc pipeline sử dụng mô hình Ollama nội bộ và vô hiệu hóa các nhà cung cấp bên ngoài.',
          options: {
            enable_llm: true,
            provider: 'ollama',
            fallback_enabled: false,
            fallback_providers: [],
          } as LLMOptionsPayload,
        },
        disabled: {
          label: 'Tắt hậu xử lý AI',
          description: 'Bỏ qua bước hiệu chỉnh bằng LLM và chỉ dùng kết quả OCR thô.',
          options: { enable_llm: false } as LLMOptionsPayload,
        },
      } as const),
    [],
  );

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
      const preset = modePresets[selectedMode];
      const response = await uploadJob(token, file, preset.options ?? undefined);
      setSuccessMessage(`Job #${response.id} đã được tạo.`);
      onJobCreated(response.id);
      setFile(null);
      setSelectedMode('auto');
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
      <label className={styles.modeField}>
        <span className={styles.modeLabel}>Chế độ xử lý AI (tùy chọn)</span>
        <select
          value={selectedMode}
          onChange={(event) => setSelectedMode(event.target.value as typeof selectedMode)}
          disabled={isSubmitting}
          className={styles.modeSelect}
        >
          {Object.entries(modePresets).map(([value, preset]) => (
            <option key={value} value={value}>
              {preset.label}
            </option>
          ))}
        </select>
        <small className={styles.modeDescription}>{modePresets[selectedMode].description}</small>
      </label>
      <button className={styles.submit} type="submit" disabled={isSubmitting}>
        {isSubmitting ? 'Đang tải...' : 'Bắt đầu xử lý'}
      </button>
      {successMessage && <p className={styles.success}>{successMessage}</p>}
      {error && <p className={styles.error}>{error}</p>}
    </form>
  );
};
