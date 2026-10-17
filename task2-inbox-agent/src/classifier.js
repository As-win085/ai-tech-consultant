const { v4: uuidv4 } = require('uuid');
const { emailSchema, classificationSchema } = require('./schemas');

const CATEGORIES = [
  'product_howto',
  'troubleshooting',
  'billing_account',
  'feature_request',
  'complaint',
  'unsupported_unclear',
];

function validateEmails(emails) {
  if (!Array.isArray(emails)) {
    throw new Error('emails must be an array');
  }
  return emails.map((e) => {
    const parsed = emailSchema.parse({ ...e });
    return {
      id: parsed.id || uuidv4(),
      from: parsed.from,
      to: parsed.to || ['support@support.example'],
      subject: parsed.subject,
      body: parsed.body,
      receivedAt: parsed.receivedAt || new Date().toISOString(),
      threadId: parsed.threadId || null,
    };
  });
}

function classifyEmail(email) {
  const text = `${email.subject}\n${email.body}`.toLowerCase();
  let category = 'unsupported_unclear';
  if (/password|login|reset|signup|account access|how to|guide/.test(text)) {
    category = 'product_howto';
  } else if (/error|not working|broken|crash|fail|issue|troubleshoot|doesn't work/.test(text)) {
    category = 'troubleshooting';
  } else if (/bill|invoice|payment|charge|refund|subscription|billing/.test(text)) {
    category = 'billing_account';
  } else if (/feature|request|suggest|improve|enhance/.test(text)) {
    category = 'feature_request';
  } else if (/complain|angry|disappointed|bad|unacceptable/.test(text)) {
    category = 'complaint';
  } else if (/mass email|cold email|bulk email|unsolicited/.test(text)) {
    category = 'product_howto';
  }
  let priority = 'medium';
  if (/urgent|asap|critical|down|blocked/.test(text)) priority = 'urgent';
  else if (/billing|payment|charge/.test(text)) priority = 'high';
  else if (/how to|feature|question/.test(text)) priority = 'low';

  const needsEscalation = category === 'complaint' || priority === 'urgent';
  const cls = { category, priority, needsEscalation };
  return classificationSchema.parse(cls);
}

module.exports = { validateEmails, classifyEmail, CATEGORIES };
