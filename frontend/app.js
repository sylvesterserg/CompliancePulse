'use strict';

const API_PORT = 8000;
const REFRESH_INTERVAL_MS = 10_000;

const getApiUrl = () => {
    const { protocol, hostname } = window.location;
    return `${protocol}//${hostname}:${API_PORT}`;
};

const formatDateTime = (value) => {
    if (!value) {
        return 'Never';
    }

    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
        return 'Unknown';
    }

    return parsed.toLocaleString();
};

const calculateAverageScore = (scores) => {
    const validScores = scores.filter((score) => typeof score === 'number' && Number.isFinite(score));

    if (validScores.length === 0) {
        return null;
    }

    const total = validScores.reduce((accumulator, score) => accumulator + score, 0);
    return total / validScores.length;
};

document.addEventListener('DOMContentLoaded', () => {
    const apiUrl = getApiUrl();

    const backendStatusCard = document.getElementById('backend-status');
    const systemsCountCard = document.getElementById('systems-count');
    const avgScoreCard = document.getElementById('avg-score');
    const systemsList = document.getElementById('systems-list');
    const apiUrlElement = document.getElementById('api-url');
    const scanButton = document.getElementById('scan-btn');
    const refreshButton = document.getElementById('refresh-btn');

    apiUrlElement.textContent = apiUrl;

    const setStatusCard = (card, status, message) => {
        card.className = ['status-card', status].filter(Boolean).join(' ');
        card.querySelector('.value').textContent = message;
    };

    const safeFetch = async (path, options = {}) => {
        const response = await fetch(`${apiUrl}${path}`, {
            credentials: 'same-origin',
            ...options
        });

        const contentType = response.headers.get('content-type') || '';
        const isJson = contentType.includes('application/json');

        if (!response.ok) {
            let errorDetails;
            try {
                errorDetails = isJson ? await response.clone().json() : await response.clone().text();
            } catch (parseError) {
                errorDetails = null;
            }

            const error = new Error(`Request failed with status ${response.status}`);
            error.status = response.status;
            if (errorDetails) {
                error.details = errorDetails;
            }
            throw error;
        }

        if (response.status === 204) {
            return null;
        }

        if (isJson) {
            return response.json();
        }

        return null;
    };

    const renderErrorState = (message) => {
        systemsList.className = 'empty-state error-text';
        systemsList.textContent = message;
    };

    const renderSystems = (systems, latestReports) => {
        if (!Array.isArray(systems) || systems.length === 0) {
            systemsList.className = 'empty-state';
            systemsList.textContent = 'No systems scanned yet. Click "Run Test Scan" to get started!';
            return;
        }

        systemsList.className = '';
        const fragment = document.createDocumentFragment();

        systems.forEach((system) => {
            const item = document.createElement('div');
            item.className = 'system-item';

            const info = document.createElement('div');
            info.className = 'system-info';

            const hostName = document.createElement('strong');
            hostName.textContent = system.hostname ?? 'Unknown host';

            const details = document.createElement('small');
            const ipAddress = system.ip || 'No IP';
            details.textContent = `${ipAddress} • Last scan: ${formatDateTime(system.last_scan)}`;

            info.append(hostName, details);

            const scoreContainer = document.createElement('div');
            scoreContainer.className = 'system-score';
            const latestReport = latestReports.get(system.id);
            scoreContainer.textContent = typeof latestReport?.score === 'number' ? `${latestReport.score}/100` : '—';

            item.append(info, scoreContainer);
            fragment.append(item);
        });

        systemsList.replaceChildren(fragment);
    };

    const checkBackend = async () => {
        try {
            await safeFetch('/health');
            setStatusCard(backendStatusCard, 'healthy', '✓ Healthy');
            return true;
        } catch (error) {
            console.error('Backend health check failed', error);
            setStatusCard(backendStatusCard, 'error', '✗ Offline');
            return false;
        }
    };

    const updateAverageCard = (scores) => {
        const averageScore = calculateAverageScore(scores);

        if (averageScore === null) {
            setStatusCard(avgScoreCard, '', '—');
            return;
        }

        const rounded = Math.round(averageScore * 10) / 10;
        let statusClass = 'healthy';
        if (rounded < 50) {
            statusClass = 'error';
        } else if (rounded < 80) {
            statusClass = 'warning';
        }

        setStatusCard(avgScoreCard, statusClass, `${rounded.toFixed(1)} / 100`);
    };

    const loadSystems = async () => {
        setStatusCard(systemsCountCard, 'loading', 'Loading…');
        setStatusCard(avgScoreCard, 'loading', 'Loading…');

        try {
            const [systemsData, reportsData] = await Promise.all([
                safeFetch('/systems'),
                safeFetch('/reports?limit=100')
            ]);

            const systems = Array.isArray(systemsData?.systems) ? systemsData.systems : [];
            const reports = Array.isArray(reportsData?.reports) ? reportsData.reports : [];

            setStatusCard(
                systemsCountCard,
                '',
                String(systemsData?.count ?? systems.length)
            );

            const latestReports = new Map();
            reports.forEach((report) => {
                if (!report || typeof report.system_id !== 'number') {
                    return;
                }

                const timestamp = report.created_at ? Date.parse(report.created_at) : 0;
                const existing = latestReports.get(report.system_id);
                if (!existing || timestamp > existing.timestamp) {
                    latestReports.set(report.system_id, {
                        score: typeof report.score === 'number' ? report.score : null,
                        timestamp
                    });
                }
            });

            updateAverageCard(Array.from(latestReports.values()).map((entry) => entry.score));
            renderSystems(systems, latestReports);
        } catch (error) {
            console.error('Failed to load systems or reports', error);
            setStatusCard(systemsCountCard, 'error', 'Error');
            setStatusCard(avgScoreCard, 'error', 'Error');
            renderErrorState('Unable to load data. Please try again later.');
        }
    };

    const testScan = async () => {
        if (scanButton.disabled) {
            return;
        }

        scanButton.disabled = true;
        scanButton.textContent = '⏳ Scanning...';

        const randomSuffix = typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
            ? crypto.randomUUID()
            : Date.now().toString(36);

        const payload = {
            hostname: `server-${randomSuffix}`,
            ip: `192.168.1.${Math.floor(Math.random() * 255)}`
        };

        try {
            const data = await safeFetch('/scan', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            const issueList = Array.isArray(data?.issues) ? data.issues : [];
            const message = [
                `Score: ${data?.score ?? 'N/A'}/100`,
                `Issues Found: ${issueList.length}`,
                '',
                'Issues:',
                ...issueList.map((issue) => `• ${issue}`)
            ].join('\n');

            window.alert(`✅ Scan Complete!\n\n${message}`);
            await loadSystems();
        } catch (error) {
            const detailMessage = error.details?.detail || error.message;
            window.alert(`❌ Scan failed: ${detailMessage}`);
        } finally {
            scanButton.disabled = false;
            scanButton.textContent = '🔍 Run Test Scan';
        }
    };

    scanButton.addEventListener('click', testScan);
    refreshButton.addEventListener('click', loadSystems);

    checkBackend();
    loadSystems();

    window.setInterval(() => {
        checkBackend();
        loadSystems();
    }, REFRESH_INTERVAL_MS);
});
