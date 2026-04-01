-- LLM Adapter Registry Table + Seed Data

CREATE TABLE IF NOT EXISTS llm_adapter (
  id bigserial PRIMARY KEY,
  adapter_code varchar(100) UNIQUE NOT NULL,
  adapter_name varchar(200) NOT NULL,
  provider_type varchar(50) NOT NULL,
  supported_models text,
  is_builtin boolean DEFAULT true,
  status varchar(20) DEFAULT 'enabled',
  config_schema jsonb,
  create_time timestamptz DEFAULT now()
);

-- Seed built-in adapters
INSERT INTO llm_adapter (adapter_code, adapter_name, provider_type, supported_models, is_builtin) VALUES
  ('openai_compatible_adapter', 'OpenAI兼容适配器', 'openai_compatible', '所有兼容OpenAI接口格式的API模型（Kimi、智谱、MiniMax、Claude via proxy、Gemini via proxy、开源模型等）', true),
  ('openai_adapter', 'OpenAI官方适配器', 'openai', 'GPT-4o、GPT-4o-mini、GPT-3.5-Turbo、Text-Embedding全系列', true),
  ('deepseek_adapter', 'DeepSeek适配器', 'deepseek', 'DeepSeek-V3、DeepSeek-Chat、DeepSeek-R1、DeepSeek-Embedding', true),
  ('wenxin_adapter', '百度文心一言适配器', 'wenxin', 'ERNIE-4.0、ERNIE-3.5、ERNIE-Speed、ERNIE-Embedding', true),
  ('tongyi_adapter', '阿里通义千问适配器', 'tongyi', 'Qwen-Max、Qwen-Plus、Qwen-Turbo、Qwen-Embedding', true),
  ('hunyuan_adapter', '腾讯混元适配器', 'hunyuan', '混元-Large、混元-Standard、混元-Embedding', true),
  ('doubao_adapter', '字节豆包适配器', 'doubao', '豆包-4.0、豆包-3.5、豆包-Embedding', true),
  ('yi_lingyi_adapter', '零一万物适配器', 'yi_lingyi', 'Yi-Large、Yi-Medium、Yi-Small、Yi-Embedding', true),
  ('anthropic_adapter', 'Anthropic Claude适配器', 'anthropic', 'Claude-3.5-Sonnet、Claude-3-Opus、Claude-3-Haiku', true)
ON CONFLICT (adapter_code) DO NOTHING;
