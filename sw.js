// Minimal service worker — only needed to show notifications on mobile Chrome.
self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil(clients.openWindow(self.location.origin));
});
