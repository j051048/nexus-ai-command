export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export interface Database {
  public: {
    Tables: {
      users: {
        Row: {
          id: string
          email: string | null
          full_name: string | null
          avatar_url: string | null
          role: 'boss' | 'manager' | 'employee' | 'admin'
          department: string | null
          department_id: string | null
          job_title: string | null
          status: 'active' | 'inactive' | 'suspended'
          phone: string | null
          organization_id: string
          created_at: string
          updated_at: string
          last_active_at: string | null
        }
        Insert: {
          id: string
          email?: string | null
          full_name?: string | null
          avatar_url?: string | null
          role?: 'boss' | 'manager' | 'employee' | 'admin'
          department?: string | null
          department_id?: string | null
          job_title?: string | null
          status?: 'active' | 'inactive' | 'suspended'
          phone?: string | null
          organization_id: string
          created_at?: string
          updated_at?: string
          last_active_at?: string | null
        }
        Update: {
          id?: string
          email?: string | null
          full_name?: string | null
          avatar_url?: string | null
          role?: 'boss' | 'manager' | 'employee' | 'admin'
          department?: string | null
          department_id?: string | null
          job_title?: string | null
          status?: 'active' | 'inactive' | 'suspended'
          phone?: string | null
          organization_id?: string
          created_at?: string
          updated_at?: string
          last_active_at?: string | null
        }
      }
      organizations: {
        Row: {
          id: string
          name: string
          slug: string
          logo_url: string | null
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          name: string
          slug: string
          logo_url?: string | null
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          name?: string
          slug?: string
          logo_url?: string | null
          created_at?: string
          updated_at?: string
        }
      }
      sales_targets: {
        Row: {
          id: string
          organization_id: string
          target_period: string
          target_type: 'monthly' | 'quarterly'
          revenue_target: number
          leads_target: number
          conversions_target: number
          win_rate_target: number
          created_by: string | null
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          organization_id: string
          target_period: string
          target_type: 'monthly' | 'quarterly'
          revenue_target?: number
          leads_target?: number
          conversions_target?: number
          win_rate_target?: number
          created_by?: string | null
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          organization_id?: string
          target_period?: string
          target_type?: 'monthly' | 'quarterly'
          revenue_target?: number
          leads_target?: number
          conversions_target?: number
          win_rate_target?: number
          created_by?: string | null
          created_at?: string
          updated_at?: string
        }
      }
      projects: {
        Row: {
          id: string
          organization_id: string
          name: string
          status: string
          description: string | null
          start_date: string | null
          end_date: string | null
          budget: number | null
          owner_id: string | null
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          organization_id: string
          name: string
          status: string
          description?: string | null
          start_date?: string | null
          end_date?: string | null
          budget?: number | null
          owner_id?: string | null
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          organization_id?: string
          name?: string
          status?: string
          description?: string | null
          start_date?: string | null
          end_date?: string | null
          budget?: number | null
          owner_id?: string | null
          created_at?: string
          updated_at?: string
        }
      }
      sales_leads: {
        Row: {
          id: string
          organization_id: string
          company_name: string
          contact_name: string | null
          email: string | null
          phone: string | null
          status: string
          score: number
          source: string | null
          user_id: string | null
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          organization_id: string
          company_name: string
          contact_name?: string | null
          email?: string | null
          phone?: string | null
          status: string
          score?: number
          source?: string | null
          user_id?: string | null
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          organization_id?: string
          company_name?: string
          contact_name?: string | null
          email?: string | null
          phone?: string | null
          status?: string
          score?: number
          source?: string | null
          user_id?: string | null
          created_at?: string
          updated_at?: string
        }
      }
      ai_settings: {
        Row: {
          id: string
          user_id: string
          organization_id: string | null
          base_url: string
          api_key: string | null
          model: string
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          user_id: string
          organization_id?: string | null
          base_url?: string
          api_key?: string | null
          model?: string
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          user_id?: string
          organization_id?: string | null
          base_url?: string
          api_key?: string | null
          model?: string
          created_at?: string
          updated_at?: string
        }
      }
      sales_metrics: {
        Row: {
          id: string
          organization_id: string
          metric_date: string
          revenue: number
          leads_count: number
          conversion_rate: number
          user_id: string | null
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          organization_id: string
          metric_date: string
          revenue?: number
          leads_count?: number
          conversion_rate?: number
          user_id?: string | null
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          organization_id?: string
          metric_date?: string
          revenue?: number
          leads_count?: number
          conversion_rate?: number
          user_id?: string | null
          created_at?: string
          updated_at?: string
        }
      }
      departments: {
          Row: {
            id: string
            organization_id: string
            name: string
            manager_id: string | null
            created_at: string
            updated_at: string
          }
          Insert: {
            id?: string
            organization_id: string
            name: string
            manager_id?: string | null
            created_at?: string
            updated_at?: string
          }
          Update: {
            id?: string
            organization_id?: string
            name?: string
            manager_id?: string | null
            created_at?: string
            updated_at?: string
          }
      }
      notifications: {
          Row: {
            id: string
            organization_id: string
            user_id: string
            title: string
            message: string
            read: boolean
            type: string
            created_at: string
          }
          Insert: {
              id?: string
              organization_id: string
              user_id: string
              title: string
              message: string
              read?: boolean
              type?: string
              created_at?: string
          }
          Update: {
              id?: string
              organization_id?: string
              user_id?: string
              title?: string
              message?: string
              read?: boolean
              type?: string
              created_at?: string
          }
      }
      document_embeddings: {
          Row: {
            id: string
            organization_id: string
            document_id: string
            content: string
            embedding: string | null 
            metadata: Json
            created_at: string
          }
          Insert: {
              id?: string
              organization_id: string
              document_id: string
              content: string
              embedding?: string | null
              metadata?: Json
              created_at?: string
          }
          Update: {
              id?: string
              organization_id?: string
              document_id?: string
              content?: string
              embedding?: string | null
              metadata?: Json
              created_at?: string
          }
      }
      oa_tasks: {
          Row: {
            id: string
            organization_id: string
            title: string
            description: string | null
            status: string
            priority: string
            assignee_id: string | null
            due_date: string | null
            created_at: string
            updated_at: string
          }
          Insert: {
              id?: string
              organization_id: string
              title: string
              description?: string | null
              status?: string
              priority?: string
              assignee_id?: string | null
              due_date?: string | null
              created_at?: string
              updated_at?: string
          }
          Update: {
              id?: string
              organization_id?: string
              title?: string
              description?: string | null
              status?: string
              priority?: string
              assignee_id?: string | null
              due_date?: string | null
              created_at?: string
              updated_at?: string
          }
      }
      finance_invoices: {
          Row: {
            id: string
            organization_id: string
            invoice_number: string
            amount: number
            status: string
            due_date: string | null
            customer_id: string | null
            created_at: string
            updated_at: string
          }
          Insert: {
              id?: string
              organization_id: string
              invoice_number: string
              amount: number
              status: string
              due_date?: string | null
              customer_id?: string | null
              created_at?: string
              updated_at?: string
          }
          Update: {
              id?: string
              organization_id?: string
              invoice_number?: string
              amount?: number
              status?: string
              due_date?: string | null
              customer_id?: string | null
              created_at?: string
              updated_at?: string
          }
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      match_documents: {
        Args: {
          query_embedding: string
          match_threshold: number
          match_count: number
          filter?: Json
          p_user_id?: string
          p_org_id?: string
        }
        Returns: {
          id: number
          content: string
          metadata: Json
          similarity: number
          organization_id: string
        }[]
      }
      match_documents_keyword: {
        Args: {
          p_query: string
          p_user_id: string
          p_limit: number
          p_org_id?: string
        }
        Returns: {
          id: number
          content: string
          metadata: Json
          similarity: number
          organization_id: string
        }[]
      }
    }
    Enums: {
      [_ in never]: never
    }
  }
}
