// AirGap Transcribe Frontend Logic
document.addEventListener('DOMContentLoaded', () => {
    // State Variables
    let selectedFile = null;
    let activeJobId = null;
    let pollingInterval = null;
    let allJobs = [];

    // Session ID Initialization for Anonymous Browser Privacy
    let appSessionId = localStorage.getItem('meeting_transcribe_session_id');
    if (!appSessionId) {
        appSessionId = 'sess_' + (crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2) + Date.now().toString(36));
        localStorage.setItem('meeting_transcribe_session_id', appSessionId);
    }

    function fetchWithSession(url, options = {}) {
        options.headers = options.headers || {};
        if (options.headers instanceof Headers) {
            options.headers.set('X-Session-ID', appSessionId);
        } else {
            options.headers['X-Session-ID'] = appSessionId;
        }
        return fetch(url, options);
    }

    // DOM Elements
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const selectedFileInfo = document.getElementById('selected-file-info');
    const fileNameEl = document.getElementById('file-name');
    const fileSizeEl = document.getElementById('file-size');
    const fileTypeIcon = document.getElementById('file-type-icon');
    const removeFileBtn = document.getElementById('remove-file-btn');

    const modelSelect = document.getElementById('model-select');
    const diarizationToggle = document.getElementById('diarization-toggle');
    const startTranscribeBtn = document.getElementById('start-transcribe-btn');

    const noActiveJob = document.getElementById('no-active-job');
    const activeJobContainer = document.getElementById('active-job-container');
    const activeFilename = document.getElementById('active-filename');
    const activeStatusBadge = document.getElementById('active-status-badge');
    const activeStageDesc = document.getElementById('active-stage-desc');
    const activeProgressPct = document.getElementById('active-progress-pct');
    const activeProgressFill = document.getElementById('active-progress-fill');

    const stepUpload = document.getElementById('step-upload');
    const stepConvert = document.getElementById('step-convert');
    const stepTranscribe = document.getElementById('step-transcribe');
    const stepExport = document.getElementById('step-export');

    const liveTranscriptText = document.getElementById('live-transcript-text');
    const segmentCountEl = document.getElementById('segment-count');
    const activeDownloadsBar = document.getElementById('active-downloads-bar');

    const dlDocxBtn = document.getElementById('dl-docx-btn');
    const dlPdfBtn = document.getElementById('dl-pdf-btn');
    const dlTxtBtn = document.getElementById('dl-txt-btn');
    const dlSrtBtn = document.getElementById('dl-srt-btn');

    const historyListContainer = document.getElementById('history-list-container');
    const historySearch = document.getElementById('history-search');
    const refreshHistoryBtn = document.getElementById('refresh-history-btn');
    const historyCountPill = document.getElementById('history-count-pill');
    const authStatusBadge = document.getElementById('auth-status-badge');

    const transcriptModal = document.getElementById('transcript-modal');
    const modalFilename = document.getElementById('modal-filename');
    const modalMeta = document.getElementById('modal-meta');
    const modalBodyText = document.getElementById('modal-body-text');
    const closeModalBtn = document.getElementById('close-modal-btn');
    const modalDlDocx = document.getElementById('modal-dl-docx');
    const modalDlPdf = document.getElementById('modal-dl-pdf');
    const modalDlTxt = document.getElementById('modal-dl-txt');

    // 1. Check Auth Status
    fetch('/api/auth-status')
        .then(res => res.json())
        .then(data => {
            if (data.keycloak_enabled) {
                authStatusBadge.innerHTML = `<i class="fa-solid fa-user-check"></i> Keycloak (${data.user.preferred_username || 'User'})`;
                authStatusBadge.style.background = 'rgba(99, 102, 241, 0.2)';
                authStatusBadge.style.color = '#a5b4fc';
            } else {
                authStatusBadge.innerHTML = `<i class="fa-solid fa-unlock"></i> Auth Mode: Off (Local)`;
            }
        })
        .catch(() => {});

    // 2. Tab Navigation
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTab = btn.getAttribute('data-tab');
            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));

            btn.classList.add('active');
            document.getElementById(targetTab).classList.add('active');

            if (targetTab === 'history-tab') {
                loadHistory();
            }
        });
    });

    // 3. File Selection & Drag-and-Drop
    dropZone.addEventListener('click', () => fileInput.click());

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('drag-over');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('drag-over');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('drag-over');
        if (e.dataTransfer.files.length > 0) {
            handleFileSelect(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileSelect(e.target.files[0]);
        }
    });

    removeFileBtn.addEventListener('click', () => {
        selectedFile = null;
        fileInput.value = '';
        selectedFileInfo.classList.add('hidden');
        dropZone.classList.remove('hidden');
        startTranscribeBtn.disabled = true;
    });

    function handleFileSelect(file) {
        selectedFile = file;
        fileNameEl.textContent = file.name;
        fileSizeEl.textContent = formatBytes(file.size);

        if (file.type.startsWith('video/') || file.name.match(/\.(mp4|mkv|avi|mov|webm)$/i)) {
            fileTypeIcon.className = 'fa-solid fa-file-video file-icon';
        } else {
            fileTypeIcon.className = 'fa-solid fa-file-audio file-icon';
        }

        selectedFileInfo.classList.remove('hidden');
        dropZone.classList.add('hidden');
        startTranscribeBtn.disabled = false;
    }

    // 4. Submit Job to API
    startTranscribeBtn.addEventListener('click', async () => {
        if (!selectedFile) return;

        startTranscribeBtn.disabled = true;
        startTranscribeBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Uploading Media...`;

        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('model_size', modelSelect.value);
        formData.append('language', 'en');
        const dToggle = document.getElementById('diarization-toggle');
        formData.append('enable_diarization', dToggle && dToggle.checked ? 'true' : 'false');

        try {
            const res = await fetch('/api/transcribe', {
                method: 'POST',
                body: formData
            });

            if (!res.ok) {
                const err = await res.json();
                alert(`Upload failed: ${err.detail || 'Server error'}`);
                startTranscribeBtn.disabled = false;
                startTranscribeBtn.innerHTML = `<i class="fa-solid fa-bolt"></i> Start Local Transcription`;
                return;
            }

            const job = await res.json();
            
            // Reset upload form
            removeFileBtn.click();
            startTranscribeBtn.innerHTML = `<i class="fa-solid fa-bolt"></i> Start Local Transcription`;

            // Display active job & start polling
            noActiveJob.classList.add('hidden');
            activeJobContainer.classList.remove('hidden');
            startGlobalJobPolling();

        } catch (e) {
            alert(`Network error during upload: ${e.message}`);
            startTranscribeBtn.disabled = false;
            startTranscribeBtn.innerHTML = `<i class="fa-solid fa-bolt"></i> Start Local Transcription`;
        }
    });

    // Expandable Queue Drawer Toggle Listener
    const queueDrawer = document.getElementById('queue-drawer');
    const queueToggleBtn = document.getElementById('queue-toggle-btn');
    const queueCount = document.getElementById('queue-count');
    const queueChevron = document.getElementById('queue-chevron');
    const queueListContainer = document.getElementById('queue-list-container');

    if (queueToggleBtn) {
        queueToggleBtn.addEventListener('click', () => {
            queueListContainer.classList.toggle('hidden');
            queueChevron.className = queueListContainer.classList.contains('hidden') 
                ? 'fa-solid fa-chevron-down' 
                : 'fa-solid fa-chevron-up';
        });
    }

    // 5. Global Polling Loop: Prioritizes Active Processing File and Updates Queue Drawer
    function startGlobalJobPolling() {
        if (pollingInterval) clearInterval(pollingInterval);

        const pollFunc = async () => {
            try {
                const res = await fetch('/api/jobs');
                if (!res.ok) return;

                const jobs = await res.json();
                allJobs = jobs;

                const processingJob = jobs.find(j => j.status === 'CONVERTING' || j.status === 'TRANSCRIBING');
                const queuedJobs = jobs.filter(j => j.status === 'QUEUED');

                // Render Queue Drawer
                if (queuedJobs.length > 0) {
                    queueDrawer.classList.remove('hidden');
                    queueCount.textContent = queuedJobs.length;
                    
                    queueListContainer.innerHTML = queuedJobs.map((qj, idx) => `
                        <div class="queue-item">
                            <span class="queue-item-name"><i class="fa-solid fa-file-audio"></i> ${qj.original_filename}</span>
                            <div class="queue-item-meta">
                                <span>${formatBytes(qj.file_size)}</span>
                                <span class="badge-mini">Position ${qj.queue_position || (idx + 1)}</span>
                            </div>
                        </div>
                    `).join('');
                } else {
                    queueDrawer.classList.add('hidden');
                }

                // Determine active job to display in main monitor card
                let targetJob = null;
                if (processingJob) {
                    targetJob = processingJob;
                    activeJobId = processingJob.id;
                } else if (queuedJobs.length > 0) {
                    targetJob = queuedJobs[0];
                    activeJobId = queuedJobs[0].id;
                } else if (activeJobId) {
                    targetJob = jobs.find(j => j.id === activeJobId);
                }

                if (targetJob) {
                    noActiveJob.classList.add('hidden');
                    activeJobContainer.classList.remove('hidden');
                    updateActiveJobUI(targetJob);
                } else {
                    noActiveJob.classList.remove('hidden');
                    activeJobContainer.classList.add('hidden');
                }

            } catch (e) {
                console.error("Polling error:", e);
            }
        };

        pollFunc(); // immediate call
        pollingInterval = setInterval(pollFunc, 1500);
    }

    // Start global polling on initial app load
    startGlobalJobPolling();

    const activeTimestampsToggle = document.getElementById('active-timestamps-toggle');
    const historyTimestampsToggle = document.getElementById('history-timestamps-toggle');

    if (activeTimestampsToggle) {
        activeTimestampsToggle.addEventListener('change', () => {
            if (activeJobId) {
                const tsParam = activeTimestampsToggle.checked ? '?timestamps=true' : '?timestamps=false';
                dlDocxBtn.href = `/api/jobs/${activeJobId}/download/docx${tsParam}`;
                dlPdfBtn.href = `/api/jobs/${activeJobId}/download/pdf${tsParam}`;
                dlTxtBtn.href = `/api/jobs/${activeJobId}/download/txt${tsParam}`;
            }
        });
    }

    if (historyTimestampsToggle) {
        historyTimestampsToggle.addEventListener('change', () => {
            renderHistoryItems(allJobs);
        });
    }

    function updateActiveJobUI(job) {
        activeFilename.textContent = job.original_filename;
        activeStageDesc.textContent = job.current_stage;
        activeProgressPct.textContent = `${job.progress}%`;
        activeProgressFill.style.width = `${job.progress}%`;

        // Update Status Badge
        activeStatusBadge.className = `status-pill status-${job.status.toLowerCase()}`;
        if (job.status === 'COMPLETED') {
            activeStatusBadge.innerHTML = `<i class="fa-solid fa-circle-check"></i> COMPLETED`;
        } else if (job.status === 'FAILED') {
            activeStatusBadge.innerHTML = `<i class="fa-solid fa-circle-exclamation"></i> FAILED`;
        } else if (job.status === 'QUEUED') {
            const posStr = job.queue_position ? ` (Line Position ${job.queue_position})` : '';
            activeStatusBadge.innerHTML = `<i class="fa-regular fa-clock"></i> QUEUED${posStr}`;
        } else {
            activeStatusBadge.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> ${job.status}`;
        }

        // Update Step Checklist
        stepUpload.className = 'step-item step-done';
        stepConvert.className = job.progress >= 15 ? 'step-item step-done' : 'step-item step-active';
        stepTranscribe.className = job.progress >= 90 ? 'step-item step-done' : (job.progress >= 15 ? 'step-item step-active' : 'step-item');
        stepExport.className = job.status === 'COMPLETED' ? 'step-item step-done' : (job.progress >= 90 ? 'step-item step-active' : 'step-item');

        // Update Live Transcript Stream
        if (job.segments && job.segments.length > 0) {
            segmentCountEl.textContent = `${job.segments.length} Segments`;
            liveTranscriptText.innerHTML = job.segments.map(s => {
                const showSpeaker = Boolean(s.speaker);
                const spkHtml = showSpeaker ? `<span class="speaker-tag ${s.speaker.toLowerCase().replace(/\s+/g, '-')}">${escapeHtml(s.speaker)}</span>` : '';
                return `
                <div class="segment-line">
                    ${spkHtml}
                    <span class="timestamp">[${formatTime(s.start)} - ${formatTime(s.end)}]</span>
                    <span>${escapeHtml(s.text)}</span>
                </div>
            `;
            }).join('');
            liveTranscriptText.scrollTop = liveTranscriptText.scrollHeight;
        } else if (job.status === 'TRANSCRIBING') {
            liveTranscriptText.innerHTML = `<em>Transcribing speech segments...</em>`;
        } else if (job.status === 'FAILED') {
            liveTranscriptText.innerHTML = `<em style="color: var(--accent-rose);">Error: ${escapeHtml(job.error_message || 'Transcription failed.')}</em>`;
        }

        // Show download buttons if complete
        if (job.status === 'COMPLETED') {
            const tsParam = activeTimestampsToggle && activeTimestampsToggle.checked ? '?timestamps=true' : '?timestamps=false';
            activeDownloadsBar.classList.remove('hidden');
            dlDocxBtn.href = `/api/jobs/${job.id}/download/docx${tsParam}`;
            dlPdfBtn.href = `/api/jobs/${job.id}/download/pdf${tsParam}`;
            dlTxtBtn.href = `/api/jobs/${job.id}/download/txt${tsParam}`;
            dlSrtBtn.href = `/api/jobs/${job.id}/download/srt`;
        } else {
            activeDownloadsBar.classList.add('hidden');
        }
    }

    // 6. Load History List
    async function loadHistory() {
        try {
            const res = await fetchWithSession('/api/jobs');
            if (!res.ok) return;
            allJobs = await res.json();
            historyCountPill.textContent = allJobs.length;
            renderHistoryItems(allJobs);
        } catch (e) {
            console.error("Failed to load history:", e);
        }
    }

    function renderHistoryItems(jobs) {
        const query = historySearch.value.toLowerCase().trim();
        const filtered = jobs.filter(j => 
            j.original_filename.toLowerCase().includes(query) ||
            (j.full_text && j.full_text.toLowerCase().includes(query))
        );

        if (filtered.length === 0) {
            historyListContainer.innerHTML = `
                <div class="empty-state">
                    <i class="fa-solid fa-folder-open"></i>
                    <p>${query ? 'No matching transcripts found.' : 'No past transcriptions found.'}</p>
                </div>`;
            return;
        }

        const tsParam = historyTimestampsToggle && historyTimestampsToggle.checked ? '?timestamps=true' : '?timestamps=false';

        historyListContainer.innerHTML = filtered.map(j => `
            <div class="history-item-card">
                <div class="history-meta-group">
                    <i class="fa-solid ${j.original_filename.match(/\.(mp4|mkv|mov)$/i) ? 'fa-file-video' : 'fa-file-audio'} history-icon"></i>
                    <div class="history-title-block">
                        <div class="title-row" id="title-container-${j.id}" style="display: flex; align-items: center; gap: 8px;">
                            <span class="title" onclick="openTranscriptModal('${j.id}')">${escapeHtml(j.original_filename)}</span>
                            <button class="btn-icon btn-rename-title" title="Rename Title" onclick="startRenameJob(event, '${j.id}')">
                                <i class="fa-solid fa-pen-to-square"></i>
                            </button>
                        </div>
                        <div class="history-submeta">
                            <span><i class="fa-regular fa-clock"></i> ${formatTime(j.duration_seconds)}</span>
                            <span><i class="fa-solid fa-brain"></i> Whisper ${j.model_size}</span>
                            ${j.enable_diarization ? `<span style="color: #fbbf24;"><i class="fa-solid fa-users"></i> Diarized</span>` : ''}
                            <span><i class="fa-regular fa-calendar"></i> ${formatDate(j.created_at)}</span>
                        </div>
                    </div>
                </div>

                <div class="history-actions" style="display: flex; gap: 8px; align-items: center;">
                    <span class="status-pill status-${j.status.toLowerCase()}">${j.status}</span>

                    ${j.status === 'COMPLETED' ? `
                        <a href="/api/jobs/${j.id}/download/docx${tsParam}" class="btn btn-export btn-docx" title="Download Word Doc">
                            <i class="fa-solid fa-file-word"></i> DOCX
                        </a>
                        <a href="/api/jobs/${j.id}/download/pdf${tsParam}" class="btn btn-export btn-pdf" title="Download PDF Document">
                            <i class="fa-solid fa-file-pdf"></i> PDF
                        </a>
                        <button class="btn btn-secondary" style="padding: 6px 12px; font-size: 12px;" onclick="openTranscriptModal('${j.id}')">
                            <i class="fa-solid fa-eye"></i> View
                        </button>
                    ` : ''}

                    <button class="btn-icon btn-delete-item" title="Delete Job" onclick="confirmDeleteJob(this, '${j.id}')">
                        <i class="fa-solid fa-trash-can"></i>
                    </button>
                </div>
            </div>
        `).join('');
    }

    historySearch.addEventListener('input', () => renderHistoryItems(allJobs));
    refreshHistoryBtn.addEventListener('click', loadHistory);

    // Title Rename Handlers
    window.startRenameJob = function(event, jobId) {
        if (event) event.stopPropagation();
        const container = document.getElementById(`title-container-${jobId}`);
        if (!container) return;

        const job = allJobs.find(j => j.id === jobId);
        if (!job) return;

        container.innerHTML = `
            <input type="text" id="rename-input-${jobId}" class="rename-title-input" value="${escapeHtml(job.original_filename)}" onkeydown="if(event.key==='Enter') saveRenameJob('${jobId}')" style="background: var(--bg-tertiary); border: 1px solid var(--accent-indigo); color: var(--text-primary); padding: 4px 8px; border-radius: 4px; font-size: 14px; width: 260px;">
            <button class="btn btn-secondary" style="padding: 4px 8px; font-size: 12px;" onclick="saveRenameJob('${jobId}')" title="Save Title">
                <i class="fa-solid fa-check" style="color: var(--accent-emerald);"></i>
            </button>
            <button class="btn-icon" style="padding: 4px 8px; font-size: 12px;" onclick="loadHistory()" title="Cancel">
                <i class="fa-solid fa-xmark"></i>
            </button>
        `;

        const inputEl = document.getElementById(`rename-input-${jobId}`);
        if (inputEl) {
            inputEl.focus();
            inputEl.select();
        }
    };

    window.saveRenameJob = async function(jobId) {
        const inputEl = document.getElementById(`rename-input-${jobId}`);
        if (!inputEl) return;

        const newTitle = inputEl.value.trim();
        if (!newTitle) return;

        try {
            const res = await fetch(`/api/jobs/${jobId}/rename`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title: newTitle })
            });

            if (res.ok) {
                const updatedJob = await res.json();
                const jobIndex = allJobs.findIndex(j => j.id === jobId);
                if (jobIndex !== -1) {
                    allJobs[jobIndex].original_filename = updatedJob.original_filename;
                }
                renderHistoryItems(allJobs);
            } else {
                const err = await res.json();
                alert(`Failed to rename title: ${err.detail || 'Server error'}`);
            }
        } catch (e) {
            alert(`Error renaming title: ${e.message}`);
        }
    };

    // 7. Global Actions: Modal & Delete
    window.openTranscriptModal = function(jobId) {
        const job = allJobs.find(j => j.id === jobId);
        if (!job) return;

        modalFilename.textContent = job.original_filename;
        modalMeta.textContent = `Duration: ${formatTime(job.duration_seconds)} | Model: Whisper ${job.model_size}${job.enable_diarization ? ' | Diarization: Enabled' : ''}`;

        modalDlDocx.href = `/api/jobs/${job.id}/download/docx`;
        modalDlPdf.href = `/api/jobs/${job.id}/download/pdf`;
        modalDlTxt.href = `/api/jobs/${job.id}/download/txt`;

        if (job.segments && job.segments.length > 0) {
            modalBodyText.innerHTML = job.segments.map(s => {
                const showSpeaker = Boolean(s.speaker);
                const spkHtml = showSpeaker ? `<span class="speaker-tag ${s.speaker.toLowerCase().replace(/\s+/g, '-')}">${escapeHtml(s.speaker)}</span>` : '';
                return `
                <p style="margin-bottom: 10px;">
                    ${spkHtml}
                    <strong style="color: var(--accent-indigo);">[${formatTime(s.start)} - ${formatTime(s.end)}]</strong>
                    ${escapeHtml(s.text)}
                </p>
            `;
            }).join('');
        } else {
            modalBodyText.innerHTML = `<p>${escapeHtml(job.full_text || 'No transcript segments available.')}</p>`;
        }

        transcriptModal.classList.remove('hidden');
    };

    closeModalBtn.addEventListener('click', () => transcriptModal.classList.add('hidden'));
    transcriptModal.addEventListener('click', (e) => {
        if (e.target === transcriptModal) transcriptModal.classList.add('hidden');
    });

    // 8. Robust In-Line Delete Confirmation
    window.confirmDeleteJob = function(btnElement, jobId) {
        if (btnElement.getAttribute('data-confirming') === 'true') {
            executeDelete(jobId, btnElement);
        } else {
            btnElement.setAttribute('data-confirming', 'true');
            btnElement.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> Confirm Delete?`;
            btnElement.style.background = 'rgba(244, 63, 94, 0.25)';
            btnElement.style.color = '#fda4af';
            btnElement.style.border = '1px solid rgba(244, 63, 94, 0.5)';
            btnElement.style.borderRadius = '6px';
            btnElement.style.padding = '4px 10px';
            btnElement.style.fontSize = '12px';

            setTimeout(() => {
                if (btnElement && btnElement.getAttribute('data-confirming') === 'true') {
                    btnElement.removeAttribute('data-confirming');
                    btnElement.innerHTML = `<i class="fa-solid fa-trash-can"></i>`;
                    btnElement.style.background = 'transparent';
                    btnElement.style.color = 'var(--text-muted)';
                    btnElement.style.border = 'none';
                    btnElement.style.padding = '4px 8px';
                }
            }, 4000);
        }
    };

    async function executeDelete(jobId, btnElement) {
        if (btnElement) {
            btnElement.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Deleting...`;
        }
        try {
            const res = await fetchWithSession(`/api/jobs/${jobId}`, { method: 'DELETE' });
            if (res.ok) {
                if (activeJobId === jobId) {
                    activeJobId = null;
                    if (pollingInterval) {
                        clearInterval(pollingInterval);
                        pollingInterval = null;
                    }
                    noActiveJob.classList.remove('hidden');
                    activeJobContainer.classList.add('hidden');
                }
                await loadHistory();
            } else {
                const err = await res.json();
                alert(`Failed to delete job: ${err.detail || 'Server error'}`);
            }
        } catch (e) {
            alert(`Error deleting job: ${e.message}`);
        }
    }

    // Helper Functions
    function formatBytes(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    function formatTime(seconds) {
        if (!seconds) return '00:00';
        const totalSecs = Math.floor(seconds);
        const hrs = Math.floor(totalSecs / 3600);
        const mins = Math.floor((totalSecs % 3600) / 60);
        const secs = totalSecs % 60;
        if (hrs > 0) {
            return `${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        }
        return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }

    function formatDate(isoStr) {
        if (!isoStr) return '';
        const d = new Date(isoStr);
        return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    function escapeHtml(str) {
        if (!str) return '';
        return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    // Initial History Fetch
    loadHistory();
});
