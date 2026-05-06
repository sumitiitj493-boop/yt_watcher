// Basic content script to hide ad elements
const adSelectors = [
    'ytd-ad-slot-renderer',
    'yt-page-ad-renderer',
    'ytd-player-legacy-desktop-watch-ads-renderer',
    '.ytp-ad-module',
    '.ytp-ad-overlay-container'
];

const hideAds = () => {
    adSelectors.forEach(selector => {
        const elements = document.querySelectorAll(selector);
        elements.forEach(el => el.style.display = 'none');
    });
};

setInterval(hideAds, 1000);
