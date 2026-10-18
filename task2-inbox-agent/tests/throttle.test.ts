import { parseRetryAfterMs, retryDelayMs, withGlobalModelThrottle } from '../src/throttle';

describe('global model request throttle', () => {
  it('parses Retry-After seconds and preserves provider delays', () => {
    expect(parseRetryAfterMs('7')).toBe(7000);
    expect(retryDelayMs(0, 7000)).toBe(7000);
  });

  it('serializes concurrent requests', async () => {
    let active = 0;
    let maxActive = 0;
    await Promise.all([1, 2, 3].map(() => withGlobalModelThrottle(async () => {
      active++;
      maxActive = Math.max(maxActive, active);
      await new Promise((resolve) => setTimeout(resolve, 2));
      active--;
    }, 0)));
    expect(maxActive).toBe(1);
  });
});
