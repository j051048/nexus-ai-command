export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.1"
  }
  public: {
    Tables: {
      approval_requests: {
        Row: {
          ai_reason: string | null
          amount: number | null
          description: string
          id: string
          metadata: Json | null
          rejection_reason: string | null
          reviewed_at: string | null
          reviewed_by: string | null
          status: string
          submitted_at: string
          submitted_by: string
          type: string
        }
        Insert: {
          ai_reason?: string | null
          amount?: number | null
          description: string
          id?: string
          metadata?: Json | null
          rejection_reason?: string | null
          reviewed_at?: string | null
          reviewed_by?: string | null
          status?: string
          submitted_at?: string
          submitted_by: string
          type: string
        }
        Update: {
          ai_reason?: string | null
          amount?: number | null
          description?: string
          id?: string
          metadata?: Json | null
          rejection_reason?: string | null
          reviewed_at?: string | null
          reviewed_by?: string | null
          status?: string
          submitted_at?: string
          submitted_by?: string
          type?: string
        }
        Relationships: []
      }
      badges: {
        Row: {
          description: string | null
          icon: string
          id: string
          name: string
          tier: string | null
          unlocked_at: string | null
          user_id: string
        }
        Insert: {
          description?: string | null
          icon: string
          id?: string
          name: string
          tier?: string | null
          unlocked_at?: string | null
          user_id: string
        }
        Update: {
          description?: string | null
          icon?: string
          id?: string
          name?: string
          tier?: string | null
          unlocked_at?: string | null
          user_id?: string
        }
        Relationships: []
      }
      notifications: {
        Row: {
          created_at: string
          data: Json | null
          id: string
          message: string
          read: boolean | null
          title: string
          type: string
          user_id: string
        }
        Insert: {
          created_at?: string
          data?: Json | null
          id?: string
          message: string
          read?: boolean | null
          title: string
          type: string
          user_id: string
        }
        Update: {
          created_at?: string
          data?: Json | null
          id?: string
          message?: string
          read?: boolean | null
          title?: string
          type?: string
          user_id?: string
        }
        Relationships: []
      }
      profiles: {
        Row: {
          avatar: string | null
          created_at: string
          department: string | null
          id: string
          name: string
          rank: number | null
          score: number | null
          total_bonus: number | null
          updated_at: string
          user_id: string
        }
        Insert: {
          avatar?: string | null
          created_at?: string
          department?: string | null
          id?: string
          name: string
          rank?: number | null
          score?: number | null
          total_bonus?: number | null
          updated_at?: string
          user_id: string
        }
        Update: {
          avatar?: string | null
          created_at?: string
          department?: string | null
          id?: string
          name?: string
          rank?: number | null
          score?: number | null
          total_bonus?: number | null
          updated_at?: string
          user_id?: string
        }
        Relationships: []
      }
      sales_metrics: {
        Row: {
          calls_made: number | null
          conversions: number | null
          created_at: string | null
          date: string
          id: string
          leads_count: number | null
          revenue: number | null
          score: number | null
          user_id: string | null
          win_rate: number | null
        }
        Insert: {
          calls_made?: number | null
          conversions?: number | null
          created_at?: string | null
          date?: string
          id?: string
          leads_count?: number | null
          revenue?: number | null
          score?: number | null
          user_id?: string | null
          win_rate?: number | null
        }
        Update: {
          calls_made?: number | null
          conversions?: number | null
          created_at?: string | null
          date?: string
          id?: string
          leads_count?: number | null
          revenue?: number | null
          score?: number | null
          user_id?: string | null
          win_rate?: number | null
        }
        Relationships: []
      }
      sales_targets: {
        Row: {
          conversions_target: number | null
          created_at: string
          created_by: string | null
          id: string
          leads_target: number | null
          revenue_target: number | null
          target_period: string
          target_type: string
          updated_at: string
          win_rate_target: number | null
        }
        Insert: {
          conversions_target?: number | null
          created_at?: string
          created_by?: string | null
          id?: string
          leads_target?: number | null
          revenue_target?: number | null
          target_period: string
          target_type: string
          updated_at?: string
          win_rate_target?: number | null
        }
        Update: {
          conversions_target?: number | null
          created_at?: string
          created_by?: string | null
          id?: string
          leads_target?: number | null
          revenue_target?: number | null
          target_period?: string
          target_type?: string
          updated_at?: string
          win_rate_target?: number | null
        }
        Relationships: []
      }
      team_performance: {
        Row: {
          avg_win_rate: number | null
          created_at: string | null
          id: string
          top_performer_id: string | null
          total_conversions: number | null
          total_leads: number | null
          total_revenue: number | null
          week_start: string
        }
        Insert: {
          avg_win_rate?: number | null
          created_at?: string | null
          id?: string
          top_performer_id?: string | null
          total_conversions?: number | null
          total_leads?: number | null
          total_revenue?: number | null
          week_start: string
        }
        Update: {
          avg_win_rate?: number | null
          created_at?: string | null
          id?: string
          top_performer_id?: string | null
          total_conversions?: number | null
          total_leads?: number | null
          total_revenue?: number | null
          week_start?: string
        }
        Relationships: []
      }
      user_roles: {
        Row: {
          id: string
          role: Database["public"]["Enums"]["app_role"]
          user_id: string
        }
        Insert: {
          id?: string
          role?: Database["public"]["Enums"]["app_role"]
          user_id: string
        }
        Update: {
          id?: string
          role?: Database["public"]["Enums"]["app_role"]
          user_id?: string
        }
        Relationships: []
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      get_user_role: {
        Args: { _user_id: string }
        Returns: Database["public"]["Enums"]["app_role"]
      }
      has_role: {
        Args: {
          _role: Database["public"]["Enums"]["app_role"]
          _user_id: string
        }
        Returns: boolean
      }
      transfer_and_delete_user: {
        Args: { _transfer_to_user?: string; _user_to_delete: string }
        Returns: undefined
      }
    }
    Enums: {
      app_role: "boss" | "employee"
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {
      app_role: ["boss", "employee"],
    },
  },
} as const
