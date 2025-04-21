document.addEventListener('DOMContentLoaded', function() {
    // Subtitle Editor & Video Preview functionality
    const subtitleEditor = document.getElementById('subtitleEditor');
    const saveEditorChanges = document.getElementById('saveEditorChanges');
    const downloadEdited = document.getElementById('downloadEdited');
    const videoPreviewFile = document.getElementById('videoPreviewFile');
    const previewVideo = document.getElementById('previewVideo');
    const subtitleOverlay = document.getElementById('subtitleOverlay');
    const videoPreviewContainer = document.querySelector('.video-preview-container');
    
    // Handle subtitle editing
    if (subtitleEditor && saveEditorChanges) {
        saveEditorChanges.addEventListener('click', function() {
            // Save the edited content
            const editedContent = subtitleEditor.value;
            localStorage.setItem('editedSubtitles', editedContent);
            showFeedback('Subtitle changes saved successfully', 'success');
        });
    }
    
    // Handle downloading edited subtitles
    if (downloadEdited) {
        downloadEdited.addEventListener('click', function() {
            const editedContent = localStorage.getItem('editedSubtitles') || subtitleEditor.value;
            const blob = new Blob([editedContent], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'edited_subtitles.srt';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        });
    }
    
    // Handle video preview
    if (videoPreviewFile && previewVideo && videoPreviewContainer) {
        videoPreviewFile.addEventListener('change', function(e) {
            if (e.target.files && e.target.files[0]) {
                const file = e.target.files[0];
                const videoURL = URL.createObjectURL(file);
                previewVideo.src = videoURL;
                videoPreviewContainer.style.display = 'block';
                
                // Load subtitles into overlay
                loadSubtitles();
                
                // Clean up when video is unloaded
                previewVideo.onended = function() {
                    URL.revokeObjectURL(videoURL);
                };
            }
        });
        
        // Handle showing subtitles during video playback
        if (previewVideo && subtitleOverlay) {
            previewVideo.addEventListener('timeupdate', function() {
                updateSubtitleOverlay(previewVideo.currentTime);
            });
        }
    }
    
    // Load and parse subtitles
    function loadSubtitles() {
        const subtitleText = localStorage.getItem('editedSubtitles') || subtitleEditor?.value;
        if (subtitleText) {
            window.parsedSubtitles = parseSubtitles(subtitleText);
        }
    }
    
    // Parse SRT format subtitles
    function parseSubtitles(subtitleText) {
        const subtitles = [];
        const subtitleBlocks = subtitleText.trim().split(/\n\s*\n/);
        
        for (const block of subtitleBlocks) {
            const lines = block.trim().split('\n');
            if (lines.length >= 3) {
                // Index is first line, timestamp is second, remaining lines are text
                const timeMatch = lines[1].match(/(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})/);
                if (timeMatch) {
                    const startTime = timeStringToSeconds(timeMatch[1]);
                    const endTime = timeStringToSeconds(timeMatch[2]);
                    const text = lines.slice(2).join('\n');
                    
                    subtitles.push({
                        start: startTime,
                        end: endTime,
                        text: text
                    });
                }
            }
        }
        
        return subtitles;
    }
    
    // Convert timestamp string to seconds
    function timeStringToSeconds(timeString) {
        const parts = timeString.split(/[,:]/);
        return parseInt(parts[0]) * 3600 + parseInt(parts[1]) * 60 + parseFloat(parts[2] + '.' + parts[3]);
    }
    
    // Display subtitle at current video time
    function updateSubtitleOverlay(currentTime) {
        if (!window.parsedSubtitles || !subtitleOverlay) return;
        
        let subtitle = window.parsedSubtitles.find(sub => 
            currentTime >= sub.start && currentTime <= sub.end
        );
        
        if (subtitle) {
            subtitleOverlay.textContent = subtitle.text;
            subtitleOverlay.style.display = 'block';
        } else {
            subtitleOverlay.textContent = '';
            subtitleOverlay.style.display = 'none';
        }
    }
    // Process form submission with Gofile and API task creation
    const uploadForm = document.getElementById('uploadForm');
    if (uploadForm) {
        uploadForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const fileInput = document.getElementById('file');
            const languageSelect = document.getElementById('language');
            const modelSelect = document.getElementById('model');
            const formatSelect = document.getElementById('format');
            const submitBtn = document.getElementById('submitBtn');
            
            // Validate file
            if (!fileInput.files || fileInput.files.length === 0) {
                showFeedback('Please select a file', 'danger');
                return;
            }
            
            const file = fileInput.files[0];
            const allowedExtensions = ['mp3', 'mp4', 'wav', 'avi', 'mov', 'mkv', 'flac', 'ogg', 'm4a'];
            const extension = file.name.split('.').pop().toLowerCase();
            
            if (!allowedExtensions.includes(extension)) {
                showFeedback(`File type not allowed. Allowed types: ${allowedExtensions.join(', ')}`, 'danger');
                return;
            }
            
            // Show processing dialog
            const processingModal = new bootstrap.Modal(document.getElementById('processingModal'));
            processingModal.show();
            
            // Update modal status
            const updateModalStatus = (message) => {
                const statusElement = document.getElementById('processingStatus');
                if (statusElement) {
                    statusElement.textContent = message;
                }
            };
            
            try {
                // 1. Get Gofile server
                updateModalStatus('Getting upload server...');
                const serverResponse = await fetch('/api/gofile/server');
                const serverData = await serverResponse.json();
                
                if (serverData.status !== 'success') {
                    throw new Error('Failed to get Gofile server');
                }
                
                const server = serverData.server;
                
                // 2. Upload file to Gofile
                updateModalStatus('Uploading file to temporary storage...');
                
                const formData = new FormData();
                formData.append('file', file);
                
                // The server-side API will handle authentication with the token
                const uploadResponse = await fetch(`https://${server}.gofile.io/uploadFile`, {
                    method: 'POST',
                    body: formData
                });
                
                const uploadData = await uploadResponse.json();
                
                if (uploadData.status !== 'ok') {
                    throw new Error('Failed to upload file to Gofile');
                }
                
                // 3. Create task for subtitle generation
                updateModalStatus('Starting subtitle generation task...');
                
                const outputLanguageSelect = document.getElementById('output_language');
                const taskData = {
                    gofile_id: uploadData.data.fileId,
                    gofile_link: uploadData.data.downloadPage,
                    filename: file.name,
                    language: languageSelect.value,
                    output_language: outputLanguageSelect ? outputLanguageSelect.value : 'same',
                    model: modelSelect.value,
                    format: formatSelect.value
                };
                
                const taskResponse = await fetch('/api/task', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(taskData)
                });
                
                const taskResult = await taskResponse.json();
                
                if (taskResult.status !== 'success') {
                    throw new Error(taskResult.message || 'Failed to create task');
                }
                
                // 4. Redirect to task status page
                window.location.href = `/task/${taskResult.task_id}`;
                
            } catch (error) {
                console.error('Error:', error);
                processingModal.hide();
                showFeedback(error.message || 'An error occurred during processing', 'danger');
            }
        });
    }
    
    // Task status checking
    const taskStatusContainer = document.getElementById('taskStatus');
    if (taskStatusContainer) {
        const taskId = taskStatusContainer.dataset.taskId;
        
        const checkTaskStatus = async () => {
            try {
                const response = await fetch(`/api/task/${taskId}`);
                const data = await response.json();
                
                if (data.status !== 'success') {
                    throw new Error(data.message || 'Failed to get task status');
                }
                
                const task = data.task;
                
                // Update UI based on task status
                updateTaskUI(task);
                
                // If task is still in progress, check again after a delay
                if (task.status === 'pending' || task.celery_status === 'STARTED' || 
                    task.celery_status === 'PROCESSING' || task.celery_status === 'UPLOADING') {
                    setTimeout(checkTaskStatus, 5000);
                }
                
            } catch (error) {
                console.error('Error checking task status:', error);
                document.getElementById('statusMessage').textContent = 'Error checking task status';
            }
        };
        
        const updateTaskUI = (task) => {
            const statusElement = document.getElementById('statusMessage');
            const progressElement = document.getElementById('progressPercentage');
            const resultLinkContainer = document.getElementById('resultLinkContainer');
            const resultLink = document.getElementById('resultLink');
            
            // Update status message
            if (task.status === 'completed') {
                statusElement.textContent = 'Subtitles generated successfully!';
                statusElement.className = 'h5 mb-3 text-success';
                
                // Show result link
                if (resultLinkContainer && resultLink && task.subtitle_gofile_link) {
                    resultLink.href = task.subtitle_gofile_link;
                    resultLinkContainer.classList.remove('d-none');
                }
                
                // Update progress
                if (progressElement) {
                    progressElement.style.width = '100%';
                    progressElement.classList.remove('progress-bar-animated', 'progress-bar-striped', 'bg-primary');
                    progressElement.classList.add('bg-success');
                    progressElement.setAttribute('aria-valuenow', 100);
                }
                
            } else if (task.status === 'failed') {
                statusElement.textContent = `Error: ${task.message || 'Task failed'}`;
                statusElement.className = 'h5 mb-3 text-danger';
                
                // Update progress to show error
                if (progressElement) {
                    progressElement.style.width = '100%';
                    progressElement.classList.remove('progress-bar-animated', 'progress-bar-striped', 'bg-primary');
                    progressElement.classList.add('bg-danger');
                }
                
            } else {
                // Task in progress
                let progressMessage = 'Processing...';
                let progressPercent = 30;
                
                if (task.celery_status === 'STARTED') {
                    progressMessage = 'Downloading file...';
                    progressPercent = 20;
                } else if (task.celery_status === 'PROCESSING') {
                    progressMessage = 'Generating subtitles...';
                    progressPercent = 60;
                } else if (task.celery_status === 'UPLOADING') {
                    progressMessage = 'Uploading subtitle file...';
                    progressPercent = 80;
                }
                
                if (task.progress) {
                    progressMessage = task.progress;
                }
                
                statusElement.textContent = progressMessage;
                
                // Update progress bar
                if (progressElement) {
                    progressElement.style.width = `${progressPercent}%`;
                    progressElement.setAttribute('aria-valuenow', progressPercent);
                }
            }
        };
        
        // Start checking status
        checkTaskStatus();
    }
    
    // Tasks list page
    const tasksListContainer = document.getElementById('tasksList');
    if (tasksListContainer) {
        const loadTasks = async () => {
            try {
                const response = await fetch('/api/my-tasks');
                const data = await response.json();
                
                if (data.status !== 'success') {
                    throw new Error(data.message || 'Failed to load tasks');
                }
                
                renderTasksList(data.tasks);
                
            } catch (error) {
                console.error('Error loading tasks:', error);
                tasksListContainer.innerHTML = `
                    <div class="alert alert-danger">
                        Failed to load tasks: ${error.message || 'Unknown error'}
                    </div>
                `;
            }
        };
        
        const renderTasksList = (tasks) => {
            if (!tasks || tasks.length === 0) {
                tasksListContainer.innerHTML = `
                    <div class="alert alert-info">
                        <i class="fas fa-info-circle me-2"></i> No subtitle generation tasks found.
                    </div>
                    <div class="text-center mt-4">
                        <a href="/" class="btn btn-primary">
                            <i class="fas fa-plus-circle me-2"></i> Create New Task
                        </a>
                    </div>
                `;
                return;
            }
            
            let html = `
                <div class="table-responsive">
                    <table class="table table-hover">
                        <thead>
                            <tr>
                                <th>File</th>
                                <th>Status</th>
                                <th>Created</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
            `;
            
            for (const task of tasks) {
                const statusClass = task.status === 'completed' ? 'text-success' : 
                                    task.status === 'failed' ? 'text-danger' : 'text-warning';
                                    
                let statusDisplay = task.status;
                if (task.status === 'pending' && task.progress) {
                    statusDisplay = task.progress;
                }
                
                html += `
                    <tr>
                        <td>${task.original_filename}</td>
                        <td><span class="${statusClass} fw-bold">${statusDisplay}</span></td>
                        <td>${task.created_at}</td>
                        <td>
                            <a href="/task/${task.task_id}" class="btn btn-sm btn-primary me-1" title="View Task Details">
                                <i class="fas fa-eye"></i>
                            </a>
                            ${task.status === 'completed' ? `
                                <a href="${task.subtitle_gofile_link}" target="_blank" class="btn btn-sm btn-success" title="Download Subtitles">
                                    <i class="fas fa-download me-1"></i>Download
                                </a>
                            ` : ''}
                        </td>
                    </tr>
                `;
            }
            
            html += `
                        </tbody>
                    </table>
                </div>
            `;
            
            tasksListContainer.innerHTML = html;
        };
        
        // Load tasks
        loadTasks();
    }
});

// Utility functions
function showFeedback(message, type) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.role = 'alert';
    
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    const container = document.querySelector('main.container');
    if (container) {
        container.insertBefore(alertDiv, container.firstChild);
        
        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            try {
                const bsAlert = new bootstrap.Alert(alertDiv);
                bsAlert.close();
            } catch (e) {
                // If bootstrap is not fully loaded, just remove the element
                alertDiv.remove();
            }
        }, 5000);
    }
}
