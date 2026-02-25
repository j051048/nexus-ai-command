/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, useState, useEffect, useRef, useMemo, useCallback, ReactNode } from 'react';
import { supabase } from '@/integrations/supabase/client';
import { User, Session, AuthError } from '@supabase/supabase-js';
import { toast } from 'sonner';

// 三级权限系统
type AppRole = 'boss' | 'manager' | 'ai_assistant' | 'employee';

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

interface AuthContextType {
  user: User | null;
  session: Session | null;
  profile: Profile | null;
  role: AppRole | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<{ error: AuthError | null }>;
  signUp: (email: string, password: string, name: string, role: AppRole) => Promise<{ error: AuthError | null }>;
  signOut: () => Promise<void>;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [role, setRole] = useState<AppRole | null>(null);
  const [loading, setLoading] = useState(true);
  const hadSessionRef = useRef(false);

  const fetchUserData = async (userId: string) => {
    try {
      // Use 'users' table instead of 'profiles'
      // Map id to user_id for backward compatibility
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const { data: profileData, error: profileError } = await (supabase.from('users') as any)
        .select('*, user_id:id')
        .eq('id', userId)
        .maybeSingle();

      if (profileError) {
        console.error('Error fetching profile:', profileError);
      } else if (profileData) {
        // Map DB fields to Profile interface if needed, or use as is
        setProfile(profileData as unknown as Profile);
      }

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const { data: roleData } = await (supabase as any)
        .rpc('get_user_role', { _user_id: userId });

      if (roleData) {
        setRole(roleData as AppRole);
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
    } catch (error) {
      console.error('Error fetching user data:', error);
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

  const signUp = useCallback(async (email: string, password: string, name: string, selectedRole: AppRole) => {
    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        emailRedirectTo: window.location.origin,
        data: {
          name,
          role: selectedRole,
        },
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
    signIn,
    signUp,
    signOut,
    refreshProfile,
  }), [user, session, profile, role, loading, signIn, signUp, signOut, refreshProfile]);

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
