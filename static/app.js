class VisualMemorySearch {
    constructor() {
        this.baseUrl = '';
        this.currentJobId = null;
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.loadLibrary();
        
        // Initialize feather icons after DOM updates
        setTimeout(() => {
            if (window.feather) {
                feather.replace();
            }
        }, 100);
    }

    setupEventListeners() {
        // File upload
        const fileInput = document.getElementById('fileInput');
        const uploadZone = document.getElementById('uploadZone');
        const browseBtn = document.getElementById('browseBtn');

        browseBtn.addEventListener('click', () => fileInput.click());
        fileInput.addEventListener('change', (e) => this.handleFileUpload(e.target.files));

        // Drag and drop
        uploadZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadZone.classList.add('drag-over');
        });

        uploadZone.addEventListener('dragleave', () => {
            uploadZone.classList.remove('drag-over');
        });

        uploadZone.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadZone.classList.remove('drag-over');
            // Small delay to let the drag-over visual effect complete
            setTimeout(() => {
                this.handleFileUpload(e.dataTransfer.files);
            }, 100);
        });

        // Search
        const searchInput = document.getElementById('searchInput');
        const searchBtn = document.getElementById('searchBtn');

        searchBtn.addEventListener('click', () => this.performSearch());
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.performSearch();
            }
        });

        // Example queries
        document.querySelectorAll('.example-query').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const query = e.target.dataset.query;
                searchInput.value = query;
                // Focus on search input for better UX
                searchInput.focus();
            });
        });

        // Refresh library
        document.getElementById('refreshLibrary').addEventListener('click', () => {
            this.loadLibrary();
        });
    }

    async handleFileUpload(files) {
        if (!files || files.length === 0) return;

        // Show immediate loading feedback
        this.showUploadLoading(true, 'Preparing upload...');

        const formData = new FormData();
        
        // Validate and add files
        let validFiles = 0;
        for (let file of files) {
            if (this.isValidImageFile(file)) {
                formData.append('files', file);
                validFiles++;
            }
        }

        if (validFiles === 0) {
            this.showUploadLoading(false);
            this.showMessage('No valid image files selected. Please select PNG, JPG, or JPEG files.', 'error');
            return;
        }

        try {
            this.showUploadLoading(true, `Uploading ${validFiles} files...`);
            this.showProgress(true);
            
            // Animate upload progress from 0 to 50% during upload
            this.animateProgressTo(50, `Uploading ${validFiles} files...`);
            
            const response = await fetch('/api/screenshots/upload', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();
            
            if (response.ok) {
                this.currentJobId = result.job_id;
                this.showUploadLoading(false);
                // Quick progress to 60% to show upload complete
                this.animateProgressTo(60, 'Upload complete, starting processing...');
                this.showMessage(`Started processing ${validFiles} files`, 'success');
                // Small delay before starting polling to show the upload complete message
                setTimeout(() => {
                    this.pollJobProgress(result.job_id);
                }, 800);
            } else {
                throw new Error(result.detail || 'Upload failed');
            }
        } catch (error) {
            console.error('Upload error:', error);
            this.showUploadLoading(false);
            this.showMessage(`Upload failed: ${error.message}`, 'error');
            this.showProgress(false);
        }
    }

    async pollJobProgress(jobId) {
        try {
            const response = await fetch(`/api/screenshots/status/${jobId}`);
            const status = await response.json();

            if (response.ok) {
                // Map processing progress from 60% to 100% (instead of 0% to 100%)
                const processingProgress = status.progress / status.total;
                const targetPercentage = Math.round(60 + (processingProgress * 40)); // 60% + (0-40%)
                
                // Animate to the target percentage smoothly
                this.animateProgressTo(targetPercentage, `Processing ${status.progress}/${status.total} files...`);

                if (status.status === 'completed') {
                    // Animate to 100% before finishing
                    this.animateProgressTo(100, 'Processing complete!', () => {
                        setTimeout(() => {
                            this.showProgress(false);
                            this.showMessage('All files processed successfully!', 'success');
                            this.loadLibrary(); // Refresh library
                        }, 500);
                    });
                } else if (status.status === 'failed') {
                    this.showProgress(false);
                    this.showMessage('Processing failed. Please try again.', 'error');
                } else if (status.status === 'processing') {
                    // Continue polling
                    setTimeout(() => this.pollJobProgress(jobId), 2000);
                }
            } else {
                throw new Error('Failed to get job status');
            }
        } catch (error) {
            console.error('Status polling error:', error);
            this.showProgress(false);
            this.showMessage('Failed to get processing status', 'error');
        }
    }

    async performSearch() {
        const query = document.getElementById('searchInput').value.trim();
        
        if (!query) {
            this.showMessage('Please enter a search query', 'warning');
            return;
        }

        try {
            this.showLoadingModal(true);
            
            const response = await fetch('/api/screenshots/search', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    query: query,
                    limit: 5
                })
            });

            const result = await response.json();
            
            if (response.ok) {
                this.displaySearchResults(result, query);
            } else {
                throw new Error(result.detail || 'Search failed');
            }
        } catch (error) {
            console.error('Search error:', error);
            this.showMessage(`Search failed: ${error.message}`, 'error');
        } finally {
            this.showLoadingModal(false);
        }
    }

    async loadLibrary() {
        try {
            const response = await fetch('/api/screenshots');
            const result = await response.json();

            if (response.ok) {
                this.displayLibrary(result.screenshots);
            } else {
                throw new Error('Failed to load library');
            }
        } catch (error) {
            console.error('Library loading error:', error);
            this.showMessage('Failed to load screenshot library', 'error');
        }
    }

    displaySearchResults(result, query) {
        const resultsSection = document.getElementById('resultsSection');
        const resultsTitle = document.getElementById('resultsTitle');
        const resultsMeta = document.getElementById('resultsMeta');
        const resultsGrid = document.getElementById('resultsGrid');

        // Update header
        resultsTitle.textContent = `Search Results for "${query}"`;
        resultsMeta.innerHTML = `
            <span>Top ${result.results.length} results found</span>
            <span>•</span>
            <span>Searched ${result.total_searched} screenshots</span>
            <span>•</span>
            <span>${result.query_time_ms}ms</span>
        `;

        // Clear and populate results
        resultsGrid.innerHTML = '';
        
        if (result.results.length === 0) {
            resultsGrid.innerHTML = `
                <div class="no-results">
                    <i data-feather="search" class="no-results-icon"></i>
                    <h3>No results found</h3>
                    <p>Try adjusting your search query or uploading more screenshots.</p>
                </div>
            `;
        } else {
            result.results.forEach(item => {
                const resultCard = this.createResultCard(item);
                resultsGrid.appendChild(resultCard);
            });
        }

        resultsSection.style.display = 'block';
        
        // Re-initialize feather icons
        setTimeout(() => {
            if (window.feather) {
                feather.replace();
            }
        }, 100);
    }

    displayLibrary(screenshots) {
        const libraryGrid = document.getElementById('libraryGrid');
        
        libraryGrid.innerHTML = '';
        
        if (screenshots.length === 0) {
            libraryGrid.innerHTML = `
                <div class="empty-library">
                    <i data-feather="image" class="empty-icon"></i>
                    <h4>No screenshots</h4>
                    <p>Upload some screenshots to start searching</p>
                </div>
            `;
        } else {
            screenshots.forEach(item => {
                const libraryCard = this.createLibraryCard(item);
                libraryGrid.appendChild(libraryCard);
            });
        }
        
        // Re-initialize feather icons
        setTimeout(() => {
            if (window.feather) {
                feather.replace();
            }
        }, 100);
    }

    createResultCard(result) {
        const card = document.createElement('div');
        card.className = 'result-card';
        
        card.innerHTML = `
            <div class="result-image">
                <img src="${result.preview_url}" alt="${result.filename}" loading="lazy">
                <div class="confidence-badge">${result.confidence_score}%</div>
            </div>
            <div class="result-content">
                <div class="result-header">
                    <h4>${result.filename}</h4>
                    <div class="result-actions">
                        <button class="action-btn" onclick="window.open('${result.preview_url}', '_blank')">
                            <i data-feather="external-link"></i>
                        </button>
                    </div>
                </div>
                <div class="matched-elements">
                    ${result.matched_elements.map(element => 
                        `<span class="match-tag">${element}</span>`
                    ).join('')}
                </div>
                <div class="result-text">
                    <div class="text-section">
                        <h5><i data-feather="type"></i> OCR Text</h5>
                        <div class="text-content collapsed" data-full-text="${this.escapeHtml(result.ocr_text || 'No text detected')}">
                            <p>${this.truncateText(result.ocr_text || 'No text detected', 100)}</p>
                            ${(result.ocr_text && result.ocr_text.length > 100) ? '<button class="expand-btn" onclick="app.toggleTextSection(this)">Read more</button>' : ''}
                        </div>
                    </div>
                    <div class="text-section">
                        <h5><i data-feather="eye"></i> Visual Description</h5>
                        <div class="text-content collapsed" data-full-text="${this.escapeHtml(result.visual_description || 'No description available')}">
                            <p>${this.truncateText(result.visual_description || 'No description available', 100)}</p>
                            ${(result.visual_description && result.visual_description.length > 100) ? '<button class="expand-btn" onclick="app.toggleTextSection(this)">Read more</button>' : ''}
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        return card;
    }

    createLibraryCard(screenshot) {
        const card = document.createElement('div');
        card.className = 'library-card';
        
        const statusIcon = screenshot.processed ? 'check-circle' : 'clock';
        const statusClass = screenshot.processed ? 'processed' : 'processing';
        
        card.innerHTML = `
            <div class="library-image">
                <img src="${screenshot.preview_url}" alt="${screenshot.filename}" loading="lazy">
                <div class="status-badge ${statusClass}">
                    <i data-feather="${statusIcon}"></i>
                </div>
                <div class="library-actions">
                    <button class="delete-btn" onclick="app.deleteScreenshot('${screenshot.id}', '${screenshot.filename}')" title="Delete screenshot">
                        <i data-feather="trash-2"></i>
                    </button>
                </div>
            </div>
            <div class="library-info">
                <h5>${screenshot.filename}</h5>
                <small>${new Date(screenshot.upload_date).toLocaleDateString()}</small>
            </div>
        `;
        
        return card;
    }

    // Utility methods
    isValidImageFile(file) {
        const validTypes = ['image/png', 'image/jpeg', 'image/jpg'];
        return validTypes.includes(file.type);
    }

    truncateText(text, maxLength) {
        if (text.length <= maxLength) return text;
        return text.substring(0, maxLength) + '...';
    }

    showProgress(show) {
        const container = document.getElementById('progressContainer');
        container.style.display = show ? 'block' : 'none';
        
        if (!show) {
            this.updateProgress(0, '');
        }
    }

    updateProgress(percentage, text) {
        const fill = document.getElementById('progressFill');
        const progressText = document.getElementById('progressText');
        
        fill.style.width = `${percentage}%`;
        progressText.textContent = text;
    }

    showLoadingModal(show) {
        const modal = document.getElementById('loadingModal');
        modal.style.display = show ? 'flex' : 'none';
    }

    async deleteScreenshot(screenshotId, filename) {
        try {
            const response = await fetch(`/api/screenshots/${screenshotId}`, {
                method: 'DELETE'
            });
            
            const result = await response.json();
            
            if (response.ok) {
                this.showMessage('Screenshot deleted successfully', 'success');
                // Refresh the library to remove the deleted item
                this.loadLibrary();
            } else {
                throw new Error(result.detail || 'Delete failed');
            }
        } catch (error) {
            console.error('Delete error:', error);
            this.showMessage(`Failed to delete screenshot: ${error.message}`, 'error');
        }
    }

    toggleTextSection(button) {
        const textContent = button.parentElement;
        const paragraph = textContent.querySelector('p');
        const fullText = textContent.dataset.fullText;
        
        if (textContent.classList.contains('collapsed')) {
            // Expand
            textContent.classList.remove('collapsed');
            textContent.classList.add('expanded');
            paragraph.textContent = fullText;
            button.textContent = 'Read less';
        } else {
            // Collapse
            textContent.classList.remove('expanded');
            textContent.classList.add('collapsed');
            paragraph.textContent = this.truncateText(fullText, 100);
            button.textContent = 'Read more';
        }
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    showUploadLoading(show, message = 'Preparing upload...') {
        const uploadZone = document.getElementById('uploadZone');
        const uploadLoading = document.getElementById('uploadLoading');
        const loadingText = uploadLoading.querySelector('p');
        
        if (show) {
            uploadZone.classList.add('uploading');
            uploadLoading.classList.add('show');
            loadingText.textContent = message;
        } else {
            uploadZone.classList.remove('uploading');
            uploadLoading.classList.remove('show');
        }
    }

    animateProgressTo(targetPercentage, text, callback) {
        const fill = document.getElementById('progressFill');
        const progressText = document.getElementById('progressText');
        
        // Get current percentage
        const currentWidth = parseFloat(fill.style.width) || 0;
        const difference = targetPercentage - currentWidth;
        const steps = 20;
        const stepSize = difference / steps;
        const stepDuration = 50; // 50ms per step
        
        let currentStep = 0;
        const animate = () => {
            if (currentStep < steps) {
                const newPercentage = currentWidth + (stepSize * (currentStep + 1));
                fill.style.width = `${Math.min(100, Math.max(0, newPercentage))}%`;
                progressText.textContent = text;
                currentStep++;
                setTimeout(animate, stepDuration);
            } else {
                // Ensure we end at the exact target
                fill.style.width = `${targetPercentage}%`;
                progressText.textContent = text;
                if (callback) callback();
            }
        };
        
        animate();
    }

    showMessage(message, type = 'info') {
        // Create a simple toast notification
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        
        // Add to document
        document.body.appendChild(toast);
        
        // Show with animation
        setTimeout(() => toast.classList.add('show'), 100);
        
        // Remove after delay
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => document.body.removeChild(toast), 300);
        }, 3000);
    }
}

// Initialize app when DOM is loaded
let app; // Global reference for delete function
document.addEventListener('DOMContentLoaded', () => {
    app = new VisualMemorySearch();
});
