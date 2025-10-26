import type { AppProps } from 'next/app';
import { AuthProvider } from '@/hooks/useAuth';
import '../styles/globals.css';

const App = ({ Component, pageProps }: AppProps) => (
  <AuthProvider>
    <Component {...pageProps} />
  </AuthProvider>
);

export default App;
