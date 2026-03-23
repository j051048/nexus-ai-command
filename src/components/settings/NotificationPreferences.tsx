/**
 * B12: 用户通知偏好设置
 * 包含通知渠道开关、免打扰时段、通知类型过滤
 */

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import { Separator } from '@/components/ui/separator';
import {
    Bell,
    Mail,
    MessageSquare,
    Save,
    Moon,
    Clock,
    Filter,
} from 'lucide-react';
import { toast } from 'sonner';
import { supabase } from '@/integrations/supabase/client';
import { useAuth } from '@/components/auth/AuthContext';

interface NotificationPreferencesData {
    // 通知渠道
    channels: {
        inApp: boolean; // 站内通知（always on）
        email: boolean; // 邮件
        wecom: boolean; // 企微
        dingtalk: boolean; // 钉钉
        feishu: boolean; // 飞书
    };
    // 免打扰时段
    doNotDisturb: {
        enabled: boolean;
        startTime: string; // HH:mm 格式
        endTime: string; // HH:mm 格式
    };
    // 通知类型过滤
    types: {
        approval: boolean; // 审批通知
        announcement: boolean; // 公告通知
        system: boolean; // 系统通知
    };
}

const DEFAULT_PREFERENCES: NotificationPreferencesData = {
    channels: {
        inApp: true,
        email: true,
        wecom: false,
        dingtalk: false,
        feishu: false,
    },
    doNotDisturb: {
        enabled: false,
        startTime: '22:00',
        endTime: '08:00',
    },
    types: {
        approval: true,
        announcement: true,
        system: true,
    },
};

export function NotificationPreferences() {
    const { user } = useAuth();
    const [preferences, setPreferences] = useState<NotificationPreferencesData>(DEFAULT_PREFERENCES);
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);

    // 从 localStorage 加载设置
    useEffect(() => {
        const loadPreferences = () => {
            try {
                const stored = localStorage.getItem('notification_preferences');
                if (stored) {
                    const parsed = JSON.parse(stored);
                    setPreferences({ ...DEFAULT_PREFERENCES, ...parsed });
                }
            } catch (error) {
                // localStorage parse failure is non-critical; use defaults
            }
        };

        loadPreferences();
    }, []);

    // 保存设置
    const handleSave = async () => {
        setSaving(true);

        try {
            // 保存到 localStorage
            localStorage.setItem('notification_preferences', JSON.stringify(preferences));

            // TODO: 保存到 supabase（当后端表结构准备好后）
            // if (user?.id) {
            //     const { error } = await supabase
            //         .from('user_preferences')
            //         .upsert({
            //             user_id: user.id,
            //             notification_preferences: preferences,
            //             updated_at: new Date().toISOString(),
            //         });
            //     if (error) throw error;
            // }

            toast.success('保存成功', { description: '通知偏好设置已更新' });
        } catch (error) {
            toast.error('保存失败', { description: '无法保存通知偏好设置，请稍后重试' });
        } finally {
            setSaving(false);
        }
    };

    // 更新渠道设置
    const updateChannel = (channel: keyof NotificationPreferencesData['channels'], enabled: boolean) => {
        setPreferences((prev) => ({
            ...prev,
            channels: {
                ...prev.channels,
                [channel]: enabled,
            },
        }));
    };

    // 更新免打扰设置
    const updateDoNotDisturb = (updates: Partial<NotificationPreferencesData['doNotDisturb']>) => {
        setPreferences((prev) => ({
            ...prev,
            doNotDisturb: {
                ...prev.doNotDisturb,
                ...updates,
            },
        }));
    };

    // 更新通知类型设置
    const updateType = (type: keyof NotificationPreferencesData['types'], enabled: boolean) => {
        setPreferences((prev) => ({
            ...prev,
            types: {
                ...prev.types,
                [type]: enabled,
            },
        }));
    };

    return (
        <div className="space-y-6">
            {/* 通知渠道设置 */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Bell className="w-5 h-5" />
                        通知渠道
                    </CardTitle>
                    <CardDescription>
                        选择接收通知的渠道，站内通知始终开启
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    {/* 站内通知 - Always On */}
                    <div className="flex items-center justify-between">
                        <div className="space-y-0.5">
                            <Label className="text-sm font-medium">站内通知</Label>
                            <p className="text-xs text-muted-foreground">
                                在应用内接收通知消息
                            </p>
                        </div>
                        <Switch checked={true} disabled />
                    </div>

                    <Separator />

                    {/* 邮件通知 */}
                    <div className="flex items-center justify-between">
                        <div className="space-y-0.5">
                            <Label className="text-sm font-medium flex items-center gap-2">
                                <Mail className="w-4 h-4" />
                                邮件通知
                            </Label>
                            <p className="text-xs text-muted-foreground">
                                通过邮件接收重要通知
                            </p>
                        </div>
                        <Switch
                            checked={preferences.channels.email}
                            onCheckedChange={(checked) => updateChannel('email', checked)}
                        />
                    </div>

                    {/* 企业微信 */}
                    <div className="flex items-center justify-between">
                        <div className="space-y-0.5">
                            <Label className="text-sm font-medium flex items-center gap-2">
                                <MessageSquare className="w-4 h-4" />
                                企业微信
                            </Label>
                            <p className="text-xs text-muted-foreground">
                                通过企业微信接收通知
                            </p>
                        </div>
                        <Switch
                            checked={preferences.channels.wecom}
                            onCheckedChange={(checked) => updateChannel('wecom', checked)}
                        />
                    </div>

                    {/* 钉钉 */}
                    <div className="flex items-center justify-between">
                        <div className="space-y-0.5">
                            <Label className="text-sm font-medium flex items-center gap-2">
                                <MessageSquare className="w-4 h-4" />
                                钉钉
                            </Label>
                            <p className="text-xs text-muted-foreground">
                                通过钉钉接收通知
                            </p>
                        </div>
                        <Switch
                            checked={preferences.channels.dingtalk}
                            onCheckedChange={(checked) => updateChannel('dingtalk', checked)}
                        />
                    </div>

                    {/* 飞书 */}
                    <div className="flex items-center justify-between">
                        <div className="space-y-0.5">
                            <Label className="text-sm font-medium flex items-center gap-2">
                                <MessageSquare className="w-4 h-4" />
                                飞书
                            </Label>
                            <p className="text-xs text-muted-foreground">
                                通过飞书接收通知
                            </p>
                        </div>
                        <Switch
                            checked={preferences.channels.feishu}
                            onCheckedChange={(checked) => updateChannel('feishu', checked)}
                        />
                    </div>
                </CardContent>
            </Card>

            {/* 免打扰时段 */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Moon className="w-5 h-5" />
                        免打扰时段
                    </CardTitle>
                    <CardDescription>
                        在指定时间段内静音通知，不影响站内消息
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="flex items-center justify-between">
                        <Label className="text-sm font-medium">启用免打扰</Label>
                        <Switch
                            checked={preferences.doNotDisturb.enabled}
                            onCheckedChange={(checked) => updateDoNotDisturb({ enabled: checked })}
                        />
                    </div>

                    {preferences.doNotDisturb.enabled && (
                        <>
                            <Separator />
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label className="text-sm flex items-center gap-2">
                                        <Clock className="w-4 h-4" />
                                        开始时间
                                    </Label>
                                    <Input
                                        type="time"
                                        value={preferences.doNotDisturb.startTime}
                                        onChange={(e) => updateDoNotDisturb({ startTime: e.target.value })}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label className="text-sm flex items-center gap-2">
                                        <Clock className="w-4 h-4" />
                                        结束时间
                                    </Label>
                                    <Input
                                        type="time"
                                        value={preferences.doNotDisturb.endTime}
                                        onChange={(e) => updateDoNotDisturb({ endTime: e.target.value })}
                                    />
                                </div>
                            </div>
                            <p className="text-xs text-muted-foreground">
                                免打扰时段：{preferences.doNotDisturb.startTime} - {preferences.doNotDisturb.endTime}
                            </p>
                        </>
                    )}
                </CardContent>
            </Card>

            {/* 通知类型过滤 */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Filter className="w-5 h-5" />
                        通知类型
                    </CardTitle>
                    <CardDescription>
                        选择要接收的通知类型
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    {/* 审批通知 */}
                    <div className="flex items-center space-x-2">
                        <Checkbox
                            id="type-approval"
                            checked={preferences.types.approval}
                            onCheckedChange={(checked) => updateType('approval', !!checked)}
                        />
                        <div className="space-y-0.5 flex-1">
                            <Label
                                htmlFor="type-approval"
                                className="text-sm font-medium cursor-pointer"
                            >
                                审批通知
                            </Label>
                            <p className="text-xs text-muted-foreground">
                                报销单、请假申请等审批相关通知
                            </p>
                        </div>
                    </div>

                    <Separator />

                    {/* 公告通知 */}
                    <div className="flex items-center space-x-2">
                        <Checkbox
                            id="type-announcement"
                            checked={preferences.types.announcement}
                            onCheckedChange={(checked) => updateType('announcement', !!checked)}
                        />
                        <div className="space-y-0.5 flex-1">
                            <Label
                                htmlFor="type-announcement"
                                className="text-sm font-medium cursor-pointer"
                            >
                                公告通知
                            </Label>
                            <p className="text-xs text-muted-foreground">
                                系统公告、重要通知等
                            </p>
                        </div>
                    </div>

                    <Separator />

                    {/* 系统通知 */}
                    <div className="flex items-center space-x-2">
                        <Checkbox
                            id="type-system"
                            checked={preferences.types.system}
                            onCheckedChange={(checked) => updateType('system', !!checked)}
                        />
                        <div className="space-y-0.5 flex-1">
                            <Label
                                htmlFor="type-system"
                                className="text-sm font-medium cursor-pointer"
                            >
                                系统通知
                            </Label>
                            <p className="text-xs text-muted-foreground">
                                系统更新、维护提醒等
                            </p>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* 保存按钮 */}
            <div className="flex justify-end">
                <Button onClick={handleSave} disabled={saving}>
                    <Save className="w-4 h-4 mr-2" />
                    {saving ? '保存中...' : '保存设置'}
                </Button>
            </div>
        </div>
    );
}
