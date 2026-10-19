import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '@/test/render';
import { kbAnswerAbstain, kbAnswerSufficient, kbTimeout } from '@/test/fixtures';

const askMock = vi.fn();

vi.mock('@/api/knowledge', () => ({
  knowledgeApi: {
    ask: (...args: unknown[]) => askMock(...args),
    health: vi.fn(),
    ready: vi.fn(),
    probe: vi.fn(),
  },
}));

import { KnowledgePage } from '@/pages/Knowledge';

describe('Knowledge Brain page', () => {
  beforeEach(() => {
    askMock.mockReset();
  });

  it('submits a question and renders the answer with citations', async () => {
    askMock.mockResolvedValue(kbAnswerSufficient);
    const user = userEvent.setup();
    renderWithProviders(<KnowledgePage />);

    await user.type(screen.getByLabelText(/your question/i), 'How do I reset a member password?');
    await user.click(screen.getByRole('button', { name: /ask/i }));

    expect(await screen.findByText(/Reset password/i)).toBeInTheDocument();
    expect(screen.getByText(/Resetting a member password/i)).toBeInTheDocument();
    expect(screen.getByText(/Citations \(1\)/i)).toBeInTheDocument();
    expect(askMock).toHaveBeenCalledTimes(1);
    expect(askMock).toHaveBeenCalledWith(expect.objectContaining({ question: 'How do I reset a member password?' }));
  });

  it('renders an abstention without fabricating citations', async () => {
    askMock.mockResolvedValue(kbAnswerAbstain);
    const user = userEvent.setup();
    renderWithProviders(<KnowledgePage />);

    await user.type(screen.getByLabelText(/your question/i), 'Unsupported question');
    await user.click(screen.getByRole('button', { name: /ask/i }));

    expect(await screen.findByText(/No citations returned/i)).toBeInTheDocument();
    expect(screen.getByText(/Escalation recommended/i)).toBeInTheDocument();
    expect(screen.getByText('insufficient', { exact: true })).toBeInTheDocument();
  });

  it('shows a recoverable error with retry on failure', async () => {
    askMock.mockRejectedValue(kbTimeout);
    const user = userEvent.setup();
    renderWithProviders(<KnowledgePage />);

    await user.type(screen.getByLabelText(/your question/i), 'Will this time out?');
    await user.click(screen.getByRole('button', { name: /ask/i }));

    expect(await screen.findByRole('heading', { name: /Request timed out/i })).toBeInTheDocument();
    // The question text is preserved in the conversation.
    expect(screen.getByText(/Will this time out\?/i)).toBeInTheDocument();
  });

  it('validates empty input before calling the API', async () => {
    const user = userEvent.setup();
    renderWithProviders(<KnowledgePage />);
    await user.click(screen.getByRole('button', { name: /ask/i }));
    await waitFor(() => {
      expect(screen.getByText(/Enter at least two characters/i)).toBeInTheDocument();
    });
    expect(askMock).not.toHaveBeenCalled();
  });
});
