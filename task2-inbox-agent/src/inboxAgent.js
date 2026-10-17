const fs = require('fs');
const path = require('path');
const { v4: uuidv4 } = require('uuid');
const { validateEmails, classifyEmail } = require('./classifier');
const { KnowledgeBrainClient } = require('./kbClient');
const { buildDraft } = require('./draft');

const DEFAULT_MAX_UNEDITED = 20;

class InboxAgent {
  constructor({ kbClient, maxConsecutiveUneditedApprovals = DEFAULT_MAX_UNEDITED, emailDatasetPath } = {}) {
    this.kbClient = kbClient || new KnowledgeBrainClient();
    this.maxConsecutiveUneditedApprovals = maxConsecutiveUneditedApprovals;
    this.items = [];
    this.audit = [];
    if (emailDatasetPath) {
      this.loadDataset(emailDatasetPath);
    }
  }

  loadDataset(filePath) {
    const full = path.resolve(filePath);
    const raw = fs.readFileSync(full, 'utf8');
    const data = JSON.parse(raw);
    const emails = Array.isArray(data) ? data : data.emails;
    return this.ingestEmails(emails);
  }

  ingestEmails(emails) {
    const validated = validateEmails(emails);
    const items = validated.map((email) => this._createItem(email));
    this.items.push(...items);
    return items;
  }

  _createItem(email) {
    const classification = classifyEmail(email);
    const item = {
      id: uuidv4(),
      email,
      classification,
      draft: null,
      state: 'pending_review',
      consecutiveUneditedApprovals: 0,
      reviewHistory: [],
      metadata: {},
    };
    this._recordAudit(item.id, 'created', { category: classification.category });
    return item;
  }

  getItems(filter = {}) {
    let res = [...this.items];
    if (filter.state) res = res.filter((i) => i.state === filter.state);
    if (filter.category) res = res.filter((i) => i.classification.category === filter.category);
    return res;
  }

  getItem(id) {
    return this.items.find((i) => i.id === id) || null;
  }

  async generateDraft(itemId) {
    const item = this.getItem(itemId);
    if (!item) throw new Error('item not found');
    const kbResp = await this.kbClient.ask(item.email.body);
    const draft = buildDraft(item.email, item.classification, kbResp);
    item.draft = draft;
    item.metadata.lastKb = {
      request_id: kbResp.request_id,
      evidence_status: kbResp.evidence_status,
    };
    this._recordAudit(itemId, 'draft_generated', { evidence_status: kbResp.evidence_status });
    return draft;
  }

  regenerateDraft(itemId) {
    return this.generateDraft(itemId);
  }

  review(itemId, action, { editedDraft, rejectionReason, escalationReason, feedback, reviewerId } = {}) {
    const item = this.getItem(itemId);
    if (!item) throw new Error('item not found');
    const draft = item.draft;
    const nextHistory = [...item.reviewHistory];
    let newState = item.state;
    let newConsec = item.consecutiveUneditedApprovals;

    if (action === 'approve') {
      if (draft && draft.grounded && draft.citations?.length > 0) {
        newState = 'approved';
        newConsec = item.consecutiveUneditedApprovals + 1;
      } else {
        newState = 'escalated';
        newConsec = 0;
        nextHistory.push({ action: 'auto_escalated_due_to_weak_evidence', at: new Date().toISOString() });
      }
    } else if (action === 'edit') {
      const finalBody = editedDraft || (draft ? draft.body : '');
      if (draft) {
        draft.body = finalBody;
        draft.notes = feedback || draft.notes;
      }
      newState = 'edited_and_approved';
      newConsec = 0;
    } else if (action === 'reject' || action === 'request_revision') {
      newState = 'rejected';
      newConsec = 0;
      nextHistory.push({ action, rejectionReason: rejectionReason || feedback, at: new Date().toISOString() });
    } else if (action === 'escalate') {
      newState = 'escalated';
      newConsec = 0;
      nextHistory.push({ action, escalationReason, at: new Date().toISOString() });
    } else {
      throw new Error('invalid action');
    }

    nextHistory.push({
      action,
      reviewerId,
      feedback,
      edited: action === 'edit',
      at: new Date().toISOString(),
    });
    item.state = newState;
    item.consecutiveUneditedApprovals = newConsec;
    item.reviewHistory = nextHistory;
    if (newConsec >= this.maxConsecutiveUneditedApprovals) {
      this._recordAudit(itemId, 'consecutive_unedited_approvals_threshold_reached', {
        count: newConsec,
        threshold: this.maxConsecutiveUneditedApprovals,
      });
    }
    this._recordAudit(itemId, 'reviewed', { action, state: newState });
    return item;
  }

  _recordAudit(itemId, event, meta = {}) {
    this.audit.push({
      itemId,
      event,
      meta,
      at: new Date().toISOString(),
    });
  }

  getAudit() {
    return [...this.audit];
  }

  getReviewHistory(itemId) {
    const item = this.getItem(itemId);
    return item ? [...item.reviewHistory] : [];
  }
}

module.exports = { InboxAgent };
