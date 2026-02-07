// API Configuration
const API_BASE_URL = 'http://localhost:5000';

// State
let currentDataset = null;
let currentResults = null;
let complianceChart = null;
let empathyChart = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    initializeEventListeners();
    loadDashboardData();
    initializeCharts();
});

// Event Listeners
function initializeEventListeners() {
    document.getElementById('generateDataset').addEventListener('click', generateDataset);
    document.getElementById('runEval').addEventListener('click', runEvaluation);
    document.getElementById('refreshResults').addEventListener('click', loadDashboardData);
}

// API Calls
async function generateDataset() {
    showLoading('Generating adversarial dataset...');
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/generate-dataset?count=50`);
        const data = await response.json();
        
        if (data.success) {
            currentDataset = data.questions;
            displayDataset(data.questions);
            showStatus(`Successfully generated ${data.count} adversarial questions!`, 'success');
        } else {
            showStatus(`Error: ${data.error}`, 'error');
        }
    } catch (error) {
        console.error('Error generating dataset:', error);
        showStatus('Failed to connect to API. Make sure the backend is running.', 'error');
    } finally {
        hideLoading();
    }
}

async function runEvaluation() {
    if (!currentDataset || currentDataset.length === 0) {
        showStatus('Please generate a dataset first!', 'warning');
        return;
    }
    
    showLoading('Running evaluation suite... This may take a few minutes.');
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/run-eval`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ dataset: currentDataset })
        });
        
        const data = await response.json();
        
        if (data.success) {
            currentResults = data.results;
            displayResults(data.results);
            updateMetrics(data.results.metrics);
            loadDashboardData(); // Refresh drift data
            showStatus('Evaluation completed successfully!', 'success');
        } else {
            showStatus(`Error: ${data.error}`, 'error');
        }
    } catch (error) {
        console.error('Error running evaluation:', error);
        showStatus('Failed to run evaluation. Check console for details.', 'error');
    } finally {
        hideLoading();
    }
}

async function loadDashboardData() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/dashboard-data`);
        const data = await response.json();
        
        if (data.success && data.data.latest_metrics) {
            updateMetrics(data.data.latest_metrics);
            updateCharts(data.data.drift_data);
        } else {
            // Try to load mock data for demo
            loadMockDriftData();
        }
    } catch (error) {
        console.error('Error loading dashboard data:', error);
        loadMockDriftData();
    }
}

async function loadMockDriftData() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/mock-drift-data`);
        const data = await response.json();
        
        if (data.success) {
            updateCharts(data.data);
        }
    } catch (error) {
        console.error('Error loading mock data:', error);
    }
}

// Display Functions
function displayDataset(questions) {
    const container = document.getElementById('datasetContainer');
    document.getElementById('datasetCount').textContent = `${questions.length} questions`;
    
    container.innerHTML = questions.slice(0, 20).map(q => `
        <div class="dataset-item ${q.risk_level}-risk">
            <div class="dataset-header">
                <span><strong>#${q.id}</strong></span>
                <div class="dataset-tags">
                    <span class="tag category">${q.category}</span>
                    <span class="tag risk">${q.risk_level} risk</span>
                    <span class="tag type">${q.adversarial_type}</span>
                </div>
            </div>
            <div class="dataset-question">${q.question}</div>
        </div>
    `).join('');
    
    if (questions.length > 20) {
        container.innerHTML += `<p class="placeholder">Showing 20 of ${questions.length} questions</p>`;
    }
}

function displayResults(results) {
    const container = document.getElementById('resultsContainer');
    
    // Show first 10 results
    const displayResults = results.results.slice(0, 10);
    
    container.innerHTML = displayResults.map(r => {
        const eval = r.evaluation;
        const isCompliant = eval.compliance_score === 1;
        
        return `
            <div class="result-item ${isCompliant ? 'compliant' : 'non-compliant'}">
                <div class="result-header">
                    <div class="result-question">
                        <strong>Q:</strong> ${r.question}
                    </div>
                    <div class="result-scores">
                        <span class="score-badge ${isCompliant ? 'compliant' : 'non-compliant'}">
                            ${isCompliant ? '✅' : '❌'} ${isCompliant ? 'Compliant' : 'Non-Compliant'}
                        </span>
                        <span class="score-badge empathy">
                            ❤️ ${eval.empathy_score}/5
                        </span>
                    </div>
                </div>
                
                <div class="result-response">
                    <strong>Bot Response:</strong> ${r.bot_response}
                </div>
                
                <div class="result-analysis">
                    <div class="analysis-item">
                        <div class="analysis-label">Empathy Analysis</div>
                        <div>${eval.empathy_reasoning}</div>
                    </div>
                    <div class="analysis-item">
                        <div class="analysis-label">Compliance Analysis</div>
                        <div>${eval.compliance_reasoning}</div>
                    </div>
                </div>
                
                ${eval.flags && eval.flags.length > 0 ? `
                    <div class="result-flags">
                        <strong>🚩 Flags:</strong> ${eval.flags.join(', ')}
                    </div>
                ` : ''}
            </div>
        `;
    }).join('');
    
    if (results.results.length > 10) {
        container.innerHTML += `<p class="placeholder">Showing 10 of ${results.results.length} results</p>`;
    }
}

function updateMetrics(metrics) {
    document.getElementById('complianceRate').textContent = 
        `${(metrics.compliance_rate * 100).toFixed(1)}%`;
    document.getElementById('empathyScore').textContent = 
        metrics.avg_empathy_score.toFixed(1);
    document.getElementById('totalFlags').textContent = 
        metrics.total_flags;
    document.getElementById('totalEvals').textContent = 
        metrics.total_evaluations;
}

// Chart Functions
function initializeCharts() {
    const complianceCtx = document.getElementById('complianceChart').getContext('2d');
    const empathyCtx = document.getElementById('empathyChart').getContext('2d');
    
    complianceChart = new Chart(complianceCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Compliance Rate',
                data: [],
                borderColor: '#10b981',
                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                tension: 0.4,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 1.0,
                    ticks: {
                        callback: function(value) {
                            return (value * 100).toFixed(0) + '%';
                        }
                    }
                }
            }
        }
    });
    
    empathyChart = new Chart(empathyCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Empathy Score',
                data: [],
                borderColor: '#2563eb',
                backgroundColor: 'rgba(37, 99, 235, 0.1)',
                tension: 0.4,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 5.0,
                    ticks: {
                        stepSize: 1
                    }
                }
            }
        }
    });
}

function updateCharts(driftData) {
    if (!driftData || driftData.length === 0) return;
    
    // Format dates and data
    const labels = driftData.map(d => {
        const date = new Date(d.timestamp);
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    });
    
    const complianceData = driftData.map(d => d.compliance_rate);
    const empathyData = driftData.map(d => d.avg_empathy);
    
    // Update compliance chart
    complianceChart.data.labels = labels;
    complianceChart.data.datasets[0].data = complianceData;
    complianceChart.update();
    
    // Update empathy chart
    empathyChart.data.labels = labels;
    empathyChart.data.datasets[0].data = empathyData;
    empathyChart.update();
}

// UI Helper Functions
function showLoading(message) {
    document.getElementById('loadingText').textContent = message;
    document.getElementById('loadingOverlay').classList.remove('hidden');
}

function hideLoading() {
    document.getElementById('loadingOverlay').classList.add('hidden');
}

function showStatus(message, type = 'success') {
    const banner = document.getElementById('statusBanner');
    const messageEl = document.getElementById('statusMessage');
    
    messageEl.textContent = message;
    banner.className = `status-banner ${type}`;
    banner.classList.remove('hidden');
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        banner.classList.add('hidden');
    }, 5000);
}
