-- P1-1: 审计日志不可变性 — 禁止 UPDATE/DELETE on audit_logs (append-only)
-- 使用 BEFORE trigger 确保任何角色（包括 DB owner）都无法修改历史审计记录

CREATE OR REPLACE FUNCTION prevent_audit_log_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'audit_logs is append-only: % operations are forbidden', TG_OP;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS audit_logs_immutable ON public.audit_logs;
CREATE TRIGGER audit_logs_immutable
    BEFORE UPDATE OR DELETE ON public.audit_logs
    FOR EACH ROW
    EXECUTE FUNCTION prevent_audit_log_mutation();
