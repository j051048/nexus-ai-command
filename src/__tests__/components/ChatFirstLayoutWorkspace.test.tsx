import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import { ChatFirstLayout } from '@/components/layout/ChatFirstLayout';

vi.mock('@/components/auth/AuthContext', () => ({ useAuth: () => ({ isPendingBoss: false }) }));
vi.mock('@/hooks/useWebSocketPush', () => ({ useWebSocketPush: () => undefined }));
vi.mock('@/components/layout/Sidebar', () => ({ Sidebar: () => <div>Sidebar</div> }));
vi.mock('@/components/ai/EnhancedAIChatPanel', () => ({
  default: () => <div>Assistant panel</div>,
}));
vi.mock('@/components/ai/GlobalAIBall', () => ({ GlobalAIBall: () => null }));
vi.mock('@/components/common/InstallPrompt', () => ({ InstallPrompt: () => null }));
vi.mock('@/components/common/WelcomeTour', () => ({ WelcomeTour: () => null }));
vi.mock('@/components/common/NotificationCenter', () => ({ NotificationCenter: () => null }));
vi.mock('@/components/billing/TrialBanner', () => ({ TrialBanner: () => null }));

describe('ChatFirstLayout workspace modes', () => {
  beforeEach(() => window.localStorage.clear());

  it('switches between business, split and assistant modes', () => {
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <ChatFirstLayout><div>Business surface</div></ChatFirstLayout>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByLabelText('专注业务'));
    expect(screen.getByText('Business surface')).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('打开助手面板'));
    fireEvent.click(screen.getByLabelText('专注助手'));
    expect(screen.getByText('Assistant panel')).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('打开业务页面'));
    expect(screen.getByText('Business surface')).toBeInTheDocument();
  });

  it('supports accessible keyboard resizing', () => {
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <ChatFirstLayout><div>Business surface</div></ChatFirstLayout>
      </MemoryRouter>,
    );
    const separator = screen.getByRole('separator', { name: '调整助手面板宽度' });
    fireEvent.keyDown(separator, { key: 'ArrowRight' });
    expect(separator).toHaveAttribute('aria-valuenow', '504');
  });
});
