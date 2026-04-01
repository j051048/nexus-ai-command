/**
 * 快速申请入口组件 + AI语音识别
 * P0-1: 首页快速按钮、模板保存、AI语音输入
 */
import React, { useState } from 'react';
import { Mic, Zap, FileText, Calendar, Plane } from 'lucide-react';

interface QuickActionProps {
  onSubmit: (data: any) => void;
}

export function QuickActions({ onSubmit }: QuickActionProps) {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');

  // AI语音识别
  const handleVoiceInput = async () => {
    setIsListening(true);

    // 调用浏览器语音识别API
    const recognition = new (window as any).webkitSpeechRecognition();
    recognition.lang = 'zh-CN';
    recognition.continuous = false;

    recognition.onresult = async (event: any) => {
      const text = event.results[0][0].transcript;
      setTranscript(text);

      // 调用AI解析意图
      const parsed = await parseVoiceIntent(text);
      if (parsed) {
        onSubmit(parsed);
      }
    };

    recognition.onend = () => setIsListening(false);
    recognition.start();
  };

  // AI解析语音意图
  const parseVoiceIntent = async (text: string) => {
    const response = await fetch('/api/ai/parse-voice-intent', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text })
    });
    return response.json();
  };

  return (
    <div className="quick-actions">
      {/* 语音输入按钮 */}
      <button
        onClick={handleVoiceInput}
        className={`voice-btn ${isListening ? 'listening' : ''}`}
      >
        <Mic className={isListening ? 'animate-pulse' : ''} />
        <span>{isListening ? '正在听...' : '语音申请'}</span>
      </button>

      {transcript && (
        <div className="transcript">识别: {transcript}</div>
      )}

      {/* 快速申请按钮 */}
      <div className="quick-buttons grid grid-cols-2 gap-3 mt-4">
        <QuickButton
          icon={<FileText />}
          label="快速报销"
          onClick={() => onSubmit({ type: 'expense' })}
        />
        <QuickButton
          icon={<Calendar />}
          label="快速请假"
          onClick={() => onSubmit({ type: 'leave' })}
        />
        <QuickButton
          icon={<Plane />}
          label="差旅申请"
          onClick={() => onSubmit({ type: 'travel' })}
        />
        <QuickButton
          icon={<Zap />}
          label="我的模板"
          onClick={() => {/* 打开模板列表 */}}
        />
      </div>
    </div>
  );
}

function QuickButton({ icon, label, onClick }) {
  return (
    <button
      onClick={onClick}
      className="quick-button p-4 border rounded-lg hover:bg-blue-50"
    >
      <div className="flex flex-col items-center gap-2">
        {icon}
        <span className="text-sm">{label}</span>
      </div>
    </button>
  );
}