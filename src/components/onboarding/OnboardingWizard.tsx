import React, { useState, useCallback } from 'react';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';
import { Label } from '@/components/ui/label';
import { useOnboarding } from '@/hooks/useOnboarding';
import { Building2, Upload, Users, MessageSquare, ChevronRight, ChevronLeft, Check, Sparkles } from 'lucide-react';

// ---------------------------------------------------------------------------
// Step 1: Welcome + Company Info
// ---------------------------------------------------------------------------

interface CompanyInfo {
  name: string;
  industry: string;
  size: string;
}

function StepCompanyInfo({
  data,
  onChange,
}: {
  data: CompanyInfo;
  onChange: (data: CompanyInfo) => void;
}) {
  return (
    <div className="space-y-6">
      <div className="text-center space-y-2">
        <div className="mx-auto w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center">
          <Building2 className="w-8 h-8 text-primary" />
        </div>
        <h2 className="text-2xl font-bold">欢迎使用 Nexus AI Command</h2>
        <p className="text-muted-foreground">
          让我们先了解一下您的企业，以便提供更精准的 AI 服务。
        </p>
      </div>

      <div className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="company-name">公司名称</Label>
          <Input
            id="company-name"
            placeholder="请输入公司名称"
            value={data.name}
            onChange={(e) => onChange({ ...data, name: e.target.value })}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="industry">所属行业</Label>
          <select
            id="industry"
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            value={data.industry}
            onChange={(e) => onChange({ ...data, industry: e.target.value })}
          >
            <option value="">请选择行业</option>
            <option value="tech">科技/互联网</option>
            <option value="manufacturing">制造业</option>
            <option value="finance">金融/保险</option>
            <option value="healthcare">医疗/健康</option>
            <option value="education">教育/培训</option>
            <option value="retail">零售/电商</option>
            <option value="realestate">房地产/建筑</option>
            <option value="consulting">咨询/服务</option>
            <option value="other">其他</option>
          </select>
        </div>

        <div className="space-y-2">
          <Label htmlFor="company-size">公司规模</Label>
          <select
            id="company-size"
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            value={data.size}
            onChange={(e) => onChange({ ...data, size: e.target.value })}
          >
            <option value="">请选择规模</option>
            <option value="1-10">1-10 人</option>
            <option value="11-50">11-50 人</option>
            <option value="51-200">51-200 人</option>
            <option value="201-500">201-500 人</option>
            <option value="500+">500 人以上</option>
          </select>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step 2: Import Data
// ---------------------------------------------------------------------------

function StepImportData({
  onChoose,
  choice,
}: {
  onChoose: (choice: 'import' | 'demo' | 'skip') => void;
  choice: string;
}) {
  return (
    <div className="space-y-6">
      <div className="text-center space-y-2">
        <div className="mx-auto w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center">
          <Upload className="w-8 h-8 text-primary" />
        </div>
        <h2 className="text-2xl font-bold">初始化您的数据</h2>
        <p className="text-muted-foreground">
          导入现有数据或使用演示数据快速体验。
        </p>
      </div>

      <div className="grid gap-4">
        <Card
          className={`cursor-pointer transition-all hover:border-primary ${
            choice === 'import' ? 'border-primary bg-primary/5' : ''
          }`}
          onClick={() => onChoose('import')}
        >
          <CardContent className="flex items-center gap-4 p-4">
            <Upload className="w-10 h-10 text-muted-foreground" />
            <div className="flex-1">
              <h3 className="font-semibold">导入现有数据</h3>
              <p className="text-sm text-muted-foreground">
                从 Excel/CSV 导入客户、线索、合同等数据
              </p>
            </div>
            {choice === 'import' && <Check className="w-5 h-5 text-primary" />}
          </CardContent>
        </Card>

        <Card
          className={`cursor-pointer transition-all hover:border-primary ${
            choice === 'demo' ? 'border-primary bg-primary/5' : ''
          }`}
          onClick={() => onChoose('demo')}
        >
          <CardContent className="flex items-center gap-4 p-4">
            <Sparkles className="w-10 h-10 text-muted-foreground" />
            <div className="flex-1">
              <h3 className="font-semibold">生成演示数据</h3>
              <p className="text-sm text-muted-foreground">
                自动生成示例数据，快速体验系统功能
              </p>
            </div>
            {choice === 'demo' && <Check className="w-5 h-5 text-primary" />}
          </CardContent>
        </Card>

        <Card
          className={`cursor-pointer transition-all hover:border-primary ${
            choice === 'skip' ? 'border-primary bg-primary/5' : ''
          }`}
          onClick={() => onChoose('skip')}
        >
          <CardContent className="flex items-center gap-4 p-4">
            <ChevronRight className="w-10 h-10 text-muted-foreground" />
            <div className="flex-1">
              <h3 className="font-semibold">跳过，稍后设置</h3>
              <p className="text-sm text-muted-foreground">
                先探索系统，随时可以导入数据
              </p>
            </div>
            {choice === 'skip' && <Check className="w-5 h-5 text-primary" />}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step 3: Invite Team Members
// ---------------------------------------------------------------------------

function StepInviteTeam({
  emails,
  onEmailsChange,
}: {
  emails: string[];
  onEmailsChange: (emails: string[]) => void;
}) {
  const [currentEmail, setCurrentEmail] = useState('');

  const addEmail = useCallback(() => {
    const trimmed = currentEmail.trim();
    if (trimmed && !emails.includes(trimmed)) {
      onEmailsChange([...emails, trimmed]);
      setCurrentEmail('');
    }
  }, [currentEmail, emails, onEmailsChange]);

  const removeEmail = useCallback(
    (email: string) => {
      onEmailsChange(emails.filter((e) => e !== email));
    },
    [emails, onEmailsChange],
  );

  return (
    <div className="space-y-6">
      <div className="text-center space-y-2">
        <div className="mx-auto w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center">
          <Users className="w-8 h-8 text-primary" />
        </div>
        <h2 className="text-2xl font-bold">邀请团队成员</h2>
        <p className="text-muted-foreground">
          邀请同事一起使用，也可以跳过此步骤稍后邀请。
        </p>
      </div>

      <div className="space-y-4">
        <div className="flex gap-2">
          <Input
            placeholder="输入邮箱地址"
            type="email"
            value={currentEmail}
            onChange={(e) => setCurrentEmail(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                addEmail();
              }
            }}
          />
          <Button variant="outline" onClick={addEmail}>
            添加
          </Button>
        </div>

        {emails.length > 0 && (
          <div className="space-y-2">
            {emails.map((email) => (
              <div
                key={email}
                className="flex items-center justify-between px-3 py-2 bg-muted rounded-md"
              >
                <span className="text-sm">{email}</span>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 px-2 text-muted-foreground hover:text-destructive"
                  onClick={() => removeEmail(email)}
                >
                  移除
                </Button>
              </div>
            ))}
          </div>
        )}

        <p className="text-xs text-muted-foreground">
          按 Enter 添加邮箱，邀请邮件将在完成引导后发送。
        </p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step 4: First AI Conversation
// ---------------------------------------------------------------------------

function StepFirstChat({ onPromptSelect }: { onPromptSelect: (prompt: string) => void }) {
  const suggestedPrompts = [
    { label: '查看销售概览', prompt: '帮我看看本月的销售概况' },
    { label: '创建客户线索', prompt: '帮我创建一条新的客户线索' },
    { label: '了解系统功能', prompt: '你能帮我做哪些事情？' },
    { label: '数据分析报告', prompt: '帮我生成一份销售数据分析报告' },
  ];

  return (
    <div className="space-y-6">
      <div className="text-center space-y-2">
        <div className="mx-auto w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center">
          <MessageSquare className="w-8 h-8 text-primary" />
        </div>
        <h2 className="text-2xl font-bold">开始您的第一次 AI 对话</h2>
        <p className="text-muted-foreground">
          选择一个话题，体验 AI 助手的能力。
        </p>
      </div>

      <div className="grid gap-3">
        {suggestedPrompts.map((item) => (
          <Card
            key={item.prompt}
            className="cursor-pointer transition-all hover:border-primary hover:bg-primary/5"
            onClick={() => onPromptSelect(item.prompt)}
          >
            <CardContent className="flex items-center gap-3 p-4">
              <Sparkles className="w-5 h-5 text-primary shrink-0" />
              <div>
                <h3 className="font-medium">{item.label}</h3>
                <p className="text-sm text-muted-foreground">&ldquo;{item.prompt}&rdquo;</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main OnboardingWizard
// ---------------------------------------------------------------------------

const TOTAL_STEPS = 4;

const STEP_LABELS = ['公司信息', '数据初始化', '邀请团队', '开始对话'];

export function OnboardingWizard() {
  const { currentStep, setCurrentStep, completeOnboarding, saveStepData } = useOnboarding();

  // Step 1 state
  const [companyInfo, setCompanyInfo] = useState<CompanyInfo>({
    name: '',
    industry: '',
    size: '',
  });

  // Step 2 state
  const [dataChoice, setDataChoice] = useState<'import' | 'demo' | 'skip' | ''>('');

  // Step 3 state
  const [inviteEmails, setInviteEmails] = useState<string[]>([]);

  const progress = ((currentStep + 1) / TOTAL_STEPS) * 100;

  const canGoNext = useCallback(() => {
    switch (currentStep) {
      case 0:
        return companyInfo.name.trim().length > 0;
      case 1:
        return dataChoice !== '';
      case 2:
        return true; // team invite is optional
      case 3:
        return true;
      default:
        return false;
    }
  }, [currentStep, companyInfo, dataChoice]);

  const handleNext = useCallback(async () => {
    // Save step data
    switch (currentStep) {
      case 0:
        await saveStepData('company_info', companyInfo);
        break;
      case 1:
        await saveStepData('data_choice', { choice: dataChoice });
        break;
      case 2:
        await saveStepData('invite_team', { emails: inviteEmails });
        break;
    }

    if (currentStep < TOTAL_STEPS - 1) {
      setCurrentStep(currentStep + 1);
    }
  }, [currentStep, companyInfo, dataChoice, inviteEmails, saveStepData, setCurrentStep]);

  const handleBack = useCallback(() => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  }, [currentStep, setCurrentStep]);

  const handlePromptSelect = useCallback(
    async (prompt: string) => {
      await saveStepData('first_prompt', { prompt });
      await completeOnboarding();
      // Navigation to AI chat will be handled by the parent component
      // after onboarding_completed flag is set
    },
    [saveStepData, completeOnboarding],
  );

  const handleSkipAll = useCallback(async () => {
    await completeOnboarding();
  }, [completeOnboarding]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <Card className="w-full max-w-lg">
        <CardHeader className="space-y-4">
          {/* Progress bar */}
          <div className="space-y-2">
            <div className="flex justify-between text-xs text-muted-foreground">
              {STEP_LABELS.map((label, i) => (
                <span
                  key={label}
                  className={i <= currentStep ? 'text-primary font-medium' : ''}
                >
                  {label}
                </span>
              ))}
            </div>
            <Progress value={progress} className="h-2" />
          </div>

          <CardTitle className="sr-only">
            {STEP_LABELS[currentStep]}
          </CardTitle>
          <CardDescription className="sr-only">
            第 {currentStep + 1} 步，共 {TOTAL_STEPS} 步
          </CardDescription>
        </CardHeader>

        <CardContent>
          {currentStep === 0 && (
            <StepCompanyInfo data={companyInfo} onChange={setCompanyInfo} />
          )}
          {currentStep === 1 && (
            <StepImportData choice={dataChoice} onChoose={setDataChoice} />
          )}
          {currentStep === 2 && (
            <StepInviteTeam emails={inviteEmails} onEmailsChange={setInviteEmails} />
          )}
          {currentStep === 3 && (
            <StepFirstChat onPromptSelect={handlePromptSelect} />
          )}
        </CardContent>

        <CardFooter className="flex justify-between">
          <div>
            {currentStep > 0 ? (
              <Button variant="ghost" onClick={handleBack}>
                <ChevronLeft className="w-4 h-4 mr-1" />
                上一步
              </Button>
            ) : (
              <Button variant="ghost" onClick={handleSkipAll}>
                跳过引导
              </Button>
            )}
          </div>

          <div>
            {currentStep < TOTAL_STEPS - 1 ? (
              <Button onClick={handleNext} disabled={!canGoNext()}>
                下一步
                <ChevronRight className="w-4 h-4 ml-1" />
              </Button>
            ) : (
              <Button variant="ghost" onClick={handleSkipAll}>
                跳过，直接进入
              </Button>
            )}
          </div>
        </CardFooter>
      </Card>
    </div>
  );
}

export default OnboardingWizard;
