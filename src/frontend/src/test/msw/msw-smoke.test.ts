import { describe, expect, it } from 'vitest';
import { server } from './server';
import { errorHandlers, defaultPayload } from './handlers';

describe('MSW smoke', () => {
  it('default GET returns schema_version 2', async () => {
    const res = await fetch('/api/admin/indicator-preferences');
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.schema_version).toBe(2);
    expect(body.toggles.ma5).toBe(true);
  });

  it('PUT echoes body with fresh updated_at', async () => {
    const res = await fetch('/api/admin/indicator-preferences', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...defaultPayload, toggles: { ...defaultPayload.toggles, bb: true } }),
    });
    const body = await res.json();
    expect(body.toggles.bb).toBe(true);
    expect(body.updated_at).not.toBe(defaultPayload.updated_at);
  });

  it('overridden handler returns 500', async () => {
    server.use(errorHandlers.get500);
    const res = await fetch('/api/admin/indicator-preferences');
    expect(res.status).toBe(500);
  });
});
