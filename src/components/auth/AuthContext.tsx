/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, useState, useEffect, useRef, useMemo, useCallback, ReactNode } from 'react';
import { supabase } from '@/integrations/supabase/client';
import { User, Session, AuthError } from '@supabase/supabase-js';
import { toast } from 'sonner';
import { httpClient } from '@/lib/httpClient';

// 权限系统
type AppRole = 'boss' | 'manager' | 'ai_assistant' | 'employee' | 'pending_boss';

interface Profile {
  id: string;
  user_id: string;
  name: string;
  avatar: string;
  department: string;
  score: number;
  rank: number;
  total_bonus: number;
  organization_id: string;
  employee_number: string | null;
  job_title: string | null;
}

// 安全提取字符串（防止 Supabase 返回非预期类型导致 React #301）
function safeProfileStr(v: unknown, field?: string): string {
  if (v == null) return '';
  if (typeof v === 'string') return v;
  if (typeof v === 'number' || typeof v === 'boolean') return String(v);
  console.warn(`[AuthContext] profile.${field} is not a string:`, typeof v, v);
  if (typeof v === 'object') {
    const name = (v as Record<string, unknown>).name;
    if (typeof name === 'string') return name;
    return JSON.stringify(v);
  }
  return String(v);
}

// 清洗 profile 数据，确保所有渲染字段都是安全类型
function sanitizeProfile(raw: Record<string, unknown>): Profile {
  return {
    id: safeProfileStr(raw.id, 'id'),
    user_id: safeProfileStr(raw.user_id ?? raw.id, 'user_id'),
    name: safeProfileStr(raw.name ?? raw.full_name, 'name'),
    avatar: safeProfileStr(raw.avatar ?? raw.avatar_url, 'avatar'),
    department: safeProfileStr(raw.department, 'department'),
    score: typeof raw.score === 'number' ? raw.score : 0,
    rank: typeof raw.rank === 'number' ? raw.rank : 0,
    total_bonus: typeof raw.total_bonus === 'number' ? raw.total_bonus : 0,
    organization_id: safeProfileStr(raw.organization_id, 'organization_id'),
    employee_number: raw.employee_number != null ? safeProfileStr(raw.employee_number, 'employee_number') : null,
    job_title: raw.job_title != null ? safeProfileStr(raw.job_title, 'job_title') : null,
  };
}

interface AuthContextType {
  user: User | null;
  session: Session | null;
  profile: Profile | null;
  role: AppRole | null;
  loading: boolean;
  isSuperAdmin: boolean;
  isPendingBoss: boolean;
  signIn: (email: string, password: string) => Promise<{ error: AuthError | null }>;
  signUp: (email: string, password: string, name: string, role: AppRole, inviteCode?: string) => Promise<{ error: AuthError | null }>;
  signOut: () => Promise<void>;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [role, setRole] = useState<AppRole | null>(null);
  const [isSuperAdmin, setIsSuperAdmin] = useState(false);
  const [isPendingBoss, setIsPendingBoss] = useState(false);
  const [loading, setLoading] = useState(true);
  const hadSessionRef = useRef(false);

  const fetchUserData = async (userId: string) => {
    try {
      const response = await httpClient.get('/api/users/profile');
      const profileData = response.data?.user;

      if (profileData) {
        setProfile(sanitizeProfile(profileData as Record<string, unknown>));
      }

      const { data: roleData } = await supabase
        .rpc('get_user_role', { _user_id: userId });

      if (roleData) {
        const roleStr = safeProfileStr(roleData, 'role');
        if (roleStr === 'pending_boss') {
          setRole('employee');
          setIsPendingBoss(true);
        } else {
          setRole(roleStr as AppRole);
          setIsPendingBoss(false);
        }
      } else {
        // Fallback: default to employee for security
        // P0 Security Fix: Do NOT trust user_metadata.role as it can be set by the user during signup
        let resolvedRole: AppRole = 'employee';

        // Only trust the DB profile role (set by admin), not auth metadata
        if (profileData && (profileData as unknown as Record<string, unknown>).role) {
          const dbRole = (profileData as unknown as Record<string, unknown>).role;
          if (dbRole === 'founder' || dbRole === 'boss') {
            resolvedRole = 'boss';
          } else if (dbRole === 'manager') {
            resolvedRole = 'manager';
          }
        }
        setRole(resolvedRole);
      }

      // Check super admin status (separate from role)
      try {
        const { data: saData } = await supabase.rpc('is_super_admin', { _user_id: userId });
        setIsSuperAdmin(!!saData);
      } catch {
        setIsSuperAdmin(false);
      }
    } catch (error) {
      // Auth data fetch failed — default to employee role for safety
      setRole('employee');
    } finally {
      // Ensure loading state is turned off regardless of success/fail
      setLoading(false);
    }
  };

  useEffect(() => {
    // Set up auth state listener first
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (event, newSession) => {
        if (import.meta.env.DEV) console.log('Auth state changed:', event);
        setSession(newSession);
        setUser(newSession?.user ?? null);

        if (newSession?.user) {
          hadSessionRef.current = true;
          // fetchUserData handles its own setLoading(false)
          fetchUserData(newSession.user.id);
        } else {
          // Session lost — notify user if they were previously signed in
          if (hadSessionRef.current && (event === 'SIGNED_OUT' || event === 'TOKEN_REFRESHED')) {
            toast.error('登录已过期，请重新登录');
          }
          hadSessionRef.current = false;
          setProfile(null);
          setRole(null);
          setIsSuperAdmin(false);
          setIsPendingBoss(false);
          setLoading(false);
        }
      }
    );

    // Then check for existing session
    supabase.auth.getSession().then(({ data: { session: existingSession } }) => {
      setSession(existingSession);
      setUser(existingSession?.user ?? null);
      if (existingSession?.user) {
        fetchUserData(existingSession.user.id);
      } else {
        setLoading(false);
      }
    });

    return () => {
      subscription.unsubscribe();
    };
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    const { error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });
    return { error };
  }, []);

  const signUp = useCallback(async (email: string, password: string, name: string, selectedRole: AppRole, inviteCode?: string) => {
    // Security: the trigger handles boss→pending_boss safely (requires super_admin approval)
    const metadata: Record<string, string> = {
      name,
      role: selectedRole === 'boss' ? 'boss' : 'employee',
    };
    if (inviteCode) {
      metadata.invite_code = inviteCode;
    }

    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        emailRedirectTo: window.location.origin,
        data: metadata,
      },
    });
    return { error };
  }, []);

  const signOut = useCallback(async () => {
    await supabase.auth.signOut();
    setUser(null);
    setSession(null);
    setProfile(null);
    setRole(null);
    setIsSuperAdmin(false);
    setIsPendingBoss(false);
  }, []);

  const refreshProfile = useCallback(async () => {
    const currentUser = user;
    if (currentUser) {
      await fetchUserData(currentUser.id);
    }
  }, [user]);

  const value = useMemo(() => ({
    user,
    session,
    profile,
    role,
    loading,
    isSuperAdmin,
    isPendingBoss,
    signIn,
    signUp,
    signOut,
    refreshProfile,
  }), [user, session, profile, role, loading, isSuperAdmin, isPendingBoss, signIn, signUp, signOut, refreshProfile]);

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
