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
          employee_number: string | null
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
          employee_number?: string | null
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
          employee_number?: string | null
          status?: 'active' | 'inactive' | 'suspended'
          phone?: string | null
          organization_id?: string
          created_at?: string
          updated_at?: string
          last_active_at?: string | null
        }
        Relationships: []
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
        Relationships: []
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
        Relationships: []
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
        Relationships: []
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
          Relationships: []
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
      approval_requests: {
          Row: {
            id: string
            organization_id: string
            type: string
            description: string | null
            amount: number | null
            status: 'pending' | 'approved' | 'rejected'
            submitted_by: string
            submitted_at: string | null
            ai_reason: string | null
            on_behalf_of: string | null
            rejection_reason: string | null
            created_at: string
            updated_at: string | null
          }
          Insert: {
              id?: string
              organization_id: string
              type: string
              description?: string | null
              amount?: number | null
              status?: 'pending' | 'approved' | 'rejected'
              submitted_by: string
              submitted_at?: string | null
              ai_reason?: string | null
              on_behalf_of?: string | null
              rejection_reason?: string | null
              created_at?: string
              updated_at?: string | null
          }
          Update: {
              id?: string
              organization_id?: string
              type?: string
              description?: string | null
              amount?: number | null
              status?: 'pending' | 'approved' | 'rejected'
              submitted_by?: string
              submitted_at?: string | null
              ai_reason?: string | null
              on_behalf_of?: string | null
              rejection_reason?: string | null
              created_at?: string
              updated_at?: string | null
          }
          Relationships: [
            {
              foreignKeyName: "approval_requests_submitted_by_fkey"
              columns: ["submitted_by"]
              referencedRelation: "users"
              referencedColumns: ["id"]
            }
          ]
      }
      documents: {
          Row: {
            id: string
            organization_id: string | null
            name: string
            doc_type: string | null
            status: string | null
            progress: number | null
            stage: string | null
            extracted_data: Json | null
            owner_id: string | null
            embedding_model: string | null
            embedding_model_version: string | null
            created_at: string
            updated_at: string | null
          }
          Insert: {
              id?: string
              organization_id?: string | null
              name: string
              doc_type?: string | null
              status?: string | null
              progress?: number | null
              stage?: string | null
              extracted_data?: Json | null
              owner_id?: string | null
              embedding_model?: string | null
              embedding_model_version?: string | null
              created_at?: string
              updated_at?: string | null
          }
          Update: {
              id?: string
              organization_id?: string | null
              name?: string
              doc_type?: string | null
              status?: string | null
              progress?: number | null
              stage?: string | null
              extracted_data?: Json | null
              owner_id?: string | null
              embedding_model?: string | null
              embedding_model_version?: string | null
              created_at?: string
              updated_at?: string | null
          }
      }
      chat_messages: {
          Row: {
            id: string
            session_id: string
            role: 'user' | 'assistant' | 'system'
            content: string
            metadata: Json | null
            user_id: string | null
            organization_id: string | null
            agent: string | null
            created_at: string
          }
          Insert: {
              id?: string
              session_id: string
              role: 'user' | 'assistant' | 'system'
              content: string
              metadata?: Json | null
              user_id?: string | null
              organization_id?: string | null
              agent?: string | null
              created_at?: string
          }
          Update: {
              id?: string
              session_id?: string
              role?: 'user' | 'assistant' | 'system'
              content?: string
              metadata?: Json | null
              user_id?: string | null
              organization_id?: string | null
              agent?: string | null
              created_at?: string
          }
      }
      starred_sessions: {
          Row: {
            id: string
            user_id: string
            session_id: string
            created_at: string
          }
          Insert: {
              id?: string
              user_id: string
              session_id: string
              created_at?: string
          }
          Update: {
              id?: string
              user_id?: string
              session_id?: string
              created_at?: string
          }
      }
      project_timeline: {
          Row: {
            id: string
            project_id: string
            event: string
            description: string | null
            event_date: string | null
            created_at: string
          }
          Insert: {
              id?: string
              project_id: string
              event: string
              description?: string | null
              event_date?: string | null
              created_at?: string
          }
          Update: {
              id?: string
              project_id?: string
              event?: string
              description?: string | null
              event_date?: string | null
              created_at?: string
          }
      }
      oa_leave_requests: {
          Row: {
            id: string
            user_id: string
            organization_id: string | null
            leave_type: string
            start_date: string
            end_date: string
            days: number
            reason: string
            status: string
            approver_id: string | null
            created_at: string
            updated_at: string | null
          }
          Insert: {
              id?: string
              user_id: string
              organization_id?: string | null
              leave_type: string
              start_date: string
              end_date: string
              days: number
              reason: string
              status?: string
              approver_id?: string | null
              created_at?: string
              updated_at?: string | null
          }
          Update: {
              id?: string
              user_id?: string
              organization_id?: string | null
              leave_type?: string
              start_date?: string
              end_date?: string
              days?: number
              reason?: string
              status?: string
              approver_id?: string | null
              created_at?: string
              updated_at?: string | null
          }
      }
      oa_meeting_bookings: {
          Row: {
            id: string
            title: string
            room_id: string | null
            organizer_id: string
            start_time: string
            end_time: string
            attendees: string[] | null
            status: string
            organization_id: string | null
            created_at: string
            updated_at: string | null
          }
          Insert: {
              id?: string
              title: string
              room_id?: string | null
              organizer_id: string
              start_time: string
              end_time: string
              attendees?: string[] | null
              status?: string
              organization_id?: string | null
              created_at?: string
              updated_at?: string | null
          }
          Update: {
              id?: string
              title?: string
              room_id?: string | null
              organizer_id?: string
              start_time?: string
              end_time?: string
              attendees?: string[] | null
              status?: string
              organization_id?: string | null
              created_at?: string
              updated_at?: string | null
          }
      }
      hr_attendance: {
          Row: {
            id: string
            user_id: string
            date: string
            check_in: string | null
            check_out: string | null
            status: string
            late_minutes: number
            early_leave_minutes: number
            overtime_hours: number
            source: string
            created_at: string
          }
          Insert: {
              id?: string
              user_id: string
              date: string
              check_in?: string | null
              check_out?: string | null
              status?: string
              late_minutes?: number
              early_leave_minutes?: number
              overtime_hours?: number
              source?: string
              created_at?: string
          }
          Update: {
              id?: string
              user_id?: string
              date?: string
              check_in?: string | null
              check_out?: string | null
              status?: string
              late_minutes?: number
              early_leave_minutes?: number
              overtime_hours?: number
              source?: string
              created_at?: string
          }
      }
      hr_salary_records: {
          Row: {
            id: string
            user_id: string
            period: string
            base_salary: number
            performance_bonus: number
            attendance_bonus: number
            other_allowances: number
            gross_salary: number
            social_insurance: number
            housing_fund: number
            tax: number
            other_deductions: number
            net_salary: number
            payment_date: string | null
            payment_status: string
            created_at: string
          }
          Insert: {
              id?: string
              user_id: string
              period: string
              base_salary?: number
              performance_bonus?: number
              attendance_bonus?: number
              other_allowances?: number
              gross_salary?: number
              social_insurance?: number
              housing_fund?: number
              tax?: number
              other_deductions?: number
              net_salary?: number
              payment_date?: string | null
              payment_status?: string
              created_at?: string
          }
          Update: {
              id?: string
              user_id?: string
              period?: string
              base_salary?: number
              performance_bonus?: number
              attendance_bonus?: number
              other_allowances?: number
              gross_salary?: number
              social_insurance?: number
              housing_fund?: number
              tax?: number
              other_deductions?: number
              net_salary?: number
              payment_date?: string | null
              payment_status?: string
              created_at?: string
          }
      }
      hr_performance_reviews: {
          Row: {
            id: string
            user_id: string
            reviewer_id: string | null
            period: string
            self_rating: number | null
            manager_rating: number | null
            final_rating: number | null
            ai_rating: number | null
            ai_analysis: string | null
            goals: Json | null
            strengths: string | null
            improvements: string | null
            status: string
            created_at: string
            updated_at: string
          }
          Insert: {
              id?: string
              user_id: string
              reviewer_id?: string | null
              period: string
              self_rating?: number | null
              manager_rating?: number | null
              final_rating?: number | null
              ai_rating?: number | null
              ai_analysis?: string | null
              goals?: Json | null
              strengths?: string | null
              improvements?: string | null
              status?: string
              created_at?: string
              updated_at?: string
          }
          Update: {
              id?: string
              user_id?: string
              reviewer_id?: string | null
              period?: string
              self_rating?: number | null
              manager_rating?: number | null
              final_rating?: number | null
              ai_rating?: number | null
              ai_analysis?: string | null
              goals?: Json | null
              strengths?: string | null
              improvements?: string | null
              status?: string
              created_at?: string
              updated_at?: string
          }
      }
      hr_job_positions: {
          Row: {
            id: string
            organization_id: string | null
            title: string
            department: string | null
            description: string | null
            requirements: string | null
            salary_range_min: number | null
            salary_range_max: number | null
            headcount: number
            hired_count: number
            status: string
            created_by: string | null
            created_at: string
            updated_at: string
          }
          Insert: {
              id?: string
              organization_id?: string | null
              title: string
              department?: string | null
              description?: string | null
              requirements?: string | null
              salary_range_min?: number | null
              salary_range_max?: number | null
              headcount?: number
              hired_count?: number
              status?: string
              created_by?: string | null
              created_at?: string
              updated_at?: string
          }
          Update: {
              id?: string
              organization_id?: string | null
              title?: string
              department?: string | null
              description?: string | null
              requirements?: string | null
              salary_range_min?: number | null
              salary_range_max?: number | null
              headcount?: number
              hired_count?: number
              status?: string
              created_by?: string | null
              created_at?: string
              updated_at?: string
          }
      }
      hr_candidates: {
          Row: {
            id: string
            position_id: string
            name: string
            email: string | null
            phone: string | null
            resume_url: string | null
            status: string
            ai_score: number | null
            ai_analysis: string | null
            interview_date: string | null
            created_at: string
          }
          Insert: {
              id?: string
              position_id: string
              name: string
              email?: string | null
              phone?: string | null
              resume_url?: string | null
              status?: string
              ai_score?: number | null
              ai_analysis?: string | null
              interview_date?: string | null
              created_at?: string
          }
          Update: {
              id?: string
              position_id?: string
              name?: string
              email?: string | null
              phone?: string | null
              resume_url?: string | null
              status?: string
              ai_score?: number | null
              ai_analysis?: string | null
              interview_date?: string | null
              created_at?: string
          }
      }
      finance_budgets: {
          Row: {
            id: string
            organization_id: string
            name: string
            total_amount: number
            used_amount: number
            period: string
            department_id: string | null
            category: string | null
            status: string
            created_by: string | null
            created_at: string
            updated_at: string
          }
          Insert: {
              id?: string
              organization_id: string
              name: string
              total_amount: number
              used_amount?: number
              period: string
              department_id?: string | null
              category?: string | null
              status?: string
              created_by?: string | null
              created_at?: string
              updated_at?: string
          }
          Update: {
              id?: string
              organization_id?: string
              name?: string
              total_amount?: number
              used_amount?: number
              period?: string
              department_id?: string | null
              category?: string | null
              status?: string
              created_by?: string | null
              created_at?: string
              updated_at?: string
          }
      }
      contracts: {
          Row: {
            id: string
            organization_id: string
            title: string
            party_a: string | null
            party_b: string | null
            amount: number | null
            start_date: string | null
            end_date: string | null
            status: string
            type: string | null
            description: string | null
            created_by: string | null
            created_at: string
            updated_at: string
          }
          Insert: {
              id?: string
              organization_id: string
              title: string
              party_a?: string | null
              party_b?: string | null
              amount?: number | null
              start_date?: string | null
              end_date?: string | null
              status?: string
              type?: string | null
              description?: string | null
              created_by?: string | null
              created_at?: string
              updated_at?: string
          }
          Update: {
              id?: string
              organization_id?: string
              title?: string
              party_a?: string | null
              party_b?: string | null
              amount?: number | null
              start_date?: string | null
              end_date?: string | null
              status?: string
              type?: string | null
              description?: string | null
              created_by?: string | null
              created_at?: string
              updated_at?: string
          }
      }
      audit_logs: {
          Row: {
            id: string
            action: string
            actor: string
            target: string | null
            details: string | null
            status: string
            ip_address: string | null
            user_agent: string | null
            created_at: string
          }
          Insert: {
              id?: string
              action: string
              actor: string
              target?: string | null
              details?: string | null
              status?: string
              ip_address?: string | null
              user_agent?: string | null
              created_at?: string
          }
          Update: {
              id?: string
              action?: string
              actor?: string
              target?: string | null
              details?: string | null
              status?: string
              ip_address?: string | null
              user_agent?: string | null
              created_at?: string
          }
      }
      dashboard_configs: {
          Row: {
            id: string
            user_id: string
            organization_id: string | null
            config_json: Json
            created_at: string
            updated_at: string
          }
          Insert: {
              id?: string
              user_id: string
              organization_id?: string | null
              config_json: Json
              created_at?: string
              updated_at?: string
          }
          Update: {
              id?: string
              user_id?: string
              organization_id?: string | null
              config_json?: Json
              created_at?: string
              updated_at?: string
          }
      }
      qa_pairs: {
          Row: {
            id: string
            question: string
            answer: string
            category: string | null
            user_id: string
            created_at: string
            updated_at: string | null
          }
          Insert: {
              id?: string
              question: string
              answer: string
              category?: string | null
              user_id: string
              created_at?: string
              updated_at?: string | null
          }
          Update: {
              id?: string
              question?: string
              answer?: string
              category?: string | null
              user_id?: string
              created_at?: string
              updated_at?: string | null
          }
      }
      contract_events: {
          Row: {
            id: string
            contract_id: string
            event_type: string
            description: string | null
            event_date: string
            created_by: string | null
            created_at: string
          }
          Insert: {
              id?: string
              contract_id: string
              event_type: string
              description?: string | null
              event_date: string
              created_by?: string | null
              created_at?: string
          }
          Update: {
              id?: string
              contract_id?: string
              event_type?: string
              description?: string | null
              event_date?: string
              created_by?: string | null
              created_at?: string
          }
      }
      customers: {
          Row: {
            id: string
            name: string
            company: string | null
            email: string | null
            phone: string | null
            address: string | null
            notes: string | null
            organization_id: string | null
            created_by: string | null
            created_at: string
            updated_at: string | null
          }
          Insert: {
              id?: string
              name: string
              company?: string | null
              email?: string | null
              phone?: string | null
              address?: string | null
              notes?: string | null
              organization_id?: string | null
              created_by?: string | null
              created_at?: string
              updated_at?: string | null
          }
          Update: {
              id?: string
              name?: string
              company?: string | null
              email?: string | null
              phone?: string | null
              address?: string | null
              notes?: string | null
              organization_id?: string | null
              created_by?: string | null
              created_at?: string
              updated_at?: string | null
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
      get_user_role: {
        Args: {
          _user_id: string
        }
        Returns: 'boss' | 'manager' | 'employee' | 'admin' | null
      }
      transfer_employee_data: {
        Args: {
          from_user_id: string
          to_user_id: string
        }
        Returns: undefined
      }
      delete_employee: {
        Args: {
          target_user_id: string
        }
        Returns: undefined
      }
      admin_update_user: {
        Args: {
          target_user_id: string
          new_role: string | null
          new_name: string | null
          new_department_id: string | null
        }
        Returns: Json
      }
      search_memories_by_embedding: {
        Args: {
          query_embedding: string
          target_user_id: string
          match_threshold: number
          match_count: number
        }
        Returns: {
          id: string
          key: string
          value: string
          category: string
          importance: number
          similarity: number
        }[]
      }
    }
    Enums: {
      [_ in never]: never
    }
  }
}
