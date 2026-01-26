/**
 * Service Worker for CT.gov Search Strategy Tool
 * Enables offline functionality and caching
 */

const CACHE_NAME = 'ctgov-search-v1';
const CACHE_VERSION = '1.0.0';

// Resources to cache immediately on install
const STATIC_CACHE = [
    'CTGov-Search-Complete.html',
    'manifest.json',
    'https://cdn.jsdelivr.net/pyodide/v0.24.1/full/pyodide.js',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css'
];

// API endpoints to cache with network-first strategy
const API_CACHE_PATTERNS = [
    /clinicaltrials\.gov\/api/,
    /corsproxy\.io/
];

// Install event - cache static resources
self.addEventListener('install', event => {
    console.log('[SW] Installing service worker...');
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                console.log('[SW] Caching static resources');
                return cache.addAll(STATIC_CACHE);
            })
            .then(() => {
                console.log('[SW] Install complete');
                return self.skipWaiting();
            })
            .catch(err => {
                console.error('[SW] Install failed:', err);
            })
    );
});

// Activate event - clean up old caches
self.addEventListener('activate', event => {
    console.log('[SW] Activating service worker...');
    event.waitUntil(
        caches.keys()
            .then(cacheNames => {
                return Promise.all(
                    cacheNames
                        .filter(name => name !== CACHE_NAME)
                        .map(name => {
                            console.log('[SW] Deleting old cache:', name);
                            return caches.delete(name);
                        })
                );
            })
            .then(() => {
                console.log('[SW] Activation complete');
                return self.clients.claim();
            })
    );
});

// Fetch event - serve from cache or network
self.addEventListener('fetch', event => {
    const url = new URL(event.request.url);

    // Skip non-GET requests
    if (event.request.method !== 'GET') {
        return;
    }

    // Check if this is an API request
    const isApiRequest = API_CACHE_PATTERNS.some(pattern => pattern.test(url.href));

    if (isApiRequest) {
        // Network-first strategy for API requests
        event.respondWith(networkFirst(event.request));
    } else {
        // Cache-first strategy for static resources
        event.respondWith(cacheFirst(event.request));
    }
});

// Cache-first strategy
async function cacheFirst(request) {
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
        // Return cached version
        return cachedResponse;
    }

    try {
        // Fetch from network
        const networkResponse = await fetch(request);

        // Cache the response if valid
        if (networkResponse.ok) {
            const cache = await caches.open(CACHE_NAME);
            cache.put(request, networkResponse.clone());
        }

        return networkResponse;
    } catch (error) {
        console.error('[SW] Fetch failed:', error);
        // Return offline fallback if available
        return caches.match('/offline.html');
    }
}

// Network-first strategy
async function networkFirst(request) {
    try {
        // Try network first
        const networkResponse = await fetch(request);

        // Cache successful responses
        if (networkResponse.ok) {
            const cache = await caches.open(CACHE_NAME);
            cache.put(request, networkResponse.clone());
        }

        return networkResponse;
    } catch (error) {
        console.log('[SW] Network failed, trying cache:', request.url);
        // Fall back to cache
        const cachedResponse = await caches.match(request);
        if (cachedResponse) {
            return cachedResponse;
        }

        // Return error response if no cache
        return new Response(JSON.stringify({
            error: 'Network unavailable and no cached data',
            offline: true
        }), {
            status: 503,
            headers: { 'Content-Type': 'application/json' }
        });
    }
}

// Handle messages from the main app
self.addEventListener('message', event => {
    if (event.data && event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }

    if (event.data && event.data.type === 'CACHE_URLS') {
        // Cache specific URLs on demand
        const urls = event.data.urls;
        caches.open(CACHE_NAME).then(cache => {
            return cache.addAll(urls);
        });
    }

    if (event.data && event.data.type === 'CLEAR_CACHE') {
        // Clear the cache
        caches.delete(CACHE_NAME).then(() => {
            console.log('[SW] Cache cleared');
        });
    }

    if (event.data && event.data.type === 'GET_VERSION') {
        event.ports[0].postMessage({ version: CACHE_VERSION });
    }
});

// Background sync for offline searches
self.addEventListener('sync', event => {
    if (event.tag === 'sync-searches') {
        event.waitUntil(syncOfflineSearches());
    }
});

async function syncOfflineSearches() {
    console.log('[SW] Syncing offline searches...');
    // This would sync any searches made while offline
    // Implementation depends on IndexedDB storage of pending searches
}

// Push notifications (if enabled)
self.addEventListener('push', event => {
    if (event.data) {
        const data = event.data.json();
        const options = {
            body: data.body || 'New update available',
            icon: 'icons/icon-192.png',
            badge: 'icons/icon-72.png',
            vibrate: [100, 50, 100],
            data: {
                url: data.url || 'CTGov-Search-Complete.html'
            }
        };

        event.waitUntil(
            self.registration.showNotification(data.title || 'CT.gov Search', options)
        );
    }
});

// Handle notification clicks
self.addEventListener('notificationclick', event => {
    event.notification.close();

    event.waitUntil(
        clients.matchAll({ type: 'window' }).then(clientList => {
            // Focus existing window if available
            for (const client of clientList) {
                if (client.url.includes('CTGov-Search') && 'focus' in client) {
                    return client.focus();
                }
            }
            // Open new window
            if (clients.openWindow) {
                return clients.openWindow(event.notification.data.url);
            }
        })
    );
});

console.log('[SW] Service worker loaded');
