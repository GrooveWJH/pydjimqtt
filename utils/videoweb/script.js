document.addEventListener('DOMContentLoaded', () => {
    // Video source configurations for different modes
    const VIDEO_CONFIGS = {
        outdoor: [
            { name: 'Drone001', url: 'http://81.70.222.38:8888/live/Drone001/index.m3u8' },
            { name: 'Drone002', url: 'http://81.70.222.38:8888/live/Drone002/index.m3u8' },
            { name: 'Drone003', url: 'http://81.70.222.38:8888/live/Drone003/index.m3u8' }
        ],
        indoor: [
            { name: 'Drone001', url: 'http://81.70.222.38:8888/live/Drone001/index.m3u8' },
            { name: 'Indoor', url: 'http://81.70.222.38:8888/live/indoor/index.m3u8' }
        ]
    };

    const videoContainer = document.getElementById('video-container');
    const modeToggleBtn = document.getElementById('mode-toggle-btn');
    const modeIcon = modeToggleBtn.querySelector('.mode-icon');
    const modeText = modeToggleBtn.querySelector('.mode-text');

    let currentMode = 'outdoor';
    let hlsInstances = []; // Track all HLS instances for cleanup
    let osdIntervals = []; // Track all OSD intervals for cleanup

    // Centralized function to handle OSD updates
    const startOsdUpdates = (wrapper, videoElement, hlsInstance) => {
        const osd = wrapper.querySelector('.osd');
        let lastDecodedFrames;

        const intervalId = setInterval(() => {
            if (videoElement.readyState < 2) {
                osd.innerHTML = "Status: Buffering...";
                return;
            }

            // Resolution
            let resText;
            if (videoElement.videoWidth > 0) {
                resText = `Res: ${videoElement.videoWidth}x${videoElement.videoHeight}`;
            } else {
                resText = "Res: Detecting...";
            }

            // FPS using the standard getVideoPlaybackQuality() API
            let fpsText;
            if (typeof videoElement.getVideoPlaybackQuality === 'function') {
                const quality = videoElement.getVideoPlaybackQuality();
                const currentDecodedFrames = quality.totalVideoFrames;

                if (typeof lastDecodedFrames === 'undefined') {
                    lastDecodedFrames = currentDecodedFrames;
                    fpsText = "FPS: Calculating...";
                } else {
                    const fps = currentDecodedFrames - lastDecodedFrames;
                    lastDecodedFrames = currentDecodedFrames;
                    fpsText = `FPS: ${fps}`;
                }
            } else {
                // Fallback for older browsers
                fpsText = "FPS: N/A";
            }

            osd.innerHTML = `${resText}<br>${fpsText}`;
        }, 1000);

        osdIntervals.push(intervalId);
        return intervalId;
    };

    const createHlsPlayer = (wrapper, videoElement, source) => {
        const statusIndicator = wrapper.querySelector('.status-indicator');
        const statusText = wrapper.querySelector('.status-text');
        const videoPath = wrapper.querySelector('.video-path');

        videoPath.textContent = source.url;

        const setStatus = (status, message) => {
            statusIndicator.className = `status-indicator ${status}`;
            statusText.textContent = message;
            if (status === 'online') {
                wrapper.classList.add('has-stream');
            } else {
                wrapper.classList.remove('has-stream');
                wrapper.querySelector('.osd').innerHTML = '';
            }
        };

        if (Hls.isSupported()) {
            const hls = new Hls({
                backBufferLength: 90,
                liveSyncDurationCount: 3,
                liveMaxLatencyDurationCount: 5,
            });

            hlsInstances.push(hls); // Track for cleanup

            hls.loadSource(source.url);
            hls.attachMedia(videoElement);

            videoElement.addEventListener('playing', () => {
                setStatus('online', 'Online');
                startOsdUpdates(wrapper, videoElement, hls);
            });

            hls.on(Hls.Events.MANIFEST_PARSED, function() {
                videoElement.play().catch(e => console.warn("Autoplay was prevented:", e));
            });

            let errorTimeout;
            hls.on(Hls.Events.ERROR, function (event, data) {
                if (data.fatal) {
                    console.error(`Fatal HLS error for ${source.url}:`, data.details);
                    setStatus('offline', 'Offline');

                    // Only retry if we're still in the same mode
                    clearTimeout(errorTimeout);
                    errorTimeout = setTimeout(() => {
                        if (hlsInstances.includes(hls)) {
                            hls.destroy();
                            const index = hlsInstances.indexOf(hls);
                            if (index > -1) hlsInstances.splice(index, 1);
                            createHlsPlayer(wrapper, videoElement, source);
                        }
                    }, 2000);
                }
            });

        } else if (videoElement.canPlayType('application/vnd.apple.mpegurl')) {
            videoElement.src = source.url;
            videoElement.addEventListener('playing', function() {
                setStatus('online', 'Online (Native)');
                startOsdUpdates(wrapper, videoElement, null);
            });
             videoElement.addEventListener('error', function() {
                setStatus('offline', 'Offline');
             });
             videoElement.play().catch(e => console.warn("Autoplay was prevented:", e));
        } else {
            console.error('HLS is not supported in this browser.');
            setStatus('offline', 'Unsupported');
        }
    };

    const createVideoWrapper = (source, index) => {
        const wrapper = document.createElement('div');
        wrapper.className = 'video-wrapper';
        wrapper.id = `video-wrapper-${index + 1}`;

        wrapper.innerHTML = `
            <div class="header">
                <span class="source-name">${source.name}</span>
                <div class="status">
                    <span class="status-indicator"></span>
                    <span class="status-text"></span>
                </div>
                <button class="zoom-btn" data-target="${index + 1}">Zoom</button>
            </div>
            <video id="video-${index + 1}" muted autoplay></video>
            <div class="osd"></div>
            <div class="video-path"></div>
        `;

        return wrapper;
    };

    const cleanupResources = () => {
        // Destroy all HLS instances
        hlsInstances.forEach(hls => {
            try {
                hls.destroy();
            } catch (e) {
                console.warn('Error destroying HLS instance:', e);
            }
        });
        hlsInstances = [];

        // Clear all OSD intervals
        osdIntervals.forEach(intervalId => clearInterval(intervalId));
        osdIntervals = [];

        // Remove all video wrappers
        videoContainer.innerHTML = '';
    };

    const initializeMode = (mode) => {
        // Cleanup existing resources
        cleanupResources();

        // Remove old mode class and add new one
        videoContainer.classList.remove('outdoor-mode', 'indoor-mode');
        videoContainer.classList.add(`${mode}-mode`);

        // Get sources for current mode
        const sources = VIDEO_CONFIGS[mode];

        // Create and initialize video wrappers
        sources.forEach((source, index) => {
            const wrapper = createVideoWrapper(source, index);
            videoContainer.appendChild(wrapper);

            const videoElement = wrapper.querySelector('video');
            createHlsPlayer(wrapper, videoElement, source);
        });

        // Update button
        if (mode === 'outdoor') {
            modeIcon.textContent = '🏠';
            modeText.textContent = '室内模式';
        } else {
            modeIcon.textContent = '🌄';
            modeText.textContent = '室外模式';
        }
    };

    // Mode toggle handler
    modeToggleBtn.addEventListener('click', () => {
        currentMode = currentMode === 'outdoor' ? 'indoor' : 'outdoor';
        initializeMode(currentMode);
        console.log(`Switched to ${currentMode} mode`);
    });

    // Zoom functionality
    videoContainer.addEventListener('click', (e) => {
        if (e.target.classList.contains('zoom-btn')) {
            const btn = e.target;
            const targetId = btn.dataset.target;
            const wrapper = document.getElementById(`video-wrapper-${targetId}`);

            if (wrapper.classList.contains('zoomed')) {
                wrapper.classList.remove('zoomed');
                videoContainer.classList.remove('zoomed-in');
                btn.textContent = 'Zoom';
                btn.classList.remove('shrink-btn');
            } else {
                const currentlyZoomed = document.querySelector('.video-wrapper.zoomed');
                if (currentlyZoomed) {
                    currentlyZoomed.classList.remove('zoomed');
                    const oldZoomBtn = currentlyZoomed.querySelector('.zoom-btn');
                    if(oldZoomBtn) {
                        oldZoomBtn.textContent = 'Zoom';
                        oldZoomBtn.classList.remove('shrink-btn');
                    }
                }

                wrapper.classList.add('zoomed');
                videoContainer.classList.add('zoomed-in');
                btn.textContent = 'Shrink';
                btn.classList.add('shrink-btn');
            }
        }
    });

    // Initialize with outdoor mode
    initializeMode('outdoor');

    // Cleanup on page unload
    window.addEventListener('beforeunload', () => {
        cleanupResources();
    });
});
