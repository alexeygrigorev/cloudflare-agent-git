import { ShortlinkService, ValidationError, ConflictError, NotFoundError } from './shortlinks.js';

export function json(status, body, headers = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8', ...headers },
  });
}

function errorResponse(err) {
  if (err instanceof ValidationError) return json(400, { error: err.message });
  if (err instanceof ConflictError) return json(409, { error: err.message });
  if (err instanceof NotFoundError) return json(404, { error: err.message });
  throw err;
}

export async function route(request, service) {
  const url = new URL(request.url);
  const method = request.method;
  const pathname = url.pathname;

  if (method === 'POST' && pathname === '/links') {
    const body = await request.json().catch(() => null);
    if (!body || typeof body !== 'object') return json(400, { error: 'invalid JSON body' });
    try {
      const record = service.create(body.slug, body.url);
      return json(201, record);
    } catch (err) {
      return errorResponse(err);
    }
  }

  if (method === 'POST' && pathname === '/links/bulk') {
    const body = await request.json().catch(() => null);
    if (!body || typeof body !== 'object' || !Array.isArray(body.links)) {
      return json(400, { error: 'body must be { "links": [...] }' });
    }
    const slugs = [];
    for (const [index, item] of body.links.entries()) {
      try {
        const record = service.create(item.slug, item.url);
        slugs.push(record.slug);
      } catch (err) {
        if (err instanceof ValidationError || err instanceof ConflictError) {
          return json(400, { error: err.message, index });
        }
        throw err;
      }
    }
    return json(201, { created: slugs.length, slugs });
  }

  if (method === 'GET' && pathname.startsWith('/') && pathname.length > 1 && pathname !== '/links') {
    const slug = pathname.slice(1);
    try {
      const record = service.resolve(slug);
      return new Response(null, { status: 302, headers: { location: record.url } });
    } catch (err) {
      return errorResponse(err);
    }
  }

  return json(404, { error: `no route: ${method} ${pathname}` });
}

const defaultService = new ShortlinkService();

export default {
  fetch(request, env) {
    return route(request, (env && env.shortlinks) || defaultService);
  },
};
