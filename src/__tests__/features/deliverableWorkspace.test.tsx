import { useState } from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { DeliverableWorkspace } from '@/components/deliverables/DeliverableWorkspace';

const auth = vi.hoisted(() => ({ profile: { organization_id: 'org-a' }, user: { id: 'user-a' } }));
vi.mock('@/components/auth/AuthContext', () => ({ useAuth: () => auth }));
vi.mock('@/components/deliverables/DeliverableCenter', () => ({
  DeliverableCenter: ({ open }: { open: boolean }) => {
    const [draft, setDraft] = useState('');
    return open ? <input aria-label="Unsent revision" value={draft} onChange={(event) => setDraft(event.target.value)} /> : null;
  },
}));

function renderWorkspace(compact: boolean) {
  return <DeliverableWorkspace compact={compact}>
    {(trigger) => compact ? <header>{trigger}</header> : <nav>{trigger}</nav>}
  </DeliverableWorkspace>;
}

afterEach(() => { cleanup(); auth.profile.organization_id = 'org-a'; auth.user.id = 'user-a'; });

describe('persistent deliverable workspace', () => {
  it('keeps the open preview and unsent revision when the header is replaced', () => {
    const view = render(renderWorkspace(false));
    fireEvent.click(screen.getByRole('button', { name: '打开成果中心' }));
    fireEvent.change(screen.getByLabelText('Unsent revision'), { target: { value: '保留安装培训要求' } });
    view.rerender(renderWorkspace(true));
    expect(screen.getByLabelText('Unsent revision')).toHaveValue('保留安装培训要求');
    view.rerender(renderWorkspace(false));
    expect(screen.getByLabelText('Unsent revision')).toHaveValue('保留安装培训要求');
  });

  it.each(['tenant', 'user'])('clears sensitive state on a %s switch', (scope) => {
    const view = render(renderWorkspace(false));
    fireEvent.click(screen.getByRole('button', { name: '打开成果中心' }));
    fireEvent.change(screen.getByLabelText('Unsent revision'), { target: { value: '私有草稿' } });
    if (scope === 'tenant') auth.profile.organization_id = 'org-b';
    else auth.user.id = 'user-b';
    view.rerender(renderWorkspace(false));
    expect(screen.queryByLabelText('Unsent revision')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '打开成果中心' }));
    expect(screen.getByLabelText('Unsent revision')).toHaveValue('');
  });
});
