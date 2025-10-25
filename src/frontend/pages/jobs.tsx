import { useEffect, useState } from 'react';
import { Layout } from '@/components/Layout';
import { UploadCard } from '@/components/UploadCard';
import { JobList } from '@/components/JobList';
import { useAuth } from '@/hooks/useAuth';
import styles from './jobs.module.css';

const JobsPage = () => {
  const { isAuthenticated, refreshProfile } = useAuth();
  const [refreshSignal, setRefreshSignal] = useState(0);

  useEffect(() => {
    if (isAuthenticated) {
      void refreshProfile();
    }
  }, [isAuthenticated, refreshProfile]);

  return (
    <Layout title="Jobs">
      <div className={styles.grid}>
        <UploadCard onJobCreated={() => setRefreshSignal((value) => value + 1)} />
        <JobList refreshSignal={refreshSignal} />
      </div>
    </Layout>
  );
};

export default JobsPage;
