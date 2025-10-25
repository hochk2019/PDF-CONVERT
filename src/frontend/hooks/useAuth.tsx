import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/router';
import { loginRequest, registerUser, fetchCurrentUser } from '@/lib/api';
import type { UserProfile, RegisterPayload } from '@/lib/api';

type AuthContextValue = {
  token: string | null;
  user: UserProfile | null;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (payload: RegisterPayload) => Promise<void>;
  logout: () => void;
  refreshProfile: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

const TOKEN_STORAGE_KEY = 'pdf-convert-token';

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<UserProfile | null>(null);

  useEffect(() => {
    const stored = typeof window !== 'undefined' ? localStorage.getItem(TOKEN_STORAGE_KEY) : null;
    if (stored) {
      setToken(stored);
    }
  }, []);

  useEffect(() => {
    if (!token) {
      setUser(null);
      return;
    }
    fetchCurrentUser(token)
      .then(setUser)
      .catch(() => {
        setToken(null);
        localStorage.removeItem(TOKEN_STORAGE_KEY);
      });
  }, [token]);

  const login = useCallback(
    async (email: string, password: string) => {
      const response = await loginRequest(email, password);
      setToken(response.accessToken);
      localStorage.setItem(TOKEN_STORAGE_KEY, response.accessToken);
      const profile = await fetchCurrentUser(response.accessToken);
      setUser(profile);
      await router.push('/jobs');
    },
    [router],
  );

  const register = useCallback(async (payload: RegisterPayload) => {
    await registerUser(payload);
    await login(payload.email, payload.password);
  }, [login]);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    if (typeof window !== 'undefined') {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
    }
    router.push('/');
  }, [router]);

  const refreshProfile = useCallback(async () => {
    if (!token) return;
    const profile = await fetchCurrentUser(token);
    setUser(profile);
  }, [token]);

  const value = useMemo<AuthContextValue>(
    () => ({
      token,
      user,
      isAuthenticated: Boolean(token),
      login,
      register,
      logout,
      refreshProfile,
    }),
    [login, logout, refreshProfile, token, user, register],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = (): AuthContextValue => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
