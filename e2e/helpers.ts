/**
 * E2E 测试共享 helper 函数
 *
 * 提供认证、环境变量加载等通用逻辑，避免各测试文件重复代码。
 */

import { Page, expect } from "@playwright/test";
import { createClient, SupabaseClient } from "@supabase/supabase-js";
import * as fs from "fs";
import * as path from "path";

/**
 * 从后端 .env 文件读取环境变量（仅在 Node.js 上下文中使用）
 */
export function loadEnvVar(key: string): string {
  try {
    const envPath = path.resolve(__dirname, "../nexus_backend/.env");
    const content = fs.readFileSync(envPath, "utf-8");
    const match = content.match(new RegExp(`^${key}=(.+)$`, "m"));
    return match ? match[1].trim() : "";
  } catch {
    return "";
  }
}

/** Supabase 配置 */
export const SUPABASE_URL =
  process.env.SUPABASE_URL ||
  loadEnvVar("SUPABASE_URL") ||
  "https://hztpazmuejgbtixihcgj.supabase.co";

export const SUPABASE_SERVICE_KEY =
  process.env.SUPABASE_SERVICE_KEY || loadEnvVar("SUPABASE_SERVICE_KEY");

/**
 * 创建 Supabase Admin 客户端（使用 service role key）
 */
export function createAdminClient(): SupabaseClient | null {
  if (!SUPABASE_SERVICE_KEY) return null;
  return createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
}

/**
 * 通过 Supabase Admin API 创建预确认的测试用户
 */
export async function createTestUser(
  adminClient: SupabaseClient,
  email: string,
  password: string,
  name: string = "E2E Test User"
): Promise<string | null> {
  const { data, error } = await adminClient.auth.admin.createUser({
    email,
    password,
    email_confirm: true,
    user_metadata: { name },
  });

  if (error) {
    console.error("Failed to create test user:", error.message);
    return null;
  }
  console.log("Created test user:", data.user?.id);
  return data.user?.id || null;
}

/**
 * 清理测试用户
 */
export async function cleanupTestUser(
  adminClient: SupabaseClient,
  email: string
): Promise<void> {
  try {
    const { data } = await adminClient.auth.admin.listUsers();
    const testUser = data?.users?.find((u) => u.email === email);
    if (testUser) {
      await adminClient.auth.admin.deleteUser(testUser.id);
      console.log("Cleaned up test user:", testUser.id);
    }
  } catch (e) {
    console.warn("Failed to clean up test user:", e);
  }
}

/**
 * 在页面上执行登录流程
 */
export async function loginAs(
  page: Page,
  email: string,
  password: string
): Promise<void> {
  await page.goto("/login");
  await page.locator("#login-email").fill(email);
  await page.locator("#login-password").fill(password);
  await page.getByRole("button", { name: "登录", exact: true }).click();

  // 等待登录成功 toast 和重定向
  await expect(page.getByText("登录成功").first()).toBeVisible({
    timeout: 15000,
  });
  await expect(page).toHaveURL(/.*\//, { timeout: 30000 });
}
