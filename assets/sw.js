const CACHE_NAME = "acfdd-cache-v1";

const urlsToCache = [
    "/",
    "/manifest.json",
    "/offline.html",
];

self.addEventListener("install", (event) => {

    event.waitUntil(

        caches.open(CACHE_NAME)

            .then((cache) => {
                return cache.addAll(urlsToCache);
            })
    );
});

self.addEventListener("fetch", (event) => {

    // Ignore Reflex websocket/event calls
    if (
        event.request.url.includes("_event")
    ) {
        return;
    }

    event.respondWith(

        fetch(event.request)

            .catch(() => {

                return caches.match(
                    event.request
                );
            })
    );
});