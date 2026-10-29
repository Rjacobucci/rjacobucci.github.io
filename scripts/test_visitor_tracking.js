// Offline tests only: evaluate the inline integration, never load count.js.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const template = fs.readFileSync(path.join(__dirname,
  '../_includes/analytics-providers/custom.html'), 'utf8');
const expectedEvent = {
  path: '__sitewide_session', title: 'Site-wide visitor session', event: true
};

function integration({is404 = false, body = {}, visibility = 'visible',
  settings = {}, requestedPath = '/missing', filtered = false, compressed = true} = {}) {
  let rendered = template
    .replace(/{% if page\.url == '\/404\.html' %}([\s\S]*?){% endif %}/g,
      (_, content) => is404 ? content : '')
    .replace(/{% if site\.analytics\.goatcounter\.code %}|{% endif %}/g, '')
    .replace('{{ site.analytics.goatcounter.code }}', 'offline-test');
  // The production compress layout collapses whitespace inside script tags
  // too. Run all behavior tests this way by default so // comments cannot
  // silently swallow the rest of an inline script after deployment.
  if (compressed) rendered = rendered.replace(/\s+/g, ' ').trim();
  const scripts = [...rendered.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/g)];
  const tracker = scripts.find((match) => /\bsrc=/.test(match[1]));
  assert.ok(tracker, 'external tracker remains present');
  const onload = tracker[1].match(/\bonload="([^"]+)"/);
  assert.ok(onload, 'tracker invokes the helper after loading');
  const listeners = new Map();
  const calls = [];
  const accepted = [];
  const document = {
    body,
    title: 'Normal page title',
    addEventListener(name, listener) {
      if (!listeners.has(name)) listeners.set(name, new Set());
      listeners.get(name).add(listener);
    },
    removeEventListener(name, listener) {
      if (listeners.has(name)) listeners.get(name).delete(listener);
    }
  };
  if (visibility !== null) document.visibilityState = visibility;
  const window = {goatcounter: settings, location: {
    pathname: requestedPath, search: '?private=value', hash: '#private'
  }};
  const context = vm.createContext({window, document});
  scripts.filter((match) => !/\bsrc=/.test(match[1]))
    .forEach((match) => vm.runInContext(match[2], context));

  return {
    window, document, calls, accepted, listeners, tracker: tracker[1],
    loadTracker() {
      // The mock preserves count(vars)'s explicit-over-default behavior and
      // can reject requests as GoatCounter's normal filter does. No network.
      window.goatcounter.count = (vars) => {
        calls.push(vars === undefined ? undefined : JSON.parse(JSON.stringify(vars)));
        if (filtered) return;
        vars = vars || {};
        const data = {
          path: vars.path === undefined ? window.goatcounter.path : vars.path,
          title: vars.title === undefined ? window.goatcounter.title : vars.title,
          event: !!(vars.event || window.goatcounter.event)
        };
        if (typeof data.path === 'function') data.path = data.path('/canonical');
        accepted.push(data);
      };
      vm.runInContext(onload[1], context);
    },
    dispatch(name) {
      for (const listener of [...(listeners.get(name) || [])]) listener();
    }
  };
}

for (const compressed of [true, false]) {
  for (const is404 of [false, true]) {
    test(`${compressed ? 'production-compressed' : 'uncompressed'} ${is404 ? '404' : 'normal'} tracking`, () => {
      const site = integration({compressed, is404, requestedPath: '/old-page',
        settings: {path: '/normal-page', title: 'Normal page'}});
      site.loadTracker();
      assert.deepEqual(site.calls, [expectedEvent]);
      assert.equal(typeof site.window.countSitewideSession, 'function');
      site.window.goatcounter.count();
      assert.deepEqual(site.accepted[1], is404 ? {
        path: '404: /old-page', title: 'Page not found', event: true
      } : {
        path: '/normal-page', title: 'Normal page', event: false
      });
    });
  }
}

test('visible page records one shared event without changing normal settings', () => {
  const originalPath = (value) => value;
  const settings = {path: originalPath, title: 'Existing title', referrer: 'Existing source'};
  const site = integration({settings});
  site.loadTracker();
  assert.deepEqual(site.calls, [expectedEvent]);
  assert.equal(site.window.goatcounter, settings);
  assert.equal(settings.path, originalPath);
  assert.equal(settings.title, 'Existing title');
  assert.equal(settings.referrer, 'Existing source');
  assert.equal(settings.event, undefined);
  assert.equal(settings.no_onload, undefined);
  assert.equal(settings.no_session, undefined);
  assert.equal(settings.allow_local, undefined);
  assert.match(site.tracker, /\basync\b/);
  // Automatic normal tracking remains the library's responsibility.
  settings.count();
  assert.deepEqual(site.accepted[1], {
    path: '/canonical', title: 'Existing title', event: false
  });
  site.window.countSitewideSession();
  site.dispatch('DOMContentLoaded');
  site.dispatch('visibilitychange');
  assert.equal(site.calls.length, 2, 'helper does not add duplicate calls');
});

test('waits for a body before recording the event', () => {
  const site = integration({body: null});
  site.loadTracker();
  site.window.countSitewideSession();
  assert.deepEqual(site.calls, []);
  assert.equal(site.listeners.get('DOMContentLoaded').size, 1);
  site.document.body = {};
  site.dispatch('DOMContentLoaded');
  assert.deepEqual(site.calls, [expectedEvent]);
  assert.equal(site.listeners.get('DOMContentLoaded').size, 0);
});

test('hidden and prerendered pages wait until first visibility', () => {
  for (const visibility of ['hidden', 'prerender']) {
    const site = integration({visibility});
    site.loadTracker();
    site.dispatch('visibilitychange');
    assert.deepEqual(site.calls, []);
    site.document.visibilityState = 'visible';
    site.dispatch('visibilitychange');
    site.document.visibilityState = 'hidden';
    site.dispatch('visibilitychange');
    site.document.visibilityState = 'visible';
    site.dispatch('visibilitychange');
    assert.deepEqual(site.calls, [expectedEvent]);
    assert.equal(site.listeners.get('visibilitychange').size, 0);
  }
});

for (const order of ['body-first', 'visibility-first']) {
  test(`body and visibility ordering: ${order}`, () => {
    const site = integration({body: null, visibility: 'hidden'});
    site.loadTracker();
    if (order === 'body-first') {
      site.document.body = {};
      site.dispatch('DOMContentLoaded');
      assert.deepEqual(site.calls, []);
      site.document.visibilityState = 'visible';
      site.dispatch('visibilitychange');
    } else {
      site.document.visibilityState = 'visible';
      site.dispatch('visibilitychange');
      assert.deepEqual(site.calls, []);
      site.document.body = {};
      site.dispatch('DOMContentLoaded');
    }
    assert.deepEqual(site.calls, [expectedEvent]);
  });
}

test('404 details remain intact while explicit shared event overrides them', () => {
  const site = integration({is404: true, requestedPath: '/old-page'});
  const settings = site.window.goatcounter;
  const originalPath = settings.path;
  assert.equal(originalPath(), '404: /old-page');
  assert.equal(settings.title, 'Page not found');
  assert.equal(settings.event, true);
  site.loadTracker();
  assert.deepEqual(site.accepted, [expectedEvent]);
  assert.equal(settings.path, originalPath);
  assert.equal(settings.title, 'Page not found');
  settings.count();
  assert.deepEqual(site.accepted[1], {
    path: '404: /old-page', title: 'Page not found', event: true
  });
});

test('works without the visibility API and tolerates an early helper call', () => {
  const site = integration({visibility: null});
  site.window.countSitewideSession();
  assert.deepEqual(site.calls, []);
  site.loadTracker();
  assert.deepEqual(site.calls, [expectedEvent]);
});

test('uses the standard count method without bypassing its filtering', () => {
  const site = integration({filtered: true});
  site.loadTracker();
  assert.deepEqual(site.calls, [expectedEvent]);
  assert.deepEqual(site.accepted, []);
  assert.equal(Object.hasOwn(site.calls[0], 'no_session'), false);
});

test('shared event name matches the Python report constant', () => {
  const report = fs.readFileSync(path.join(__dirname, 'daily_traffic_email.py'), 'utf8');
  const match = report.match(/^SITEWIDE_SESSION_EVENT\s*=\s*['"]([^'"]+)['"]/m);
  assert.ok(match, 'Python report defines SITEWIDE_SESSION_EVENT');
  assert.equal(match[1], expectedEvent.path);
});
