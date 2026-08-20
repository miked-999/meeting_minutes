// AirGap Transcribe Frontend Logic
document.addEventListener('DOMContentLoaded', () => {
    // State Variables
    let selectedFile = null;
    let activeJobId = null;
    let pollingInterval = null;
    let allJobs = [];

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
            activeJobId = job.id;

            // Reset upload form
            removeFileBtn.click();
            startTranscribeBtn.innerHTML = `<i class="fa-solid fa-bolt"></i> Start Local Transcription`;

            // Display active job & start polling
            noActiveJob.classList.add('hidden');
            activeJobContainer.classList.remove('hidden');
            startPollingActiveJob(job.id);

        } catch (e) {
            alert(`Network error during upload: ${e.message}`);
            startTranscribeBtn.disabled = false;
            startTranscribeBtn.innerHTML = `<i class="fa-solid fa-bolt"></i> Start Local Transcription`;
        }
    });

    // 5. Polling Active Job Status
    function startPollingActiveJob(jobId) {
        if (pollingInterval) clearInterval(pollingInterval);

        const pollFunc = async () => {
            try {
                const res = await fetch(`/api/jobs/${jobId}`);
                if (!res.ok) return;

                const job = await res.json();
                updateActiveJobUI(job);

                if (job.status === 'COMPLETED' || job.status === 'FAILED') {
                    clearInterval(pollingInterval);
                    pollingInterval = null;
                    loadHistory(); // Refresh background count
                }
            } catch (e) {
                console.error("Polling error:", e);
            }
        };

        pollFunc(); // immediate call
        pollingInterval = setInterval(pollFunc, 1500);
    }

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
                const spkHtml = s.speaker ? `<span class="speaker-tag ${s.speaker.toLowerCase().replace(/\s+/g, '-')}">${escapeHtml(s.speaker)}</span>` : '';
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
            const res = await fetch('/api/jobs');
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
                        <span class="title" onclick="openTranscriptModal('${j.id}')">${escapeHtml(j.original_filename)}</span>
                        <div class="history-submeta">
                            <span><i class="fa-regular fa-clock"></i> ${formatTime(j.duration_seconds)}</span>
                            <span><i class="fa-solid fa-brain"></i> Whisper ${j.model_size}</span>
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

                    <button class="btn-icon" title="Delete Job" onclick="deleteJob('${j.id}')">
                        <i class="fa-solid fa-trash-can"></i>
                    </button>
                </div>
            </div>
        `).join('');
    }

    historySearch.addEventListener('input', () => renderHistoryItems(allJobs));
    refreshHistoryBtn.addEventListener('click', loadHistory);

    // 7. Global Actions: Modal & Delete
    window.openTranscriptModal = function(jobId) {
        const job = allJobs.find(j => j.id === jobId);
        if (!job) return;

        modalFilename.textContent = job.original_filename;
        modalMeta.textContent = `Duration: ${formatTime(job.duration_seconds)} | Model: Whisper ${job.model_size}`;

        modalDlDocx.href = `/api/jobs/${job.id}/download/docx`;
        modalDlPdf.href = `/api/jobs/${job.id}/download/pdf`;
        modalDlTxt.href = `/api/jobs/${job.id}/download/txt`;

        if (job.segments && job.segments.length > 0) {
            modalBodyText.innerHTML = job.segments.map(s => {
                const spk = s.speaker || 'Speaker 1';
                const spkClass = spk.toLowerCase().replace(/\s+/g, '-');
                return `
                <p style="margin-bottom: 10px;">
                    <span class="speaker-tag ${spkClass}">${escapeHtml(spk)}</span>
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

    window.deleteJob = async function(jobId) {
        if (!confirm("Are you sure you want to delete this transcription job?")) return;

        try {
            const res = await fetch(`/api/jobs/${jobId}`, { method: 'DELETE' });
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
    };

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
