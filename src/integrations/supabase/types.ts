import type { DatabaseTables } from "./database-tables";
export type Tables<Name extends keyof DatabaseTables> = DatabaseTables[Name]['Row'];
export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export interface Database {
  public: {
    Tables: DatabaseTables
    Views: {
      [_ in never]: never
    }
    Functions: {
      is_super_admin: {
        Args: { _user_id: string }
        Returns: boolean
      }
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
